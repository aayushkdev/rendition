import { Play } from "lucide-react";

import { cn } from "@/lib/utils";

import type { FeedVideo } from "./types";

type VideoSurfaceProps = {
  video: FeedVideo;
  className?: string;
  onClick?: () => void;
  player?: boolean;
};

export function VideoSurface({
  video,
  className,
  onClick,
  player = false,
}: VideoSurfaceProps) {
  const content = (
    <>
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/60 to-transparent" />
      <span className="absolute bottom-3 right-3 rounded-md bg-black/70 px-2 py-1 text-xs font-medium">
        {video.duration}
      </span>
      <div
        className={cn(
          "m-auto grid place-items-center rounded-full bg-white/16 ring-1 ring-white/30 backdrop-blur transition-transform",
          player ? "size-20" : "size-14 group-hover:scale-105",
        )}
      >
        <div
          className={cn(
            "grid place-items-center rounded-full bg-primary text-primary-foreground shadow-lg",
            player ? "size-12" : "size-9",
          )}
        >
          <Play className={cn("fill-current", player ? "size-5" : "size-4")} />
        </div>
      </div>
    </>
  );

  const baseClassName = cn(
    "group relative flex aspect-video overflow-hidden rounded-md text-white shadow-inner",
    video.palette,
    className,
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          baseClassName,
          "w-full text-left outline-none transition-transform hover:-translate-y-0.5 focus-visible:ring-ring/50 focus-visible:ring-[3px]",
        )}
      >
        {content}
      </button>
    );
  }

  return (
    <div
      className={cn(
        baseClassName,
        player && "rounded-lg",
      )}
    >
      {content}
    </div>
  );
}
