#!/usr/bin/env python3
"""Report Codex session size with a hard warning before the 32 MB upstream limit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


MIB = 1024 * 1024
GREEN_LIMIT = 8 * MIB
ORANGE_LIMIT = 16 * MIB
RED_LIMIT = 24 * MIB


def find_rollout(session_id: str | None, codex_home: Path) -> Path:
    pattern = f"*{session_id}*.jsonl" if session_id else "rollout-*.jsonl"
    candidates = list((codex_home / "sessions").rglob(pattern))
    if not candidates:
        raise FileNotFoundError(f"no rollout found under {codex_home / 'sessions'}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def classify(size_bytes: int) -> tuple[str, str]:
    if size_bytes >= RED_LIMIT:
        return "RED", "stop this session now, write the stage result, and start a new chat"
    if size_bytes >= ORANGE_LIMIT:
        return "ORANGE", "no more images; finish the current text-only step, then start a new chat"
    if size_bytes >= GREEN_LIMIT:
        return "YELLOW", "one final compressed contact sheet only; never open individual images"
    return "GREEN", "continue, but keep image viewing to one compressed contact sheet per stage"


def inspect_rollout(path: Path) -> dict[str, int | float | str]:
    image_bytes = 0
    image_items = 0
    function_output_bytes = 0
    malformed_lines = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                malformed_lines += 1
                continue
            if record.get("type") != "response_item":
                continue
            payload = record.get("payload") or {}
            if payload.get("type") != "function_call_output":
                continue
            output = payload.get("output")
            function_output_bytes += len(
                json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if not isinstance(output, list):
                continue
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "input_image":
                    continue
                image_url = item.get("image_url") or ""
                if isinstance(image_url, str) and image_url:
                    image_items += 1
                    image_bytes += len(image_url.encode("utf-8"))

    size_bytes = path.stat().st_size
    status, action = classify(size_bytes)
    return {
        "rollout": str(path),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / MIB, 2),
        "image_payload_bytes": image_bytes,
        "image_payload_mb": round(image_bytes / MIB, 2),
        "image_items": image_items,
        "function_output_bytes": function_output_bytes,
        "malformed_lines": malformed_lines,
        "status": status,
        "action": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", help="exact Codex thread/session id")
    parser.add_argument("--rollout", type=Path, help="explicit rollout JSONL path")
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    parser.add_argument("--strict", action="store_true", help="exit nonzero at ORANGE or RED")
    args = parser.parse_args()

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    try:
        session_id = args.session_id or os.environ.get("CODEX_THREAD_ID")
        rollout = args.rollout or find_rollout(session_id, codex_home)
        result = inspect_rollout(rollout)
    except (FileNotFoundError, OSError) as exc:
        print(f"session_budget: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"rollout={result['rollout']}")
        print(f"size_mb={result['size_mb']} status={result['status']}")
        print(
            "image_payload_mb="
            f"{result['image_payload_mb']} image_items={result['image_items']}"
        )
        print(f"action={result['action']}")

    if args.strict and result["status"] in {"ORANGE", "RED"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
