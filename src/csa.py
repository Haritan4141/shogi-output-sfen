from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .piece_recognizer import Piece
from .sfen import to_sfen

CSA_TO_KIND = {
    "FU": "P",
    "KY": "L",
    "KE": "N",
    "GI": "S",
    "KI": "G",
    "KA": "B",
    "HI": "R",
    "OU": "K",
    "TO": "+P",
    "NY": "+L",
    "NK": "+N",
    "NG": "+S",
    "UM": "+B",
    "RY": "+R",
}

DEMOTE = {
    "+P": "P",
    "+L": "L",
    "+N": "N",
    "+S": "S",
    "+B": "B",
    "+R": "R",
}


@dataclass(frozen=True)
class CsaMove:
    side: str
    source: str
    destination: str
    kind: str
    raw: str


class CsaParseError(ValueError):
    pass


class CsaPosition:
    def __init__(self):
        self.board: list[list[Piece | None]] = [[None for _ in range(9)] for _ in range(9)]
        self.hands: dict[str, Counter[str]] = {"b": Counter(), "w": Counter()}
        self.moves: list[CsaMove] = []
        self.last_side: str | None = None

    @classmethod
    def from_file(cls, path: str | Path, move_number: int | None = None) -> "CsaPosition":
        text = Path(path).read_text(encoding="utf-8-sig")
        return cls.from_text(text, move_number=move_number)

    @classmethod
    def from_text(cls, text: str, move_number: int | None = None) -> "CsaPosition":
        position = cls()
        all_moves: list[CsaMove] = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("P") and len(line) > 2 and line[1].isdigit():
                position._parse_board_rank(line)
            elif _is_move_line(line):
                all_moves.append(_parse_move(line.strip()))

        limit = len(all_moves) if move_number is None else move_number
        if limit < 0 or limit > len(all_moves):
            raise CsaParseError(f"move_number out of range: {move_number}, moves={len(all_moves)}")

        for move in all_moves[:limit]:
            position.apply_move(move)
        return position

    @property
    def turn(self) -> str:
        if self.last_side is None:
            return "b"
        return "w" if self.last_side == "b" else "b"

    def to_sfen(self, move_number: int = 1) -> str:
        return to_sfen(self.board, self.turn, dict(self.hands["b"]), dict(self.hands["w"]), move_number=move_number)

    def apply_move(self, move: CsaMove) -> None:
        side = move.side
        to_row, to_col = _coord_to_index(move.destination)
        captured = self.board[to_row][to_col]
        if captured is not None:
            self.hands[side][_demote(captured.kind)] += 1

        if move.source == "00":
            dropped = _demote(move.kind)
            self.hands[side][dropped] -= 1
            if self.hands[side][dropped] < 0:
                raise CsaParseError(f"drop without hand piece: {move.raw}")
        else:
            from_row, from_col = _coord_to_index(move.source)
            moving = self.board[from_row][from_col]
            if moving is None:
                raise CsaParseError(f"source square is empty: {move.raw}")
            if moving.side != side:
                raise CsaParseError(f"moving opponent piece: {move.raw}")
            self.board[from_row][from_col] = None

        self.board[to_row][to_col] = Piece(side, move.kind)
        self.moves.append(move)
        self.last_side = side

    def _parse_board_rank(self, line: str) -> None:
        rank = int(line[1])
        if rank < 1 or rank > 9:
            raise CsaParseError(f"invalid rank line: {line}")
        rest = line[2:]
        tokens = [rest[i : i + 3] for i in range(0, len(rest), 3)]
        if len(tokens) < 9:
            raise CsaParseError(f"rank line has fewer than 9 squares: {line}")
        row = rank - 1
        for col, token in enumerate(tokens[:9]):
            self.board[row][col] = _parse_square(token)


def _is_move_line(line: str) -> bool:
    return len(line) >= 7 and line[0] in "+-" and line[1:5].isdigit()


def _parse_move(line: str) -> CsaMove:
    side = "b" if line[0] == "+" else "w"
    kind = _csa_kind_to_piece(line[5:7])
    return CsaMove(side=side, source=line[1:3], destination=line[3:5], kind=kind, raw=line)


def _parse_square(token: str) -> Piece | None:
    if token == " * ":
        return None
    if len(token) != 3 or token[0] not in "+-":
        raise CsaParseError(f"invalid square token: {token!r}")
    side = "b" if token[0] == "+" else "w"
    return Piece(side, _csa_kind_to_piece(token[1:3]))


def _csa_kind_to_piece(kind: str) -> str:
    try:
        return CSA_TO_KIND[kind]
    except KeyError as exc:
        raise CsaParseError(f"unsupported CSA piece: {kind}") from exc


def _coord_to_index(coord: str) -> tuple[int, int]:
    file = int(coord[0])
    rank = int(coord[1])
    if not (1 <= file <= 9 and 1 <= rank <= 9):
        raise CsaParseError(f"invalid square coordinate: {coord}")
    return rank - 1, 9 - file


def _demote(kind: str) -> str:
    return DEMOTE.get(kind, kind)
