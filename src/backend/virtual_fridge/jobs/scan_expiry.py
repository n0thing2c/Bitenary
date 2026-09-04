from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import logging

from core.config import get_settings
from core.database import AsyncSessionLocal
from virtual_fridge.infrastructure.sqlalchemy_notifications import (
    SqlAlchemyNotificationRepository,
)
from virtual_fridge.service.expiry_notifications import ExpiryNotificationService


logger = logging.getLogger(__name__)


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--now must include a timezone offset")
    return parsed


async def run_scan(now: datetime | None = None) -> dict[str, int]:
    settings = get_settings()
    scan_time = now or datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        repository = SqlAlchemyNotificationRepository(session)
        service = ExpiryNotificationService(
            repository,
            default_warning_days=settings.fridge_expiry_warning_days,
            default_timezone=settings.fridge_default_timezone,
            default_delivery_hour=settings.fridge_default_delivery_hour,
        )
        result = await service.scan(now=scan_time)
        return {
            "scanned": result.scanned,
            "created": result.created,
            "skipped": result.skipped,
        }


async def run_scheduler(interval_seconds: int) -> None:
    """Continuously create expiry notifications while the API is running."""
    while True:
        try:
            result = await run_scan()
            logger.info(
                "Expiry scan complete: scanned=%d created=%d skipped=%d",
                result["scanned"],
                result["created"],
                result["skipped"],
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            # A temporary database failure must not stop future scans.
            logger.exception("Expiry scan failed; it will be retried")
        await asyncio.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create idempotent in-app notifications for expiring fridge items."
    )
    parser.add_argument(
        "--now",
        type=parse_datetime,
        default=None,
        help="Timezone-aware ISO timestamp used for deterministic/manual scans.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_scan(args.now))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
