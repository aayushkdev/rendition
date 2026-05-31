import { Eye, Film } from "lucide-react";

import type { FeedVideo } from "./types";
import { VideoSurface } from "./video-surface";

type VideoCardProps = {
  video: FeedVideo;
};

export function VideoCard({ video }: VideoCardProps) {
  return (
    <article className="group">
      <VideoSurface video={video} />
      <div className="mt-3 flex items-start gap-3">
        <div className="mt-1 grid size-9 shrink-0 place-items-center rounded-md bg-secondary text-secondary-foreground">
          <Film className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="line-clamp-2 text-sm font-semibold leading-5">
            {video.title}
          </h2>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {video.owner} / {video.uploadedAt}
          </p>
          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Eye className="size-3.5" />
              {video.views}
            </span>
            <span>{video.quality}</span>
          </div>
        </div>
      </div>
    </article>
  );
}
