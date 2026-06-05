"use client";

import Hls, { type Level } from "hls.js";
import { Settings } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/animate-ui/components/radix/dropdown-menu";

type HlsPlayerProps = {
  src: string;
  title?: string;
  onReloadSource?: () => void;
};

type QualityLevel = {
  value: string;
  label: string;
  height: number;
};

function qualityLabel(level: Level) {
  if (level.height) return `${level.height}p`;
  if (level.bitrate) return `${Math.round(level.bitrate / 1000)} kbps`;
  return "Source";
}

export function HlsPlayer({ src, title, onReloadSource }: HlsPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [levels, setLevels] = useState<QualityLevel[]>([]);
  const [selectedQuality, setSelectedQuality] = useState("auto");
  const [autoLevelHeight, setAutoLevelHeight] = useState<number | null>(null);

  const selectedQualityLabel = useMemo(() => {
    if (selectedQuality === "auto") {
      return autoLevelHeight ? `Auto (${autoLevelHeight}p)` : "Auto";
    }

    return (
      levels.find((level) => level.value === selectedQuality)?.label ?? "Quality"
    );
  }, [autoLevelHeight, levels, selectedQuality]);

  const handleQualityChange = useCallback((value: string) => {
    setSelectedQuality(value);

    const hls = hlsRef.current;
    if (!hls) return;

    hls.currentLevel = value === "auto" ? -1 : Number(value);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    setLevels([]);
    setSelectedQuality("auto");
    setAutoLevelHeight(null);

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
      return () => {
        video.removeAttribute("src");
        video.load();
      };
    }

    if (!Hls.isSupported()) {
      onReloadSource?.();
      return;
    }

    const hls = new Hls({
      capLevelToPlayerSize: true,
      startLevel: -1,
    });
    hlsRef.current = hls;

    hls.loadSource(src);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      const parsedLevels = hls.levels
        .map((level, index) => ({
          value: String(index),
          label: qualityLabel(level),
          height: level.height || 0,
        }))
        .sort((first, second) => second.height - first.height);

      setLevels(parsedLevels);
    });
    hls.on(Hls.Events.LEVEL_SWITCHED, (_event, data) => {
      const level = hls.levels[data.level];
      setAutoLevelHeight(level?.height || null);
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (!data.fatal) return;

      if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
        hls.recoverMediaError();
        return;
      }

      onReloadSource?.();
    });

    return () => {
      hlsRef.current = null;
      hls.destroy();
    };
  }, [src, onReloadSource]);

  return (
    <div className="relative bg-black">
      <video
        ref={videoRef}
        className="aspect-video w-full bg-black"
        controls
        playsInline
        preload="metadata"
        title={title}
      />
      {levels.length > 0 ? (
        <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
          <span className="rounded-md bg-black/70 px-2 py-1 text-xs font-medium text-white shadow-sm">
            {selectedQualityLabel}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                className="border-white/20 bg-black/70 text-white hover:bg-black/80 hover:text-white"
              >
                <Settings className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-40">
              <DropdownMenuLabel>Quality</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuRadioGroup
                value={selectedQuality}
                onValueChange={handleQualityChange}
              >
                <DropdownMenuRadioItem value="auto">
                  <span className="flex w-full items-center justify-between gap-4">
                    Auto
                    {autoLevelHeight ? (
                      <span className="text-xs text-muted-foreground">
                        {autoLevelHeight}p
                      </span>
                    ) : null}
                  </span>
                </DropdownMenuRadioItem>
                {levels.map((level) => (
                  <DropdownMenuRadioItem key={level.value} value={level.value}>
                    {level.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ) : null}
    </div>
  );
}
