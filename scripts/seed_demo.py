from __future__ import annotations

from datetime import UTC, datetime

import cv2
import numpy as np

from app.config import get_settings
from app.image_analysis import ImageAnalyzer
from app.models import PhotoRecord
from app.repository import MongoReportRepository
from app.storage import LocalPhotoStorage

DEMO_REPORTS = (
    ("Pothole beside bus stop", "pothole", 3.1390, 101.6869, (58, 72, 82)),
    ("Blocked drain after rain", "flooding", 3.1451, 101.6953, (95, 92, 54)),
    ("Overflowing recycling point", "waste", 3.1324, 101.6812, (54, 96, 62)),
)


def make_demo_photo(title: str, color: tuple[int, int, int]) -> bytes:
    image = np.full((600, 800, 3), color, dtype=np.uint8)
    for x in range(0, 800, 40):
        cv2.line(image, (x, 0), (x, 600), (110, 120, 115), 1)
    for y in range(0, 600, 40):
        cv2.line(image, (0, y), (800, y), (110, 120, 115), 1)
    cv2.ellipse(image, (410, 345), (170, 95), -8, 0, 360, (28, 34, 31), -1)
    cv2.putText(
        image,
        title,
        (42, 64),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (245, 248, 245),
        2,
        cv2.LINE_AA,
    )
    encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not encoded:
        raise RuntimeError("Could not encode demo image.")
    return buffer.tobytes()


def main() -> None:
    settings = get_settings()
    client, repository = MongoReportRepository.connect(
        settings.mongo_uri,
        settings.mongo_database,
    )
    storage = LocalPhotoStorage(settings.upload_dir)
    analyzer = ImageAnalyzer()
    try:
        repository.ensure_indexes()
        for title, category, latitude, longitude, color in DEMO_REPORTS:
            content = make_demo_photo(title, color)
            analysis = analyzer.analyze(content)
            storage_name, url = storage.save(content, "image/jpeg")
            now = datetime.now(UTC)
            photo = PhotoRecord(
                url=url,
                storage_name=storage_name,
                content_type="image/jpeg",
                analysis=analysis,
                uploaded_at=now,
            ).model_dump(mode="python")
            report = repository.create(
                {
                    "title": title,
                    "category": category,
                    "description": "Synthetic portfolio demo report generated locally.",
                    "location": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
                    "status": "reported",
                    "before_photo": photo,
                    "after_photo": None,
                    "change_analysis": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            print(f"Created {report['id']}: {title}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
