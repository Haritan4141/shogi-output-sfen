from __future__ import annotations

from .piece_recognizer import Piece

HAND_ORDER = "RBGSNLP"


def piece_to_sfen(piece: Piece) -> str:
    kind = piece.kind
    promoted = kind.startswith("+")
    base = kind[1:] if promoted else kind
    token = base if piece.side == "b" else base.lower()
    return f"+{token}" if promoted else token


def board_to_sfen(board: list[list[Piece | None]]) -> str:
    if len(board) != 9 or any(len(row) != 9 for row in board):
        raise ValueError("board must be 9x9")

    ranks: list[str] = []
    for row in board:
        rank = []
        empty = 0
        for piece in row:
            if piece is None:
                empty += 1
                continue
            if empty:
                rank.append(str(empty))
                empty = 0
            rank.append(piece_to_sfen(piece))
        if empty:
            rank.append(str(empty))
        ranks.append("".join(rank))
    return "/".join(ranks)


def format_hands(black: dict[str, int] | None, white: dict[str, int] | None) -> str:
    black = black or {}
    white = white or {}
    parts: list[str] = []
    for piece in HAND_ORDER:
        count = int(black.get(piece, 0))
        if count > 0:
            parts.append(_format_hand_piece(piece, count))
    for piece in HAND_ORDER.lower():
        count = int(white.get(piece.upper(), 0))
        if count > 0:
            parts.append(_format_hand_piece(piece, count))
    return "".join(parts) if parts else "-"


def _format_hand_piece(piece: str, count: int) -> str:
    if count < 1:
        return ""
    return f"{count if count > 1 else ''}{piece}"


def to_sfen(
    board: list[list[Piece | None]],
    turn: str,
    black_hands: dict[str, int] | None = None,
    white_hands: dict[str, int] | None = None,
    move_number: int = 1,
) -> str:
    if turn not in {"b", "w"}:
        raise ValueError("turn must be 'b' or 'w'")
    return f"{board_to_sfen(board)} {turn} {format_hands(black_hands, white_hands)} {move_number}"

