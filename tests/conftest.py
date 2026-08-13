from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repository import InMemoryReportRepository


def make_test_image(*, inverted: bool = False, width: int = 800, height: int = 600) -> bytes:
    grid_x, grid_y = np.meshgrid(np.arange(width), np.arange(height))
    pattern = ((grid_x // 24 + grid_y // 24) % 2 * 150 + 50).astype(np.uint8)
    if inverted:
        pattern = 255 - pattern
    image = cv2.merge((pattern, np.roll(pattern, 12, axis=1), np.roll(pattern, 12, axis=0)))
    encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert encoded
    return buffer.tobytes()


@pytest.fixture
def image_bytes() -> bytes:
    return make_test_image()


@pytest.fixture
def after_image_bytes() -> bytes:
    return make_test_image(inverted=True)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        google_maps_api_key="",
        admin_api_key="test-admin-key",
        use_in_memory=True,
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=2 * 1024 * 1024,
    )
    application = create_app(settings=settings, repository=InMemoryReportRepository())
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def create_report(client: TestClient, image_bytes: bytes):
    def factory(
        *,
        title: str = "Pothole near station",
        category: str = "pothole",
        latitude: float = 3.139,
        longitude: float = 101.6869,
    ) -> dict:
        response = client.post(
            "/api/reports",
            data={
                "title": title,
                "category": category,
                "description": "Deep enough to be hazardous after rain.",
                "latitude": str(latitude),
                "longitude": str(longitude),
            },
            files={"photo": ("evidence.jpg", image_bytes, "image/jpeg")},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return factory
