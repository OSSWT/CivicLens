from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import GridFSBucket
from gridfs.errors import NoFile
from pymongo.database import Database

SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
CONTENT_TYPES_BY_EXTENSION = {
    extension: content_type for content_type, extension in SUPPORTED_CONTENT_TYPES.items()
}


class PhotoStorage(Protocol):
    def save(self, content: bytes, content_type: str) -> tuple[str, str]: ...

    def read(self, storage_name: str) -> tuple[bytes, str]: ...

    def delete(self, storage_name: str | None) -> None: ...


class LocalPhotoStorage:
    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, content_type: str) -> tuple[str, str]:
        extension = SUPPORTED_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise ValueError("Only JPEG, PNG, and WebP images are supported.")
        storage_name = f"{uuid4().hex}{extension}"
        (self.upload_dir / storage_name).write_bytes(content)
        return storage_name, f"/uploads/{storage_name}"

    def read(self, storage_name: str) -> tuple[bytes, str]:
        safe_name = Path(storage_name).name
        return (self.upload_dir / safe_name).read_bytes(), _content_type(safe_name)

    def delete(self, storage_name: str | None) -> None:
        if not storage_name:
            return
        safe_name = Path(storage_name).name
        (self.upload_dir / safe_name).unlink(missing_ok=True)


class MongoPhotoStorage:
    def __init__(self, database: Database) -> None:
        self.bucket = GridFSBucket(database, bucket_name="photos")

    def save(self, content: bytes, content_type: str) -> tuple[str, str]:
        extension = SUPPORTED_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise ValueError("Only JPEG, PNG, and WebP images are supported.")
        file_id = ObjectId()
        storage_name = f"{file_id}{extension}"
        self.bucket.upload_from_stream_with_id(
            file_id,
            storage_name,
            content,
            metadata={"content_type": content_type},
        )
        return storage_name, f"/uploads/{storage_name}"

    def read(self, storage_name: str) -> tuple[bytes, str]:
        file_id = _file_id(storage_name)
        try:
            stream = self.bucket.open_download_stream(file_id)
            content_type = (stream.metadata or {}).get("content_type") or _content_type(
                storage_name
            )
            return stream.read(), content_type
        except NoFile as error:
            raise FileNotFoundError(storage_name) from error

    def delete(self, storage_name: str | None) -> None:
        if not storage_name:
            return
        try:
            self.bucket.delete(_file_id(storage_name))
        except (NoFile, FileNotFoundError):
            return


def _content_type(storage_name: str) -> str:
    content_type = CONTENT_TYPES_BY_EXTENSION.get(Path(storage_name).suffix.lower())
    if content_type is None:
        raise FileNotFoundError(storage_name)
    return content_type


def _file_id(storage_name: str) -> ObjectId:
    try:
        return ObjectId(Path(storage_name).stem)
    except (InvalidId, TypeError) as error:
        raise FileNotFoundError(storage_name) from error
