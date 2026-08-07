"""
uploader_meta.py
----------------
Publishes videos to Facebook Reels and Instagram Reels using the Meta Graph API v19.0+.

Instagram Reels API Flow:
  1. POST /{ig-user-id}/media (media_type=REELS, video_url=..., caption=...)
  2. Poll GET /{container-id}?fields=status_code until FINISHED
  3. POST /{ig-user-id}/media_publish (creation_id=...)

Facebook Reels API Flow:
  1. POST /{page-id}/video_reels (upload_phase=start)
  2. Upload binary MP4 payload to returned upload_url
  3. POST /{page-id}/video_reels (upload_phase=finish, video_state=PUBLISHED)

Public API:
    result = upload_to_meta(video_path, title, caption, no_upload=False)
"""

from __future__ import annotations

import logging
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

import config

logger = logging.getLogger("uploader_meta")

GRAPH_API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# ── Retry helper ──────────────────────────────────────────────────────────────
def _retry_request(fn, retries: int = 3, backoff: float = 3.0):
    """Call fn() with exponential backoff retries on network errors."""
    last_exc = None
    for attempt in range(retries):
        try:
            return fn()
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            wait = backoff * (2 ** attempt)
            logger.warning("Network error (attempt %d/%d): %s — retrying in %.0fs...", attempt + 1, retries, exc, wait)
            time.sleep(wait)
        except Exception:
            raise
    raise last_exc

# ── Error parsing ─────────────────────────────────────────────────────────────
def _raise_for_status_with_meta_msg(resp: requests.Response) -> None:
    """Raise a detailed RuntimeError with Meta's error message if request failed."""
    if not resp.ok:
        try:
            body = resp.json()
            err = body.get("error", {})
            msg     = err.get("message", resp.text)
            code    = err.get("code", "?")
            subcode = err.get("error_subcode", "?")
            fbtrace = err.get("fbtrace_id", "")
            logger.error("Meta API raw error response: %s", body)
            raise RuntimeError(
                f"Meta Graph API Error {resp.status_code} | Code {code}/{subcode} | {msg}"
                + (f" | trace={fbtrace}" if fbtrace else "")
            )
        except (ValueError, KeyError):
            # JSON parse failed — raise raw HTTP error
            resp.raise_for_status()

# ── Page Access Token exchange ───────────────────────────────────────────────
def get_page_access_token(page_id: str, user_token: str) -> str:
    """
    Exchange a User Access Token for a Page Access Token.
    Page tokens are required to post videos/reels to a Facebook Page.
    Falls back to user_token if exchange fails.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/{page_id}",
            params={"fields": "access_token", "access_token": user_token},
            timeout=10,
        )
        if resp.ok:
            page_token = resp.json().get("access_token")
            if page_token:
                logger.info("Page Access Token obtained for Page %s", page_id)
                return page_token
        logger.warning("Could not get Page Access Token — using User Token as fallback")
    except Exception as exc:
        logger.warning("Page token exchange failed: %s — using User Token", exc)
    return user_token


# ── Token validation ──────────────────────────────────────────────────────────
def validate_meta_token() -> bool:
    """
    Check if the META_ACCESS_TOKEN is valid and log its permissions.
    Returns True if valid, False if expired or invalid.
    """
    if not config.META_ACCESS_TOKEN:
        logger.warning("META_ACCESS_TOKEN is not set in .env")
        return False
    try:
        resp = requests.get(
            f"{BASE_URL}/me",
            params={"access_token": config.META_ACCESS_TOKEN, "fields": "id,name"},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            logger.info("✅ Meta token valid. Account: %s (ID: %s)", data.get("name"), data.get("id"))
            return True
        else:
            body = resp.json()
            err  = body.get("error", {})
            logger.error(
                "❌ Meta token INVALID: Code %s — %s",
                err.get("code"), err.get("message")
            )
            if err.get("code") == 190:
                logger.error(
                    "⚠️  Token expired or invalid. Go to https://developers.facebook.com/tools/explorer/ "
                    "→ Generate new token with: pages_manage_posts, pages_read_engagement, "
                    "pages_show_list, instagram_basic, instagram_content_publish"
                )
            return False
    except Exception as exc:
        logger.warning("Could not validate Meta token (network issue?): %s", exc)
        return True  # Don't block upload on connectivity issues during check


# ── Public video hosting (5 fallback hosts) ───────────────────────────────────
def _try_cloudinary(video_path: Path) -> Optional[str]:
    """Upload to Cloudinary if credentials are configured in .env."""
    cloud = getattr(config, "CLOUDINARY_CLOUD_NAME", "")
    key   = getattr(config, "CLOUDINARY_API_KEY", "")
    secret= getattr(config, "CLOUDINARY_API_SECRET", "")
    if not (cloud and key and secret):
        return None
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(cloud_name=cloud, api_key=key, api_secret=secret)
        logger.info("Trying Cloudinary (most reliable)...")
        result = cloudinary.uploader.upload(
            str(video_path),
            resource_type="video",
            folder="navi_reels",
        )
        url = result.get("secure_url")
        if url:
            logger.info("✅ Cloudinary upload success: %s", url)
            return url
    except Exception as exc:
        logger.warning("Cloudinary failed: %s", exc)
    return None


def host_video_publicly(video_path: Path) -> str:
    """
    Upload video to a public file host so Instagram Graph API can fetch it via
    a DIRECT MP4 URL (not a download page). Instagram rejects page/redirect URLs.
    Tries hosts in order: Cloudinary → pixeldrain → 0x0.st → filebin → uguu.se → catbox → litterbox.
    Raises RuntimeError if all hosts fail.
    """
    import random, string
    size_mb = video_path.stat().st_size / (1024 * 1024)
    logger.info("Uploading video (%.2f MB) to public host for Instagram...", size_mb)

    # ── Host 1: Cloudinary (most reliable — if credentials set in .env) ───────
    url = _try_cloudinary(video_path)
    if url:
        return url

    # ── Host 2: Pixeldrain — AWS-backed, fast, direct URL ────────────────────
    try:
        logger.info("Trying pixeldrain.com (direct URL)...")
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://pixeldrain.com/api/file",
                files={"file": (video_path.name, f, "video/mp4")},
                timeout=180,
            )
        if resp.ok:
            file_id = resp.json().get("id")
            if file_id:
                url = f"https://pixeldrain.com/api/file/{file_id}?download"
                logger.info("✅ pixeldrain upload success: %s", url)
                return url
    except Exception as exc:
        logger.warning("pixeldrain failed: %s", exc)

    # ── Host 3: 0x0.st — direct permanent URL ──────────────────────────────
    try:
        logger.info("Trying 0x0.st (direct URL)...")
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://0x0.st",
                files={"file": (video_path.name, f, "video/mp4")},
                timeout=180,
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            url = resp.text.strip()
            logger.info("✅ 0x0.st upload success: %s", url)
            return url
    except Exception as exc:
        logger.warning("0x0.st failed: %s", exc)

    # ── Host 4: filebin.net — no auth, direct URL ───────────────────────────
    try:
        logger.info("Trying filebin.net (direct URL)...")
        bin_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        with open(video_path, "rb") as f:
            resp = requests.post(
                f"https://filebin.net/{bin_id}/{video_path.name}",
                data=f,
                headers={"Content-Type": "video/mp4", "Accept": "application/json"},
                timeout=180,
            )
        if resp.ok:
            url = f"https://filebin.net/{bin_id}/{video_path.name}"
            logger.info("✅ filebin.net upload success: %s", url)
            return url
    except Exception as exc:
        logger.warning("filebin.net failed: %s", exc)

    # ── Host 5: uguu.se — simple, direct URL (48h) ──────────────────────────
    try:
        logger.info("Trying uguu.se (direct URL, 48h)...")
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://uguu.se/upload",
                files={"files[]": (video_path.name, f, "video/mp4")},
                timeout=180,
            )
        if resp.ok:
            files = resp.json().get("files", [])
            if files:
                url = files[0].get("url", "")
                if url.startswith("http"):
                    logger.info("✅ uguu.se upload success: %s", url)
                    return url
    except Exception as exc:
        logger.warning("uguu.se failed: %s", exc)

    # ── Host 6: catbox.moe ─────────────────────────────────────────────────────
    try:
        logger.info("Trying catbox.moe...")
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (video_path.name, f, "video/mp4")},
                timeout=180,
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            url = resp.text.strip()
            logger.info("✅ catbox.moe upload success: %s", url)
            return url
    except Exception as exc:
        logger.warning("catbox.moe failed: %s", exc)

    # ── Host 7: litterbox (1h temp) ───────────────────────────────────────
    try:
        logger.info("Trying litterbox.catbox.moe...")
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "1h"},
                files={"fileToUpload": (video_path.name, f, "video/mp4")},
                timeout=180,
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            url = resp.text.strip()
            logger.info("✅ litterbox upload success: %s", url)
            return url
    except Exception as exc:
        logger.warning("litterbox failed: %s", exc)

    raise RuntimeError(
        "All 7 public video hosts failed. "
        "PERMANENT FIX: Add Cloudinary credentials to .env "
        "(CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET) "
        "for guaranteed Instagram uploads. Free at: https://cloudinary.com"
    )


# ── Instagram Reel Upload ─────────────────────────────────────────────────────
def upload_instagram_reel(video_url: str, caption: str) -> Dict[str, Any]:
    """Upload Reel to Instagram Business Account via Graph API container flow."""
    if not config.META_ACCESS_TOKEN or not config.META_IG_USER_ID:
        raise ValueError("META_ACCESS_TOKEN and META_IG_USER_ID are required for Instagram upload.")

    logger.info("Initializing Instagram Reel media container...")
    create_url = f"{BASE_URL}/{config.META_IG_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": config.META_ACCESS_TOKEN,
    }

    def _create():
        resp = requests.post(create_url, data=payload, timeout=30)
        _raise_for_status_with_meta_msg(resp)
        return resp

    resp = _retry_request(_create)
    container_id = resp.json().get("id")
    if not container_id:
        raise RuntimeError(f"Instagram container creation returned no ID: {resp.json()}")
    logger.info("Instagram Media Container created. ID: %s", container_id)

    # Poll until FINISHED (up to 5 minutes)
    status_url = f"{BASE_URL}/{container_id}"
    params = {"fields": "status_code,status", "access_token": config.META_ACCESS_TOKEN}
    for attempt in range(30):
        time.sleep(10)
        st_resp = requests.get(status_url, params=params, timeout=15)
        st_json = st_resp.json()
        code = st_json.get("status_code", "UNKNOWN")
        logger.info("Instagram Container Status [%d/30]: %s", attempt + 1, code)
        if code == "FINISHED":
            break
        elif code == "ERROR":
            raise RuntimeError(f"Instagram media processing failed: {st_json}")
    else:
        raise RuntimeError("Instagram container did not finish processing in time (5 min timeout).")

    # Publish
    pub_url = f"{BASE_URL}/{config.META_IG_USER_ID}/media_publish"
    pub_payload = {"creation_id": container_id, "access_token": config.META_ACCESS_TOKEN}

    def _publish():
        r = requests.post(pub_url, data=pub_payload, timeout=30)
        _raise_for_status_with_meta_msg(r)
        return r

    pub_resp = _retry_request(_publish)
    media_id = pub_resp.json().get("id")
    logger.info("✅ Instagram Reel published! Media ID: %s", media_id)
    return {"status": "success", "instagram_media_id": media_id}


# ── Facebook Reel Upload ──────────────────────────────────────────────────────
def upload_facebook_reel(video_path: Path, description: str, page_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload Reel to Facebook Page via Graph API 3-phase Resumable Upload.
    Requires Page Access Token with: pages_manage_posts, pages_read_engagement.
    If page_token is provided it is used instead of META_ACCESS_TOKEN.
    """
    if not config.META_ACCESS_TOKEN or not config.META_FB_PAGE_ID:
        raise ValueError("META_ACCESS_TOKEN and META_FB_PAGE_ID are required for Facebook upload.")

    token = page_token or config.META_ACCESS_TOKEN

    # Phase 1: Start upload session
    logger.info("Phase 1: Initializing Facebook Reel upload session...")
    start_url = f"{BASE_URL}/{config.META_FB_PAGE_ID}/video_reels"
    start_payload = {
        "upload_phase": "start",
        "access_token": token,
    }

    def _start():
        r = requests.post(start_url, data=start_payload, timeout=30)
        _raise_for_status_with_meta_msg(r)
        return r

    start_resp = _retry_request(_start)
    start_json = start_resp.json()
    video_id   = start_json.get("video_id")
    upload_url = start_json.get("upload_url")

    if not video_id or not upload_url:
        raise RuntimeError(f"Facebook start phase returned unexpected response: {start_json}")
    logger.info("Facebook Reel session started. Video ID: %s", video_id)

    # Phase 2: Binary upload
    file_size = video_path.stat().st_size
    logger.info("Phase 2: Uploading binary video (%.2f MB)...", file_size / (1024 * 1024))
    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
    }

    def _upload():
        with open(video_path, "rb") as f:
            r = requests.post(upload_url, headers=headers, data=f, timeout=180)
            _raise_for_status_with_meta_msg(r)
            return r

    _retry_request(_upload)
    logger.info("Phase 2: Binary upload complete.")

    # Phase 3: Finish & publish
    logger.info("Phase 3: Publishing Facebook Reel...")
    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": description,
        "access_token": token,
    }

    def _finish():
        r = requests.post(start_url, data=finish_payload, timeout=30)
        _raise_for_status_with_meta_msg(r)
        return r

    _retry_request(_finish)
    logger.info("✅ Facebook Reel published! Video ID: %s", video_id)
    return {"status": "success", "facebook_video_id": video_id}


# ── Main Orchestrator ─────────────────────────────────────────────────────────
def upload_to_meta(
    video_path: Path,
    title: str,
    caption: str,
    no_upload: bool = False,
    video_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrate publishing to Facebook & Instagram Reels."""

    if no_upload or config.DRY_RUN:
        logger.info("[DRY RUN] Upload skipped. (DRY_RUN=True or --no-upload flag)")
        logger.info("[DRY RUN] Video: %s", video_path)
        logger.info("[DRY RUN] Title: %s", title)
        logger.info("[DRY RUN] Caption: %s", caption[:80])
        return {"status": "skipped", "reason": "dry_run_or_no_upload_flag"}

    if not config.META_ACCESS_TOKEN:
        logger.warning("META_ACCESS_TOKEN missing in .env — skipping Meta upload.")
        return {"status": "skipped", "reason": "missing_credentials"}

    # Pre-flight: validate token
    logger.info("Validating Meta access token...")
    validate_meta_token()

    results = {}

    # ── 1. Facebook Reel ──────────────────────────────────────────────────────
    if config.META_FB_PAGE_ID:
        try:
            logger.info("📘 Posting to Facebook Page (ID: %s)...", config.META_FB_PAGE_ID)
            # Exchange User Token → Page Access Token (required for video posting)
            page_token = get_page_access_token(config.META_FB_PAGE_ID, config.META_ACCESS_TOKEN)
            results["facebook"] = upload_facebook_reel(video_path, caption, page_token=page_token)
        except Exception as exc:
            logger.error("❌ Facebook Reel upload FAILED: %s", exc)
            results["facebook_error"] = str(exc)
    else:
        logger.info("META_FB_PAGE_ID not set — skipping Facebook Reels.")

    # ── 2. Instagram Reel ─────────────────────────────────────────────────────
    if config.META_IG_USER_ID:
        target_url = video_url
        if not target_url:
            try:
                target_url = host_video_publicly(video_path)
            except Exception as exc:
                logger.error("❌ Public video hosting FAILED: %s", exc)
                results["instagram_error"] = str(exc)

        if target_url:
            try:
                logger.info("📸 Posting to Instagram Business (ID: %s)...", config.META_IG_USER_ID)
                results["instagram"] = upload_instagram_reel(target_url, caption)
            except Exception as exc:
                logger.error("❌ Instagram Reel upload FAILED: %s", exc)
                results["instagram_error"] = str(exc)
    else:
        logger.info("META_IG_USER_ID not set — skipping Instagram Reels.")

    # ── Summary ───────────────────────────────────────────────────────────────
    fb_ok = "facebook" in results and results["facebook"].get("status") == "success"
    ig_ok = "instagram" in results and results["instagram"].get("status") == "success"
    logger.info("Upload Summary → Facebook: %s | Instagram: %s",
                "✅ SUCCESS" if fb_ok else "❌ FAILED",
                "✅ SUCCESS" if ig_ok else "❌ FAILED")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Uploader module loaded. Run validate_meta_token() to check credentials.")
