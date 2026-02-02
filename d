
# Rendition – Distributed Video Transcoding & Streaming System


## Goal

Build a **fine-grained, horizontally scalable video transcoding and streaming system** where each video is decomposed into independent transcoding jobs and served via **adaptive bitrate streaming (HLS)**.

---

## 1. High-Level Architecture

```
Client (Web / Mobile Player)
  |
  | Upload
  v
FastAPI (Control Plane)
  |
  | Create Jobs
  v
RabbitMQ (Job Queue)  <——— PostgreSQL
  |
  | Pull Jobs
  v
Transcoding Workers (stateless, scalable)
  |
  | Upload segments & playlists
  v
Object Storage (S3 / MinIO)
  |
  v
CDN
  |
  v
HLS Player (ABR)
```

---

## 2. Core Design Principle (Key Interview Point)

> **Each transcoding rendition is an independent job.**

A single uploaded video is split into multiple jobs:

* 1080p job
* 720p job
* 480p job

Each job:

* Runs on any worker
* Retries independently
* Produces its own HLS playlist and segments

This enables parallelism, fault isolation, and horizontal scaling.

---

## 3. Components and Responsibilities

### A. API / Control Plane (FastAPI)

**Responsibilities**

* Accept uploads (or object references)
* Extract metadata (`ffprobe`)
* Decide renditions
* Fan out jobs
* Track state
* Expose streaming URLs

**Does NOT**

* Run FFmpeg
* Serve video bytes

**Why this matters**

* Keeps API responsive
* Clean separation of orchestration vs execution

**Stack**

* FastAPI
* PostgreSQL

---

### B. Job Queue (RabbitMQ)

**Purpose**

* Distribute transcoding jobs
* Apply backpressure
* Enable retries

**Why RabbitMQ**

* Explicit acknowledgements
* At-least-once delivery
* Dead-letter queues
* Natural fit for work execution

**Key features used**

* One queue per job type (optional)
* Retry with backoff
* DLQ for poisoned jobs

Kafka is **not** used for job execution.

---

### C. Transcoding Workers

**Worker model**

* Long-running processes
* Pull one job at a time
* Run one FFmpeg process
* Upload outputs
* Acknowledge job on success

**Stateless**

* No durable local state
* Safe to kill and replace

**Why one job per worker**

* FFmpeg is CPU-intensive
* Predictable resource usage
* Easier scheduling

---

### D. Object Storage

**Purpose**

* Durable storage for inputs and outputs
* Decouple compute from serving

**Structure (HLS-ready)**

```
outputs/{video_id}/
├── 1080p/
│   ├── index.m3u8
│   └── segment_000.ts
├── 720p/
│   ├── index.m3u8
│   └── segment_000.ts
├── 480p/
│   ├── index.m3u8
│   └── segment_000.ts
└── master.m3u8
```

---

### E. Database (Metadata & State)

**Tables**

* `videos`
* `jobs`
* `renditions`

**Used for**

* Job state
* Retry tracking
* Progress reporting
* Idempotency
* Observability

---

## 4. Job Lifecycle

### 1. Upload

User uploads a video via FastAPI.

### 2. Metadata extraction

API runs:

```
ffprobe → duration, resolution, codec
```

### 3. Job fan-out

API creates one job per rendition:

```
(video_id, resolution, bitrate)
```

### 4. Queue dispatch

Jobs are published to RabbitMQ.

### 5. Worker execution

Worker:

* Downloads input
* Runs FFmpeg with HLS output
* Uploads segments + playlist
* Updates job state
* Acknowledges message

### 6. Master playlist generation

When all jobs complete:

* API (or a finalizer worker) generates `master.m3u8`
* Video marked **ready**

---

## 5. Adaptive Bitrate Streaming (ABR)

### Key Principle

> **The backend does not choose the quality. The player does.**

### How it works

* Client requests `master.m3u8`
* Player measures bandwidth and device capability
* Player automatically switches renditions

### Master Playlist Example

```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
1080p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=854x480
480p/index.m3u8
```

### API role

* Expose URL to `master.m3u8`
* Never serve media bytes

---

## 6. Failure Handling

### Worker crash

* Message not acknowledged
* RabbitMQ requeues job

### Encoding failure

* Retry with limit
* Send to DLQ if persistent

### Partial success

* Some renditions available
* Master playlist can be generated with available qualities (optional)

---

## 7. Scaling Strategy

### Horizontal scaling

Increase worker count to increase throughput.

### Backpressure

RabbitMQ absorbs spikes without overloading API or storage.

### Priority queues (optional)

* Separate queues for HD vs SD jobs

---

## 8. Why This Is the Best System Design

This design demonstrates:

* Fine-grained job decomposition
* Stateless workers
* Horizontal scalability
* Failure isolation
* Proper use of RabbitMQ
* Correct ABR streaming model
* Clean separation of concerns

---

## 9. Interview Explanation (Key Paragraph)

> “Rendition decomposes each uploaded video into independent transcoding jobs, one per rendition. Jobs are distributed via RabbitMQ to stateless workers running FFmpeg. Each job produces HLS segments and playlists, and a master playlist enables adaptive bitrate streaming where the client selects quality automatically. Object storage and a CDN decouple compute from delivery, and job state is tracked in a database for retries and observability.”

---

## 10. Final Recommendation

**Use Option B.**

* FastAPI control plane
* RabbitMQ for job execution
* Stateless FFmpeg workers
* HLS + ABR for streaming
* CDN for delivery

This is a **production-grade, interview-winning system design**.

If you want next, I can:

* Add FFmpeg HLS command examples
* Design the exact DB schema
* Add worker retry logic
* Draw the final architecture diagram for README/interviews
