from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from .config import RecognitionConfig
from .errors import RecognitionError
from .image_io import read_image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
BLACK_ALIASES = {"b", "black", "sente", "先手"}
WHITE_ALIASES = {"w", "white", "gote", "後手"}
EMPTY_LABELS = {"empty", "blank", "none", "vacant", "-", "."}
PIECE_KINDS = {"K", "R", "B", "G", "S", "N", "L", "P", "+R", "+B", "+S", "+N", "+L", "+P"}


@dataclass(frozen=True)
class Piece:
    side: str
    kind: str

    def __post_init__(self):
        if self.side not in {"b", "w"}:
            raise ValueError(f"invalid side: {self.side}")
        if self.kind not in PIECE_KINDS:
            raise ValueError(f"invalid piece kind: {self.kind}")


@dataclass(frozen=True)
class ParsedLabel:
    label: str
    side: str | None
    kind: str | None
    is_empty: bool = False


@dataclass(frozen=True)
class Template:
    label: str
    parsed: ParsedLabel
    path: Path
    image: object


@dataclass
class RecognitionResult:
    label: str | None
    piece: Piece | None
    score: float
    is_empty: bool = False
    scores: dict[str, float] | None = None

    @property
    def ok(self) -> bool:
        return self.is_empty or self.piece is not None


def parse_piece_label(label: str) -> ParsedLabel:
    raw = label.strip()
    normalized = raw.replace("-", "_")
    lower = normalized.lower()
    if lower in EMPTY_LABELS:
        return ParsedLabel(label=raw, side=None, kind=None, is_empty=True)

    parts = [part for part in normalized.split("_") if part]
    if len(parts) < 2:
        return ParsedLabel(label=raw, side=None, kind=None, is_empty=False)

    side_token = parts[0].lower()
    if side_token in BLACK_ALIASES:
        side = "b"
    elif side_token in WHITE_ALIASES:
        side = "w"
    else:
        return ParsedLabel(label=raw, side=None, kind=None, is_empty=False)

    kind_token = "_".join(parts[1:]).upper()
    aliases = {
        "PR": "+R",
        "PB": "+B",
        "PS": "+S",
        "PN": "+N",
        "PL": "+L",
        "PP": "+P",
        "PROM_R": "+R",
        "PROM_B": "+B",
        "PROM_S": "+S",
        "PROM_N": "+N",
        "PROM_L": "+L",
        "PROM_P": "+P",
    }
    kind = aliases.get(kind_token, kind_token)
    if kind not in PIECE_KINDS:
        return ParsedLabel(label=raw, side=side, kind=None, is_empty=False)
    return ParsedLabel(label=raw, side=side, kind=kind, is_empty=False)


class PieceRecognizer:
    def __init__(self, config: RecognitionConfig):
        self.config = config
        self.templates = self._load_templates(config.pieces_dir)

    def recognize(self, image, threshold: float | None = None, include_scores: bool = False) -> RecognitionResult:
        if not self.templates:
            raise RecognitionError(
                f"no piece templates found in {self.config.pieces_dir}. "
                "Create templates such as b_P.png, w_P.png, b_+P.png, empty.png."
            )
        scores = self.score_all(image)
        label, score = max(scores.items(), key=lambda item: item[1])
        parsed = self._template_by_label(label).parsed
        score_map = scores if include_scores else None

        if parsed.is_empty:
            empty_threshold = self.config.empty_threshold if threshold is None else threshold
            if score < empty_threshold:
                return RecognitionResult(label=label, piece=None, score=score, scores=score_map)
            return RecognitionResult(label=label, piece=None, score=score, is_empty=True, scores=score_map)
        threshold_value = self.config.piece_threshold if threshold is None else threshold
        if score < threshold_value:
            return RecognitionResult(label=label, piece=None, score=score, scores=score_map)
        if parsed.side and parsed.kind:
            return RecognitionResult(label=label, piece=Piece(parsed.side, parsed.kind), score=score, scores=score_map)
        return RecognitionResult(label=label, piece=None, score=score, scores=score_map)

    def score_all(self, image) -> dict[str, float]:
        target = self._prepare(image)
        scores: dict[str, float] = {}
        for template in self.templates:
            score = self._score(target, template.image)
            if template.label not in scores or score > scores[template.label]:
                scores[template.label] = score
        return scores

    def max_score_for(self, image, side: str | None = None, kind: str | None = None, empty: bool = False) -> float:
        target = self._prepare(image)
        best = -1.0
        for template in self.templates:
            parsed = template.parsed
            if empty:
                if not parsed.is_empty:
                    continue
            else:
                if parsed.is_empty:
                    continue
                if side is not None and parsed.side != side:
                    continue
                if kind is not None and parsed.kind != kind:
                    continue
            best = max(best, self._score(target, template.image))
        return best

    def labels_for(self, side: str | None = None, kind: str | None = None) -> list[str]:
        labels = []
        for template in self.templates:
            parsed = template.parsed
            if parsed.is_empty:
                continue
            if side is not None and parsed.side != side:
                continue
            if kind is not None and parsed.kind != kind:
                continue
            labels.append(template.label)
        return sorted(set(labels))

    def _load_templates(self, root: Path) -> list[Template]:
        if not root.exists():
            return []
        templates: list[Template] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label = path.parent.name if path.parent != root else path.stem
            parsed = parse_piece_label(label)
            if not (parsed.is_empty or (parsed.side and parsed.kind)):
                continue
            image = self._prepare(read_image(path))
            templates.append(Template(label=label, parsed=parsed, path=path, image=image))
        return templates

    def _template_by_label(self, label: str) -> Template:
        for template in self.templates:
            if template.label == label:
                return template
        raise RecognitionError(f"internal error: unknown template label {label}")

    def _prepare(self, image):
        cropped = self._crop_margin(image, self.config.cell_crop_margin)
        resized = cv2.resize(cropped, self.config.match_size, interpolation=cv2.INTER_AREA)
        if self.config.mode == "grayscale":
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            return cv2.equalizeHist(gray)
        return resized

    @staticmethod
    def _crop_margin(image, margin: int):
        if margin <= 0:
            return image
        h, w = image.shape[:2]
        if margin * 2 >= h or margin * 2 >= w:
            return image
        return image[margin : h - margin, margin : w - margin]

    @staticmethod
    def _score(target, template) -> float:
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        value = float(result.max())
        if np.isnan(value):
            return -1.0
        return value


def recognition_piece_to_debug(piece: Piece | None) -> str:
    if piece is None:
        return "empty"
    return f"{piece.side}_{piece.kind}"


def pieces_from_results(results: Iterable[RecognitionResult]) -> list[Piece | None]:
    return [result.piece for result in results]
