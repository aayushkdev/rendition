import { Play } from "lucide-react";

import { Button } from "@/components/animate-ui/components/buttons/button";
import { cn } from "@/lib/utils";

import type { FeedVideo } from "./types";

type VideoSurfaceProps = {
  video: FeedVideo;
  className?: string;
};

export function VideoSurface({ video, className }: VideoSurfaceProps) {
  return (
    <div
      className={cn(
        "relative flex aspect-video overflow-hidden rounded-md text-white shadow-inner",
        video.palette,
        className,
      )}
    >
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/60 to-transparent" />
      <span className="absolute bottom-3 right-3 rounded-md bg-black/70 px-2 py-1 text-xs font-medium">
        {video.duration}
      </span>
      <div className="m-auto grid size-14 place-items-center rounded-full bg-white/16 ring-1 ring-white/30 backdrop-blur">
        <Button type="button" size="icon" className="rounded-full">
          <Play className="size-4 fill-current" />
        </Button>
      </div>
    </div>
  );
}
