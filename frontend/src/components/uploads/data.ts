import type { UploadedVideo } from "./types";

export const uploadedVideos: UploadedVideo[] = [
  {
    id: "vid_01",
    title: "launch-demo.mp4",
    uploadedAt: "Today, 10:42",
    status: "processing",
    size: "1.8 GB",
    progress: 62,
  },
  {
    id: "vid_02",
    title: "city-walkthrough.mov",
    uploadedAt: "Yesterday",
    status: "done",
    size: "842 MB",
    progress: 100,
  },
  {
    id: "vid_03",
    title: "studio-cut.mkv",
    uploadedAt: "May 31",
    status: "pending",
    size: "3.1 GB",
    progress: 0,
  },
  {
    id: "vid_04",
    title: "broken-export.mp4",
    uploadedAt: "May 30",
    status: "failed",
    size: "611 MB",
    progress: 18,
  },
];
