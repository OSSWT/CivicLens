from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReportCategory(StrEnum):
    POTHOLE = "pothole"
    FLOODING = "flooding"
    WASTE = "waste"
    STREETLIGHT = "streetlight"
    SIDEWALK = "sidewalk"
    OTHER = "other"


class ReportStatus(StrEnum):
    REPORTED = "reported"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class GeoJSONPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]

    @model_validator(mode="after")
    def validate_coordinates(self) -> GeoJSONPoint:
        longitude, latitude = self.coordinates
        if not -180 <= longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if not -90 <= latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return self


class ImageAnalysis(BaseModel):
    width: int
    height: int
    brightness: float
    blur_score: float
    accepted: bool
    warnings: list[str] = Field(default_factory=list)


class ChangeAnalysis(BaseModel):
    mean_difference_percent: float
    histogram_similarity: float


class PhotoRecord(BaseModel):
    url: str
    storage_name: str
    content_type: str
    analysis: ImageAnalysis
    uploaded_at: datetime


class ReportResponse(BaseModel):
    id: str
    title: str
    category: ReportCategory
    description: str
    location: GeoJSONPoint
    status: ReportStatus
    before_photo: PhotoRecord
    after_photo: PhotoRecord | None = None
    change_analysis: ChangeAnalysis | None = None
    created_at: datetime
    updated_at: datetime


class StatusUpdate(BaseModel):
    status: ReportStatus


class PublicConfig(BaseModel):
    google_maps_api_key: str
    maps_enabled: bool
    default_center: tuple[float, float] = (3.1390, 101.6869)
