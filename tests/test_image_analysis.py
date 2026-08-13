from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.image_analysis import ImageAnalyzer, InvalidImageError


def test_clear_image_passes_quality_checks(image_bytes: bytes) -> None:
    result = ImageAnalyzer().analyze(image_bytes)

    assert result.accepted is True
    assert result.width == 800
    assert result.height == 600
    assert result.blur_score > 80
    assert 45 < result.brightness < 220


def test_dark_small_image_returns_explainable_warnings() -> None:
    image = np.full((120, 160, 3), 10, dtype=np.uint8)
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded

    result = ImageAnalyzer().analyze(buffer.tobytes())

    assert result.accepted is False
    assert "Image resolution is below 640 x 480." in result.warnings
    assert "Image is too dark." in result.warnings
    assert "Image may be too blurry for reliable evidence." in result.warnings


def test_compare_reports_visible_change(image_bytes: bytes, after_image_bytes: bytes) -> None:
    result = ImageAnalyzer().compare(image_bytes, after_image_bytes)

    assert result.mean_difference_percent > 10
    assert -1 <= result.histogram_similarity <= 1


def test_non_image_content_is_rejected() -> None:
    with pytest.raises(InvalidImageError, match="not a valid image"):
        ImageAnalyzer().analyze(b"not-an-image")
