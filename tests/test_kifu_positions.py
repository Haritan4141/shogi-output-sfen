import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from src.csa import CsaPosition


class KifuPositionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_path = Path(__file__).with_name("kifu_positions.yaml")
        cls.positions = yaml.safe_load(data_path.read_text(encoding="utf-8"))["positions"]

    def test_screenshot_matches_csa_kifu_position(self):
        for position in self.positions:
            with self.subTest(position=position["name"]):
                expected = CsaPosition.from_file(position["kifu"], move_number=position["move_number"]).to_sfen(
                    move_number=position.get("sfen_move_number", 1)
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        "shogi_sfen_reader.py",
                        position["image"],
                        "--config",
                        position["config"],
                        "--turn",
                        expected.split()[1],
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
