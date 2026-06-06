from enum import Enum
import logging
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from sqlalchemy.orm import Session

from core.config import settings
from core.encoding import (
    HlsEncoder,
    VideoProber,
    VideoSourceMetadata,
    get_hls_preset,
    is_hls_preset_applicable,
)
from core.queue.messages import EncodingJobMessage
from core.services.job_service import (
    EncodingJobContext,
    EncodingJobError,
    claim_encoding_job,
    heartbeat_encoding_job,
    mark_encoding_job_failed,
    mark_encoding_job_skipped,
    mark_encoding_job_succeeded,
)
from core.storage import (
    ObjectStorage,
    build_hls_playlist_key,
    build_hls_segment_key,
    get_object_storage,
)

HLS_PLAYLIST_CONTENT_TYPE = "application/vnd.apple.mpegurl"
HLS_SEGMENT_CONTENT_TYPE = "video/mp2t"
HLS_PLAYLIST_CACHE_CONTROL = "max-age=60"
HLS_SEGMENT_CACHE_CONTROL = "max-age=31536000, immutable"

logger = logging.getLogger("rendition.worker.processor")


class WorkerMessageAction(str, Enum):
    ack = "ack"
    requeue = "requeue"
    reject = "reject"


@dataclass(frozen=True)
class EncodingProcessorResult:
    output_path: str | None = None
    source_metadata: VideoSourceMetadata | None = None
    skipped_reason: str | None = None


class EncodingProcessor(Protocol):
    def process(
        self,
        context: EncodingJobContext,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> EncodingProcessorResult: ...


class EncodingJobOwnershipLost(RuntimeError):
    pass


SessionScope = Callable[[], AbstractContextManager[Session]]


class JobHeartbeat:
    def __init__(
        self,
        session_scope: SessionScope,
        job_id,
        worker_id: str,
        interval_seconds: int,
    ) -> None:
        self._session_scope = session_scope
        self._job_id = job_id
        self._worker_id = worker_id
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._lost_ownership = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def lost_ownership(self) -> bool:
        return self._lost_ownership

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            try:
                with self._session_scope() as db:
                    still_owned = heartbeat_encoding_job(
                        db=db,
                        job_id=self._job_id,
                        worker_id=self._worker_id,
                    )
            except Exception:
                logger.exception(
                    "encoding job heartbeat failed job_id=%s worker_id=%s",
                    self._job_id,
                    self._worker_id,
                )
                continue

            if not still_owned:
                self._lost_ownership = True
                self._stop_event.set()


class FfmpegEncodingProcessor:
    def __init__(
        self,
        storage: ObjectStorage | None = None,
        encoder: HlsEncoder | None = None,
        prober: VideoProber | None = None,
        temp_root: Path | None = None,
    ) -> None:
        self._storage = storage or get_object_storage()
        self._encoder = encoder or HlsEncoder()
        self._prober = prober or VideoProber()
        self._temp_root = temp_root or Path(settings.WORKER_TEMP_ROOT)

    def process(
        self,
        context: EncodingJobContext,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> EncodingProcessorResult:
        self._temp_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix=f"rendition-{context.job_id}-",
            dir=self._temp_root,
        ) as temp_dir:
            job_dir = Path(temp_dir)
            input_path = job_dir / (context.source_filename or "source")
            output_dir = job_dir / "hls"

            _raise_if_cancelled(is_cancelled)
            self._storage.download_file(context.source, str(input_path))
            _raise_if_cancelled(is_cancelled)
            source_metadata = self._prober.probe(input_path)
            preset = get_hls_preset(context.resolution)
            if not is_hls_preset_applicable(preset, source_metadata):
                return EncodingProcessorResult(
                    source_metadata=source_metadata,
                    skipped_reason=(
                        f"{context.resolution} is not applicable for "
                        f"{source_metadata.width}x{source_metadata.height} source"
                    ),
                )

            _raise_if_cancelled(is_cancelled)
            self._encoder.encode(
                input_path=input_path,
                output_dir=output_dir,
                resolution=context.resolution,
            )
            _raise_if_cancelled(is_cancelled)
            return EncodingProcessorResult(
                output_path=self._upload_hls_outputs(
                    context,
                    output_dir,
                    is_cancelled=is_cancelled,
                ),
                source_metadata=source_metadata,
            )

    def _upload_hls_outputs(
        self,
        context: EncodingJobContext,
        output_dir: Path,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> str:
        segment_paths = sorted((output_dir / "segments").glob("*.ts"))
        if not segment_paths:
            raise RuntimeError("HLS encoder did not create any segments")

        for segment_path in segment_paths:
            _raise_if_cancelled(is_cancelled)
            segment_key = build_hls_segment_key(
                context.video_id,
                context.resolution,
                segment_path.name,
            )
            self._storage.upload_file(
                local_path=str(segment_path),
                key=segment_key,
                content_type=HLS_SEGMENT_CONTENT_TYPE,
                cache_control=HLS_SEGMENT_CACHE_CONTROL,
            )

        playlist_path = output_dir / "index.m3u8"
        playlist_key = build_hls_playlist_key(context.video_id, context.resolution)
        _raise_if_cancelled(is_cancelled)
        self._storage.upload_file(
            local_path=str(playlist_path),
            key=playlist_key,
            content_type=HLS_PLAYLIST_CONTENT_TYPE,
            cache_control=HLS_PLAYLIST_CACHE_CONTROL,
        )

        return playlist_key


def _raise_if_cancelled(is_cancelled: Callable[[], bool] | None) -> None:
    if is_cancelled is not None and is_cancelled():
        raise EncodingJobOwnershipLost("encoding job ownership was lost")


def _build_ownership_lost_checker(
    session_scope: SessionScope,
    heartbeat: JobHeartbeat,
    context: EncodingJobContext,
) -> Callable[[], bool]:
    last_checked_at = 0.0
    lost_ownership = False
    min_check_interval_seconds = 5.0

    def is_lost() -> bool:
        nonlocal last_checked_at, lost_ownership
        if lost_ownership or heartbeat.lost_ownership:
            return True

        now = time.monotonic()
        if now - last_checked_at < min_check_interval_seconds:
            return False
        last_checked_at = now

        try:
            with session_scope() as db:
                still_owned = heartbeat_encoding_job(
                    db=db,
                    job_id=context.job_id,
                    worker_id=context.worker_id,
                )
        except Exception:
            logger.exception(
                "encoding job ownership check failed job_id=%s worker_id=%s",
                context.job_id,
                context.worker_id,
            )
            return False

        if not still_owned:
            lost_ownership = True
            return True
        return False

    return is_lost


def process_encoding_message(
    session_scope: SessionScope,
    message: EncodingJobMessage,
    processor: EncodingProcessor,
    storage: ObjectStorage | None = None,
    worker_id: str = "local-worker",
) -> WorkerMessageAction:
    try:
        with session_scope() as db:
            context = claim_encoding_job(
                db=db,
                job_id=message.job_id,
                video_id=message.video_id,
                rendition_id=message.rendition_id,
                worker_id=worker_id,
            )
    except EncodingJobError:
        return WorkerMessageAction.reject

    if context is None:
        return WorkerMessageAction.ack

    heartbeat = JobHeartbeat(
        session_scope=session_scope,
        job_id=context.job_id,
        worker_id=context.worker_id,
        interval_seconds=settings.WORKER_HEARTBEAT_INTERVAL_SECONDS,
    )
    heartbeat.start()
    is_cancelled = _build_ownership_lost_checker(
        session_scope=session_scope,
        heartbeat=heartbeat,
        context=context,
    )
    try:
        try:
            result = processor.process(
                context,
                is_cancelled=is_cancelled,
            )
        except EncodingJobOwnershipLost:
            return WorkerMessageAction.ack
        except Exception as exc:
            with session_scope() as db:
                should_retry = mark_encoding_job_failed(
                    db,
                    context.job_id,
                    str(exc),
                    worker_id=context.worker_id,
                    storage=storage,
                )
            if should_retry is None:
                return WorkerMessageAction.ack

            logger.exception(
                "encoding job failed job_id=%s video_id=%s rendition_id=%s resolution=%s attempt=%s/%s retry=%s error=%s",
                context.job_id,
                context.video_id,
                context.rendition_id,
                context.resolution,
                context.attempt_count + 1,
                context.max_attempts,
                should_retry,
                exc,
            )
            if should_retry:
                return WorkerMessageAction.ack
            return WorkerMessageAction.reject
    finally:
        heartbeat.stop()

    if heartbeat.lost_ownership:
        return WorkerMessageAction.ack

    with session_scope() as db:
        if result.skipped_reason is not None:
            updated = mark_encoding_job_skipped(
                db,
                context.job_id,
                result.skipped_reason,
                worker_id=context.worker_id,
                source_metadata=result.source_metadata,
                storage=storage,
            )
        else:
            updated = mark_encoding_job_succeeded(
                db,
                context.job_id,
                worker_id=context.worker_id,
                output_path=result.output_path,
                source_metadata=result.source_metadata,
                storage=storage,
            )

    if not updated:
        return WorkerMessageAction.ack
    return WorkerMessageAction.ack
