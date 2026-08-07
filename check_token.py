"""
check_token.py
--------------
Quick diagnostic script to validate your Meta access token
and check all required permissions before running the automation.

Usage:
    python check_token.py
"""

import sys
import logging
import requests
import config

# Force UTF-8 on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_token")

GRAPH = "https://graph.facebook.com/v19.0"

REQUIRED_PERMISSIONS = [
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_show_list",
    "instagram_content_publish",
]


def check():
    token = config.META_ACCESS_TOKEN
    if not token:
        logger.error("META_ACCESS_TOKEN is empty in .env!")
        return

    print("\n" + "=" * 60)
    print("  Meta Access Token Diagnostic")
    print("=" * 60)

    # 1. Token identity
    print("\n[1] Token Identity...")
    resp = requests.get(
        f"{GRAPH}/me",
        params={"access_token": token, "fields": "id,name"},
        timeout=10,
    )
    if not resp.ok:
        err = resp.json().get("error", {})
        print(f"  INVALID TOKEN: {err.get('message')}")
        print(f"  Code: {err.get('code')} | Subcode: {err.get('error_subcode')}")
        if err.get("code") == 190:
            print("\n  TOKEN IS EXPIRED. Regenerate at:")
            print("  https://developers.facebook.com/tools/explorer/")
        return
    d = resp.json()
    print(f"  OK  Token valid — Account: {d.get('name')} (ID: {d.get('id')})")

    # 2. Permissions
    print("\n[2] Checking Permissions...")
    perms_resp = requests.get(
        f"{GRAPH}/me/permissions",
        params={"access_token": token},
        timeout=10,
    )
    granted = set()
    if perms_resp.ok:
        for p in perms_resp.json().get("data", []):
            if p.get("status") == "granted":
                granted.add(p["permission"])

    all_good = True
    for perm in REQUIRED_PERMISSIONS:
        if perm in granted:
            print(f"  OK  {perm}")
        else:
            print(f"  MISSING  {perm}")
            all_good = False

    # 3. Facebook Page (direct ID access — no me/accounts needed)
    print(f"\n[3] Facebook Page (ID: {config.META_FB_PAGE_ID})...")
    if not config.META_FB_PAGE_ID:
        print("  WARNING  META_FB_PAGE_ID not set in .env")
    else:
        pg = requests.get(
            f"{GRAPH}/{config.META_FB_PAGE_ID}",
            params={"access_token": token, "fields": "id,name,category"},
            timeout=10,
        )
        if pg.ok:
            pd = pg.json()
            print(f"  OK  Page: {pd.get('name')} | Category: {pd.get('category')} | ID: {pd.get('id')}")
        else:
            err = pg.json().get("error", {})
            print(f"  FAILED  {err.get('message')}")

    # 4. Instagram via connected_instagram_account (correct field for new Pages)
    print(f"\n[4] Instagram Account via connected_instagram_account...")
    ig_resp = requests.get(
        f"{GRAPH}/{config.META_FB_PAGE_ID}",
        params={"access_token": token, "fields": "connected_instagram_account"},
        timeout=10,
    )
    if ig_resp.ok:
        ig_data = ig_resp.json().get("connected_instagram_account", {})
        ig_id = ig_data.get("id")
        if ig_id:
            print(f"  OK  Instagram Account ID: {ig_id}")
            if ig_id == config.META_IG_USER_ID:
                print(f"  OK  Matches META_IG_USER_ID in .env")
            else:
                print(f"  WARNING  Mismatch! .env has {config.META_IG_USER_ID} but API returned {ig_id}")
                print(f"  --> Update META_IG_USER_ID={ig_id} in .env")
        else:
            print("  FAILED  No Instagram account connected to this Page")
    else:
        err = ig_resp.json().get("error", {})
        print(f"  FAILED  {err.get('message')}")

    # 5. Summary
    print("\n" + "=" * 60)
    if all_good:
        print("  All checks passed! Ready to run automation.")
    else:
        print("  Fix the issues above, then run: python main.py post")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    check()
