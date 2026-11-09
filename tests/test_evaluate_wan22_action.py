from __future__ import annotations

import subprocess
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_wan22_action import evaluate_video  # noqa: E402


LOCAL_FFMPEG = Path.home() / "workspace" / "ffmpeg-full" / "ffmpeg"
FFMPEG = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg") or str(LOCAL_FFMPEG)


def make_motion_video(path: Path, x_expression: str) -> None:
    command = [
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1:r=12",
        "-f", "lavfi", "-i", "color=c=white:s=40x40:d=1:r=12",
        "-filter_complex", f"[0:v][1:v]overlay=x={x_expression}:y=40,format=yuv420p",
        "-an", str(path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def test_evaluator_distinguishes_static_and_large_motion(tmp_path: Path) -> None:
    static = tmp_path / "static.mp4"
    moving = tmp_path / "moving.mp4"
    make_motion_video(static, "40")
    make_motion_video(moving, "'20+100*t'")

    static_result = evaluate_video(static)
    moving_result = evaluate_video(moving)

    assert static_result["status"] == "FAIL"
    assert static_result["freeze_ratio"] > 0.5
    assert moving_result["motion"]["mean_flow"] > static_result["motion"]["mean_flow"] * 5
    assert moving_result["freeze_ratio"] < 0.5
