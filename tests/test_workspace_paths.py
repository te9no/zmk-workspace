"""Path/CDC regression tests. Run with python3 -m unittest discover -s tests -v.

Fixtures are isolated temporary workspaces; no Docker, serial port or device is used.
"""

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class WorkspacePathsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zmk-path-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "scripts").mkdir()
        for file in ("just.sh", "tools/zmk-flash-log.sh",
                     "scripts/workspace-safety.sh"):
            shutil.copy2(SOURCE / file, self.root / file)
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("ZMK_", "GIT_"))
        }
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
        self.checkout = self.root / "work" / "temporary-checkout"
        self.checkout.mkdir(parents=True)
        self.git("init", "-b", "codex/current")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-m", "Fixture")
        self.git("remote", "add", "origin", "https://github.com/example/canonical-keyboard.git")
        self.profile = "validation"
        self.metadata = self.root / ".zmk-workspace/profiles/validation/metadata"
        self.metadata.mkdir(parents=True)
        (self.metadata / "config-name").write_text("stale-name\n")
        (self.metadata / "config-branch").write_text("old-branch\n")
        (self.metadata / "config-root").write_text(str(self.checkout) + "\n")
        self.west_config = self.root / ".zmk-workspace/profiles/validation/west/.west/config"
        self.write_west(self.west_config, self.checkout)
        (self.root / ".zmk-workspace/active-profile").write_text(self.profile + "\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.checkout), *args], env=self.env,
                              text=True, capture_output=True, check=True).stdout.strip()

    def write_west(self, path, checkout):
        path.parent.mkdir(parents=True, exist_ok=True)
        relative = os.path.relpath(checkout / "config", path.parent.parent)
        path.write_text(f"[manifest]\npath = {relative}\nfile = west.yml\n")

    def run_script(self, *args, script="just.sh", env=None, ok=True):
        result = subprocess.run(["bash", str(self.root / script), *args], cwd=self.root,
                                env=self.env | (env or {}), text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def expected(self, repo="canonical-keyboard", branch="codex-current"):
        return str(self.root / "firmware" / repo / branch)

    def artifact(self, branch="codex-current", name="RIGHT"):
        path = Path(self.expected(branch=branch)) / f"{name}.uf2"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"UF2 fixture - never flash")
        return path

    def test_current_checkout_beats_metadata_without_writing_it(self):
        before = {p.name: p.read_bytes() for p in self.metadata.iterdir()}
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(), self.expected())
        self.git("switch", "-c", "zmk-0.4")
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(),
                         self.expected(branch="zmk-0.4"))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.metadata.iterdir()})

    def test_explicit_overrides_and_sanitization(self):
        result = self.run_script("firmware-dir", env={"ZMK_CONFIG_NAME": "my repo",
                                 "ZMK_CONFIG_BRANCH": "test/a:b"})
        self.assertEqual(result.stdout.strip(), self.expected("my-repo", "test-a-b"))
        for value in (".", "..", "///"):
            with self.subTest(value=value):
                result = self.run_script("firmware-dir", env={"ZMK_CONFIG_NAME": value,
                                         "ZMK_CONFIG_BRANCH": value})
                self.assertEqual(result.stdout.strip(), self.expected(self.profile, self.profile))

    def test_partial_override_preserves_live_branch(self):
        self.assertEqual(self.run_script("firmware-dir", env={"ZMK_CONFIG_NAME": "alias"}).stdout.strip(),
                         self.expected("alias"))

    def test_detached_checkout_uses_commit_not_stale_branch(self):
        self.git("checkout", "--detach")
        revision = self.git("rev-parse", "--short=12", "HEAD")
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(),
                         self.expected(branch=f"detached-{revision}"))

    def test_missing_checkout_falls_back_to_metadata(self):
        self.checkout.rename(self.checkout.with_name("moved-away"))
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(),
                         self.expected("stale-name", "old-branch"))

    def test_non_git_profile_does_not_use_parent_workspace_git(self):
        self.run_script("--profile", "new", "firmware-dir")
        subprocess.run(["git", "init", "-b", "workspace-main", str(self.root)],
                       env=self.env, capture_output=True, check=True)
        plain = self.root / "work/plain-config"
        plain.mkdir()
        result = self.run_script("--profile", "new", "firmware-dir",
                                 env={"ZMK_CONFIG_ROOT": str(plain)})
        self.assertEqual(result.stdout.strip(), self.expected("new", "new"))

    def test_explicit_root_and_container_alias(self):
        self.west_config.unlink()
        (self.metadata / "config-root").write_text("/missing\n")
        result = self.run_script("firmware-dir", env={
            "ZMK_CONFIG_ROOT": "/zmk-workspace/work/temporary-checkout"})
        self.assertEqual(result.stdout.strip(), self.expected())

    def test_saved_root_without_west(self):
        self.west_config.unlink()
        (self.metadata / "config-root").write_text("/zmk-workspace/work/temporary-checkout\n")
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(), self.expected())

    def test_moved_checkout_with_updated_west(self):
        moved = self.checkout.with_name("new-location")
        self.checkout.rename(moved)
        self.write_west(self.west_config, moved)
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(), self.expected())

    def test_root_manifest_resolves_to_repository_not_parent(self):
        relative = os.path.relpath(self.checkout, self.west_config.parent.parent)
        self.west_config.write_text(
            f"[manifest]\npath = {relative}\nfile = west.yml\n"
        )
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(), self.expected())

    def test_parent_workspace_git_is_not_mistaken_for_config_repository(self):
        subprocess.run(["git", "init", "-b", "workspace-main", str(self.root)],
                       env=self.env, capture_output=True, check=True)
        plain = self.root / "plain-config"
        (plain / "config").mkdir(parents=True)
        relative = os.path.relpath(plain / "config", self.west_config.parent.parent)
        self.west_config.write_text(
            f"[manifest]\npath = {relative}\nfile = west.yml\n"
        )
        (self.metadata / "config-name").unlink()
        (self.metadata / "config-branch").unlink()
        result = self.run_script("firmware-dir")
        self.assertEqual(result.stdout.strip(), self.expected(self.profile, self.profile))

    def test_no_remote_uses_checkout_name(self):
        self.git("remote", "remove", "origin")
        self.assertEqual(self.run_script("firmware-dir").stdout.strip(),
                         self.expected("temporary-checkout"))

    def test_legacy_config_only_for_default_profile(self):
        self.write_west(self.root / ".west/config", self.checkout)
        self.assertEqual(self.run_script("--profile", "default", "firmware-dir").stdout.strip(),
                         self.expected())
        self.assertEqual(self.run_script("--profile", "other", "firmware-dir").stdout.strip(),
                         self.expected("other", "other"))

    def test_custom_storage_and_profile(self):
        self.write_west(self.root / "custom/profiles/special/west/.west/config", self.checkout)
        env = {"ZMK_WORK_ROOT": "custom", "ZMK_WORK_PROFILE": "special"}
        self.assertEqual(self.run_script("firmware-dir", env=env).stdout.strip(), self.expected())
        self.assertEqual(self.run_script("log-dir", env=env).stdout.strip(),
                         str(self.root / "custom/profiles/special/logs"))

    def test_paths_and_cdc_share_destination(self):
        artifact = self.artifact()
        result = self.run_script("paths")
        self.assertIn("Firmware:  " + self.expected(), result.stdout)
        result = self.run_script("--resolve", "RIGHT", script="tools/zmk-flash-log.sh")
        self.assertEqual(result.stdout.strip(), str(artifact))
        result = self.run_script("--profile", self.profile, "flash-log", "--resolve", "RIGHT")
        self.assertEqual(result.stdout.strip(), str(artifact))
        self.assertFalse((self.root / "logs").exists())
        self.assertFalse((self.root / ".zmk-workspace/profiles/validation/logs").exists())
        self.assertFalse((self.root / ".zmk-workspace/cache").exists())

    def test_build_container_receives_same_resolved_identity(self):
        dockerfile = self.root / ".devcontainer/Dockerfile"
        dockerfile.parent.mkdir()
        dockerfile.write_text("FROM scratch\n")
        digest = hashlib.sha256(dockerfile.read_bytes()).hexdigest()
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            f"if [[ $1 == image ]]; then printf '%s\\n' '{digest}'; "
            "elif [[ $1 == run ]]; then printf '%s\\n' \"$@\"; else exit 99; fi\n"
        )
        fake_docker.chmod(0o755)
        result = self.run_script("build", "RIGHT", env={"PATH": str(fake_bin) + ":" + self.env["PATH"]})
        self.assertIn("ZMK_CONFIG_NAME=canonical-keyboard\n", result.stdout)
        self.assertIn("ZMK_CONFIG_BRANCH=codex-current\n", result.stdout)
        self.assertIn("ZMK_WORK_PROFILE=validation\n", result.stdout)

    def test_cdc_will_not_select_unique_artifact_from_other_branch(self):
        self.artifact(branch="wrong-branch")
        result = self.run_script("--resolve", "RIGHT", script="tools/zmk-flash-log.sh", ok=False)
        self.assertIn("Other branches are not searched", result.stderr)
        self.assertIn(self.expected(), result.stderr)

    def test_cdc_explicit_path_without_profile(self):
        path = self.artifact(branch="explicit")
        result = self.run_script("--resolve", str(path), script="tools/zmk-flash-log.sh",
                                 env={"ZMK_WORK_PROFILE": "unused"})
        self.assertEqual(result.stdout.strip(), str(path))

    def test_cdc_resolve_rejects_build_and_missing_target(self):
        result = self.run_script("--resolve", "RIGHT", "--build",
                                 script="tools/zmk-flash-log.sh", ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)
        self.assertEqual(self.run_script("--resolve", script="tools/zmk-flash-log.sh",
                                         ok=False).returncode, 2)

    def test_cdc_sanitizes_qualified_artifact(self):
        path = self.artifact(name="xiao-nrf52840")
        result = self.run_script("--resolve", "xiao/nrf52840", script="tools/zmk-flash-log.sh")
        self.assertEqual(result.stdout.strip(), str(path))


if __name__ == "__main__":
    unittest.main()
