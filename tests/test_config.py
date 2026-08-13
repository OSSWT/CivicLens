from __future__ import annotations

import pytest

from app.config import Settings


def test_production_settings_require_persistent_database_and_strong_admin_key() -> None:
    with pytest.raises(ValueError, match="in-memory"):
        Settings(
            environment="production",
            use_in_memory=True,
            admin_api_key="strong-secret",
        )

    with pytest.raises(ValueError, match="non-local"):
        Settings(
            environment="production",
            mongo_uri="mongodb://localhost:27017",
            admin_api_key="strong-secret",
        )

    with pytest.raises(ValueError, match="strong"):
        Settings(
            environment="production",
            mongo_uri="mongodb+srv://cluster.example.net",
            admin_api_key="dev-admin-key",
        )

    with pytest.raises(ValueError, match="at least 24"):
        Settings(
            environment="production",
            mongo_uri="mongodb+srv://cluster.example.net",
            admin_api_key="too-short",
        )


def test_production_accepts_atlas_gridfs_configuration() -> None:
    settings = Settings(
        environment="production",
        mongo_uri="mongodb+srv://cluster.example.net",
        mongo_database="civiclens",
        admin_api_key="a-long-random-production-secret",
        photo_storage="mongodb",
    )

    assert settings.photo_storage == "mongodb"
    assert settings.use_in_memory is False


def test_mongodb_photo_storage_cannot_use_memory_repository() -> None:
    with pytest.raises(ValueError, match="requires the MongoDB report repository"):
        Settings(use_in_memory=True, photo_storage="mongodb")
