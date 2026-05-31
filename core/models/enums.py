import enum


class ProcessingStatus(str, enum.Enum):
    uploading = "uploading"
    uploaded = "uploaded"
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
