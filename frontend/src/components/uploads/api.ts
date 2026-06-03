export type MultipartUploadPart = {
  part_number: number;
  upload_url: string;
};

export type VideoCreateResponse = {
  video_id: string;
  bucket: string;
  key: string;
  upload_id: string;
  parts: MultipartUploadPart[];
};

export type UploadConfigResponse = {
  max_size_bytes: number;
  max_part_count: number;
  part_size_bytes: number;
  allowed_content_types: string[];
};

export type VideoState = {
  video_id: string;
  status:
    | "uploading"
    | "uploaded"
    | "pending"
    | "running"
    | "partial"
    | "done"
    | "skipped"
    | "failed";
  renditions: Array<{
    resolution: string;
    status:
      | "uploading"
      | "uploaded"
      | "pending"
      | "running"
      | "partial"
      | "done"
      | "skipped"
      | "failed";
  }>;
};

export type VideoListItem = {
  video_id: string;
  title: string;
  uploaded_at: string | null;
  created_at: string;
  status: VideoState["status"];
  size_bytes: number | null;
};

type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "/api/v1";

async function readApiError(response: Response) {
  let body: ApiErrorBody | null = null;

  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = null;
  }

  return body?.error?.message ?? `request failed with ${response.status}`;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  return (await response.json()) as T;
}

export function createVideoUpload(payload: {
  filename: string;
  content_type: string;
  size_bytes: number;
  part_count: number;
}) {
  return requestJson<VideoCreateResponse>("/videos", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getUploadConfig() {
  return requestJson<UploadConfigResponse>("/videos/upload/config");
}

export function listVideos() {
  return requestJson<VideoListItem[]>("/videos");
}

export function refreshVideoUpload(videoId: string, partCount: number) {
  return requestJson<VideoCreateResponse>(`/videos/${videoId}/upload/refresh`, {
    method: "POST",
    body: JSON.stringify({ part_count: partCount }),
  });
}

export function completeVideoUpload(
  videoId: string,
  parts: Array<{ part_number: number; etag: string }>,
) {
  return requestJson<VideoState>(`/videos/${videoId}/upload/complete`, {
    method: "POST",
    body: JSON.stringify({ parts }),
  });
}

export async function abortVideoUpload(videoId: string) {
  const response = await fetch(`${API_BASE_URL}/videos/${videoId}/upload`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 404) {
    throw new Error(await readApiError(response));
  }
}
