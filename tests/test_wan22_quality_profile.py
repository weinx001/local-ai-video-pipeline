from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from wan22_shots import OFFICIAL_TI2V_5B, build_graph, validate_shot  # noqa: E402


def production_shot(tmp_path: Path) -> dict:
    image = tmp_path / "frame.png"
    image.write_bytes(b"not-an-image-but-present")
    return {
        "name": "eye_contact",
        "image": image.name,
        "prompt": "悟空保持身体不动，只缓慢抬眼看向画面左下方，呼吸带动肩部轻微起伏。",
        "tier": "production",
        **OFFICIAL_TI2V_5B,
    }


def test_production_graph_uses_official_ti2v_5b_defaults(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)
    assert graph["55"]["inputs"]["width"] == 704
    assert graph["55"]["inputs"]["height"] == 1280
    assert graph["55"]["inputs"]["length"] == 121
    assert graph["3"]["inputs"]["steps"] == 50
    assert graph["3"]["inputs"]["cfg"] == 5.0
    assert graph["3"]["inputs"]["sampler_name"] == "uni_pc"
    assert graph["48"]["inputs"]["shift"] == 5.0
    assert graph["57"]["inputs"]["fps"] == 24



def test_production_accepts_official_landscape_size(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(width=1280, height=704)
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)
    assert graph["55"]["inputs"]["width"] == 1280
    assert graph["55"]["inputs"]["height"] == 704


def test_production_rejects_low_spec_recipe(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(width=512, height=768, length=41, steps=20, shift=8.0)
    with pytest.raises(ValueError, match="official TI2V-5B"):
        validate_shot(shot, tmp_path)


def test_production_rejects_long_i2v_prompt(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot["prompt"] = "悟空" * 51
    with pytest.raises(ValueError, match="100 Chinese characters"):
        validate_shot(shot, tmp_path)


def test_preview_can_use_reduced_resources(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(tier="preview", width=512, height=768, length=41, steps=20, shift=8.0, sampler_name="euler")
    validate_shot(shot, tmp_path)


def test_preview_accepts_custom_wan_compatible_size(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(tier="preview", width=384, height=576, length=49, steps=4, cfg=1.0)
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)
    assert graph["55"]["inputs"]["width"] == 384
    assert graph["55"]["inputs"]["height"] == 576


def test_preview_rejects_size_not_compatible_with_wan_latent_grid(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(tier="preview", width=390, height=576, length=49, steps=4, cfg=1.0)
    with pytest.raises(ValueError, match="multiples of 32"):
        validate_shot(shot, tmp_path)


def test_preview_graph_can_apply_model_only_lora(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(
        tier="preview",
        width=512,
        height=768,
        length=41,
        steps=4,
        cfg=1.0,
        shift=5.0,
        lora_name="turbo.safetensors",
        lora_strength=0.8,
    )
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)

    assert graph["60"]["class_type"] == "LoraLoaderModelOnly"
    assert graph["60"]["inputs"] == {
        "model": ["37", 0],
        "lora_name": "turbo.safetensors",
        "strength_model": 0.8,
    }
    assert graph["48"]["inputs"]["model"] == ["60", 0]


def test_preview_graph_can_anchor_end_frame_and_custom_negative(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    end_image = tmp_path / "end.png"
    end_image.write_bytes(b"not-an-image-but-present")
    middle_image = tmp_path / "middle.png"
    middle_image.write_bytes(b"not-an-image-but-present")
    shot.update(
        tier="preview",
        width=512,
        height=768,
        length=61,
        steps=6,
        cfg=1.0,
        middle_image=middle_image.name,
        end_image=end_image.name,
        negative_prompt="镜头移动，金箍棒断裂",
    )
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)

    assert graph["59"]["class_type"] == "LoadImage"
    assert graph["59"]["inputs"]["image"] == end_image.name
    assert graph["61"]["class_type"] == "LoadImage"
    assert graph["61"]["inputs"]["image"] == middle_image.name
    assert graph["55"]["class_type"] == "XiyouWan22FirstLastFrameToVideoLatent"
    assert graph["55"]["inputs"]["start_image"] == ["56", 0]
    assert graph["55"]["inputs"]["middle_image"] == ["61", 0]
    assert graph["55"]["inputs"]["end_image"] == ["59", 0]
    assert graph["3"]["inputs"]["positive"] == ["6", 0]
    assert graph["3"]["inputs"]["negative"] == ["7", 0]
    assert graph["3"]["inputs"]["latent_image"] == ["55", 0]
    assert graph["7"]["inputs"]["text"] == "镜头移动，金箍棒断裂"


def test_preview_graph_can_select_model_and_apply_camera_conditioning(tmp_path: Path) -> None:
    shot = production_shot(tmp_path)
    shot.update(
        tier="preview",
        unet_name="Wan2.2-Fun-5B-Control-Camera-Q4_K_M.gguf",
        width=384,
        height=576,
        length=49,
        steps=4,
        cfg=1.0,
        camera_pose="Static",
        camera_speed=1.0,
    )
    validate_shot(shot, tmp_path)
    graph = build_graph(shot)

    assert graph["37"]["inputs"]["unet_name"] == "Wan2.2-Fun-5B-Control-Camera-Q4_K_M.gguf"
    assert graph["63"]["class_type"] == "WanCameraEmbedding"
    assert graph["63"]["inputs"]["camera_pose"] == "Static"
    assert graph["63"]["inputs"]["length"] == 49
    assert graph["64"]["class_type"] == "XiyouWan22CameraConditioning"
    assert graph["64"]["inputs"]["camera_conditions"] == ["63", 0]
    assert graph["3"]["inputs"]["positive"] == ["64", 0]
    assert graph["3"]["inputs"]["negative"] == ["64", 1]
