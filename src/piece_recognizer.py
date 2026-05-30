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
        self._template_matrix = self._build_template_matrix()

    def recognize(self, image, threshold: float | None = None, include_scores: bool = False) -> RecognitionResult:
        if not self.templates:
            raise RecognitionError(
                f"no piece templates found in {self.config.pieces_dir}. "
                "Create templates such as b_P.png, w_P.png, b_+P.png, empty.png."
            )
        scores = self.score_all(image)
        label, score = max(scores.items(), key=lambda item: item[1])
        label, score = self._apply_red_ink_check(image, scores, label, score)
        parsed = self._template_by_label(label).parsed
        score_map = scores if include_scores else None

        if parsed.is_empty:
            empty_threshold = self.config.empty_threshold if threshold is None else threshold
            if score < empty_threshold:
                if self._looks_empty_cell(image):
                    return RecognitionResult(label=label, piece=None, score=score, is_empty=True, scores=score_map)
                return RecognitionResult(label=label, piece=None, score=score, scores=score_map)
            return RecognitionResult(label=label, piece=None, score=score, is_empty=True, scores=score_map)
        threshold_value = self.config.piece_threshold if threshold is None else threshold
        if score < threshold_value:
            if self._looks_empty_cell(image):
                return RecognitionResult(label="empty", piece=None, score=score, is_empty=True, scores=score_map)
            return RecognitionResult(label=label, piece=None, score=score, scores=score_map)
        if parsed.side and parsed.kind:
            return RecognitionResult(label=label, piece=Piece(parsed.side, parsed.kind), score=score, scores=score_map)
        return RecognitionResult(label=label, piece=None, score=score, scores=score_map)

    def score_all(self, image) -> dict[str, float]:
        template_scores = self._score_all_templates(image)
        scores: dict[str, float] = {}
        for template, score_value in zip(self.templates, template_scores):
            score = float(score_value)
            if np.isnan(score):
                score = -1.0
            if template.label not in scores or score > scores[template.label]:
                scores[template.label] = score
        return scores

    def max_score_for(self, image, side: str | None = None, kind: str | None = None, empty: bool = False) -> float:
        template_scores = self._score_all_templates(image)
        best = -1.0
        for template, score_value in zip(self.templates, template_scores):
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
            score = float(score_value)
            if not np.isnan(score):
                best = max(best, score)
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

    def _apply_red_ink_check(
        self,
        image,
        scores: dict[str, float],
        label: str,
        score: float,
    ) -> tuple[str, float]:
        if not self.config.promoted_red_check_enabled or self.config.mode != "color":
            return label, score

        parsed = self._template_by_label(label).parsed
        if parsed.is_empty or not parsed.side or not parsed.kind:
            return label, score

        red_ratio = self._red_ink_ratio(image)
        if parsed.kind.startswith("+"):
            if red_ratio >= self.config.promoted_red_min_ratio:
                return label, score
            replacement = self._best_unpromoted_replacement(scores, parsed)
        else:
            if red_ratio < self.config.promoted_red_min_ratio:
                return label, score
            replacement = self._best_promoted_replacement(scores, parsed)
        if replacement is not None:
            replacement_label, replacement_score = replacement
            if score - replacement_score <= self.config.promoted_red_score_margin:
                return replacement_label, max(score, replacement_score)
        return label, score

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

    def _build_template_matrix(self):
        if not self.templates:
            return np.empty((0, 0), dtype=np.float32)
        vectors = [self._normalize_for_match(template.image) for template in self.templates]
        return np.vstack(vectors)

    def _score_all_templates(self, image):
        if self._template_matrix.size == 0:
            return np.empty((0,), dtype=np.float32)
        target = self._normalize_for_match(self._prepare(image))
        return self._template_matrix @ target

    @staticmethod
    def _normalize_for_match(image):
        values = image.astype(np.float32)
        if values.ndim == 3:
            values = values - values.mean(axis=(0, 1), keepdims=True)
        else:
            values = values - values.mean()
        vector = values.reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0 or np.isnan(norm):
            return np.zeros_like(vector, dtype=np.float32)
        return (vector / norm).astype(np.float32)

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

    @staticmethod
    def _red_ink_ratio(image) -> float:
        resized = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        red = (
            ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 168))
            & (hsv[:, :, 1] > 45)
            & (hsv[:, :, 2] > 40)
        )
        dark = (gray < 105) & ~red
        ink = red | dark
        return float(red.sum() / max(1, int(ink.sum())))

    def _best_unpromoted_replacement(
        self,
        scores: dict[str, float],
        parsed: ParsedLabel,
    ) -> tuple[str, float] | None:
        kinds = [parsed.kind.lstrip("+")]
        if parsed.kind in {"+P", "+L", "+N", "+S"}:
            kinds.append("G")

        best: tuple[str, float] | None = None
        for kind in kinds:
            for candidate_label in self.labels_for(side=parsed.side, kind=kind):
                candidate_score = scores.get(candidate_label)
                if candidate_score is None:
                    continue
                if best is None or candidate_score > best[1]:
                    best = (candidate_label, candidate_score)
        return best

    def _best_promoted_replacement(
        self,
        scores: dict[str, float],
        parsed: ParsedLabel,
    ) -> tuple[str, float] | None:
        if parsed.kind in {"P", "L", "N", "S", "B", "R"}:
            kinds = [f"+{parsed.kind}"]
        elif parsed.kind == "G":
            kinds = ["+P", "+L", "+N", "+S"]
        else:
            return None

        best: tuple[str, float] | None = None
        for kind in kinds:
            for candidate_label in self.labels_for(side=parsed.side, kind=kind):
                candidate_score = scores.get(candidate_label)
                if candidate_score is None:
                    continue
                if best is None or candidate_score > best[1]:
                    best = (candidate_label, candidate_score)
        return best

    @staticmethod
    def _looks_empty_cell(image) -> bool:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        dark_ratio = float((gray < 80).mean())
        red_ratio = float(
            (
                ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 168))
                & (hsv[:, :, 1] > 70)
                & (hsv[:, :, 2] > 100)
            ).mean()
        )
        return dark_ratio < 0.075 and red_ratio < 0.02


def recognition_piece_to_debug(piece: Piece | None) -> str:
    if piece is None:
        return "empty"
    return f"{piece.side}_{piece.kind}"


def pieces_from_results(results: Iterable[RecognitionResult]) -> list[Piece | None]:
    return [result.piece for result in results]
