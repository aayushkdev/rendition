from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str = "sqlite:///./rendition.db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/%2F"

    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_PUBLIC_ENDPOINT: str | None = None
    STORAGE_ACCESS_KEY_ID: str = "minioadmin"
    STORAGE_SECRET_ACCESS_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "rendition"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_PRESIGNED_URL_EXPIRES_SECONDS: int = 21_600


settings = Settings()
