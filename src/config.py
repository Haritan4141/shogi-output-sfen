from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by environment
    raise ConfigError("PyYAML is required. Install it with: pip install pyyaml") from exc


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_value(cls, value: Any, field_name: str) -> "Rect":
        if isinstance(value, dict):
            try:
                return cls(
                    int(value["x"]),
                    int(value["y"]),
                    int(value["width"]),
                    int(value["height"]),
                )
            except KeyError as exc:
                raise ConfigError(f"{field_name} must contain x, y, width, height") from exc
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return cls(*(int(v) for v in value))
        raise ConfigError(f"{field_name} must be [x, y, width, height] or a mapping")

    def crop(self, image):
        return image[self.y : self.y + self.height, self.x : self.x + self.width]


@dataclass(frozen=True)
class BoardConfig:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BoardConfig":
        if not isinstance(data, dict):
            raise ConfigError("board must be a mapping")

        top_left = data.get("top_left")
        if not (isinstance(top_left, (list, tuple)) and len(top_left) == 2):
            raise ConfigError("board.top_left must be [x, y]")

        if "size" in data:
            size = data["size"]
            if isinstance(size, (list, tuple)) and len(size) == 2:
                width, height = int(size[0]), int(size[1])
            else:
                width = height = int(size)
        else:
            width = int(data.get("width", 0))
            height = int(data.get("height", 0))

        if width <= 0 or height <= 0:
            raise ConfigError("board.size or board.width/height must be positive")
        return cls(int(top_left[0]), int(top_left[1]), width, height)

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class HandSlotConfig:
    piece: str
    rect: Rect
    digit_rect: Rect | None = None
    required: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> "HandSlotConfig":
        if not isinstance(data, dict):
            raise ConfigError(f"hands slot #{index} must be a mapping")
        piece = str(data.get("piece", "")).upper()
        if piece not in {"R", "B", "G", "S", "N", "L", "P"}:
            raise ConfigError(f"hands slot #{index} has invalid piece: {piece}")
        rect = Rect.from_value(data.get("rect"), f"hands slot {piece}.rect")
        digit_value = data.get("digit_rect")
        digit_rect = Rect.from_value(digit_value, f"hands slot {piece}.digit_rect") if digit_value is not None else None
        return cls(piece=piece, rect=rect, digit_rect=digit_rect, required=bool(data.get("required", False)))


@dataclass(frozen=True)
class HandAreaConfig:
    rect: Rect
    relative_to: str
    slots: list[HandSlotConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], side_name: str) -> "HandAreaConfig":
        if not isinstance(data, dict):
            raise ConfigError(f"hands.{side_name} must be a mapping")
        rect = Rect.from_value(data.get("rect"), f"hands.{side_name}.rect")
        relative_to = str(data.get("relative_to", "hand"))
        if relative_to not in {"hand", "screen"}:
            raise ConfigError(f"hands.{side_name}.relative_to must be 'hand' or 'screen'")
        slots = [HandSlotConfig.from_dict(slot, i) for i, slot in enumerate(data.get("slots", []), 1)]
        return cls(rect=rect, relative_to=relative_to, slots=slots)


@dataclass(frozen=True)
class RecognitionConfig:
    pieces_dir: Path = Path("templates/pieces")
    hand_digits_dir: Path = Path("templates/hand_digits")
    piece_threshold: float = 0.72
    hand_piece_threshold: float = 0.70
    hand_presence_threshold: float = 0.45
    digit_threshold: float = 0.70
    empty_threshold: float = 0.70
    match_size: tuple[int, int] = (64, 64)
    cell_crop_margin: int = 2
    slot_crop_margin: int = 0
    mode: str = "color"
    promoted_red_check_enabled: bool = False
    promoted_red_min_ratio: float = 0.25
    promoted_red_score_margin: float = 0.12

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RecognitionConfig":
        data = data or {}
        match_size = data.get("match_size", [64, 64])
        if not (isinstance(match_size, (list, tuple)) and len(match_size) == 2):
            raise ConfigError("recognition.match_size must be [width, height]")
        mode = str(data.get("mode", "color"))
        if mode not in {"color", "grayscale"}:
            raise ConfigError("recognition.mode must be 'color' or 'grayscale'")
        return cls(
            pieces_dir=Path(data.get("pieces_dir", "templates/pieces")),
            hand_digits_dir=Path(data.get("hand_digits_dir", "templates/hand_digits")),
            piece_threshold=float(data.get("piece_threshold", 0.72)),
            hand_piece_threshold=float(data.get("hand_piece_threshold", 0.70)),
            hand_presence_threshold=float(data.get("hand_presence_threshold", 0.45)),
            digit_threshold=float(data.get("digit_threshold", 0.70)),
            empty_threshold=float(data.get("empty_threshold", 0.70)),
            match_size=(int(match_size[0]), int(match_size[1])),
            cell_crop_margin=int(data.get("cell_crop_margin", 2)),
            slot_crop_margin=int(data.get("slot_crop_margin", 0)),
            mode=mode,
            promoted_red_check_enabled=bool(data.get("promoted_red_check_enabled", False)),
            promoted_red_min_ratio=float(data.get("promoted_red_min_ratio", 0.25)),
            promoted_red_score_margin=float(data.get("promoted_red_score_margin", 0.12)),
        )


@dataclass(frozen=True)
class AppConfig:
    board: BoardConfig
    black_hand: HandAreaConfig
    white_hand: HandAreaConfig
    recognition: RecognitionConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError("config root must be a mapping")

    hands = data.get("hands", {})
    if not isinstance(hands, dict):
        raise ConfigError("hands must be a mapping")
    return AppConfig(
        board=BoardConfig.from_dict(data.get("board")),
        black_hand=HandAreaConfig.from_dict(hands.get("black", {}), "black"),
        white_hand=HandAreaConfig.from_dict(hands.get("white", {}), "white"),
        recognition=RecognitionConfig.from_dict(data.get("recognition")),
    )

