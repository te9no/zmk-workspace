import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("just"), "just is required")
class JustfileInitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-init-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy2(SOURCE / "Justfile", self.root / "Justfile")
        (self.root / "scripts").mkdir()
        for name in ("workspace-safety.sh", "build_targets.py"):
            shutil.copy2(SOURCE / "scripts" / name, self.root / "scripts" / name)
        self.config_repo = self.root / "config/example"
        (self.config_repo / "config").mkdir(parents=True)
        (self.config_repo / "west.yml").write_text("manifest:\n  self:\n    path: .\n")
        (self.config_repo / "config/west.yml").write_text(
            "manifest:\n  projects:\n    - name: zmk\n      url: https://example.invalid/zmk\n"
        )
        self.west_workspace = self.root / "managed/profiles/test/west"
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_west = fake_bin / "west"
        fake_west.write_text("#!/usr/bin/env bash\nset -eu\nexit 0\n")
        fake_west.chmod(0o755)
        self.env = os.environ | {
            "IN_ZMK_CONTAINER": "1",
            "ZMK_WORK_ROOT": str(self.root / "managed"),
            "ZMK_WORK_PROFILE": "test",
            "ZMK_WEST_WORKSPACE": str(self.west_workspace),
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        }

    def run_init(self, selection):
        return subprocess.run(
            ["just", "--justfile", str(self.root / "Justfile"), "init", selection],
            cwd=self.root, env=self.env, text=True, capture_output=True,
        )

    def manifest_config(self):
        parser = configparser.ConfigParser()
        parser.read(self.west_workspace / ".west/config")
        return parser["manifest"]

    def test_nested_manifest_is_preferred(self):
        result = self.run_init("config/example")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest_config()["file"], "example/config/west.yml")

    def test_root_manifest_can_be_selected_explicitly(self):
        result = self.run_init("config/example/west.yml")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest_config()["file"], "example/west.yml")


if __name__ == "__main__":
    unittest.main()
