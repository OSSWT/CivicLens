from __future__ import annotations

from pathlib import Path
from uuid import uuid4


class LocalPhotoStorage:
    EXTENSIONS = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, content_type: str) -> tuple[str, str]:
        extension = self.EXTENSIONS.get(content_type)
        if extension is None:
            raise ValueError("Only JPEG, PNG, and WebP images are supported.")
        storage_name = f"{uuid4().hex}{extension}"
        (self.upload_dir / storage_name).write_bytes(content)
        return storage_name, f"/uploads/{storage_name}"

    def read(self, storage_name: str) -> bytes:
        safe_name = Path(storage_name).name
        return (self.upload_dir / safe_name).read_bytes()

    def delete(self, storage_name: str | None) -> None:
        if not storage_name:
            return
        safe_name = Path(storage_name).name
        (self.upload_dir / safe_name).unlink(missing_ok=True)
