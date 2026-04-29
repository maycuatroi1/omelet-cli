from pathlib import Path
from typing import Union

import cv2
import numpy as np


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def strip_image_metadata(image_path: Union[str, Path]) -> bool:
    path = Path(image_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False

    cv2.imwrite(str(path), img)
    return True


def scrub_watermark(image_path: Union[str, Path], strength: float = 0.7) -> bool:
    path = Path(image_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False

    h, w = img.shape[:2]
    scale = max(0.4, min(0.9, strength))
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))

    small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)

    rng = np.random.default_rng()
    noise = rng.normal(0.0, 1.2, small.shape).astype(np.float32)
    small = np.clip(small.astype(np.float32) + noise, 0, 255).astype(img.dtype)

    upscaled = cv2.resize(small, (w, h), interpolation=cv2.INTER_LANCZOS4)

    blurred = cv2.GaussianBlur(upscaled, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(upscaled, 1.4, blurred, -0.4, 0)

    cv2.imwrite(str(path), sharpened)
    return True
