from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Settings:
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "civiclens"
    google_maps_api_key: str = ""
    admin_api_key: str = "dev-admin-key"
    use_in_memory: bool = False
    max_upload_bytes: int = 8 * 1024 * 1024
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")
        max_upload_mb = max(1, int(os.getenv("CIVICLENS_MAX_UPLOAD_MB", "8")))
        return cls(
            mongo_uri=os.getenv("CIVICLENS_MONGO_URI", "mongodb://localhost:27017"),
            mongo_database=os.getenv("CIVICLENS_MONGO_DATABASE", "civiclens"),
            google_maps_api_key=os.getenv("CIVICLENS_GOOGLE_MAPS_API_KEY", "").strip(),
            admin_api_key=os.getenv("CIVICLENS_ADMIN_API_KEY", "dev-admin-key"),
            use_in_memory=os.getenv("CIVICLENS_USE_IN_MEMORY", "false").lower()
            in {"1", "true", "yes"},
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            upload_dir=Path(
                os.getenv("CIVICLENS_UPLOAD_DIR", str(PROJECT_ROOT / "data" / "uploads"))
            ).resolve(),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
