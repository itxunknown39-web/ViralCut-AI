# ViralCut AI — Project Completion Lock & Change-Control Contract

This document serves as the authoritative, permanent change-control contract for **ViralCut AI**. It tracks verified, locked subsystems, architectural decisions, and regression prevention rules.

---

## 🔒 Master Principles & Rules

1. **Verified Core Rule**: NEVER modify a feature that has already been verified and marked `LOCKED` unless required by a dependency or a confirmed bug with reproducible trace logs.
2. **No Aesthetic Refactoring**: NEVER replace working architecture merely for style or personal preference.
3. **No Unverified Claims**: NEVER claim a feature is complete without empirical, automated runtime testing.
4. **Mandatory Test Loop**: Every task must follow: `DISCOVER` → `TRACE` → `IMPLEMENT` → `TEST` → `REGRESSION CHECK` → `LOCK`.
5. **Caption Guard**: If an ASS subtitle file generates 0 dialogue events (`Dialogue count == 0`), rendering MUST abort with a descriptive diagnostic error rather than producing a captionless output video.
6. **Hardware Acceleration**: Always prefer NVIDIA NVENC (`h264_nvenc`) on T4 GPU with CUDA float16 Whisper transcription.
7. **Composition Integrity**: Preserve the bottom black gradient overlay, cinematic color grades, vignette, zoom/punch-in, background music mixing, and audio ducking as part of the unified CapCut-style short-form editing engine.

---

## 🔒 Subsystem Lock Registry

| Subsystem ID | Component | Status | Verification & Guard Details |
|---|---|---|---|
| **SUB-01** | **Download & Probe Engine** | `LOCKED` | HD 1080p priority (`yt-dlp`), non-temp file handoff validation, `.part`/`.ytdl` safety guard, `ffprobe` stream validation. |
| **SUB-02** | **Transcription Engine** | `LOCKED` | Faster-Whisper on CUDA float16, word-level timestamps, cached transcript reuse. |
| **SUB-03** | **Clip Selection Engine** | `LOCKED` | Timestamp range extraction (`source_start` to `source_end`), window scoring. |
| **SUB-04** | **Caption Serialization** | `LOCKED` | 29-property payload builder in `Create.jsx`, Pydantic `CaptionOverrides`, `exclude_none=True` model dump. |
| **SUB-05** | **ASS Subtitle Renderer** | `LOCKED` | `captions.build_ass()`, main layer dialogue row generation, relative timestamp mapping (`ev["start"] - clip_start`), word-level highlight animation (`\1c...\t(...)`). |
| **SUB-06** | **ASS Pre-Render Validator** | `LOCKED` | Auto-inspection of generated ASS file prior to FFmpeg invocation (`dialogue_count > 0` validation). |
| **SUB-07** | **Composition & Effects Engine** | `LOCKED` | Unified FFmpeg filter complex: crop/square mode, bottom black gradient overlay, top gradient, vignette, color grade, signature watermark. |
| **SUB-08** | **Audio & Music Engine** | `LOCKED` | Background music track mixing, automatic speech ducking via sidechain compressor. |
| **SUB-09** | **Hardware Render Engine** | `LOCKED` | NVIDIA NVENC GPU acceleration (`-c:v h264_nvenc -preset p4 -cq 20 -pix_fmt yuv420p`), single GPU queue. |
| **SUB-10** | **Frontend Bundle Synchronization** | `LOCKED` | `_sync_frontend_dist()` in `app/main.py` & `publish_to_github.py` (`web/dist` -> `static/`). |

---

## 🧪 Comprehensive Automated Test Matrix

- [x] **Downloader Test**: Rejects `.part` and `.ytdl` files, verifies HD video/audio streams via `ffprobe`.
- [x] **Whisper CUDA Test**: Transcribes audio on `cuda` with `float16` precision.
- [x] **Timeline Converter Test**: Maps source timestamps (`00:10:30`) to clip-local ASS timestamps (`00:00:10`).
- [x] **ASS Pre-Render Validation Test**: Rejects 0-dialogue ASS files before FFmpeg execution.
- [x] **Caption Styling Test**: Verifies font, colors, scale, position, tracking, outline, shadow, and word highlighting.
- [x] **Filter Complex Composition Test**: Verifies bottom black gradient, vignette, signature, and ASS subtitle layers.
- [x] **NVENC Hardware Acceleration Test**: Probes `h264_nvenc` availability and parameters.
- [x] **Phase 1 CapCut Caption Test**: Verifies emoji keyword mappings and bounce pop-in scale transforms.
