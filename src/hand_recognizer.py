from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import HandAreaConfig, HandSlotConfig, RecognitionConfig, Rect
from .image_io import read_image
from .piece_recognizer import IMAGE_EXTENSIONS, PieceRecognizer


@dataclass
class SlotRecognition:
    side: str
    piece: str
    present: bool
    count: int
    piece_score: float
    empty_score: float
    digit_label: str | None = None
    digit_score: float | None = None
    error: str | None = None
    slot_image: object | None = None
    digit_image: object | None = None


class DigitRecognizer:
    def __init__(self, templates_dir: Path, match_size: tuple[int, int] = (28, 28)):
        self.templates_dir = templates_dir
        self.match_size = match_size
        self.templates = self._load_templates(templates_dir)

    @property
    def available(self) -> bool:
        return bool(self.templates)

    def recognize(self, image) -> tuple[int | None, float, str | None]:
        if not self.templates:
            return None, -1.0, None
        target = self._prepare(image)
        best_label = None
        best_score = -1.0
        best_value = None
        for label, value, template in self.templates:
            score = self._score(target, template)
            if score > best_score:
                best_label = label
                best_score = score
                best_value = value
        return best_value, best_score, best_label

    def _load_templates(self, root: Path):
        if not root.exists():
            return []
        loaded = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label = path.parent.name if path.parent != root else path.stem
            try:
                value = int(label)
            except ValueError:
                continue
            if value < 0 or value > 18:
                continue
            loaded.append((label, value, self._prepare(read_image(path))))
        return loaded

    def _prepare(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.match_size, interpolation=cv2.INTER_AREA)
        return cv2.equalizeHist(resized)

    @staticmethod
    def _score(target, template) -> float:
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        value = float(result.max())
        if np.isnan(value):
            return -1.0
        return value


class HandRecognizer:
    def __init__(self, config: RecognitionConfig, piece_recognizer: PieceRecognizer | None = None):
        self.config = config
        self.piece_recognizer = piece_recognizer or PieceRecognizer(config)
        self.digit_recognizer = DigitRecognizer(config.hand_digits_dir)

    def recognize(self, full_image, side: str, hand_image, hand_config: HandAreaConfig) -> tuple[dict[str, int], list[SlotRecognition]]:
        results: dict[str, int] = {}
        slot_results: list[SlotRecognition] = []
        for slot in hand_config.slots:
            slot_image = self._crop_slot(full_image, hand_image, hand_config, slot.rect)
            if self.config.slot_crop_margin:
                slot_image = self._crop_margin(slot_image, self.config.slot_crop_margin)
            piece_score = self.piece_recognizer.max_score_for(slot_image, side=side, kind=slot.piece)
            empty_score = self.piece_recognizer.max_score_for(slot_image, empty=True)

            slot_result = SlotRecognition(
                side=side,
                piece=slot.piece,
                present=False,
                count=0,
                piece_score=piece_score,
                empty_score=empty_score,
                slot_image=slot_image,
            )

            if piece_score >= self.config.hand_piece_threshold:
                count = 1
                if slot.digit_rect is not None:
                    digit_image = self._crop_slot(full_image, hand_image, hand_config, slot.digit_rect)
                    slot_result.digit_image = digit_image
                    count, digit_error, digit_score, digit_label = self._recognize_count(digit_image)
                    slot_result.digit_score = digit_score
                    slot_result.digit_label = digit_label
                    if digit_error:
                        slot_result.error = digit_error
                slot_result.present = True
                slot_result.count = count
                if not slot_result.error:
                    results[slot.piece] = count
            elif empty_score >= self.config.empty_threshold or piece_score < self.config.hand_presence_threshold:
                if slot.required:
                    slot_result.error = "required hand slot is empty"
            else:
                slot_result.error = (
                    f"uncertain hand slot, piece_score={piece_score:.3f}, empty_score={empty_score:.3f}"
                )
            slot_results.append(slot_result)

        return results, slot_results

    def _recognize_count(self, digit_image) -> tuple[int, str | None, float | None, str | None]:
        if self._looks_blank(digit_image):
            return 1, None, None, None
        if not self.digit_recognizer.available:
            return 1, "digit_rect is configured but no digit templates were found", None, None
        value, score, label = self.digit_recognizer.recognize(digit_image)
        if value is not None and score >= self.config.digit_threshold:
            return max(1, value), None, score, label
        return 1, f"digit recognition failed, best={label}, score={score:.3f}", score, label

    @staticmethod
    def _looks_blank(image) -> bool:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        red = ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 168)) & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 100)
        if float(red.mean()) < 0.02:
            return True
        return float(gray.std()) < 8.0

    @staticmethod
    def _crop_margin(image, margin: int):
        h, w = image.shape[:2]
        if margin <= 0 or margin * 2 >= h or margin * 2 >= w:
            return image
        return image[margin : h - margin, margin : w - margin]

    @staticmethod
    def _crop_slot(full_image, hand_image, hand_config: HandAreaConfig, rect: Rect):
        if hand_config.relative_to == "screen":
            return rect.crop(full_image)
        return rect.crop(hand_image)
