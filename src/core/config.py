from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    rabbitmq_url: str = Field(
        "amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL"
    )
    storage_path: str = Field("/data/videos", alias="STORAGE_PATH")
    max_upload_size_mb: int = Field(200, alias="MAX_UPLOAD_SIZE_MB")
    allowed_mime_types: list[str] = Field(
        default=["video/mp4", "video/avi", "video/quicktime", "video/x-matroska"],
        alias="ALLOWED_MIME_TYPES",
    )
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = {"env_file": ".env", "populate_by_name": True}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
