"""
scheduler.py
------------
Automated periodic runner for Navi-FBI-Automation.
Generates and posts Facebook & Instagram Reels on a configurable timer.

Usage:
  python scheduler.py --interval-hours 6 --no-upload
"""

import argparse
import logging
import config
from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

def main():
    parser = argparse.ArgumentParser(description="Navi-FBI-Automation Scheduled Runner")
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=config.POST_EVERY_HOURS,
        help=f"Hours between video generations (default: {config.POST_EVERY_HOURS})",
    )
    parser.add_argument("--no-upload", action="store_true", help="Run in local test mode without uploading")
    args = parser.parse_args()

    interval_hours = args.interval_hours
    interval_sec = interval_hours * 3600
    no_upload = args.no_upload or config.DRY_RUN

    logger.info("⏰ Starting Reels Automation Scheduler (Interval: %.1f hours)...", interval_hours)
    if no_upload:
        logger.info("⚠️ Running in TEST mode (uploads disabled).")

    while True:
        try:
            logger.info("⚡ Triggering scheduled Reels pipeline run...")
            run_pipeline(no_upload=no_upload)
        except Exception as exc:
            logger.error("Scheduled run failed: %s", exc)

        logger.info("Sleeping for %.1f hours until next run...", interval_hours)
        time.sleep(interval_sec)

if __name__ == "__main__":
    main()

