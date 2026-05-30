from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./rendition.db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/%2F"

    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_ACCESS_KEY_ID: str = "minioadmin"
    STORAGE_SECRET_ACCESS_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "rendition"
    STORAGE_REGION: str = "us-east-1"

    class Config:
        env_file = ".env"


settings = Settings()
