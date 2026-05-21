from __future__ import annotations

from dataclasses import dataclass

from .config import HandAreaConfig, Rect


@dataclass(frozen=True)
class HandCrop:
    side: str
    image: object
    rect: Rect
    config: HandAreaConfig


class HandDetector:
    def __init__(self, black_config: HandAreaConfig, white_config: HandAreaConfig):
        self.configs = {"b": black_config, "w": white_config}

    def crop(self, image, side: str) -> HandCrop:
        config = self.configs[side]
        rect = config.rect
        return HandCrop(side=side, image=rect.crop(image), rect=rect, config=config)

