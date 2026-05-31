import { Progress } from "@/components/animate-ui/components/radix/progress";

import { StatusBadge, statusLabels } from "./status-badge";
import type { UploadedVideo } from "./types";

type StatusCellProps = {
  video: UploadedVideo;
};

export function StatusCell({ video }: StatusCellProps) {
  if (video.status === "uploading" || video.status === "processing") {
    return (
      <div className="flex min-w-44 flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-foreground">
            {statusLabels[video.status]}
          </span>
          <span className="text-xs text-muted-foreground">{video.progress}%</span>
        </div>
        <Progress value={video.progress} className="h-2" />
      </div>
    );
  }

  return <StatusBadge status={video.status} />;
}
