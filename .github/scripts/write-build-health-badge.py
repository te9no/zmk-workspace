#!/usr/bin/env python3
import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def safe_path_segment(value: str) -> str:
    value = re.sub(r'[":<>|*?\\/]+', "-", value or "")
    value = value.strip(". ")
    return value or "unknown"


def normalize_status(status: str) -> tuple[str, str]:
    status = (status or "unknown").lower()
    if status in {"success", "succeeded", "passed", "pass"}:
        return "passing", "#2ea44f"
    if status in {"failure", "failed", "timed_out", "action_required"}:
        return "failing", "#d73a49"
    if status in {"cancelled", "canceled"}:
        return "cancelled", "#6a737d"
    if status == "skipped":
        return "skipped", "#6a737d"
    return "unknown", "#dbab09"


def svg_badge(label: str, message: str, color: str) -> str:
    label_width = max(len(label) * 7 + 10, 78)
    message_width = max(len(message) * 7 + 10, 70)
    width = label_width + message_width
    escaped_label = html.escape(label)
    escaped_message = html.escape(message)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{escaped_label}: {escaped_message}">
  <title>{escaped_label}: {escaped_message}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{message_width}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="{label_width * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(label_width - 10) * 10}">{escaped_label}</text>
    <text x="{label_width * 5}" y="140" transform="scale(.1)" fill="#fff" textLength="{(label_width - 10) * 10}">{escaped_label}</text>
    <text aria-hidden="true" x="{(label_width + message_width / 2) * 10}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(message_width - 10) * 10}">{escaped_message}</text>
    <text x="{(label_width + message_width / 2) * 10}" y="140" transform="scale(.1)" fill="#fff" textLength="{(message_width - 10) * 10}">{escaped_message}</text>
  </g>
</svg>
"""


def append_outputs(path: str | None, outputs: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as file:
        for key, value in outputs.items():
            file.write(f"{key}={value}\n")


def append_summary(path: str | None, data: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as file:
        file.write("## Build Health Badge\n\n")
        file.write(f"- Repository: `{data['repository']}`\n")
        file.write(f"- Branch: `{data['branch']}`\n")
        file.write(f"- Target: `{data['target']}`\n")
        file.write(f"- Status: **{data['status']}**\n")
        file.write(f"- Folder: `{data['badge_dir']}`\n")
        file.write(f"- SVG: `{data['badge_svg']}`\n")
        file.write(f"- Shields endpoint: `{data['endpoint_json']}`\n")
        file.write(f"- Generated at: `{data['generated_at']}`\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", default="unknown")
    parser.add_argument("--target", default="all")
    parser.add_argument("--repo", default="unknown/unknown")
    parser.add_argument("--branch", default="unknown")
    parser.add_argument("--sha", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-number", default="")
    parser.add_argument("--server-url", default="")
    parser.add_argument("--folder", default="badges/build-health")
    parser.add_argument("--github-output", default="")
    parser.add_argument("--github-summary", default="")
    args = parser.parse_args()

    repo_name = args.repo.split("/")[-1] if args.repo else "unknown"
    safe_repo = safe_path_segment(repo_name)
    safe_branch = safe_path_segment(args.branch)
    status, color = normalize_status(args.status)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_url = f"{args.server_url}/{args.repo}/actions/runs/{args.run_id}" if args.server_url and args.repo and args.run_id else ""

    badge_dir = Path(args.folder) / safe_repo / safe_branch
    badge_dir.mkdir(parents=True, exist_ok=True)

    health = {
        "repository": args.repo,
        "branch": args.branch,
        "target": args.target,
        "status": status,
        "raw_status": args.status,
        "color": color,
        "sha": args.sha,
        "run_id": args.run_id,
        "run_number": args.run_number,
        "run_url": run_url,
        "generated_at": generated_at,
    }
    endpoint = {
        "schemaVersion": 1,
        "label": "build",
        "message": status,
        "color": color.removeprefix("#"),
        "namedLogo": "githubactions",
    }

    health_path = badge_dir / "build-health.json"
    endpoint_path = badge_dir / "shields.json"
    svg_path = badge_dir / "build-health.svg"

    health_path.write_text(json.dumps(health, indent=2) + "\n", encoding="utf-8")
    endpoint_path.write_text(json.dumps(endpoint, indent=2) + "\n", encoding="utf-8")
    svg_path.write_text(svg_badge("build", status, color), encoding="utf-8")

    outputs = {
        "badge_dir": str(badge_dir),
        "badge_svg": str(svg_path),
        "endpoint_json": str(endpoint_path),
        "health_json": str(health_path),
    }
    append_outputs(args.github_output, outputs)
    append_summary(
        args.github_summary,
        {
            "repository": args.repo,
            "branch": args.branch,
            "target": args.target,
            "status": status,
            "generated_at": generated_at,
            **outputs,
        },
    )

    print(f"Wrote {health_path}")
    print(f"Wrote {endpoint_path}")
    print(f"Wrote {svg_path}")


if __name__ == "__main__":
    main()
