from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageStat

from src.core.config import settings
from src.models.domain import PageQualityReport, QualityReport


def assess_page_quality(path: Path, page_number: int) -> PageQualityReport:
    """Contrôle qualité d'une page : résolution, luminosité, flou (variance Laplacien)."""
    pil_img = Image.open(path).convert("L")
    width, height = pil_img.size
    brightness = ImageStat.Stat(pil_img).mean[0]

    cv_img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    blur_variance = float(cv2.Laplacian(cv_img, cv2.CV_64F).var()) if cv_img is not None else 0.0

    issues: list[str] = []
    if width < settings.image_min_resolution or height < settings.image_min_resolution:
        issues.append("low_resolution")
    if brightness < 60:
        issues.append("too_dark")
    if brightness > 235:
        issues.append("too_bright")
    if blur_variance < settings.image_blur_threshold:
        issues.append("blurry")

    return PageQualityReport(
        page_number=page_number,
        width=width,
        height=height,
        brightness=round(brightness, 2),
        blur_variance=round(blur_variance, 2),
        issues=issues,
        quality="poor" if issues else "good",
    )


def assess_copy_quality(copy_id: str, image_paths: list[Path]) -> QualityReport:
    """Agrège les rapports de qualité de toutes les pages d'une copie."""
    pages = [assess_page_quality(p, i + 1) for i, p in enumerate(image_paths)]
    any_poor = any(p.quality == "poor" for p in pages)

    return QualityReport(
        copy_id=copy_id,
        global_quality="poor" if any_poor else "good",
        pages=pages,
        rescan_requested=any_poor,
    )
