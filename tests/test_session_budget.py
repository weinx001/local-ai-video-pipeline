from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from session_budget import ORANGE_LIMIT, RED_LIMIT, classify, inspect_rollout  # noqa: E402


def test_classify_has_three_guarded_regions():
    assert classify(1)[0] == "GREEN"
    assert classify(9 * 1024 * 1024)[0] == "YELLOW"
    assert classify(ORANGE_LIMIT)[0] == "ORANGE"
    assert classify(RED_LIMIT)[0] == "RED"


def test_inspect_rollout_counts_embedded_images(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    image_record = {
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "output": [{
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,AAAA",
            }],
        },
    }
    text_record = {
        "type": "response_item",
        "payload": {"type": "function_call_output", "output": "short text"},
    }
    rollout.write_text(
        "\n".join(json.dumps(item) for item in (image_record, text_record)) + "\n",
        encoding="utf-8",
    )
    result = inspect_rollout(rollout)
    assert result["image_items"] == 1
    assert result["image_payload_bytes"] == len("data:image/jpeg;base64,AAAA")
    assert result["status"] == "GREEN"
