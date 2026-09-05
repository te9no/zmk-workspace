import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class FlashSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-flash-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mounts = self.root / "mounts"
        self.mounts.mkdir()
        self.script = self.root / "flash.sh"
        shutil.copy2(SOURCE / "flash.sh", self.script)
        self.firmware = self.root / "firmware.uf2"
        self.firmware.write_bytes(b"UF2 test fixture - never sent to hardware")
        self.env = os.environ | {"ZMK_FLASH_MOUNT_ROOT": str(self.mounts)}

    def loader(self, name):
        path = self.mounts / name
        path.mkdir()
        (path / "INFO_UF2.TXT").write_text("UF2 fixture\n")
        return path

    def run_flash(self, *args, env=None, input_text=None):
        return subprocess.run(
            ["bash", str(self.script), str(self.firmware), *args],
            env=self.env | (env or {}), text=True, capture_output=True,
            input=input_text,
        )

    def test_single_loader_is_used(self):
        loader = self.loader("ONE")
        result = self.run_flash()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((loader / self.firmware.name).read_bytes(),
                         self.firmware.read_bytes())

    def test_multiple_loaders_are_rejected_without_copy(self):
        first = self.loader("ONE")
        second = self.loader("TWO")
        result = self.run_flash()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Multiple UF2 loaders", result.stderr)
        self.assertFalse((first / self.firmware.name).exists())
        self.assertFalse((second / self.firmware.name).exists())

    def test_explicit_hint_selects_one_loader(self):
        first = self.loader("ONE")
        second = self.loader("TWO")
        result = self.run_flash("TWO")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((first / self.firmware.name).exists())
        self.assertTrue((second / self.firmware.name).exists())

    def test_copy_failure_never_prints_success(self):
        self.loader("ONE")
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_cp = fake_bin / "cp"
        fake_cp.write_text("#!/usr/bin/env bash\nexit 23\n")
        fake_cp.chmod(0o755)
        result = self.run_flash(env={
            "PATH": str(fake_bin) + os.pathsep + self.env["PATH"],
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Flash completed!", result.stdout)

    def test_keyboard_cancel_is_not_reported_as_success(self):
        result = self.run_flash(input_text="q")
        self.assertEqual(result.returncode, 130)
        self.assertIn("Cancelled", result.stdout)


if __name__ == "__main__":
    unittest.main()
