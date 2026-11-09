# ROCm and MI300X Validation Plan

## Objective

Evaluate whether the same ComfyUI-based image and video workflow can run reproducibly on a single AMD Instinct MI300X, and produce a reusable report covering setup, compatibility, performance, quality, and failure modes.

## Target environment

- One MI300X with 192 GB HBM3 through AMD Developer Cloud
- AMD AI Developer Program credit budget
- PyTorch and ComfyUI on ROCm
- Wan2.2 and Qwen-Image as the primary generative workloads

## Proposed work

1. Establish a minimal ROCm, PyTorch, ComfyUI, and FFmpeg smoke test.
2. Validate text-to-image keyframe generation with Qwen-Image.
3. Validate image-to-video generation with Wan2.2 under several bounded profiles.
4. Compare practical low-memory and high-quality configurations, including frame count, resolution, sampler steps, attention backend, and quantization format.
5. Measure end-to-end latency, GPU memory, host memory, startup overhead, output duration, task success rate, and common runtime failures.
6. Run the same motion, freeze, black-frame, and decode checks used in the Apple Silicon workflow.
7. Produce compressed visual review sheets and document quality differences that metrics alone cannot catch.

## Initial benchmark matrix

| Workload | Initial candidate | Purpose |
|---|---|---|
| Qwen-Image keyframe | 768x1344, representative step count | Image pipeline compatibility |
| Wan2.2 TI2V-5B | 384x576, 61 frames | Fast compatibility and quality baseline |
| Wan2.2 TI2V-5B | 512x768, 81 frames | Higher-quality single-clip comparison |
| Wan2.2 TI2V-5B | Official 704x1280, 121 frames | Stretch test, subject to time and stability |

Profiles will be reduced if they consume too much of the limited credit or fail to remain stable.

## Deliverables

- Reproducible environment notes and launch commands
- Sanitized scripts for the tested workload path
- Machine-readable benchmark summaries
- Contact sheets for visual comparison
- A report covering performance, quality, compatibility, and unresolved issues
- Clear separation between preview-quality and production-quality results

## Budget and safety

The initial `$100` credit is finite and expires after 30 days. The plan reserves a meaningful fraction for setup, driver checks, model loading, and retries.

- Power off is not treated as stopping billing; GPU instances must be destroyed.
- Large model downloads and storage are tracked separately from GPU credit.
- No private credentials, restricted datasets, or model weights will be published.
- Results will be reported only for configurations that actually run.

## Success criteria

- A clean MI300X environment can be reproduced from documented steps.
- At least one Wan2.2 image-to-video workload runs from the ComfyUI API path.
- Runtime and quality can be compared against the existing Apple Silicon measurements.
- The main compatibility limits are documented with actionable evidence.
