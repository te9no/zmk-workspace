from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class WorkflowContractsTest(unittest.TestCase):
    def text(self, name):
        return (SOURCE / ".github/workflows" / name).read_text(encoding="utf-8")

    def test_publish_requires_complete_build_and_download(self):
        text = self.text("build-zmk-firmware.yml")
        self.assertIn("needs.build.result == 'success'", text)
        download = re.search(
            r"name: ⬇️ Download firmware artifacts(?P<body>.*?)(?=\n      - name:)",
            text, re.S,
        ).group("body")
        self.assertNotIn("continue-on-error", download)
        self.assertIn("target_count", text)
        self.assertIn("total_target_count", text)
        self.assertIn("publish_mode", text)
        self.assertIn("install-firmware-tree.py", text)
        self.assertIn('--mode "$PUBLISH_MODE"', text)
        self.assertLess(text.index("Check downloaded firmware"),
                        text.index("Install verified firmware set"))
        run_blocks = re.findall(r"\n        run: \|\n(?P<body>(?:          .*\n)*)", text)
        self.assertFalse(any("${{ inputs.firmware_folder }}" in block
                             for block in run_blocks))
        self.assertIn("steps.output-path.outputs.firmware_root", text)

    def test_draw_tolerance_does_not_refail_or_commit_partial_results(self):
        text = self.text("draw-keymap-svg.yml")
        self.assertIn("steps.draw.outcome == 'success'", text)
        self.assertIn("${{ inputs.output_folder }}/*.svg", text)
        check = text[text.index("- name: Check job success"):]
        self.assertNotIn("exit 1", check)
        self.assertIn("::warning::", check)


if __name__ == "__main__":
    unittest.main()
