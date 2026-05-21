from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .board_detector import BoardDetector
from .cell_extractor import CellExtractor
from .config import load_config
from .errors import ShogiSfenReaderError, RecognitionError
from .hand_detector import HandDetector
from .hand_recognizer import HandRecognizer, SlotRecognition
from .image_io import read_image, write_image
from .piece_recognizer import PieceRecognizer, recognition_piece_to_debug
from .sfen import to_sfen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read a shogi screenshot and print SFEN.")
    parser.add_argument("input", help="PNG/JPEG screenshot path")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--turn", choices=["b", "w"], required=True, help="Side to move: b=sente, w=gote")
    parser.add_argument("--debug", action="store_true", help="Save debug crops and JSON details")
    parser.add_argument("--debug-dir", default="out/debug", help="Debug output directory")
    parser.add_argument("--save-cells", help="Directory to save 81 board cell crops")
    parser.add_argument("--save-hands", help="Directory to save hand area and slot crops")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        image = read_image(args.input)

        debug_dir = Path(args.debug_dir)
        debug_data: dict[str, object] = {"board": [], "hands": {"black": [], "white": []}}

        board_crop = BoardDetector(config.board).crop(image)
        cells = CellExtractor().split(board_crop.image)
        if args.debug:
            write_image(debug_dir / "board.png", board_crop.image)
        if args.save_cells:
            _save_cells(Path(args.save_cells), cells)
        elif args.debug:
            _save_cells(debug_dir / "cells", cells)

        hand_detector = HandDetector(config.black_hand, config.white_hand)
        black_crop = hand_detector.crop(image, "b")
        white_crop = hand_detector.crop(image, "w")
        if args.save_hands:
            hand_dir = Path(args.save_hands)
            _save_hand_area(hand_dir, "black", black_crop.image)
            _save_hand_area(hand_dir, "white", white_crop.image)
            _save_configured_hand_slots(hand_dir, "black", image, black_crop)
            _save_configured_hand_slots(hand_dir, "white", image, white_crop)
        elif args.debug:
            hand_dir = debug_dir / "hands"
            _save_hand_area(hand_dir, "black", black_crop.image)
            _save_hand_area(hand_dir, "white", white_crop.image)
            _save_configured_hand_slots(hand_dir, "black", image, black_crop)
            _save_configured_hand_slots(hand_dir, "white", image, white_crop)

        piece_recognizer = PieceRecognizer(config.recognition)
        board = [[None for _ in range(9)] for _ in range(9)]
        unknown_cells: list[str] = []
        for cell in cells:
            result = piece_recognizer.recognize(cell.image, include_scores=args.debug)
            board[cell.row][cell.col] = result.piece
            debug_data["board"].append(
                {
                    "cell": cell.name,
                    "row": cell.row + 1,
                    "col": cell.col + 1,
                    "label": result.label,
                    "piece": recognition_piece_to_debug(result.piece),
                    "empty": result.is_empty,
                    "score": result.score,
                    "scores": result.scores,
                }
            )
            if not result.ok:
                unknown_cells.append(f"{cell.name} best={result.label} score={result.score:.3f}")
            if args.debug:
                label = _safe_name(result.label or "unknown")
                write_image(debug_dir / "cells_recognized" / f"{cell.name}_{label}_{result.score:.3f}.png", cell.image)

        if unknown_cells:
            if args.debug:
                _write_debug_json(debug_dir, debug_data)
            raise RecognitionError("unrecognized board cells: " + ", ".join(unknown_cells))

        hand_recognizer = HandRecognizer(config.recognition, piece_recognizer)

        black_hands, black_slots = hand_recognizer.recognize(image, "b", black_crop.image, config.black_hand)
        white_hands, white_slots = hand_recognizer.recognize(image, "w", white_crop.image, config.white_hand)
        if args.save_hands:
            _save_slots(Path(args.save_hands), "black", black_slots)
            _save_slots(Path(args.save_hands), "white", white_slots)
        elif args.debug:
            _save_slots(debug_dir / "hands", "black", black_slots)
            _save_slots(debug_dir / "hands", "white", white_slots)

        debug_data["hands"]["black"] = [_slot_to_json(slot) for slot in black_slots]
        debug_data["hands"]["white"] = [_slot_to_json(slot) for slot in white_slots]

        hand_errors = []
        for side_name, slots in (("black", black_slots), ("white", white_slots)):
            for slot in slots:
                if slot.error:
                    hand_errors.append(f"{side_name} hand {slot.piece}: {slot.error}")

        if args.debug:
            _write_debug_json(debug_dir, debug_data)

        if hand_errors:
            raise RecognitionError("; ".join(hand_errors))

        print(to_sfen(board, args.turn, black_hands, white_hands, move_number=1))
        return 0
    except ShogiSfenReaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _save_cells(directory: Path, cells) -> None:
    for cell in cells:
        write_image(directory / f"{cell.name}.png", cell.image)


def _save_hand_area(directory: Path, side_name: str, image) -> None:
    write_image(directory / f"{side_name}_area.png", image)


def _save_slots(directory: Path, side_name: str, slots: list[SlotRecognition]) -> None:
    for slot in slots:
        suffix = f"{side_name}_{slot.piece}_piece_{slot.piece_score:.3f}"
        if slot.slot_image is not None:
            write_image(directory / f"{suffix}.png", slot.slot_image)
        if slot.digit_image is not None:
            digit_suffix = f"{side_name}_{slot.piece}_digit_{slot.digit_label or 'unknown'}"
            write_image(directory / f"{digit_suffix}.png", slot.digit_image)


def _save_configured_hand_slots(directory: Path, side_name: str, full_image, hand_crop) -> None:
    raw_dir = directory / f"{side_name}_raw_slots"
    for slot in hand_crop.config.slots:
        slot_image = _crop_config_rect(full_image, hand_crop.image, hand_crop.config, slot.rect)
        write_image(raw_dir / f"{side_name}_{slot.piece}_slot.png", slot_image)
        if slot.digit_rect is not None:
            digit_image = _crop_config_rect(full_image, hand_crop.image, hand_crop.config, slot.digit_rect)
            write_image(raw_dir / f"{side_name}_{slot.piece}_digit.png", digit_image)


def _crop_config_rect(full_image, hand_image, hand_config, rect):
    if hand_config.relative_to == "screen":
        return rect.crop(full_image)
    return rect.crop(hand_image)


def _slot_to_json(slot: SlotRecognition) -> dict[str, object]:
    return {
        "side": slot.side,
        "piece": slot.piece,
        "present": slot.present,
        "count": slot.count,
        "piece_score": slot.piece_score,
        "empty_score": slot.empty_score,
        "digit_label": slot.digit_label,
        "digit_score": slot.digit_score,
        "error": slot.error,
    }


def _write_debug_json(debug_dir: Path, debug_data: dict[str, object]) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "recognition.json").write_text(
        json.dumps(debug_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.+-]+", "_", value)


if __name__ == "__main__":
    raise SystemExit(main())
