# Benchmark Notes

These notes summarize internal runs made while building the local pipeline. They are useful for comparing relative tradeoffs on one machine, but they are not a vendor benchmark or a universal performance claim.

## Test environment

- Apple M4 Mac mini
- 16 GB unified memory
- ComfyUI using the local Apple Silicon path
- Wan2.2-TI2V-5B Q8 GGUF
- Python, OpenCV, and FFmpeg used for evaluation and delivery checks

## Full-body action study

The stable baseline used a 512x768, 81-frame, 24 fps, 20-step Wan2.2 request. A long prop arc repeatedly introduced broken prop topology, so the workflow was changed to body-heavy motion with limited prop displacement.

| Variation | Time | Optical-flow class | Automatic result | Human structure review |
|---|---:|---|---|---|
| Wide swing, initial composition | 2544.5 s | large | PASS | FAIL: camera drift and feet leaving frame |
| Reduced character scale | 2062.0 s | large | PASS | FAIL: prop drag and black artifacts |
| Prompt simplified to one swing | 2041.7 s | large | PASS | FAIL: prop ends repeatedly corrupted |
| Step-and-lunge with small prop motion | 2041.8 s | large | PASS | WARN: stable framing, slight face drift |
| Same action at 30 steps | 2942.5 s | moderate | PASS | FAIL: color artifacts and texture collapse |

The practical conclusion was to split fast impacts into several shots instead of asking one generation to contain an approach, strike, hit reaction, and result.

## Speed and quality tradeoffs

| Resolution and frames | Duration | Steps | Time | Relative speed | Intended use |
|---|---:|---:|---:|---:|---|
| 512x768 / 81 | 3.375 s | 20 | 2041.3 s | 1.00x | Quality baseline |
| 512x768 / 81 | 3.375 s | 4 | 420.4 s | 4.86x | Fast preview |
| 512x768 / 49 | 2.042 s | 4 | 300.5 s | 6.79x | Short preview |
| 448x672 / 61 | 2.542 s | 4 | 255.6 s | 7.99x | Balanced preview |
| 384x576 / 81 | 3.375 s | 4 | 225.2 s | 9.06x | Fast three-second preview |
| 416x608 / 73 | 3.042 s | 4 | 240.3 s | 8.50x | Composition-oriented preview |
| 384x576 / 61 | 2.542 s | 4 | 165.2 s | 12.36x | Fastest practical preview |

Decode and file-write costs are substantial at this scale. Reducing frames or dimensions often improves total turnaround more reliably than changing only the sampler step count.

## End-to-end validation short

The source project assembled an original 31-second vertical short from locally generated keyframes and short Wan2.2 clips.

- Output: 1080x1920, 30 fps, H.264
- Audio: AAC stereo, 48 kHz, approximately -14 LUFS, -1.1 dBTP true peak
- Captions: burned-in subtitles plus a `zho` soft-subtitle track
- Format checks: zero failures and zero warnings in the project's TikTok profile
- Content checks: zero percent black frames; longest frozen segment 2.4 seconds; 15% silence

Those checks prove format and decode compliance. They do not replace editorial review.

## Interpreting the evaluator

The evaluator is intentionally conservative but limited:

- Optical flow and frame differences can detect motion and freezes.
- Mean luminance can detect black frames.
- ffprobe and full decode checks catch malformed files.
- None of these metrics understand anatomy, identity, prop continuity, or story.

Every automated PASS must still be followed by a compressed contact-sheet review and, where needed, full editorial review.
