import subprocess
import sys
import unittest
from pathlib import Path

import yaml


class ExpectedPositionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_path = Path(__file__).with_name("expected_positions.yaml")
        cls.positions = yaml.safe_load(data_path.read_text(encoding="utf-8"))["positions"]

    def test_expected_sfen_outputs(self):
        for position in self.positions:
            with self.subTest(position=position["name"]):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "shogi_sfen_reader.py",
                        position["image"],
                        "--config",
                        position["config"],
                        "--turn",
                        position["turn"],
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout.strip(), position["sfen"])


if __name__ == "__main__":
    unittest.main()
