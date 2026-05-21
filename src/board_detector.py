from __future__ import annotations

from dataclasses import dataclass

from .config import BoardConfig, Rect


@dataclass(frozen=True)
class BoardCrop:
    image: object
    rect: Rect


class BoardDetector:
    """Config-driven board cropper.

    The name leaves room for future automatic detection without changing callers.
    """

    def __init__(self, config: BoardConfig):
        self.config = config

    def crop(self, image) -> BoardCrop:
        rect = self.config.rect
        return BoardCrop(image=rect.crop(image), rect=rect)

