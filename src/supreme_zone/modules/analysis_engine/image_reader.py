from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .models import ChartImageSnapshot


@dataclass(slots=True)
class ChartImageInspector:
    def inspect(self, path: Path) -> ChartImageSnapshot | None:
        if not path.exists():
            return None
        try:
            from PIL import Image
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Pillow is required for chart image inspection") from exc

        with path.open("rb") as handle:
            raw = handle.read()
        digest = sha256(raw).hexdigest()

        with Image.open(path) as image:
            width, height = image.size
            gray = image.convert("L")
            pixels = list(gray.getdata())

        if pixels:
            mean = sum(pixels) / len(pixels)
            variance = sum((pixel - mean) ** 2 for pixel in pixels) / len(pixels)
            contrast = variance ** 0.5
        else:
            mean = 0.0
            contrast = 0.0

        aspect_ratio = float(width) / float(height) if height else 0.0
        return ChartImageSnapshot(
            path=path,
            width=width,
            height=height,
            file_size=len(raw),
            aspect_ratio=aspect_ratio,
            brightness=float(mean),
            contrast=float(contrast),
            digest=digest,
        )
