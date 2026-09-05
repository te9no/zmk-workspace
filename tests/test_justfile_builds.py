import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("just"), "just is required")
class JustfileBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-build-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config-repo"
        (self.config / "config").mkdir(parents=True)
        subprocess.run(['git', 'init', str(self.config)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.config), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty',
                        '-m', 'fixture'], check=True, capture_output=True)
        self.west = self.root / "managed/profiles/test/west"
        self.west.mkdir(parents=True)
        self.build = self.root / "managed/profiles/test/build"
        self.fake_bin = self.root / "fake-bin"
        self.fake_bin.mkdir()
        self.west_log = self.root / "west.log"
        self.cmake_log = self.root / "cmake.log"
        fake_west = self.fake_bin / "west"
        fake_west.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            "[ \"$1\" != list ] || exit 0\n"
            "printf '<%s>\\n' \"$@\" > \"$WEST_LOG\"\n"
            "build_dir=''\nprevious=''\n"
            "for arg in \"$@\"; do [ \"$previous\" != -d ] || build_dir=\"$arg\"; previous=\"$arg\"; done\n"
            "mkdir -p \"$build_dir/zephyr\"\n"
            "touch \"$build_dir/build.ninja\"\n"
            "touch \"$build_dir/zephyr/.config\" \"$build_dir/zephyr/zephyr.dts\"\n"
            "[ \"${WEST_SKIP_ARTIFACT:-0}\" = 1 ] || printf fixture > \"$build_dir/zephyr/zmk.uf2\"\n"
        )
        fake_west.chmod(0o755)
        fake_cmake = self.fake_bin / "cmake"
        fake_cmake.write_text(
            "#!/usr/bin/env bash\nset -eu\nprintf '<%s>\\n' \"$@\" > \"$CMAKE_LOG\"\n"
        )
        fake_cmake.chmod(0o755)
        self.env = os.environ | {
            "IN_ZMK_CONTAINER": "1",
            "ZMK_WORK_ROOT": str(self.root / "managed"),
            "ZMK_WORK_PROFILE": "test",
            "ZMK_BUILD_ROOT": str(self.build),
            "ZMK_WEST_WORKSPACE": str(self.west),
            "ZMK_CONFIG_ROOT": str(self.config),
            "WEST_LOG": str(self.west_log),
            "CMAKE_LOG": str(self.cmake_log),
            "PATH": str(self.fake_bin) + os.pathsep + os.environ["PATH"],
        }
        self.target = json.dumps({
            "board": "board_a",
            "shield": "left",
            "artifact-name": "left-board",
            "cmake-args": '-DRESET=y -DNAME="two words"',
            "cmake-argv": ["-DRESET=y", "-DNAME=two words"],
        }, separators=(",", ":"))

    def build_once(self, env=None, target=None):
        return subprocess.run(
            ["just", "--justfile", str(SOURCE / "Justfile"),
             "_build_single", target or self.target],
            cwd=self.root, env=self.env | (env or {}), text=True, capture_output=True,
        )

    def test_cmake_args_and_signature_control_incremental_reuse(self):
        first = self.build_once()
        self.assertEqual(first.returncode, 0, first.stderr)
        west_args = self.west_log.read_text()
        self.assertIn("<-DRESET=y>", west_args)
        self.assertIn("<-DNAME=two words>", west_args)
        signature = self.build / "left-board/.zmk-workspace-config"
        self.assertIn("version=2", signature.read_text())

        self.west_log.unlink()
        second = self.build_once()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(self.west_log.exists())
        self.assertIn("<--build>", self.cmake_log.read_text())

        other_west = self.root / "managed/profiles/test/west-other"
        other_west.mkdir()
        self.cmake_log.unlink()
        third = self.build_once({"ZMK_WEST_WORKSPACE": str(other_west)})
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("<-p>", self.west_log.read_text())
        self.assertIn("<always>", self.west_log.read_text())
        self.assertFalse(self.cmake_log.exists())

    def test_cmake_and_module_changes_force_reconfiguration(self):
        self.assertEqual(self.build_once().returncode, 0)
        changed = json.loads(self.target)
        changed["cmake-args"] = "-DRESET=n"
        changed["cmake-argv"] = ["-DRESET=n"]
        self.assertEqual(self.build_once(target=json.dumps(changed, separators=(",", ":"))).returncode, 0)
        self.assertIn("<always>", self.west_log.read_text())

        (self.config / "zephyr").mkdir()
        (self.config / "zephyr/module.yml").write_text("build:\n")
        self.assertEqual(self.build_once(target=json.dumps(changed, separators=(",", ":"))).returncode, 0)
        self.assertIn("<-DZMK_EXTRA_MODULES=" + str(self.config) + ">",
                      self.west_log.read_text())

    def test_missing_firmware_does_not_write_signature(self):
        result = self.build_once({"WEST_SKIP_ARTIFACT": "1"})
        self.assertNotEqual(result.returncode, 0)
        signature = self.build / "left-board/.zmk-workspace-config"
        self.assertFalse(signature.exists())


if __name__ == "__main__":
    unittest.main()
