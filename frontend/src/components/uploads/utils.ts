import type { VideoState } from "./api";

export function formatBytes(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function renditionProgressFromRenditions(
  renditions: VideoState["renditions"],
) {
  const relevantRenditions = renditions.filter(
    (rendition) => rendition.status !== "skipped",
  );
  const completed = relevantRenditions.filter(
    (rendition) => rendition.status === "done",
  ).length;

  return {
    completed,
    total: relevantRenditions.length,
  };
}
