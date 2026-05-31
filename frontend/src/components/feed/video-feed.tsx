"use client";

import Link from "next/link";
import { Clock3, Play, Plus, Search, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/animate-ui/components/radix/tooltip";
import { feedVideos } from "./data";
import { UpNextList } from "./up-next-list";
import { VideoCard } from "./video-card";
import { VideoSurface } from "./video-surface";

export function VideoFeed() {
  const featured = feedVideos[0];

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
            <Button type="button" asChild>
              <Link href="/dashboard">
                <Plus className="size-4" />
                Upload
              </Link>
            </Button>
          </div>
        </header>

        <section className="grid gap-5 lg:grid-cols-[1.55fr_0.85fr]">
          <div>
            <VideoSurface video={featured} className="rounded-lg" />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-normal md:text-3xl">
                  {featured.title}
                </h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  {featured.owner} / {featured.uploadedAt} / {featured.views} views
                </p>
              </div>
              <Button type="button" variant="outline">
                <Clock3 className="size-4" />
                Watch later
              </Button>
            </div>
          </div>

          <UpNextList videos={feedVideos.slice(1, 4)} />
        </section>

        <section className="grid gap-x-5 gap-y-7 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {feedVideos.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </section>
      </div>
    </main>
  );
}
