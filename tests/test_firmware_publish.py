import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
MODULE_PATH = SOURCE / ".github/scripts/install-firmware-tree.py"
SPEC = importlib.util.spec_from_file_location("install_firmware_tree", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FirmwarePublishTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-publish-test-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        self.firmware_root = self.workspace / "firmware"
        self.destination = self.firmware_root / "repo/main"
        self.destination.mkdir(parents=True)
        (self.destination / "LEFT.uf2").write_bytes(b"old-left")
        (self.destination / "RIGHT.uf2").write_bytes(b"old-right")
        self.staging = Path(self.temp.name) / "staging"
        self.staging.mkdir()

    def install(self, count, mode="replace", replace=None):
        kwargs = {}
        if replace is not None:
            kwargs["replace"] = replace
        MODULE.install_firmware_tree(
            self.workspace, self.firmware_root, self.staging,
            self.destination, count, mode, **kwargs,
        )

    def test_replace_installs_complete_tree(self):
        (self.staging / "LEFT.uf2").write_bytes(b"new-left")
        self.install(1)
        self.assertEqual([p.name for p in self.destination.iterdir()], ["LEFT.uf2"])
        self.assertEqual((self.destination / "LEFT.uf2").read_bytes(), b"new-left")

    def test_merge_preserves_unselected_and_replaces_extension(self):
        (self.staging / "LEFT.bin").write_bytes(b"new-left-bin")
        self.install(1, "merge")
        self.assertFalse((self.destination / "LEFT.uf2").exists())
        self.assertEqual((self.destination / "LEFT.bin").read_bytes(), b"new-left-bin")
        self.assertEqual((self.destination / "RIGHT.uf2").read_bytes(), b"old-right")

    def test_invalid_staging_leaves_destination_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.destination.iterdir()}
        (self.staging / "notes.txt").write_text("not firmware")
        with self.assertRaises(ValueError):
            self.install(1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.destination.iterdir()})

    def test_symlinked_staging_file_is_rejected(self):
        source = Path(self.temp.name) / "outside.uf2"
        source.write_bytes(b"outside")
        try:
            (self.staging / "LEFT.uf2").symlink_to(source)
        except OSError as error:
            self.skipTest(f"symlinks are unavailable: {error}")
        with self.assertRaises(ValueError):
            self.install(1)

    def test_symlinked_staging_directory_is_rejected(self):
        real_staging = Path(self.temp.name) / "real-staging"
        real_staging.mkdir()
        (real_staging / "LEFT.uf2").write_bytes(b"new")
        self.staging.rmdir()
        self.staging.symlink_to(real_staging, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.install(1)

    def test_firmware_root_and_destination_symlinks_are_rejected(self):
        other_root = self.workspace / "other-firmware"
        other_root.mkdir()
        linked_root = self.workspace / "linked-firmware"
        linked_root.symlink_to(other_root, target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULE.resolve_firmware_root(self.workspace, "linked-firmware")

        other = self.firmware_root / "repo/other"
        other.mkdir(parents=True)
        (other / "keep.uf2").write_bytes(b"keep")
        shutil.rmtree(self.destination)
        self.destination.symlink_to(other, target_is_directory=True)
        (self.staging / "LEFT.uf2").write_bytes(b"new")
        with self.assertRaises(ValueError):
            self.install(1, "merge")
        self.assertEqual((other / "keep.uf2").read_bytes(), b"keep")

    def test_existing_tree_symlink_and_regular_file_destination_are_rejected(self):
        outside = Path(self.temp.name) / "outside-secret"
        outside.write_bytes(b"secret")
        (self.destination / "SECRET.uf2").symlink_to(outside)
        (self.staging / "LEFT.uf2").write_bytes(b"new")
        with self.assertRaises(ValueError):
            self.install(1, "merge")
        self.assertEqual(outside.read_bytes(), b"secret")

        (self.destination / "SECRET.uf2").unlink()
        shutil.rmtree(self.destination)
        self.destination.write_bytes(b"not-a-directory")
        with self.assertRaises(ValueError):
            self.install(1)
        self.assertEqual(self.destination.read_bytes(), b"not-a-directory")

    def test_publish_paths_reject_injection_and_support_nested_folder(self):
        values = MODULE.publish_paths(
            self.workspace, "artifacts/firmware", "owner/repo", "feature/test"
        )
        self.assertEqual(values["firmware_root"], "artifacts/firmware")
        self.assertEqual(values["firmware_dir"], "artifacts/firmware/repo/feature-test")
        for value in ('firmware"; touch marker; #', "firmware`id`", "firmware$(id)",
                      "firmware\nextra", "firmware\r\nextra"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.publish_paths(self.workspace, value, "owner/repo", "main")

    def test_paths_cli_does_not_execute_malicious_folder(self):
        marker = Path(self.temp.name) / "marker"
        output = Path(self.temp.name) / "output"
        malicious = f'firmware"; touch {marker}; #'
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "paths", "--workspace", str(self.workspace),
             "--firmware-folder", malicious, "--repository", "owner/repo",
             "--branch", "main", "--github-output", str(output)],
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_unsafe_destination_and_folder_are_rejected(self):
        (self.staging / "LEFT.uf2").write_bytes(b"new")
        with self.assertRaises(ValueError):
            MODULE.install_firmware_tree(
                self.workspace, self.firmware_root, self.staging,
                self.workspace.parent / "outside", 1, "replace",
            )
        for value in ("", ".", "..", "/tmp/firmware", "C:\\temp\\firmware",
                      ".git/firmware", "firmware/../.git/output"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.resolve_firmware_root(self.workspace, value)

    def test_swap_failure_restores_old_tree(self):
        (self.staging / "LEFT.uf2").write_bytes(b"new-left")
        real_replace = MODULE.os.replace
        calls = 0

        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated swap failure")
            return real_replace(source, destination)

        with self.assertRaises(OSError):
            self.install(1, replace=fail_second)
        self.assertEqual((self.destination / "LEFT.uf2").read_bytes(), b"old-left")
        self.assertEqual((self.destination / "RIGHT.uf2").read_bytes(), b"old-right")


if __name__ == "__main__":
    unittest.main()
