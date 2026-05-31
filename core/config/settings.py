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

    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_PUBLIC_ENDPOINT: str | None = None
    STORAGE_ACCESS_KEY_ID: str = "minioadmin"
    STORAGE_SECRET_ACCESS_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "rendition"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_PRESIGNED_URL_EXPIRES_SECONDS: int = 21_600

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


settings = Settings()
