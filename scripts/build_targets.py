#!/usr/bin/env python3
"""Parse ZMK build.yaml targets for local recipes.

The public CSV format is retained for compatibility. Internal callers use one
compact JSON object per line so values such as cmake-args are not truncated.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import shlex
import sys
from pathlib import Path

import yaml


FIELDS = ("board", "shield", "snippet", "artifact-name", "cmake-args")


def as_values(value):
    if value is None:
        return [None]
    return value if isinstance(value, list) else [value]


def targets_from(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    targets = []
    base = [as_values(data.get(field)) for field in FIELDS]
    if base[0] != [None]:
        for values in itertools.product(*base):
            targets.append({field: value for field, value in zip(FIELDS, values)
                            if value is not None})
    for entry in data.get("include", []) or []:
        if not isinstance(entry, dict):
            raise ValueError("each build.yaml include entry must be a mapping")
        targets.append({field: entry[field] for field in FIELDS if entry.get(field) is not None})
    return targets


def with_cmake_argv(target):
    result = dict(target)
    raw = result.get("cmake-args", "")
    if not isinstance(raw, str):
        raise ValueError("cmake-args must be a shell-style string")
    try:
        result["cmake-argv"] = shlex.split(raw)
    except ValueError as error:
        raise ValueError(f"invalid cmake-args: {error}") from error
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("build_yaml", type=Path)
    parser.add_argument("expression")
    parser.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    args = parser.parse_args()

    pattern = ".*" if args.expression.lower() == "all" else args.expression
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        for target in targets_from(args.build_yaml):
            searchable = " ".join(str(target.get(field, ""))
                                  for field in FIELDS[:4])
            if not regex.search(searchable):
                continue
            if args.format == "jsonl":
                target = with_cmake_argv(target)
                print(json.dumps(target, ensure_ascii=False, separators=(",", ":")))
            else:
                print(",".join(str(target.get(field, "")) for field in FIELDS[:4]))
    except (OSError, re.error, ValueError, yaml.YAMLError) as error:
        print(f"build target error: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
