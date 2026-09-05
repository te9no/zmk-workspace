#!/usr/bin/env python3
"""Safely install a verified firmware staging set into the canonical tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile
import uuid


ALLOWED_SUFFIXES = {".uf2", ".bin"}
UNSAFE_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def reject_symlink_components(path: Path, anchor: Path, label: str) -> None:
    path = lexical_absolute(path)
    anchor = lexical_absolute(anchor)
    try:
        relative = path.relative_to(anchor)
    except ValueError as error:
        raise ValueError(f"unsafe {label}: {path}") from error
    current = anchor
    if current.is_symlink():
        raise ValueError(f"unsafe {label} symlink: {current}")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"unsafe {label} symlink: {current}")


def strict_child(path: Path, root: Path, label: str) -> Path:
    absolute = lexical_absolute(path)
    root_absolute = lexical_absolute(root)
    if absolute == root_absolute or root_absolute not in absolute.parents:
        raise ValueError(f"unsafe {label}: {absolute}")
    reject_symlink_components(absolute, root_absolute, label)
    resolved = absolute.resolve()
    root_resolved = root_absolute.resolve()
    if resolved == root_resolved or root_resolved not in resolved.parents:
        raise ValueError(f"unsafe {label}: {resolved}")
    return absolute


def validate_folder(folder: str) -> Path:
    if UNSAFE_CONTROL.search(folder) or "\\" in folder:
        raise ValueError(f"unsafe firmware folder: {folder!r}")
    relative = Path(folder)
    if (not folder.strip() or relative.is_absolute() or PureWindowsPath(folder).is_absolute()
            or relative in (Path("."), Path(".."))
            or any(part in ("", ".", "..", ".git")
                   or not re.fullmatch(r"[A-Za-z0-9._-]+", part)
                   for part in relative.parts)):
        raise ValueError(f"unsafe firmware folder: {folder!r}")
    return relative


def resolve_firmware_root(workspace: Path, folder: str) -> Path:
    workspace = lexical_absolute(workspace)
    if workspace.is_symlink():
        raise ValueError(f"unsafe workspace symlink: {workspace}")
    return strict_child(workspace / validate_folder(folder), workspace, "firmware root")


def safe_publish_component(value: str, label: str) -> str:
    if not value or UNSAFE_CONTROL.search(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    if not safe or safe in (".", ".."):
        raise ValueError(f"unsafe {label}: {value!r}")
    return safe


def publish_paths(workspace: Path, folder: str, repository: str, branch: str):
    root = resolve_firmware_root(workspace, folder)
    repo = repository.rsplit("/", 1)[-1]
    safe_repo = safe_publish_component(repo, "repository")
    safe_branch = safe_publish_component(branch, "branch")
    destination = strict_child(root / safe_repo / safe_branch, root, "firmware destination")
    workspace = lexical_absolute(workspace)
    return {
        "repo": repo,
        "safe_repo": safe_repo,
        "branch": branch,
        "safe_branch": safe_branch,
        "firmware_root": root.relative_to(workspace).as_posix(),
        "firmware_dir": destination.relative_to(workspace).as_posix(),
    }


def validate_metadata(entries, required=False):
    binaries = [p for p in entries if p.suffix.lower() in ALLOWED_SUFFIXES]
    allowed = set(binaries) | {Path(str(p) + '.json') for p in binaries}
    if any(p not in allowed for p in entries):
        raise ValueError('unexpected file type or orphan provenance')
    for binary in binaries:
        sidecar = Path(str(binary) + '.json')
        if sidecar not in entries:
            if required:
                raise ValueError('missing firmware provenance')
            continue
        metadata = json.loads(sidecar.read_text(encoding='utf-8'))
        with binary.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if (metadata.get('schema') != 1 or metadata.get('artifact') !=
                {'name': binary.name, 'sha256': sha}):
            raise ValueError('firmware provenance does not match binary')
    return binaries


def validate_staging(staging: Path, expected_count: int, require_provenance=False) -> list[Path]:
    staging = lexical_absolute(staging)
    reject_symlink_components(staging, Path(staging.anchor), "staging directory")
    if expected_count < 1:
        raise ValueError("expected firmware count must be positive")
    if not staging.is_dir():
        raise ValueError(f"staging directory not found: {staging}")
    entries = list(staging.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ValueError("staging must contain only flat firmware files")
    binaries = validate_metadata(entries, require_provenance)
    if len(binaries) != expected_count:
        raise ValueError(
            f"expected {expected_count} firmware files, found {len(entries)}"
        )
    return entries


def validate_existing_tree(destination: Path) -> list[Path]:
    if not destination.exists() and not destination.is_symlink():
        return []
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("existing firmware destination must be a real directory")
    entries = list(destination.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ValueError("existing firmware tree must contain only flat regular files")
    validate_metadata(entries)
    return entries


def install_firmware_tree(
    workspace: Path,
    firmware_root: Path,
    staging: Path,
    destination: Path,
    expected_count: int,
    mode: str,
    replace=os.replace,
    require_provenance=False,
) -> None:
    workspace = lexical_absolute(workspace)
    firmware_root = strict_child(firmware_root, workspace, "firmware root")
    destination = strict_child(destination, firmware_root, "firmware destination")
    files = validate_staging(staging, expected_count, require_provenance)
    existing_files = validate_existing_tree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    incoming = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.incoming-", dir=destination.parent
    ))
    backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
    moved_old = False
    try:
        if mode == "merge":
            for source in existing_files:
                shutil.copy2(source, incoming / source.name)
        for source in files:
            if source.suffix.lower() in ALLOWED_SUFFIXES:
                for suffix in ALLOWED_SUFFIXES:
                    (incoming / f"{source.stem}{suffix}").unlink(missing_ok=True)
                    (incoming / f"{source.stem}{suffix}.json").unlink(missing_ok=True)
        for source in files:
            shutil.copy2(source, incoming / source.name)

        if destination.exists():
            replace(destination, backup)
            moved_old = True
        try:
            replace(incoming, destination)
        except Exception:
            if moved_old:
                replace(backup, destination)
                moved_old = False
            raise
        if moved_old:
            shutil.rmtree(backup)
            moved_old = False
    finally:
        if incoming.exists():
            shutil.rmtree(incoming)
        if moved_old and backup.exists() and not destination.exists():
            replace(backup, destination)


def write_github_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            if UNSAFE_CONTROL.search(value):
                raise ValueError(f"unsafe control character in output {key}")
            output.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    paths = subparsers.add_parser("paths")
    paths.add_argument("--workspace", type=Path, required=True)
    paths.add_argument("--firmware-folder", required=True)
    paths.add_argument("--repository", required=True)
    paths.add_argument("--branch", required=True)
    paths.add_argument("--github-output", type=Path, required=True)
    install = subparsers.add_parser("install")
    install.add_argument("--workspace", type=Path, required=True)
    install.add_argument("--firmware-folder", required=True)
    install.add_argument("--staging", type=Path, required=True)
    install.add_argument("--destination", type=Path, required=True)
    install.add_argument("--expected-count", type=int, required=True)
    install.add_argument("--mode", choices=("replace", "merge"), required=True)
    install.add_argument("--require-provenance", action="store_true")
    args = parser.parse_args()
    if args.command == "paths":
        values = publish_paths(
            args.workspace, args.firmware_folder, args.repository, args.branch
        )
        write_github_output(args.github_output, values)
        return
    firmware_root = resolve_firmware_root(args.workspace, args.firmware_folder)
    install_firmware_tree(
        args.workspace, firmware_root, args.staging, args.destination,
        args.expected_count, args.mode,
        require_provenance=args.require_provenance,
    )


if __name__ == "__main__":
    main()
