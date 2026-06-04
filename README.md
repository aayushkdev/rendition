# Rendition

Rendition is a distributed video transcoding system. It accepts large video
uploads, stores the source video in S3-compatible object storage, queues encoding
jobs, generates HLS renditions with `ffmpeg`, and publishes a master playlist for
playback.

The local stack uses FastAPI, PostgreSQL, RabbitMQ, MinIO, a Python worker, an
outbox publisher, and a Next.js frontend.

## What It Does

- Direct browser-to-object-storage multipart uploads using presigned URLs.
- Upload validation for file size, content type, part count, part ordering, and
  ETags.
- Upload completion verification against object metadata before work is queued.
- One encoding job per target rendition.
- RabbitMQ job publishing through an outbox so jobs are not lost if RabbitMQ is
  temporarily unavailable.
- Worker-side job claiming with manual ack/nack behavior.
- Source probing with `ffprobe` for width, height, bitrate, and duration.
- HLS encoding with `ffmpeg` for 1080p, 720p, and 480p presets.
- Source-aware rendition skipping. For example, a 720p source will not create a
  1080p output.
- HLS segment and rendition playlist upload to object storage.
- Master playlist generation at `hls/{video_id}/master.m3u8`.
- Partial playback support when at least one rendition succeeds.
- Request IDs and consistent API error responses.
- A dashboard UI for uploads, progress, cancellation, retry, and uploaded video
  status.

## Architecture

```mermaid
flowchart LR
  frontend[Frontend] --> api[API]
  frontend --> storage[(Object Storage)]
  api --> storage
  api --> postgres[(PostgreSQL)]
  api --> rabbitmq[(RabbitMQ)]
  outbox[Outbox Publisher] --> postgres
  outbox --> rabbitmq
  rabbitmq --> worker[Encoding Worker]
  worker --> postgres
  worker --> storage
```

### Services

- `frontend`: Next.js app for upload testing and video/dashboard views.
- `api`: FastAPI service exposing health checks, upload APIs, and video APIs.
- `worker`: consumes encoding jobs and runs `ffprobe`/`ffmpeg`.
- `outbox`: periodically publishes pending queue messages from PostgreSQL to
  RabbitMQ.
- `postgres`: application database.
- `rabbitmq`: job queue.
- `minio`: local S3-compatible object storage for development.
- `minio-init`: creates the private local bucket.

## Upload And Encoding Flow

1. The frontend asks the API for upload limits and allowed content types.
2. The frontend starts an upload with filename, content type, size, and part
   count.
3. The API creates a `Video`, an `UploadSession`, and a multipart upload in
   object storage.
4. The frontend uploads each chunk directly to MinIO/S3 with presigned part URLs.
5. The frontend completes the upload by sending part numbers and ETags to the
   API.
6. The API completes the multipart upload and verifies object size/content type.
7. The API creates renditions, jobs, and outbox messages in the database.
8. The API attempts immediate queue publishing; the outbox service retries any
   pending messages every 30 seconds.
9. The worker claims a pending job, downloads the source video, and probes it.
10. If the requested rendition is not valid for the source, the rendition is
    marked `skipped`.
11. Valid renditions are encoded to HLS in a temporary per-job directory.
12. The worker uploads HLS segments and the rendition playlist.
13. Once all rendition work is terminal, a master playlist is generated and
    uploaded.
14. `videos.playback_path` points at the master playlist.

## Local Development

The local setup runs with:

- FastAPI API
- Next.js frontend
- PostgreSQL
- RabbitMQ
- MinIO
- Python encoding worker
- Outbox publisher


Create your local environment file:

```bash
cp .env.example .env
```

Start everything:

```bash
docker compose up --build
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Open:

- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`
- RabbitMQ console: `http://localhost:15672`

Default local credentials from `.env.example`:

```text
Postgres:  rendition / rendition
RabbitMQ:  rendition / rendition
Object storage: rendition / rendition-secret
Bucket:    rendition
```

## Production Deployment

Use `docker-compose.prod.yml` when object storage is provided externally by AWS
S3, Cloudflare R2, or another S3-compatible provider.

Create a production environment file with working database, RabbitMQ, and
storage credentials, then start the stack with:

```bash
docker compose -f docker-compose.prod.yml up --build
```

At minimum, the production environment should provide:

```text
POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DB=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...

RABBITMQ_DEFAULT_USER=...
RABBITMQ_DEFAULT_PASS=...

STORAGE_ENDPOINT=...
STORAGE_PRESIGN_ENDPOINT=...
STORAGE_ACCESS_KEY_ID=...
STORAGE_SECRET_ACCESS_KEY=...
STORAGE_BUCKET=...
STORAGE_REGION=...
```

Typical production flow:

1. Create the object storage bucket ahead of time.
2. Prepare the production environment file or exported environment variables.
3. Start the stack with `docker compose -f docker-compose.prod.yml up --build -d`.
4. Run database migrations with `uv run alembic upgrade head`.
5. Verify the API health endpoint and frontend before sending traffic.

Unlike the local stack, the production compose file does not provision MinIO or
create a bucket for you. It assumes PostgreSQL, RabbitMQ, and your
S3-compatible storage are already available and correctly configured.
