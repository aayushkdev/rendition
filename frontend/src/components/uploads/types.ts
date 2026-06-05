export type VideoStatus =
  | "uploading"
  | "upload_failed"
  | "pending"
  | "processing"
  | "partial"
  | "done"
  | "failed";

export type UploadedVideo = {
  id: string;
  videoId?: string;
  title: string;
  uploadedAt: string;
  status: VideoStatus;
  size: string;
  progress: number;
  renditionProgress?: {
    completed: number;
    total: number;
  };
  canRetry?: boolean;
  canCancel?: boolean;
};
