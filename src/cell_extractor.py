from __future__ import annotations

from dataclasses import dataclass

from .config import Rect


@dataclass(frozen=True)
class CellImage:
    row: int
    col: int
    image: object
    rect: Rect

    @property
    def name(self) -> str:
        return f"r{self.row + 1}c{self.col + 1}"


class CellExtractor:
    def split(self, board_image) -> list[CellImage]:
        height, width = board_image.shape[:2]
        cells: list[CellImage] = []
        for row in range(9):
            y0 = round(row * height / 9)
            y1 = round((row + 1) * height / 9)
            for col in range(9):
                x0 = round(col * width / 9)
                x1 = round((col + 1) * width / 9)
                rect = Rect(x0, y0, x1 - x0, y1 - y0)
                cells.append(CellImage(row=row, col=col, image=rect.crop(board_image), rect=rect))
        return cells

