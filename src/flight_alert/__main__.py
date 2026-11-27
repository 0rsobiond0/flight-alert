from __future__ import annotations

import argparse
import logging

from flight_alert.config import Settings
from flight_alert.worker import run_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Search flight deals and send Telegram alerts")
    parser.add_argument("--once", action="store_true", help="run one search cycle")
    parser.add_argument("--dry-run", action="store_true", help="never send Telegram messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        import os
        os.environ["DRY_RUN"] = "true"
    settings = Settings.from_env()
    if not args.once:
        parser.error("--once is required for the scheduled worker")
    run_once(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
