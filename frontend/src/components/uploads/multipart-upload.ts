import {
  abortVideoUpload,
  completeVideoUpload,
  createVideoUpload,
  refreshVideoUpload,
  type UploadConfigResponse,
  type MultipartUploadPart,
} from "./api";
import type { UploadedVideo, VideoStatus } from "./types";
import { formatBytes } from "./utils";

const MAX_CONCURRENT_PART_UPLOADS = 3;

type CompletedPart = {
  part_number: number;
  etag: string;
};

type UploadPartResult = CompletedPart & {
  loadedBytes: number;
};

export type MultipartUploadSnapshot = {
  row: UploadedVideo;
};

export type MultipartUploadController = {
  snapshot: MultipartUploadSnapshot;
  start: () => Promise<void>;
  retryFailedParts: () => Promise<void>;
  cancel: () => Promise<void>;
};

type MultipartUploadOptions = {
  file: File;
  uploadConfig: UploadConfigResponse;
  onChange: (snapshot: MultipartUploadSnapshot) => void;
};

function getPartCount(file: File, partSizeBytes: number) {
  return Math.ceil(file.size / partSizeBytes);
}

export function normalizeContentType(file: File) {
  if (file.type) return file.type;

  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "mp4") return "video/mp4";
  if (extension === "mov") return "video/quicktime";
  if (extension === "mkv") return "video/x-matroska";

  return "application/octet-stream";
}

function mapVideoStatus(status: string): VideoStatus {
  if (status === "running") return "processing";
  if (status === "partial") return "partial";
  if (status === "failed") return "failed";
  if (status === "done") return "done";
  if (status === "skipped") return "done";
  return "pending";
}

function partBlob(file: File, partNumber: number, partSizeBytes: number) {
  const start = (partNumber - 1) * partSizeBytes;
  return file.slice(start, Math.min(start + partSizeBytes, file.size));
}

function uploadPart(
  uploadUrl: string,
  blob: Blob,
  signal: AbortSignal,
  onProgress: (loadedBytes: number) => void,
): Promise<{ etag: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    signal.addEventListener(
      "abort",
      () => {
        xhr.abort();
        reject(new DOMException("upload aborted", "AbortError"));
      },
      { once: true },
    );

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded);
      }
    };

    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(`part upload failed with ${xhr.status}`));
        return;
      }

      const etag = xhr.getResponseHeader("ETag");
      if (!etag) {
        reject(new Error("storage did not return an ETag"));
        return;
      }

      onProgress(blob.size);
      resolve({ etag });
    };

    xhr.onerror = () => reject(new Error("part upload failed"));
    xhr.onabort = () => reject(new DOMException("upload aborted", "AbortError"));
    xhr.open("PUT", uploadUrl);
    xhr.send(blob);
  });
}

export function createMultipartUploadController({
  file,
  uploadConfig,
  onChange,
}: MultipartUploadOptions): MultipartUploadController {
  const partCount = getPartCount(file, uploadConfig.part_size_bytes);
  let abortController = new AbortController();
  const completedParts = new Map<number, CompletedPart>();
  const partProgress = new Map<number, number>();
  let failedPartNumbers = new Set<number>();
  let uploadParts: MultipartUploadPart[] = [];
  let videoId: string | null = null;
  let status: VideoStatus = "uploading";

  const controller: MultipartUploadController = {
    snapshot: {
      row: {
        id: crypto.randomUUID(),
        title: file.name,
        uploadedAt: "Now",
        status,
        size: formatBytes(file.size),
        progress: 0,
        canCancel: true,
      },
    },
    start,
    retryFailedParts,
    cancel,
  };

  function emit() {
    const loadedBytes = Array.from(partProgress.values()).reduce(
      (total, loaded) => total + loaded,
      0,
    );
    const progress =
      file.size === 0 ? 0 : Math.min(100, Math.round((loadedBytes / file.size) * 100));

    controller.snapshot = {
      row: {
        ...controller.snapshot.row,
        status,
        progress,
        canCancel: status === "uploading" || status === "upload_failed",
        canRetry: status === "upload_failed" && failedPartNumbers.size > 0,
      },
    };
    onChange(controller.snapshot);
  }

  async function start() {
    try {
      abortController = new AbortController();
      emit();
      const upload = await createVideoUpload({
        filename: file.name,
        content_type: normalizeContentType(file),
        size_bytes: file.size,
        part_count: partCount,
      });

      videoId = upload.video_id;
      uploadParts = upload.parts;
      await uploadMissingParts(uploadParts);
      await completeUpload();
    } catch (caught) {
      if (abortController.signal.aborted) return;
      status = "upload_failed";
      emit();
      throw caught;
    }
  }

  async function retryFailedParts() {
    if (!videoId || failedPartNumbers.size === 0) return;

    abortController = new AbortController();
    status = "uploading";
    failedPartNumbers.forEach((partNumber) => {
      partProgress.set(partNumber, 0);
    });
    emit();

    try {
      const upload = await refreshVideoUpload(videoId, partCount);
      uploadParts = upload.parts;
      await uploadMissingParts(
        uploadParts.filter((part) => failedPartNumbers.has(part.part_number)),
      );
      await completeUpload();
    } catch (caught) {
      if (abortController.signal.aborted) return;
      status = "upload_failed";
      emit();
      throw caught;
    }
  }

  async function cancel() {
    abortController.abort();
    if (videoId) {
      await abortVideoUpload(videoId);
    }
  }

  async function uploadMissingParts(parts: MultipartUploadPart[]) {
    const queue = [...parts].sort((left, right) => left.part_number - right.part_number);
    failedPartNumbers = new Set();
    let nextIndex = 0;

    async function worker() {
      while (nextIndex < queue.length) {
        const part = queue[nextIndex];
        nextIndex += 1;

        try {
          const result = await uploadSinglePart(part);
          completedParts.set(result.part_number, {
            part_number: result.part_number,
            etag: result.etag,
          });
          partProgress.set(result.part_number, result.loadedBytes);
          emit();
        } catch (caught) {
          if (abortController.signal.aborted) throw caught;
          failedPartNumbers.add(part.part_number);
        }
      }
    }

    await Promise.all(
      Array.from(
        { length: Math.min(MAX_CONCURRENT_PART_UPLOADS, queue.length) },
        () => worker(),
      ),
    );

    if (failedPartNumbers.size > 0) {
      throw new Error(`${failedPartNumbers.size} part upload failed`);
    }
  }

  async function uploadSinglePart(part: MultipartUploadPart): Promise<UploadPartResult> {
    const blob = partBlob(file, part.part_number, uploadConfig.part_size_bytes);
    const { etag } = await uploadPart(
      part.upload_url,
      blob,
      abortController.signal,
      (loadedBytes) => {
        partProgress.set(part.part_number, loadedBytes);
        emit();
      },
    );

    return {
      part_number: part.part_number,
      etag,
      loadedBytes: blob.size,
    };
  }

  async function completeUpload() {
    if (!videoId) return;
    const parts = Array.from(completedParts.values()).sort(
      (left, right) => left.part_number - right.part_number,
    );

    if (parts.length !== partCount) {
      throw new Error("upload is missing completed parts");
    }

    const video = await completeVideoUpload(videoId, parts);
    status = mapVideoStatus(video.status);
    controller.snapshot = {
      row: {
        ...controller.snapshot.row,
        videoId: video.video_id,
        status,
        progress: 100,
        canCancel: false,
        canRetry: false,
      },
    };
    onChange(controller.snapshot);
  }

  return controller;
}
