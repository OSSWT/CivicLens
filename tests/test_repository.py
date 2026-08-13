from __future__ import annotations

from datetime import UTC, datetime

from app.repository import InMemoryReportRepository, MongoReportRepository


class FakeCursor(list):
    def limit(self, limit: int):
        return FakeCursor(self[:limit])


class FakeCollection:
    def __init__(self) -> None:
        self.indexes = []
        self.last_query = None

    def create_index(self, keys, **options):
        self.indexes.append((keys, options))

    def find(self, query):
        self.last_query = query
        return FakeCursor()


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def get_collection(self, name: str):
        assert name == "reports"
        return self.collection


def report_document(title: str, longitude: float, latitude: float, category: str = "pothole"):
    now = datetime.now(UTC)
    return {
        "title": title,
        "category": category,
        "description": "Test report",
        "location": {"type": "Point", "coordinates": [longitude, latitude]},
        "status": "reported",
        "before_photo": {},
        "after_photo": None,
        "change_analysis": None,
        "created_at": now,
        "updated_at": now,
    }


def test_nearby_uses_distance_and_returns_nearest_first() -> None:
    repository = InMemoryReportRepository()
    repository.create(report_document("Farther", 101.695, 3.139))
    repository.create(report_document("Nearest", 101.687, 3.139))
    repository.create(report_document("Outside", 101.8, 3.139))

    matches = repository.nearby(
        longitude=101.6869,
        latitude=3.139,
        radius_meters=2_000,
    )

    assert [report["title"] for report in matches] == ["Nearest", "Farther"]


def test_category_and_status_filters_can_be_combined() -> None:
    repository = InMemoryReportRepository()
    pothole = repository.create(report_document("Pothole", 101.6869, 3.139))
    repository.create(report_document("Waste", 101.6869, 3.139, category="waste"))
    repository.update_status(pothole["id"], "resolved", datetime.now(UTC))

    matches = repository.list_reports(category="pothole", status="resolved")

    assert [report["title"] for report in matches] == ["Pothole"]


def test_mongo_repository_builds_geosphere_index_and_near_query() -> None:
    database = FakeDatabase()
    repository = MongoReportRepository(database)

    repository.ensure_indexes()
    repository.nearby(
        longitude=101.6869,
        latitude=3.139,
        radius_meters=5_000,
        category="pothole",
        status="reported",
    )

    assert database.collection.indexes[0][0] == [("location", "2dsphere")]
    assert database.collection.last_query == {
        "category": "pothole",
        "status": "reported",
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [101.6869, 3.139],
                },
                "$maxDistance": 5_000,
            }
        },
    }
