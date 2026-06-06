import logging
import signal
import time
from datetime import datetime, timedelta, timezone

from core.config import settings
from core.db.session import SessionLocal
from core.models import job, outbox, rendition, upload_session, video  # noqa: F401
from core.services.job_service import reap_stale_encoding_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rendition.reaper")


def reap_once() -> int:
    db = SessionLocal()
    try:
        stale_before = datetime.now(timezone.utc) - timedelta(
            seconds=settings.JOB_STALE_TIMEOUT_SECONDS
        )
        return reap_stale_encoding_jobs(db=db, stale_before=stale_before)
    finally:
        db.close()


def main() -> None:
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logger.info(
        "job reaper ready",
        extra={
            "interval_seconds": settings.JOB_REAPER_INTERVAL_SECONDS,
            "stale_timeout_seconds": settings.JOB_STALE_TIMEOUT_SECONDS,
        },
    )
    while not stopping:
        try:
            reaped_count = reap_once()
            if reaped_count:
                logger.info("reaped stale encoding jobs", extra={"count": reaped_count})
        except Exception:
            logger.exception("job reaper iteration failed")

        sleep_until = time.monotonic() + settings.JOB_REAPER_INTERVAL_SECONDS
        while not stopping and time.monotonic() < sleep_until:
            time.sleep(1)

    logger.info("job reaper stopped")


if __name__ == "__main__":
    main()
