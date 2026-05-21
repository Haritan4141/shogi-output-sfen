from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .errors import ImageLoadError


def read_image(path: str | Path):
    """Read an image using a Windows-unicode-safe OpenCV path flow."""
    image_path = Path(path)
    if not image_path.exists():
        raise ImageLoadError(f"image not found: {image_path}")

    data = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageLoadError(f"failed to decode image: {image_path}")
    return image


def write_image(path: str | Path, image) -> None:
    """Write an image using a Windows-unicode-safe OpenCV path flow."""
    image_path = Path(path)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    ext = image_path.suffix or ".png"
    ok, encoded = cv2.imencode(ext, image)
    if not ok:
        raise ImageLoadError(f"failed to encode image: {image_path}")
    encoded.tofile(str(image_path))

