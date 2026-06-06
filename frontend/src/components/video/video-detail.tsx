"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  getVideoPlayback,
  getVideoState,
  type VideoPlayback,
  type VideoState,
} from "@/components/uploads/api";
import { StatusBadge } from "@/components/uploads/status-badge";
import type { VideoStatus } from "@/components/uploads/types";
import { renditionProgressFromRenditions } from "@/components/uploads/utils";

import { HlsPlayer } from "./hls-player";

type VideoDetailProps = {
  videoId: string;
};

function isPlayable(status: VideoState["status"]) {
  return status === "done";
}

function mapStatus(status: VideoState["status"]): VideoStatus {
  if (status === "done" || status === "skipped") return "done";
  if (status === "failed") return "failed";
  return "processing";
}

function shouldShowRenditionProgress(status: VideoState["status"]) {
  return status === "pending" || status === "running" || status === "partial";
}

function RenditionProgressLabel({ videoState }: { videoState: VideoState }) {
  const { completed, total } = renditionProgressFromRenditions(
    videoState.renditions,
  );

  return (
    <span className="text-sm font-medium text-foreground">
      {completed}/{total} renditions done
    </span>
  );
}

export function VideoDetail({ videoId }: VideoDetailProps) {
  const [videoState, setVideoState] = useState<VideoState | null>(null);
  const [playback, setPlayback] = useState<VideoPlayback | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadPlayback = useCallback(async () => {
    const nextPlayback = await getVideoPlayback(videoId);
    setPlayback(nextPlayback);
  }, [videoId]);

  const reloadPlayback = useCallback(() => {
    void loadPlayback().catch((error: unknown) => {
      toast.error("Playback refresh failed", {
        description:
          error instanceof Error
            ? error.message
            : "Unable to refresh playback URL",
      });
    });
  }, [loadPlayback]);

  const loadVideo = useCallback(async () => {
    const nextState = await getVideoState(videoId);
    setVideoState(nextState);

    if (isPlayable(nextState.status)) {
      await loadPlayback();
    }
  }, [loadPlayback, videoId]);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialVideo() {
      setIsLoading(true);
      try {
        await loadVideo();
      } catch (error) {
        if (!isMounted) return;
        toast.error("Video unavailable", {
          description:
            error instanceof Error ? error.message : "Unable to load this video",
        });
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadInitialVideo();

    return () => {
      isMounted = false;
    };
  }, [loadVideo]);

  useEffect(() => {
    if (!videoState || isPlayable(videoState.status)) return;

    const intervalId = window.setInterval(() => {
      void loadVideo().catch((error: unknown) => {
        toast.error("Video status unavailable", {
          description:
            error instanceof Error ? error.message : "Unable to refresh status",
        });
      });
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [loadVideo, videoState]);

  const title = videoState ? `Video ${videoState.video_id}` : "Video";

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <Button type="button" variant="outline" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="size-4" />
              </Link>
            </Button>
            <div className="min-w-0">
              <p className="text-sm font-medium text-muted-foreground">
                Playback
              </p>
              <h1 className="mt-1 truncate text-2xl font-semibold tracking-normal">
                {title}
              </h1>
            </div>
          </div>
          {videoState ? (
            shouldShowRenditionProgress(videoState.status) ? (
              <RenditionProgressLabel videoState={videoState} />
            ) : (
              <StatusBadge status={mapStatus(videoState.status)} />
            )
          ) : null}
        </header>

        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          {playback ? (
            <HlsPlayer
              src={playback.streaming.master_playlist_url}
              title={title}
              onReloadSource={reloadPlayback}
            />
          ) : (
            <div className="grid aspect-video place-items-center bg-muted text-center">
              <div>
                <p className="text-sm font-medium">
                  {isLoading ? "Loading video..." : "Video is not playable yet"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Waiting for encoder output.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-4"
                  onClick={() => void loadVideo()}
                  disabled={isLoading}
                >
                  <RefreshCw className="size-4" />
                  Refresh
                </Button>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
