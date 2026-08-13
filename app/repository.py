from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Protocol
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, MongoClient, ReturnDocument
from pymongo.database import Database

Document = dict[str, Any]


class ReportRepository(Protocol):
    def ensure_indexes(self) -> None: ...

    def healthcheck(self) -> None: ...

    def create(self, document: Document) -> Document: ...

    def list_reports(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]: ...

    def nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_meters: int,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]: ...

    def get(self, report_id: str) -> Document | None: ...

    def update_status(self, report_id: str, status: str, updated_at: Any) -> Document | None: ...

    def set_after_photo(
        self,
        report_id: str,
        photo: Document,
        change_analysis: Document,
        updated_at: Any,
    ) -> Document | None: ...

    def delete(self, report_id: str) -> Document | None: ...


class MongoReportRepository:
    def __init__(self, database: Database[Document]) -> None:
        self.collection = database.get_collection("reports")

    @classmethod
    def connect(
        cls,
        uri: str,
        database_name: str,
    ) -> tuple[MongoClient[Document], MongoReportRepository]:
        client: MongoClient[Document] = MongoClient(
            uri,
            serverSelectionTimeoutMS=5_000,
            tz_aware=True,
        )
        return client, cls(client.get_database(database_name))

    def ensure_indexes(self) -> None:
        self.collection.create_index([("location", GEOSPHERE)], name="reports_location_2dsphere")
        self.collection.create_index(
            [("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)],
            name="reports_filter_sort",
        )

    def healthcheck(self) -> None:
        self.collection.database.command("ping")

    def create(self, document: Document) -> Document:
        stored = deepcopy(document)
        result = self.collection.insert_one(stored)
        stored["_id"] = result.inserted_id
        return self._serialize(stored)

    def list_reports(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        query = self._filters(category=category, status=status)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).limit(limit)
        return [self._serialize(document) for document in cursor]

    def nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_meters: int,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        query = self._filters(category=category, status=status)
        query["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                "$maxDistance": radius_meters,
            }
        }
        return [self._serialize(document) for document in self.collection.find(query).limit(limit)]

    def get(self, report_id: str) -> Document | None:
        object_id = self._object_id(report_id)
        if object_id is None:
            return None
        document = self.collection.find_one({"_id": object_id})
        return self._serialize(document) if document else None

    def update_status(self, report_id: str, status: str, updated_at: Any) -> Document | None:
        object_id = self._object_id(report_id)
        if object_id is None:
            return None
        document = self.collection.find_one_and_update(
            {"_id": object_id},
            {"$set": {"status": status, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(document) if document else None

    def set_after_photo(
        self,
        report_id: str,
        photo: Document,
        change_analysis: Document,
        updated_at: Any,
    ) -> Document | None:
        object_id = self._object_id(report_id)
        if object_id is None:
            return None
        document = self.collection.find_one_and_update(
            {"_id": object_id},
            {
                "$set": {
                    "after_photo": photo,
                    "change_analysis": change_analysis,
                    "status": "resolved",
                    "updated_at": updated_at,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(document) if document else None

    def delete(self, report_id: str) -> Document | None:
        object_id = self._object_id(report_id)
        if object_id is None:
            return None
        document = self.collection.find_one_and_delete({"_id": object_id})
        return self._serialize(document) if document else None

    @staticmethod
    def _filters(*, category: str | None, status: str | None) -> Document:
        query: Document = {}
        if category:
            query["category"] = category
        if status:
            query["status"] = status
        return query

    @staticmethod
    def _object_id(value: str) -> ObjectId | None:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            return None

    @staticmethod
    def _serialize(document: Document) -> Document:
        serialized = deepcopy(document)
        serialized["id"] = str(serialized.pop("_id"))
        return serialized


class InMemoryReportRepository:
    """Deterministic repository for tests and optional zero-setup demos."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def ensure_indexes(self) -> None:
        return None

    def healthcheck(self) -> None:
        return None

    def create(self, document: Document) -> Document:
        report_id = uuid4().hex
        stored = deepcopy(document)
        stored["id"] = report_id
        self._documents[report_id] = stored
        return deepcopy(stored)

    def list_reports(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        matches = self._matching(category=category, status=status)
        matches.sort(key=lambda item: item["created_at"], reverse=True)
        return deepcopy(matches[:limit])

    def nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_meters: int,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        matches: list[tuple[float, Document]] = []
        for document in self._matching(category=category, status=status):
            item_longitude, item_latitude = document["location"]["coordinates"]
            distance = self._haversine(
                longitude,
                latitude,
                item_longitude,
                item_latitude,
            )
            if distance <= radius_meters:
                matches.append((distance, document))
        matches.sort(key=lambda pair: pair[0])
        return deepcopy([document for _, document in matches[:limit]])

    def get(self, report_id: str) -> Document | None:
        document = self._documents.get(report_id)
        return deepcopy(document) if document else None

    def update_status(self, report_id: str, status: str, updated_at: Any) -> Document | None:
        document = self._documents.get(report_id)
        if document is None:
            return None
        document["status"] = status
        document["updated_at"] = updated_at
        return deepcopy(document)

    def set_after_photo(
        self,
        report_id: str,
        photo: Document,
        change_analysis: Document,
        updated_at: Any,
    ) -> Document | None:
        document = self._documents.get(report_id)
        if document is None:
            return None
        document["after_photo"] = deepcopy(photo)
        document["change_analysis"] = deepcopy(change_analysis)
        document["status"] = "resolved"
        document["updated_at"] = updated_at
        return deepcopy(document)

    def delete(self, report_id: str) -> Document | None:
        document = self._documents.pop(report_id, None)
        return deepcopy(document) if document else None

    def _matching(self, *, category: str | None, status: str | None) -> list[Document]:
        return [
            document
            for document in self._documents.values()
            if (category is None or document["category"] == category)
            and (status is None or document["status"] == status)
        ]

    @staticmethod
    def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        earth_radius_meters = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        value = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return earth_radius_meters * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
