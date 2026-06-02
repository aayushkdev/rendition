import { cn } from "@/lib/utils";

import type { VideoStatus } from "./types";

export const statusLabels: Record<VideoStatus, string> = {
  done: "Done",
  pending: "Queued",
  processing: "Processing",
  partial: "Partial",
  uploading: "Uploading",
  failed: "Failed",
  upload_failed: "Upload failed",
};

const statusStyles: Record<VideoStatus, string> = {
  done: "border-emerald-200 bg-emerald-50 text-emerald-700",
  pending: "border-stone-200 bg-stone-50 text-stone-600",
  processing: "border-sky-200 bg-sky-50 text-sky-700",
  partial: "border-amber-200 bg-amber-50 text-amber-700",
  uploading: "border-sky-200 bg-sky-50 text-sky-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  upload_failed: "border-red-200 bg-red-50 text-red-700",
};

type StatusBadgeProps = {
  status: VideoStatus;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center rounded-md border px-2.5 text-xs font-medium",
        statusStyles[status],
      )}
    >
      {statusLabels[status]}
    </span>
  );
}
