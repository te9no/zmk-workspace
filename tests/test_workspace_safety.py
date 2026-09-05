"""Regression tests for generated-data path containment.

The tests exercise only validation helpers and the host-side preflight. They
never invoke Docker or a cleanup recipe.
"""

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class WorkspaceSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-safety-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(SOURCE / "just.sh", self.root / "just.sh")
        shutil.copy2(SOURCE / "Justfile", self.root / "Justfile")
        shutil.copy2(SOURCE / "scripts/workspace-safety.sh",
                     self.root / "scripts/workspace-safety.sh")
        shutil.copy2(SOURCE / "scripts/build_targets.py",
                     self.root / "scripts/build_targets.py")
        (self.root / ".devcontainer").mkdir()
        (self.root / ".devcontainer/Dockerfile").write_text("FROM scratch\n")
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("ZMK_")}

    def run_guard(self, candidate, allowed):
        script = (
            f'source "{SOURCE / "scripts/workspace-safety.sh"}"; '
            'zmk_require_safe_child "$CANDIDATE" "$ALLOWED" test'
        )
        return subprocess.run(
            ["bash", "-c", script],
            env=self.env | {"CANDIDATE": str(candidate), "ALLOWED": str(allowed)},
            text=True,
            capture_output=True,
        )

    def test_guard_accepts_only_descendants(self):
        allowed = self.root / ".zmk-workspace/profiles/default"
        safe = allowed / "build"
        self.assertEqual(self.run_guard(safe, allowed).returncode, 0)

        for unsafe in (allowed, self.root, self.root.parent, Path("/"),
                       allowed / "../..", self.root / "config"):
            with self.subTest(unsafe=unsafe):
                result = self.run_guard(unsafe, allowed)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Refusing unsafe", result.stderr)

    def test_guard_rejects_internal_symlink(self):
        allowed = self.root / ".zmk-workspace/profiles/default"
        west = allowed / "west"
        west.mkdir(parents=True)
        (allowed / "build").symlink_to(west, target_is_directory=True)
        result = self.run_guard(allowed / "build", allowed)
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink component", result.stderr)
        self.assertTrue(west.is_dir())

    def test_wrapper_rejects_dangerous_build_root_before_docker(self):
        marker = self.root / "docker-was-called"
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            f"touch '{marker}'\n"
            "exit 99\n"
        )
        fake_docker.chmod(0o755)
        result = subprocess.run(
            ["bash", str(self.root / "just.sh"), "clean"],
            cwd=self.root,
            env=self.env | {
                "ZMK_BUILD_ROOT": ".",
                "PATH": str(fake_bin) + os.pathsep + self.env["PATH"],
            },
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ZMK_BUILD_ROOT", result.stderr)
        self.assertFalse(marker.exists())

    def test_wrapper_rejects_traversing_work_root(self):
        result = subprocess.run(
            ["bash", str(self.root / "just.sh"), "paths"],
            cwd=self.root,
            env=self.env | {"ZMK_WORK_ROOT": "../outside"},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ZMK_WORK_ROOT", result.stderr)

    def test_nondestructive_paths_keeps_workspace_alias_and_custom_roots(self):
        alias = subprocess.run(
            ["bash", str(self.root / "just.sh"), "paths"], cwd=self.root,
            env=self.env | {"ZMK_WORK_ROOT": str(self.root)},
            text=True, capture_output=True,
        )
        self.assertEqual(alias.returncode, 0, alias.stderr)

        custom = subprocess.run(
            ["bash", str(self.root / "just.sh"), "paths"], cwd=self.root,
            env=self.env | {"ZMK_BUILD_ROOT": ".build-legacy"},
            text=True, capture_output=True,
        )
        self.assertEqual(custom.returncode, 0, custom.stderr)
        self.assertIn(str(self.root / ".build-legacy"), custom.stdout)

    @unittest.skipUnless(shutil.which("just"), "just is required")
    def test_direct_clean_rejects_profile_traversal_without_deleting(self):
        protected = SOURCE / "docs"
        before = sorted(path.name for path in protected.iterdir())
        result = subprocess.run(
            ["just", "--justfile", str(SOURCE / "Justfile"), "clean"],
            cwd=SOURCE,
            env=self.env | {"ZMK_WORK_PROFILE": "../../docs"},
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid profile", result.stderr)
        self.assertEqual(before, sorted(path.name for path in protected.iterdir()))

    def test_firmware_symlink_and_tracked_trees_are_rejected(self):
        outside = self.root.parent / "outside-firmware"
        outside.mkdir()
        (self.root / "firmware").symlink_to(outside, target_is_directory=True)
        result = self.run_guard(self.root / "firmware", self.root)
        self.assertEqual(result.returncode, 2)

        subprocess.run(["git", "init", "-b", "main", str(self.root)],
                       env=self.env, capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "scripts/workspace-safety.sh"],
                       env=self.env, capture_output=True, check=True)
        script = (
            f'source "{SOURCE / "scripts/workspace-safety.sh"}"; '
            'zmk_require_untracked_child "$CANDIDATE" "$WORKSPACE" test'
        )
        tracked = subprocess.run(
            ["bash", "-c", script],
            env=self.env | {"CANDIDATE": str(self.root / "scripts"),
                            "WORKSPACE": str(self.root)},
            text=True, capture_output=True,
        )
        self.assertEqual(tracked.returncode, 2)
        self.assertIn("tracked files", tracked.stderr)

    def test_untracked_guard_fails_closed_when_git_fails(self):
        candidate = self.root / "generated"
        candidate.mkdir()
        fake_bin = self.root / "git-failure-bin"
        fake_bin.mkdir()
        fake_git = fake_bin / "git"
        fake_git.write_text("#!/usr/bin/env bash\nexit 128\n")
        fake_git.chmod(0o755)
        script = (
            f'source "{SOURCE / "scripts/workspace-safety.sh"}"; '
            'zmk_require_untracked_child "$CANDIDATE" "$WORKSPACE" test'
        )
        result = subprocess.run(
            ["bash", "-c", script],
            env=self.env | {"CANDIDATE": str(candidate),
                            "WORKSPACE": str(self.root),
                            "PATH": str(fake_bin) + os.pathsep + self.env["PATH"]},
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("tracking state is unavailable", result.stderr)
        self.assertTrue(candidate.is_dir())

    @unittest.skipUnless(shutil.which("just"), "just is required")
    def test_clean_rejects_internal_build_and_firmware_symlinks(self):
        profile = self.root / ".zmk-workspace/profiles/default"
        west = profile / "west"
        west.mkdir(parents=True)
        (profile / "build").symlink_to(west, target_is_directory=True)
        result = subprocess.run(
            ["just", "--justfile", str(self.root / "Justfile"), "clean"],
            cwd=self.root, env=self.env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertTrue(west.is_dir())

        (profile / "build").unlink()
        other = self.root / "firmware/repo/other"
        other.mkdir(parents=True)
        (other / "keep.uf2").write_bytes(b"keep")
        (self.root / "firmware/repo/main").symlink_to(
            other, target_is_directory=True
        )
        result = subprocess.run(
            ["just", "--justfile", str(self.root / "Justfile"), "clean"],
            cwd=self.root,
            env=self.env | {"ZMK_CONFIG_NAME": "repo", "ZMK_CONFIG_BRANCH": "main"},
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual((other / "keep.uf2").read_bytes(), b"keep")

    @unittest.skipUnless(shutil.which("just"), "just is required")
    def test_clean_all_preflights_west_projects_before_any_removal(self):
        subprocess.run(["git", "init", "-b", "main", str(self.root)],
                       env=self.env, capture_output=True, check=True)
        (self.root / "docs").mkdir()
        (self.root / "docs/keep.txt").write_text("tracked and protected")
        subprocess.run(["git", "-C", str(self.root), "add", "docs/keep.txt"],
                       env=self.env, capture_output=True, check=True)
        (self.root / ".west").mkdir()
        build_marker = self.root / ".zmk-workspace/profiles/default/build/keep.txt"
        build_marker.parent.mkdir(parents=True)
        build_marker.write_text("must survive preflight")

        fake_bin = self.root / "west-bin"
        fake_bin.mkdir()
        fake_west = fake_bin / "west"
        fake_west.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' '{self.root / 'docs'}'\n"
        )
        fake_west.chmod(0o755)
        result = subprocess.run(
            ["just", "--justfile", str(self.root / "Justfile"), "clean-all"],
            cwd=self.root,
            env=self.env | {"PATH": str(fake_bin) + os.pathsep + self.env["PATH"]},
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("tracked files", result.stderr)
        self.assertTrue(build_marker.exists())

    def test_flash_rejects_multiple_targets_before_platform_access(self):
        digest = hashlib.sha256(
            (self.root / ".devcontainer/Dockerfile").read_bytes()
        ).hexdigest()
        fake_bin = self.root / "target-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        build_marker = self.root / "build-was-called"
        fake_docker.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            f"if [[ $1 == image ]]; then printf '%s\\n' '{digest}'; exit 0; fi\n"
            "if [[ $1 == run ]]; then\n"
            f"  [[ ' $* ' != *' just build '* ]] || touch '{build_marker}'\n"
            "  printf '%s\\n' '{\"board\":\"board_a\",\"shield\":\"left\"}'\n"
            "  printf '%s\\n' '{\"board\":\"board_a\",\"shield\":\"right\"}'\n"
            "  exit 0\n"
            "fi\nexit 99\n"
        )
        fake_docker.chmod(0o755)
        result = subprocess.run(
            ["bash", str(self.root / "just.sh"), "flash", "all", "-r"],
            cwd=self.root,
            env=self.env | {"PATH": str(fake_bin) + os.pathsep + self.env["PATH"]},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("matches multiple targets", result.stderr)
        self.assertFalse(build_marker.exists())

    def test_flash_propagates_target_parser_failure(self):
        digest = hashlib.sha256(
            (self.root / ".devcontainer/Dockerfile").read_bytes()
        ).hexdigest()
        fake_bin = self.root / "failure-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            f"if [[ $1 == image ]]; then printf '%s\\n' '{digest}'; exit 0; fi\n"
            "if [[ $1 == run ]]; then exit 17; fi\n"
            "exit 99\n"
        )
        fake_docker.chmod(0o755)
        result = subprocess.run(
            ["bash", str(self.root / "just.sh"), "flash", "all"],
            cwd=self.root,
            env=self.env | {"PATH": str(fake_bin) + os.pathsep + self.env["PATH"]},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("No matching targets", result.stderr)


if __name__ == "__main__":
    unittest.main()
