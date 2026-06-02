import enum


class ProcessingStatus(str, enum.Enum):
    uploading = "uploading"
    uploaded = "uploaded"
    pending = "pending"
    running = "running"
    partial = "partial"
    done = "done"
    failed = "failed"


class UploadStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    aborted = "aborted"
    failed = "failed"


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
