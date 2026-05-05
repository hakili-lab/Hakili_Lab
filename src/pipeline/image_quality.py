from pathlib import Path
from typing import Dict
from PIL import Image, ImageStat


def assess_image_quality(path: Path) -> Dict[str, object]:
    """Simple MVP quality check. Extend with OpenCV blur/crop detection."""
    image = Image.open(path).convert("L")
    stat = ImageStat.Stat(image)
    brightness = stat.mean[0]
    width, height = image.size
    issues = []
    if width < 1000 or height < 1000:
        issues.append("low_resolution")
    if brightness < 60:
        issues.append("too_dark")
    if brightness > 235:
        issues.append("too_bright")
    return {"width": width, "height": height, "brightness": brightness, "issues": issues, "quality": "poor" if issues else "good"}
