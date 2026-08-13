from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "civiclens"
    google_maps_api_key: str = ""
    admin_api_key: str = "dev-admin-key"
    use_in_memory: bool = False
    photo_storage: str = "local"
    max_upload_bytes: int = 8 * 1024 * 1024
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"

    def __post_init__(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("CIVICLENS_ENVIRONMENT must be development, test, or production.")
        if self.photo_storage not in {"local", "mongodb"}:
            raise ValueError("CIVICLENS_PHOTO_STORAGE must be local or mongodb.")
        if self.use_in_memory and self.photo_storage == "mongodb":
            raise ValueError("MongoDB photo storage requires the MongoDB report repository.")
        if self.environment == "production":
            if self.use_in_memory:
                raise ValueError("Production cannot use the in-memory repository.")
            if self.mongo_uri.startswith("mongodb://localhost"):
                raise ValueError("Production requires a non-local CIVICLENS_MONGO_URI.")
            if len(self.admin_api_key) < 24 or self.admin_api_key in {
                "dev-admin-key",
                "change-this-before-deployment",
            }:
                raise ValueError(
                    "Production requires a strong CIVICLENS_ADMIN_API_KEY "
                    "of at least 24 characters."
                )

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")
        max_upload_mb = max(1, int(os.getenv("CIVICLENS_MAX_UPLOAD_MB", "8")))
        return cls(
            environment=os.getenv("CIVICLENS_ENVIRONMENT", "development").lower(),
            mongo_uri=os.getenv("CIVICLENS_MONGO_URI", "mongodb://localhost:27017"),
            mongo_database=os.getenv("CIVICLENS_MONGO_DATABASE", "civiclens"),
            google_maps_api_key=os.getenv("CIVICLENS_GOOGLE_MAPS_API_KEY", "").strip(),
            admin_api_key=os.getenv("CIVICLENS_ADMIN_API_KEY", "dev-admin-key"),
            use_in_memory=os.getenv("CIVICLENS_USE_IN_MEMORY", "false").lower()
            in {"1", "true", "yes"},
            photo_storage=os.getenv("CIVICLENS_PHOTO_STORAGE", "local").lower(),
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            upload_dir=Path(
                os.getenv("CIVICLENS_UPLOAD_DIR", str(PROJECT_ROOT / "data" / "uploads"))
            ).resolve(),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
