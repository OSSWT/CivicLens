from __future__ import annotations

import cv2
import numpy as np

from app.models import ChangeAnalysis, ImageAnalysis


class InvalidImageError(ValueError):
    """Raised when uploaded bytes cannot be decoded as an image."""


class ImageAnalyzer:
    def analyze(self, content: bytes) -> ImageAnalysis:
        image = self._decode(content)
        height, width = image.shape[:2]
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(grayscale))
        blur_score = float(cv2.Laplacian(grayscale, cv2.CV_64F).var())

        warnings: list[str] = []
        if width < 640 or height < 480:
            warnings.append("Image resolution is below 640 x 480.")
        if blur_score < 80:
            warnings.append("Image may be too blurry for reliable evidence.")
        if brightness < 45:
            warnings.append("Image is too dark.")
        elif brightness > 220:
            warnings.append("Image is overexposed.")

        return ImageAnalysis(
            width=width,
            height=height,
            brightness=round(brightness, 2),
            blur_score=round(blur_score, 2),
            accepted=not warnings,
            warnings=warnings,
        )

    def compare(self, before_content: bytes, after_content: bytes) -> ChangeAnalysis:
        before = self._decode(before_content)
        after = self._decode(after_content)
        target_size = (320, 240)
        before = cv2.resize(before, target_size, interpolation=cv2.INTER_AREA)
        after = cv2.resize(after, target_size, interpolation=cv2.INTER_AREA)

        difference = cv2.absdiff(before, after)
        mean_difference = float(np.mean(difference) / 255 * 100)
        before_hist = cv2.calcHist([before], [0, 1], None, [32, 32], [0, 256, 0, 256])
        after_hist = cv2.calcHist([after], [0, 1], None, [32, 32], [0, 256, 0, 256])
        cv2.normalize(before_hist, before_hist)
        cv2.normalize(after_hist, after_hist)
        similarity = float(cv2.compareHist(before_hist, after_hist, cv2.HISTCMP_CORREL))

        return ChangeAnalysis(
            mean_difference_percent=round(mean_difference, 2),
            histogram_similarity=round(max(-1.0, min(1.0, similarity)), 4),
        )

    @staticmethod
    def _decode(content: bytes) -> np.ndarray:
        encoded = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise InvalidImageError("The uploaded file is not a valid image.")
        return image
