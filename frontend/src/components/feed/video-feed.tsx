"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Clock3,
  Maximize,
  Play,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Volume2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/animate-ui/components/radix/tooltip";
import { feedVideos } from "./data";
import { UpNextList } from "./up-next-list";
import type { FeedVideo } from "./types";
import { VideoCard } from "./video-card";
import { VideoGridSkeleton } from "./video-feed-skeleton";
import { VideoSurface } from "./video-surface";

export function VideoFeed() {
  const [selectedVideo, setSelectedVideo] = useState<FeedVideo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const sideVideos = useMemo(
    () =>
      selectedVideo
        ? feedVideos.filter((video) => video.id !== selectedVideo.id)
        : feedVideos.slice(1),
    [selectedVideo],
  );

  function refreshFeed() {
    setIsLoading(true);
    window.setTimeout(() => {
      setIsLoading(false);
      toast.info("Feed refreshed");
    }, 700);
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-7 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 lg:flex-row lg:items-center lg:justify-between">
          <Link href="/" className="flex w-fit items-center gap-3">
            <div className="grid size-10 place-items-center rounded-md bg-foreground text-background">
              <Play className="size-4 fill-current" />
            </div>
            <div>
              <p className="text-lg font-semibold leading-none">Rendition</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Video delivery
              </p>
            </div>
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-10 min-w-64 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm text-muted-foreground">
              <Search className="size-4" />
              <span>Search videos</span>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button type="button" variant="outline" size="icon">
                  <SlidersHorizontal className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Filters</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={refreshFeed}
                  disabled={isLoading}
                >
                  <RefreshCw className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Refresh feed</TooltipContent>
            </Tooltip>
            <Button type="button" asChild>
              <Link href="/dashboard">
                <Plus className="size-4" />
                Upload
              </Link>
            </Button>
          </div>
        </header>

        {selectedVideo ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <div className="min-w-0">
              <Button
                type="button"
                variant="ghost"
                className="mb-3"
                onClick={() => setSelectedVideo(null)}
              >
                <ArrowLeft className="size-4" />
                All videos
              </Button>
              <VideoSurface video={selectedVideo} className="rounded-lg" player />
              <div className="mt-3 flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="outline" size="icon">
                      <Play className="size-4 fill-current" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Play</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="outline" size="icon">
                      <Volume2 className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Volume</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="outline" size="icon">
                      <Maximize className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Fullscreen</TooltipContent>
                </Tooltip>
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h1 className="text-2xl font-semibold tracking-normal md:text-3xl">
                    {selectedVideo.title}
                  </h1>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {selectedVideo.owner} / {selectedVideo.uploadedAt} /{" "}
                    {selectedVideo.views} views
                  </p>
                </div>
                <Button type="button" variant="outline">
                  <Clock3 className="size-4" />
                  Watch later
                </Button>
              </div>
            </div>

            <UpNextList videos={sideVideos} onSelect={setSelectedVideo} />
          </section>
        ) : (
          isLoading ? (
            <VideoGridSkeleton />
          ) : (
            <section className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {feedVideos.map((video) => (
                <VideoCard
                  key={video.id}
                  video={video}
                  onSelect={setSelectedVideo}
                />
              ))}
            </section>
          )
        )}
      </div>
    </main>
  );
}
