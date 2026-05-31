export type VideoStatus =
  | "uploading"
  | "upload_failed"
  | "pending"
  | "processing"
  | "done"
  | "failed";

export type UploadedVideo = {
  id: string;
  title: string;
  uploadedAt: string;
  status: VideoStatus;
  size: string;
  progress: number;
};
