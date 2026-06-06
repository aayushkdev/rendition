from pydantic import Field, model_validator
from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "rendition"
    POSTGRES_USER: str = "rendition"
    POSTGRES_PASSWORD: str = "rendition"

    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/%2F"
    RABBITMQ_CONNECT_RETRY_COUNT: int = Field(default=30, ge=1)
    OUTBOX_PUBLISH_BATCH_SIZE: int = Field(default=100, ge=1)
    OUTBOX_PUBLISH_INTERVAL_SECONDS: float = Field(default=30.0, gt=0)

    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_PRESIGN_ENDPOINT: str | None = None
    STORAGE_ACCESS_KEY_ID: str = "minioadmin"
    STORAGE_SECRET_ACCESS_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "rendition"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_PRESIGNED_URL_EXPIRES_SECONDS: int = 21_600

    UPLOAD_MAX_SIZE_BYTES: int = Field(default=5_368_709_120, gt=0)
    UPLOAD_MAX_PART_COUNT: int = Field(default=10_000, ge=1, le=10_000)
    UPLOAD_PART_SIZE_BYTES: int = Field(default=8_388_608, ge=5_242_880)
    UPLOAD_ALLOWED_CONTENT_TYPES: str = "video/mp4,video/quicktime,video/x-matroska"

    WORKER_JOB_RETRY_COUNT: int = Field(default=3, ge=0)
    WORKER_QUEUE_NAME: str = "jobs.encode"
    WORKER_PREFETCH_COUNT: int = Field(default=1, ge=1)
    WORKER_TEMP_ROOT: str = "/tmp/rendition"
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = Field(default=60, ge=1)
    JOB_REAPER_INTERVAL_SECONDS: int = Field(default=120, ge=1)
    JOB_STALE_TIMEOUT_SECONDS: int = Field(default=300, ge=1)
    JOB_RETRY_BACKOFF_SECONDS: str = "30,120,600"

    ENVIRONMENT: str = "local"

    @property
    def DATABASE_URL(self) -> str:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @property
    def upload_allowed_content_types(self) -> set[str]:
        return {
            content_type.strip()
            for content_type in self.UPLOAD_ALLOWED_CONTENT_TYPES.split(",")
            if content_type.strip()
        }

    @property
    def job_retry_backoff_seconds(self) -> list[int]:
        values: list[int] = []
        for raw_value in self.JOB_RETRY_BACKOFF_SECONDS.split(","):
            value = raw_value.strip()
            if not value:
                continue
            values.append(max(0, int(value)))
        return values or [0]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            default_secret_values = {
                "rendition",
                "rendition-secret",
                "minioadmin",
                "guest",
            }
            sensitive_values = {
                self.POSTGRES_PASSWORD,
                self.STORAGE_ACCESS_KEY_ID,
                self.STORAGE_SECRET_ACCESS_KEY,
            }
            if sensitive_values & default_secret_values:
                raise ValueError("production settings must not use default secrets")

        return self


settings = Settings()
