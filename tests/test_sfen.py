import unittest

from src.piece_recognizer import Piece
from src.sfen import board_to_sfen, format_hands, piece_to_sfen, to_sfen


class SfenTest(unittest.TestCase):
    def test_initial_position(self):
        board = [
            [Piece("w", k) for k in "LNSGKGSNL"],
            [None, Piece("w", "R"), None, None, None, None, None, Piece("w", "B"), None],
            [Piece("w", "P") for _ in range(9)],
            [None for _ in range(9)],
            [None for _ in range(9)],
            [None for _ in range(9)],
            [Piece("b", "P") for _ in range(9)],
            [None, Piece("b", "B"), None, None, None, None, None, Piece("b", "R"), None],
            [Piece("b", k) for k in "LNSGKGSNL"],
        ]
        self.assertEqual(
            to_sfen(board, "b", {}, {}),
            "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
        )

    def test_promoted_piece(self):
        self.assertEqual(piece_to_sfen(Piece("b", "+P")), "+P")
        self.assertEqual(piece_to_sfen(Piece("w", "+R")), "+r")

    def test_hand_format(self):
        self.assertEqual(format_hands({"P": 2, "R": 1}, {"B": 1}), "R2Pb")
        self.assertEqual(format_hands({}, {}), "-")

    def test_empty_compression(self):
        board = [[None for _ in range(9)] for _ in range(9)]
        board[0][0] = Piece("w", "K")
        board[0][8] = Piece("b", "K")
        self.assertEqual(board_to_sfen(board), "k7K/9/9/9/9/9/9/9/9")


if __name__ == "__main__":
    unittest.main()

