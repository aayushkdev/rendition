"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Activity, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/animate-ui/components/radix/tooltip";

import {
  getUploadConfig,
  listVideos,
  type UploadConfigResponse,
  type VideoListItem,
} from "./api";
import {
  createMultipartUploadController,
  normalizeContentType,
  type MultipartUploadController,
  type MultipartUploadSnapshot,
} from "./multipart-upload";
import { StatusBadge } from "./status-badge";
import type { UploadedVideo } from "./types";
import { UploadDropzone } from "./upload-dropzone";
import { UploadsTable } from "./uploads-table";
import { formatBytes } from "./utils";

function formatUploadDate(value: string | null) {
  if (!value) return "Not uploaded";

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function mapVideoStatus(status: VideoListItem["status"]): UploadedVideo["status"] {
  if (status === "running") return "processing";
  if (status === "partial") return "partial";
  if (status === "done") return "done";
  if (status === "skipped") return "done";
  if (status === "failed") return "failed";
  return "pending";
}

function toUploadedVideo(video: VideoListItem): UploadedVideo {
  return {
    id: video.video_id,
    videoId: video.video_id,
    title: video.title,
    uploadedAt: formatUploadDate(video.uploaded_at ?? video.created_at),
    status: mapVideoStatus(video.status),
    size: video.size_bytes === null ? "-" : formatBytes(video.size_bytes),
    progress:
      video.status === "done"
        ? 100
        : video.status === "failed"
          ? 0
          : video.status === "partial"
            ? 75
            : 25,
  };
}

export function UploadDashboard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadControllersRef = useRef(new Map<string, MultipartUploadController>());
  const [isDragging, setIsDragging] = useState(false);
  const [uploadRows, setUploadRows] = useState<UploadedVideo[]>([]);
  const [videos, setVideos] = useState<UploadedVideo[]>([]);
  const [uploadConfig, setUploadConfig] = useState<UploadConfigResponse | null>(null);
  const [isLoadingVideos, setIsLoadingVideos] = useState(true);

  const activeVideoIds = new Set(uploadRows.map((row) => row.videoId).filter(Boolean));
  const tableVideos: UploadedVideo[] = [
    ...uploadRows,
    ...videos.filter((video) => !activeVideoIds.has(video.videoId)),
  ];

  useEffect(() => {
    const uploadControllers = uploadControllersRef.current;

    return () => {
      uploadControllers.forEach((controller) => {
        void controller.cancel();
      });
    };
  }, []);

  useEffect(() => {
    void loadUploadConfig();
    void loadVideos();
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void loadVideos();
    }, 10000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  async function loadUploadConfig() {
    try {
      setUploadConfig(await getUploadConfig());
    } catch (error: unknown) {
      toast.error("Upload limits unavailable", {
        description:
          error instanceof Error ? error.message : "Unable to load upload configuration",
      });
    }
  }

  async function loadVideos() {
    setIsLoadingVideos(true);
    try {
      const response = await listVideos();
      setVideos(response.map(toUploadedVideo));
    } catch (error: unknown) {
      toast.error("Videos unavailable", {
        description: error instanceof Error ? error.message : "Unable to load videos",
      });
    } finally {
      setIsLoadingVideos(false);
    }
  }

  function handleFile(file: File | undefined) {
    if (!file) return;
    if (!uploadConfig) {
      toast.error("Upload limits are still loading");
      return;
    }

    const contentType = normalizeContentType(file);
    const partCount = Math.ceil(file.size / uploadConfig.part_size_bytes);

    if (!uploadConfig.allowed_content_types.includes(contentType)) {
      toast.error("Unsupported video type", {
        description: contentType,
      });
      return;
    }

    if (file.size > uploadConfig.max_size_bytes) {
      toast.error("Video is too large", {
        description: `Maximum size is ${formatBytes(uploadConfig.max_size_bytes)}`,
      });
      return;
    }

    if (partCount > uploadConfig.max_part_count) {
      toast.error("Video has too many upload parts", {
        description: `Maximum part count is ${uploadConfig.max_part_count}`,
      });
      return;
    }

    const controller = createMultipartUploadController({
      file,
      uploadConfig,
      onChange: updateUploadRow,
    });

    uploadControllersRef.current.set(controller.snapshot.row.id, controller);
    setUploadRows((current) => [controller.snapshot.row, ...current]);

    toast.success("Upload started", {
      description: file.name,
    });

    void controller.start().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      toast.error("Upload failed", {
        description: error instanceof Error ? error.message : file.name,
      });
    });
  }

  function updateUploadRow(snapshot: MultipartUploadSnapshot) {
    if (!snapshot.row.canCancel && !snapshot.row.canRetry) {
      uploadControllersRef.current.delete(snapshot.row.id);
      setUploadRows((current) =>
        current.filter((row) => row.id !== snapshot.row.id),
      );
      void loadVideos();
      return;
    }

    setUploadRows((current) =>
      current.map((row) => (row.id === snapshot.row.id ? snapshot.row : row)),
    );
  }

  function handleRetryUpload(rowId: string) {
    const controller = uploadControllersRef.current.get(rowId);
    if (!controller) return;

    toast.info("Retrying upload", {
      description: controller.snapshot.row.title,
    });

    void controller.retryFailedParts().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      toast.error("Retry failed", {
        description:
          error instanceof Error ? error.message : controller.snapshot.row.title,
      });
    });
  }

  function handleCancelUpload(rowId: string) {
    const controller = uploadControllersRef.current.get(rowId);
    if (!controller) return;

    const title = controller.snapshot.row.title;
    void controller.cancel().catch(() => undefined);
    uploadControllersRef.current.delete(rowId);
    setUploadRows((current) => current.filter((row) => row.id !== rowId));
    toast.warning("Upload cancelled", {
      description: title,
    });
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Button type="button" variant="outline" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="size-4" />
              </Link>
            </Button>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Rendition library
              </p>
              <h1 className="mt-1 text-2xl font-semibold md:text-3xl">
                Uploads
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status="processing" />
            <Tooltip>
              <TooltipTrigger className="inline-flex size-9 items-center justify-center rounded-md border border-border bg-card text-muted-foreground">
                <Activity className="size-4" />
              </TooltipTrigger>
              <TooltipContent>Encoder status</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <section className="flex flex-col gap-5">
          <UploadDropzone
            inputRef={inputRef}
            isDragging={isDragging}
            allowedContentTypes={uploadConfig?.allowed_content_types ?? []}
            disabled={!uploadConfig}
            onDraggingChange={setIsDragging}
            onFileSelected={handleFile}
          />
          <UploadsTable
            videos={tableVideos}
            isLoading={isLoadingVideos}
            onCancelUpload={handleCancelUpload}
            onRetryUpload={handleRetryUpload}
          />
        </section>
      </div>
    </main>
  );
}
