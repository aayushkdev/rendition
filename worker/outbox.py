import logging
import signal
import time

from core.config import settings
from core.db.session import SessionLocal
from core.queue import get_job_queue_publisher
from core.services.outbox_service import publish_pending_outbox_messages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rendition.outbox")


def publish_once() -> int:
    db = SessionLocal()
    try:
        return publish_pending_outbox_messages(
            db=db,
            publisher=get_job_queue_publisher(),
            limit=settings.OUTBOX_PUBLISH_BATCH_SIZE,
        )
    finally:
        db.close()


def main() -> None:
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logger.info("outbox publisher ready")
    while not stopping:
        try:
            published_count = publish_once()
            if published_count:
                logger.info(
                    "published outbox messages",
                    extra={"published_count": published_count},
                )
        except Exception:
            logger.exception("outbox publish iteration failed")

        time.sleep(settings.OUTBOX_PUBLISH_INTERVAL_SECONDS)

    logger.info("outbox publisher stopped")


if __name__ == "__main__":
    main()
