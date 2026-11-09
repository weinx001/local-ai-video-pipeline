#!/usr/bin/env python3
"""Independently measure Wan2.2 motion, freeze, black frames and decode integrity."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np


MAX_ANALYSIS_WIDTH = 320
FREEZE_MAE_THRESHOLD = 0.4


def resolve_ffprobe() -> str:
    configured = os.environ.get("FFPROBE_BIN")
    if configured:
        return configured
    local = Path.home() / "workspace" / "ffmpeg-full" / "ffprobe"
    if local.is_file():
        return str(local)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise RuntimeError("ffprobe not found; set FFPROBE_BIN or add ffprobe to PATH")


def probe(path: Path) -> dict:
    ffprobe = resolve_ffprobe()
    result = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries",
            "format=duration,size:stream=index,codec_name,codec_type,width,height,r_frame_rate,avg_frame_rate",
            "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def classify_motion(mean_flow: float) -> str:
    if mean_flow < 0.05:
        return "static"
    if mean_flow < 0.35:
        return "micro"
    if mean_flow < 1.0:
        return "moderate"
    return "large"


def evaluate_video(path: Path) -> dict:
    path = Path(path).resolve()
    metadata = probe(path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV cannot open {path}")

    previous_gray: np.ndarray | None = None
    flow_means: list[float] = []
    frame_maes: list[float] = []
    black_frames = 0
    frozen_pairs = 0
    frame_count = 0
    first_gray: np.ndarray | None = None
    last_gray: np.ndarray | None = None

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frame_count += 1
        if frame.shape[1] > MAX_ANALYSIS_WIDTH:
            scale = MAX_ANALYSIS_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if first_gray is None:
            first_gray = gray.copy()
        last_gray = gray
        if float(gray.mean()) < 8.0:
            black_frames += 1
        if previous_gray is not None:
            mae = float(cv2.absdiff(previous_gray, gray).mean())
            frame_maes.append(mae)
            if mae < FREEZE_MAE_THRESHOLD:
                frozen_pairs += 1
            flow = cv2.calcOpticalFlowFarneback(
                previous_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            magnitude = cv2.magnitude(flow[..., 0], flow[..., 1])
            flow_means.append(float(magnitude.mean()))
        previous_gray = gray

    capture.release()
    if frame_count == 0 or first_gray is None or last_gray is None:
        raise RuntimeError(f"no decodable frames in {path}")

    pair_count = max(len(flow_means), 1)
    freeze_ratio = frozen_pairs / pair_count
    black_ratio = black_frames / frame_count
    whole_mae = float(cv2.absdiff(first_gray, last_gray).mean())
    height, width = first_gray.shape
    cy0, cy1 = height // 4, height - height // 4
    cx0, cx1 = width // 4, width - width // 4
    center_mae = float(cv2.absdiff(first_gray[cy0:cy1, cx0:cx1], last_gray[cy0:cy1, cx0:cx1]).mean())
    mean_flow = float(np.mean(flow_means)) if flow_means else 0.0
    p95_flow = float(np.percentile(flow_means, 95)) if flow_means else 0.0
    median_flow = float(np.median(flow_means)) if flow_means else 0.0
    motion_class = classify_motion(mean_flow)

    failures: list[str] = []
    warnings: list[str] = []
    if freeze_ratio > 0.5:
        failures.append("more than half of consecutive frames are frozen")
    if black_ratio > 0.8:
        failures.append("more than 80% of frames are black")
    if motion_class == "static":
        warnings.append("motion is below the actionable threshold")
    status = "FAIL" if failures else "PASS"

    stream = next(
        item for item in metadata["streams"]
        if item.get("codec_type") == "video"
    )
    return {
        "path": str(path),
        "status": status,
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": stream.get("avg_frame_rate") or stream.get("r_frame_rate"),
        "duration_seconds": float(metadata["format"]["duration"]),
        "size_bytes": int(metadata["format"]["size"]),
        "decoded_frames": frame_count,
        "motion": {
            "mean_flow": round(mean_flow, 6),
            "median_flow": round(median_flow, 6),
            "p95_flow": round(p95_flow, 6),
            "class": motion_class,
        },
        "freeze_ratio": round(freeze_ratio, 6),
        "black_ratio": round(black_ratio, 6),
        "first_last_mae": round(whole_mae, 6),
        "center_first_last_mae": round(center_mae, 6),
        "failures": failures,
        "warnings": warnings,
        "manual_structure_review_required": True,
        "metric_scope": "whole-frame analysis; identity and anatomy require contact-sheet review",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = evaluate_video(args.video)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
