from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.repository import MongoReportRepository


@pytest.mark.integration
def test_real_mongo_repository_geospatial_crud() -> None:
    uri = os.getenv("TEST_MONGO_URI")
    if not uri:
        pytest.skip("TEST_MONGO_URI is not configured")

    database_name = f"civiclens_integration_{uuid4().hex}"
    client, repository = MongoReportRepository.connect(uri, database_name)
    now = datetime.now(UTC)
    try:
        repository.ensure_indexes()
        indexes = repository.collection.index_information()
        assert indexes["reports_location_2dsphere"]["key"] == [("location", "2dsphere")]

        created = repository.create(
            {
                "title": "MongoDB integration pothole",
                "category": "pothole",
                "description": "Created by the CI integration test.",
                "location": {
                    "type": "Point",
                    "coordinates": [101.6869, 3.139],
                },
                "status": "reported",
                "before_photo": {},
                "after_photo": None,
                "change_analysis": None,
                "created_at": now,
                "updated_at": now,
            }
        )

        nearby = repository.nearby(
            longitude=101.6869,
            latitude=3.139,
            radius_meters=500,
            category="pothole",
            status="reported",
        )
        assert [report["id"] for report in nearby] == [created["id"]]

        updated = repository.update_status(created["id"], "in_progress", now)
        assert updated is not None
        assert updated["status"] == "in_progress"

        deleted = repository.delete(created["id"])
        assert deleted is not None
        assert repository.get(created["id"]) is None
    finally:
        client.drop_database(database_name)
        client.close()
