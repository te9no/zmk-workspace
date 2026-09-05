#!/usr/bin/env python3
"""Record build inputs before compiling; bind unchanged inputs to an artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.PIPE)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git_state(root, paths=None):
    root = Path(root)
    spec = paths or ['.', ':(exclude)firmware', ':(exclude)keymap-svg',
                     ':(exclude)keymap-drawer', ':(exclude)badges']
    sha = run('git', '-C', str(root), 'rev-parse', 'HEAD').decode().strip()
    delta = run('git', '-C', str(root), 'diff', '--binary', 'HEAD', '--', *spec)
    untracked = run('git', '-C', str(root), 'ls-files', '-z', '--others',
                    '--exclude-standard', '--', *spec).decode().split('\0')
    extras = {name: digest(root / name) for name in untracked if name}
    return {'commit': sha, 'dirty': bool(delta or extras),
            'diff_sha256': hashlib.sha256(delta).hexdigest(), 'untracked': extras}


def snapshot(source, west, tools):
    # Only build inputs: public metadata never includes local absolute paths or diff contents.
    config = git_state(source, ['config', 'boards', 'snippets', 'src', 'include', 'dts',
                               'zephyr', 'Kconfig', 'CMakeLists.txt', 'build.yaml'])
    dependencies = {}
    projects = run('west', 'list', '-f', '{name}\t{abspath}', cwd=west).decode()
    for row in projects.splitlines():
        name, path = row.split('\t', 1)
        if name == 'manifest':
            continue
        dependencies[name] = git_state(path)
    return {'source': config, 'dependencies': dependencies,
            'workspace_tools': git_state(tools, ['scripts', '.github/scripts', 'Justfile', 'just.sh'])}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def verify_publish(source, current, root, firmware_folder='firmware'):
    # Allow generated commits, but never attach an old binary to different source.
    subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', source, current],
                   check=True, capture_output=True)
    changed = run('git', '-C', str(root), 'diff', '--name-only', source, current,
                  '--', '.', f':(exclude){firmware_folder}', ':(exclude)keymap-svg',
                  ':(exclude)keymap-drawer', ':(exclude)badges')
    if changed.strip():
        raise ValueError('Branch source changed during build; refusing stale firmware publish')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['capture', 'finish', 'guard'])
    parser.add_argument('--source', required=True)
    parser.add_argument('--west')
    parser.add_argument('--tools', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--record', type=Path)
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--target', default='{}')
    parser.add_argument('--name')
    parser.add_argument('--current')
    parser.add_argument('--root', default='.')
    parser.add_argument('--firmware-folder', default='firmware')
    args = parser.parse_args()
    if args.command == 'guard':
        verify_publish(args.source, args.current, args.root, args.firmware_folder)
        return
    current = snapshot(args.source, args.west, args.tools)
    if args.command == 'capture':
        write_json(args.record, current)
        return
    if json.loads(args.record.read_text(encoding='utf-8')) != current:
        raise ValueError('Build inputs changed while compiling; rebuild before publishing')
    metadata = {'schema': 1, 'inputs': current, 'target': json.loads(args.target),
                'artifact': {'name': args.name or args.artifact.name, 'sha256': digest(args.artifact)},
                'generated': {name: digest(args.build / 'zephyr' / name)
                              for name in ('.config', 'zephyr.dts')}}
    if os.environ.get('GITHUB_RUN_ID'):
        metadata['run_id'] = os.environ['GITHUB_RUN_ID']
    write_json(str(args.artifact) + '.json', metadata)


if __name__ == '__main__':
    main()
