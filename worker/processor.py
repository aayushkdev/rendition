from enum import Enum
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
    def process(self, context: EncodingJobContext) -> EncodingProcessorResult: ...


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

    def process(self, context: EncodingJobContext) -> EncodingProcessorResult:
        self._temp_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix=f"rendition-{context.job_id}-",
            dir=self._temp_root,
        ) as temp_dir:
            job_dir = Path(temp_dir)
            input_path = job_dir / (context.source_filename or "source")
            output_dir = job_dir / "hls"

            self._storage.download_file(context.source, str(input_path))
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

            self._encoder.encode(
                input_path=input_path,
                output_dir=output_dir,
                resolution=context.resolution,
            )
            return EncodingProcessorResult(
                output_path=self._upload_hls_outputs(context, output_dir),
                source_metadata=source_metadata,
            )

    def _upload_hls_outputs(
        self,
        context: EncodingJobContext,
        output_dir: Path,
    ) -> str:
        segment_paths = sorted((output_dir / "segments").glob("*.ts"))
        if not segment_paths:
            raise RuntimeError("HLS encoder did not create any segments")

        for segment_path in segment_paths:
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
        self._storage.upload_file(
            local_path=str(playlist_path),
            key=playlist_key,
            content_type=HLS_PLAYLIST_CONTENT_TYPE,
            cache_control=HLS_PLAYLIST_CACHE_CONTROL,
        )

        return playlist_key


SessionScope = Callable[[], AbstractContextManager[Session]]


def process_encoding_message(
    session_scope: SessionScope,
    message: EncodingJobMessage,
    processor: EncodingProcessor,
    storage: ObjectStorage | None = None,
) -> WorkerMessageAction:
    try:
        with session_scope() as db:
            context = claim_encoding_job(
                db=db,
                job_id=message.job_id,
                video_id=message.video_id,
                rendition_id=message.rendition_id,
            )
    except EncodingJobError:
        return WorkerMessageAction.reject

    if context is None:
        return WorkerMessageAction.ack

    try:
        result = processor.process(context)
    except Exception as exc:
        with session_scope() as db:
            should_retry = mark_encoding_job_failed(
                db,
                context.job_id,
                str(exc),
                storage=storage,
            )
        if should_retry:
            return WorkerMessageAction.requeue
        return WorkerMessageAction.ack

    with session_scope() as db:
        if result.skipped_reason is not None:
            mark_encoding_job_skipped(
                db,
                context.job_id,
                result.skipped_reason,
                source_metadata=result.source_metadata,
                storage=storage,
            )
        else:
            mark_encoding_job_succeeded(
                db,
                context.job_id,
                output_path=result.output_path,
                source_metadata=result.source_metadata,
                storage=storage,
            )
    return WorkerMessageAction.ack
