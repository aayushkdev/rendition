import type { FeedVideo } from "./types";
import { VideoSurface } from "./video-surface";

type UpNextListProps = {
  videos: FeedVideo[];
};

export function UpNextList({ videos }: UpNextListProps) {
  return (
    <aside className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">
          Up next
        </h2>
        <span className="text-xs text-muted-foreground">Autoplay</span>
      </div>
      <div className="mt-4 grid gap-4">
        {videos.map((video) => (
          <article key={video.id} className="grid grid-cols-[128px_1fr] gap-3">
            <VideoSurface video={video} className="rounded-md" />
            <div className="min-w-0">
              <h3 className="line-clamp-2 text-sm font-semibold">
                {video.title}
              </h3>
              <p className="mt-1 truncate text-xs text-muted-foreground">
                {video.owner}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                {video.duration} / {video.quality}
              </p>
            </div>
          </article>
        ))}
      </div>
    </aside>
  );
}
