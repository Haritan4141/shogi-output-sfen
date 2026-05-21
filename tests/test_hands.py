import unittest

import numpy as np

from src.config import HandSlotConfig, Rect
from src.hand_recognizer import DigitRecognizer, HandRecognizer


class HandConfigTest(unittest.TestCase):
    def test_hand_slot_requires_valid_piece(self):
        slot = HandSlotConfig.from_dict({"piece": "p", "rect": [1, 2, 3, 4]}, 1)
        self.assertEqual(slot.piece, "P")
        self.assertEqual(slot.rect, Rect(1, 2, 3, 4))

    def test_digit_recognizer_without_templates(self):
        recognizer = DigitRecognizer(templates_dir=__import__("pathlib").Path("missing"))
        self.assertFalse(recognizer.available)

    def test_digit_area_without_red_count_is_treated_as_one(self):
        image = np.full((30, 42, 3), (40, 140, 210), dtype=np.uint8)
        image[:, 30:36] = (20, 20, 20)
        recognizer = HandRecognizer.__new__(HandRecognizer)

        count, error, digit_score, digit_label = recognizer._recognize_count(image)

        self.assertEqual(count, 1)
        self.assertIsNone(error)
        self.assertIsNone(digit_score)
        self.assertIsNone(digit_label)


if __name__ == "__main__":
    unittest.main()
