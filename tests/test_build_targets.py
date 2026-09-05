import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / "scripts/build_targets.py"


class BuildTargetsTest(unittest.TestCase):
    def run_parser(self, text, expression="all", output_format="jsonl"):
        with tempfile.TemporaryDirectory(prefix="zmk-target-test-") as temp:
            build_yaml = Path(temp) / "build.yaml"
            build_yaml.write_text(text, encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(build_yaml), expression,
                 "--format", output_format],
                text=True, capture_output=True, check=True,
            ).stdout.splitlines()

    def test_jsonl_preserves_per_target_cmake_arguments(self):
        lines = self.run_parser("""
board: [board_a]
shield: [left]
include:
  - board: board_a
    shield: settings_reset
    artifact-name: reset-image
    cmake-args: '-DRESET=y -DNAME="two words"'
""")
        targets = [json.loads(line) for line in lines]
        reset = next(target for target in targets
                     if target.get("artifact-name") == "reset-image")
        self.assertEqual(reset["cmake-args"], '-DRESET=y -DNAME="two words"')

    def test_csv_interface_remains_four_columns(self):
        lines = self.run_parser(
            "board: board_a\nshield: [left, right]\n",
            output_format="csv",
        )
        self.assertEqual(lines, ["board_a,left,,", "board_a,right,,"])

    def test_filter_ignores_cmake_arguments(self):
        lines = self.run_parser("""
include:
  - board: board_a
    shield: left
    cmake-args: -DMAGIC_FILTER_TERM=y
""", expression="MAGIC_FILTER_TERM")
        self.assertEqual(lines, [])

    def test_invalid_cmake_arguments_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="zmk-target-test-") as temp:
            build_yaml = Path(temp) / "build.yaml"
            build_yaml.write_text(
                "include:\n  - board: board_a\n    cmake-args: '\"unterminated'\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(SCRIPT), str(build_yaml), "all", "--format", "jsonl"],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid cmake-args", result.stderr)


if __name__ == "__main__":
    unittest.main()
