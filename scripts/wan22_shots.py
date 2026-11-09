#!/usr/bin/env python3
"""Submit Wan2.2 TI2V shots serially to the local ComfyUI server."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
    "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
    "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
    "杂乱的背景，三条腿，背景人很多，倒着走"
)

OPENERS = {scheme: urllib.request.build_opener(urllib.request.ProxyHandler({}))
           for scheme in ("http", "https")}

OFFICIAL_TI2V_5B = {
    "width": 704,
    "height": 1280,
    "length": 121,
    "fps": 24,
    "steps": 50,
    "cfg": 5.0,
    "shift": 5.0,
    "sampler_name": "uni_pc",
    "scheduler": "simple",
}

OFFICIAL_TI2V_5B_SIZES = {(704, 1280), (1280, 704)}
PREVIEW_DIMENSION_MULTIPLE = 32
PREVIEW_MIN_DIMENSION = 256
PREVIEW_MAX_DIMENSION = 2048


def api(base: str, path: str, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    opener = OPENERS[urllib.parse.urlsplit(base).scheme]
    with opener.open(request, timeout=30) as response:
        body = response.read()
    return json.loads(body) if body else {}


def build_graph(shot: dict) -> dict:
    length = shot.get("length", 121)
    fps = shot.get("fps", 24)
    steps = shot.get("steps", 50)
    cfg = shot.get("cfg", 5.0)
    shift = shot.get("shift", 5.0)
    sampler_name = shot.get("sampler_name", "uni_pc")
    scheduler = shot.get("scheduler", "simple")
    negative_prompt = shot.get("negative_prompt", NEGATIVE_PROMPT)
    model_source = ["37", 0]
    graph = {
        "37": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": shot.get("unet_name", "Wan2.2-TI2V-5B-Q8_0.gguf")},
        },
        "38": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "device": "default",
                "type": "wan",
            },
        },
        "39": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "wan2.2_vae.safetensors"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": shot["prompt"], "clip": ["38", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["38", 0]},
        },
        "48": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"shift": shift, "model": model_source},
        },
        "56": {
            "class_type": "LoadImage",
            "inputs": {"image": shot["image"]},
        },
        "55": {
            "class_type": "Wan22ImageToVideoLatent",
            "inputs": {
                "width": shot.get("width", 512),
                "height": shot.get("height", 768),
                "length": length,
                "batch_size": 1,
                "vae": ["39", 0],
                "start_image": ["56", 0],
            },
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["48", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["55", 0],
                "seed": shot.get("seed", 777),
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["39", 0]},
        },
        "57": {
            "class_type": "CreateVideo",
            "inputs": {"fps": fps, "images": ["8", 0]},
        },
        "58": {
            "class_type": "SaveVideo",
            "inputs": {
                "filename_prefix": shot["name"],
                "codec": "auto",
                "format": "auto",
                "video": ["57", 0],
            },
        },
    }
    if shot.get("lora_name"):
        graph["60"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["37", 0],
                "lora_name": shot["lora_name"],
                "strength_model": shot.get("lora_strength", 1.0),
            },
        }
        graph["48"]["inputs"]["model"] = ["60", 0]
    if shot.get("end_image"):
        if shot.get("middle_image"):
            graph["61"] = {
                "class_type": "LoadImage",
                "inputs": {"image": shot["middle_image"]},
            }
        graph["59"] = {
            "class_type": "LoadImage",
            "inputs": {"image": shot["end_image"]},
        }
        graph["55"] = {
            "class_type": "XiyouWan22FirstLastFrameToVideoLatent",
            "inputs": {
                "vae": ["39", 0],
                "width": shot.get("width", 512),
                "height": shot.get("height", 768),
                "length": length,
                "batch_size": 1,
                "start_image": ["56", 0],
                "end_image": ["59", 0],
            },
        }
        if shot.get("middle_image"):
            graph["55"]["inputs"]["middle_image"] = ["61", 0]
        graph["3"]["inputs"]["latent_image"] = ["55", 0]
    if shot.get("camera_pose"):
        graph["63"] = {
            "class_type": "WanCameraEmbedding",
            "inputs": {
                "camera_pose": shot["camera_pose"],
                "width": shot.get("width", 512),
                "height": shot.get("height", 768),
                "length": length,
                "speed": shot.get("camera_speed", 1.0),
            },
        }
        graph["64"] = {
            "class_type": "XiyouWan22CameraConditioning",
            "inputs": {
                "positive": graph["3"]["inputs"]["positive"],
                "negative": graph["3"]["inputs"]["negative"],
                "camera_conditions": ["63", 0],
            },
        }
        graph["3"]["inputs"]["positive"] = ["64", 0]
        graph["3"]["inputs"]["negative"] = ["64", 1]
    return graph


def assert_queue_empty(base: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while True:
        queue = api(base, "/queue")
        if not queue.get("queue_running") and not queue.get("queue_pending"):
            return
        if time.time() >= deadline:
            raise RuntimeError("ComfyUI queue did not become empty before the timeout")
        time.sleep(15)


def output_paths(history_item: dict) -> list[str]:
    names: list[str] = []
    for node_output in history_item.get("outputs", {}).values():
        for key in ("videos", "gifs", "images"):
            for item in node_output.get(key, []) or []:
                filename = item.get("filename")
                if filename and filename.lower().endswith((".mp4", ".webm", ".mov")):
                    names.append(filename)
    return names


def submit_and_wait(base: str, shot: dict, output_dir: Path,
                    timeout: int, poll_seconds: int) -> dict:
    graph = build_graph(shot)
    client_id = str(uuid.uuid4())
    response = api(base, "/prompt", method="POST", payload={
        "prompt": graph,
        "client_id": client_id,
    })
    if response.get("node_errors"):
        raise RuntimeError(f"ComfyUI rejected the graph: {response['node_errors']}")
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI returned no prompt_id: {response}")

    started = time.time()
    deadline = started + timeout
    while time.time() < deadline:
        history = api(base, f"/history/{prompt_id}")
        item = history.get(prompt_id)
        if item:
            status = item.get("status", {})
            status_str = status.get("status_str", "unknown")
            if status_str == "error":
                raise RuntimeError(f"ComfyUI job failed: {status}")
            if status_str == "success" or output_paths(item):
                names = output_paths(item)
                if not names:
                    raise RuntimeError("ComfyUI reported success but returned no video")
                paths = [str(output_dir / name) for name in names]
                missing = [path for path in paths if not Path(path).is_file()]
                if missing:
                    raise RuntimeError(f"ComfyUI output missing on disk: {missing}")
                return {
                    "prompt_id": prompt_id,
                    "status": status_str,
                    "elapsed_seconds": round(time.time() - started, 1),
                    "outputs": paths,
                }
        time.sleep(poll_seconds)
    raise TimeoutError(f"Wan2.2 job {prompt_id} exceeded {timeout}s")


def load_shots(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    shots = data.get("shots") if isinstance(data, dict) else data
    if not isinstance(shots, list) or not shots:
        raise ValueError("shots file must contain a non-empty shots list")
    return shots


def validate_shot(shot: dict, input_dir: Path) -> None:
    required = ("name", "image", "prompt", "tier")
    missing = [key for key in required if not shot.get(key)]
    if missing:
        raise ValueError(f"shot missing required keys: {missing}")
    if not (input_dir / shot["image"]).is_file():
        raise FileNotFoundError(input_dir / shot["image"])
    if shot.get("end_image") and not (input_dir / shot["end_image"]).is_file():
        raise FileNotFoundError(input_dir / shot["end_image"])
    if shot.get("middle_image") and not (input_dir / shot["middle_image"]).is_file():
        raise FileNotFoundError(input_dir / shot["middle_image"])
    width, height = shot.get("width", 512), shot.get("height", 768)
    dimensions_are_valid = all(
        isinstance(value, int)
        and PREVIEW_MIN_DIMENSION <= value <= PREVIEW_MAX_DIMENSION
        and value % PREVIEW_DIMENSION_MULTIPLE == 0
        for value in (width, height)
    )
    if not dimensions_are_valid:
        raise ValueError(
            "preview width and height must be integers between "
            f"{PREVIEW_MIN_DIMENSION} and {PREVIEW_MAX_DIMENSION} "
            f"and multiples of {PREVIEW_DIMENSION_MULTIPLE}"
        )
    length = shot.get("length", 121)
    if length < 5 or (length - 1) % 4:
        raise ValueError("Wan2.2 length must be a 4n+1 frame count")
    if shot["tier"] not in {"preview", "production"}:
        raise ValueError("tier must be preview or production")
    if shot["tier"] == "production":
        actual = {
            key: shot.get(key, OFFICIAL_TI2V_5B[key])
            for key in OFFICIAL_TI2V_5B
        }
        actual_size = (actual.pop("width"), actual.pop("height"))
        expected = dict(OFFICIAL_TI2V_5B)
        expected.pop("width")
        expected.pop("height")
        if actual_size not in OFFICIAL_TI2V_5B_SIZES or actual != expected:
            raise ValueError(f"production shots must match official TI2V-5B profile: {OFFICIAL_TI2V_5B}")
        if len(shot["prompt"].strip()) > 100:
            raise ValueError("production I2V prompt must be 100 Chinese characters or fewer")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, required=True)
    parser.add_argument("--base", default="http://127.0.0.1:8188")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--name", action="append", help="only run the named shot")
    parser.add_argument("--resume", action="store_true", help="skip successful completed shots")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--queue-timeout", type=int, default=7200)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()

    shots = load_shots(args.shots)
    selected = set(args.name or [])
    if selected:
        shots = [shot for shot in shots if shot.get("name") in selected]
    if not shots:
        raise ValueError("no matching shots")

    args.runs_dir.mkdir(parents=True, exist_ok=True)
    for shot in shots:
        validate_shot(shot, args.input_dir)
        graph = build_graph(shot)
        if args.dry_run:
            print(json.dumps(shot, ensure_ascii=False, indent=2))
            print(json.dumps(graph, ensure_ascii=False, indent=2))
            continue

        manifest = args.runs_dir / f"{shot['name']}.json"
        if args.resume and manifest.is_file():
            previous = json.loads(manifest.read_text(encoding="utf-8"))
            outputs = previous.get("outputs", [])
            if previous.get("status") == "success" and outputs and all(Path(p).is_file() for p in outputs):
                print(f"skip completed: {shot['name']}")
                continue

        assert_queue_empty(args.base, args.queue_timeout)
        print(f"submit: {shot['name']} seed={shot.get('seed', 777)}", flush=True)
        result = submit_and_wait(args.base, shot, args.output_dir, args.timeout, args.poll_seconds)
        record = {"shot": shot, "status": "success", **result}
        manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
