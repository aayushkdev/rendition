"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
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
import { listVideos, type VideoListItem } from "@/components/uploads/api";

import { UpNextList } from "./up-next-list";
import type { FeedVideo } from "./types";
import { VideoCard } from "./video-card";
import { VideoGridSkeleton } from "./video-feed-skeleton";
import { VideoSurface } from "./video-surface";

const PAGE_SIZE = 8;
const VIDEO_PALETTES = [
  "bg-[linear-gradient(135deg,#10241f,#2a6f62_46%,#d6b65b)]",
  "bg-[linear-gradient(135deg,#101827,#245b87_48%,#9ed6d0)]",
  "bg-[linear-gradient(135deg,#261513,#985b31_48%,#e3c06f)]",
  "bg-[linear-gradient(135deg,#1c1830,#496c62_50%,#d77d4d)]",
  "bg-[linear-gradient(135deg,#17221b,#647148_50%,#e1d0a1)]",
  "bg-[linear-gradient(135deg,#202020,#67523a_50%,#c5aa74)]",
  "bg-[linear-gradient(135deg,#14201f,#2f7771_48%,#b7d7c9)]",
  "bg-[linear-gradient(135deg,#241814,#8f4f32_48%,#e7a85f)]",
];

function formatUploadedAt(value: string | null) {
  if (!value) return "Uploaded";

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function paletteForVideo(videoId: string) {
  const total = Array.from(videoId).reduce(
    (sum, character) => sum + character.charCodeAt(0),
    0,
  );

  return VIDEO_PALETTES[total % VIDEO_PALETTES.length];
}

function toFeedVideo(video: VideoListItem): FeedVideo {
  return {
    id: video.video_id,
    title: video.title,
    owner: "Rendition",
    uploadedAt: formatUploadedAt(video.uploaded_at ?? video.created_at),
    duration: "Ready",
    quality: "HLS",
    views: "Playable",
    palette: paletteForVideo(video.video_id),
  };
}

export function VideoFeed() {
  const router = useRouter();
  const [selectedVideo, setSelectedVideo] = useState<FeedVideo | null>(null);
  const [videos, setVideos] = useState<FeedVideo[]>([]);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const sideVideos = useMemo(
    () =>
      selectedVideo
        ? videos.filter((video) => video.id !== selectedVideo.id)
        : videos.slice(1),
    [selectedVideo, videos],
  );
  const canGoNext = videos.length === PAGE_SIZE;

  const loadVideos = useCallback(async (nextPage: number, showToast = false) => {
    setIsLoading(true);

    try {
      const response = await listVideos({
        page: nextPage,
        pageSize: PAGE_SIZE,
        status: "done",
      });

      setVideos(response.map(toFeedVideo));
      setSelectedVideo(null);

      if (showToast) {
        toast.info("Feed refreshed");
      }
    } catch (error) {
      toast.error("Videos unavailable", {
        description:
          error instanceof Error ? error.message : "Unable to load videos",
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadVideos(page);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [loadVideos, page]);

  function refreshFeed() {
    void loadVideos(page, true);
  }

  function openVideo(video: FeedVideo) {
    router.push(`/videos/${video.id}`);
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
        ) : isLoading ? (
          <VideoGridSkeleton />
        ) : videos.length > 0 ? (
          <>
            <section className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {videos.map((video) => (
                <VideoCard
                  key={video.id}
                  video={video}
                  onSelect={openVideo}
                />
              ))}
            </section>

            <div className="flex items-center justify-between border-t border-border pt-4 text-sm text-muted-foreground">
              <p>Page {page}</p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page === 1 || isLoading}
                >
                  <ChevronLeft className="size-4" />
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!canGoNext || isLoading}
                >
                  Next
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <section className="grid min-h-80 place-items-center border-y border-border py-12 text-center">
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">
                No completed videos yet
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Finished transcodes will appear here.
              </p>
              <Button type="button" className="mt-5" asChild>
                <Link href="/dashboard">
                  <Plus className="size-4" />
                  Upload
                </Link>
              </Button>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
