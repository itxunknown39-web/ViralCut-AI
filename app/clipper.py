"""Cut, reframe, and burn captions with ffmpeg.

Each clip is re-encoded (libx264 + aac) so cuts are frame-accurate and the ASS
captions are burned into the pixels.

``crop`` scales to *cover* the chosen aspect ratio (9:16 / 16:9) and center-crops
to fill it. ``square`` renders a 9:16 canvas with the source cropped to a 1:1
square, given **soft rounded corners**, and centered on black — with an optional
title drawn above it (the "rounded square reel" look). The aspect ratio is
ignored in square mode (the canvas is always 9:16).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import effects
from .models import AspectRatio, ClipGenerationError, FitMode
from .paths import CLIPS_DIR, FONTS_DIR, MASKS_DIR

logger = logging.getLogger(__name__)

# Target frame sizes per aspect ratio. Default 9:16 is 1080x1920, 16:9 is 1920x1080.
_TARGETS = {
    AspectRatio.NINE_16: (1080, 1920),
    AspectRatio.SIXTEEN_9: (1920, 1080),
}

# Square ("rounded reel") mode: a 9:16 canvas with a centered, rounded 1:1 square.
_SQUARE_CANVAS = (1080, 1920)   # output frame (aspect ratio is ignored)
_SQUARE_INNER = 1020            # side of the centered square
_SQUARE_RADIUS = 60             # corner radius of that square (soft, anti-aliased)


def target_size(aspect_ratio: AspectRatio, fit_mode: FitMode) -> tuple[int, int]:
    """Output (width, height): 9:16 canvas for square mode, else the aspect size."""
    if fit_mode == FitMode.SQUARE:
        return _SQUARE_CANVAS
    return _TARGETS[aspect_ratio]


def ensure_rounded_mask(size: int = _SQUARE_INNER, radius: int = _SQUARE_RADIUS) -> Path:
    """Create (once) and cache a grayscale rounded-rectangle mask via ffmpeg.

    White inside the rounded square, black outside; used by ``alphamerge`` to
    give the centered square its soft corners. Generated with ffmpeg's ``geq``
    so we need no extra image library.
    """
    path = MASKS_DIR / f"rounded_{size}_{radius}.png"
    if path.exists():
        return path
    MASKS_DIR.mkdir(parents=True, exist_ok=True)

    if radius <= 0:
        # Sharp corners: a fully opaque square needs no SDF ramp — solid white.
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=white:s={size}x{size}:d=0.1",
            "-frames:v", "1", str(path),
        ]
    else:
        edge = size - 1 - radius
        # Distance from each pixel to the inner rectangle's edge (the rounded-rect SDF);
        # a ~1.5px soft ramp around `radius` anti-aliases the corners (smooth, not jaggy).
        # alpha = 255 inside, 0 outside. Commas are escaped for the filtergraph.
        expr = (
            f"255*clip(0.5+({radius}-hypot("
            f"max(0\\,{radius}-X)+max(0\\,X-{edge})\\,"
            f"max(0\\,{radius}-Y)+max(0\\,Y-{edge})))/1.5\\,0\\,1)"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={size}x{size}:d=0.1",
            "-vf", f"geq=lum='{expr}':cb=128:cr=128",
            "-frames:v", "1", str(path),
        ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ClipGenerationError(
            "ffmpeg was not found on PATH (needed to build the rounded mask)."
        ) from exc
    if proc.returncode != 0 or not path.exists():
        tail = (proc.stderr or "").strip().splitlines()[-8:]
        raise ClipGenerationError(
            "Could not generate the rounded-corner mask:\n" + "\n".join(tail)
        )
    return path

_BAR_FONT = FONTS_DIR / "Roboto-Bold.ttf"


@dataclass
class ClipOptions:
    """Everything generate_clip needs beyond the time range."""

    aspect_ratio: AspectRatio
    fit_mode: FitMode
    ass_path: Path
    clip_id: str
    index: int
    square_corners: str = "round"      # "round" | "square" — square fit mode only
    bar_text: Optional[str] = None
    bar_text_color: str = "#FFFFFF"     # square title colour
    bar_text_anim: str = "none"         # square title entrance: none | fade | slide
    cinematic: Optional[dict] = None  # cinematic effects config (see app.effects)
    music_path: Optional[Path] = None  # background-music track to mix under the audio
    music_volume: float = 35.0         # 0-100, reels-style (ducked under speech)
    music_duck: float = 70.0           # 0-100, how hard music dips under the voice
    music_start: float = 0.0           # seconds into the track to start from (beat-aligned)
    signature: Optional[dict] = None   # burned-in watermark (see app.models.Signature)


def _rel_for_filter(target: Path, start_dir: Path) -> str:
    """Return `target` relative to `start_dir` with forward slashes."""
    return os.path.relpath(str(target), str(start_dir)).replace("\\", "/")


def _escape_drawtext(text: str) -> str:
    """Escape user text for ffmpeg drawtext (the value is wrapped in quotes)."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "’")
        .replace("%", "\\%")
    )


def _ass_filter(opts: ClipOptions, work_dir: Path) -> str:
    """The caption-burn filter. Relative paths keep the drive colon/spaces out."""
    return (
        f"ass={_rel_for_filter(opts.ass_path, work_dir)}:"
        f"fontsdir={_rel_for_filter(FONTS_DIR, work_dir)}"
    )


def _caption_stage(in_label: str, opts: ClipOptions, work_dir: Path) -> str:
    """The final stage that burns the captions onto ``in_label`` -> ``[outv]``."""
    return f"[{in_label}]{_ass_filter(opts, work_dir)}[outv]"


def _signature_stages(in_label: str, sig: Optional[dict], w: int, h: int, work_dir: Path) -> tuple[list[str], str]:
    if not sig or not sig.get("enabled") or not (sig.get("text") or "").strip():
        return [], in_label
    scale = w / 1080.0
    size = max(10, int(round(float(sig.get("size") or 34) * scale)))
    alpha = max(0.0, min(1.0, float(sig.get("opacity") if sig.get("opacity") is not None else 75) / 100.0))
    col = (sig.get("color") or "#FFFFFF").replace("#", "0x")
    px = max(0.0, min(1.0, float(sig.get("pos_x") if sig.get("pos_x") is not None else 50) / 100.0))
    py = max(0.0, min(1.0, float(sig.get("pos_y") if sig.get("pos_y") is not None else 92) / 100.0))
    txt = _escape_drawtext(sig["text"].strip())
    stage = (
        f"[{in_label}]drawtext=fontfile={_rel_for_filter(_BAR_FONT, work_dir)}:"
        f"text='{txt}':fontcolor={col}@{alpha:.3f}:fontsize={size}:"
        f"x=(w-text_w)*{px:.4f}:y=(h-text_h)*{py:.4f}:"
        f"borderw=2:bordercolor=black@{min(0.55, alpha):.3f}:shadowcolor=black@0.4:shadowx=1:shadowy=1[sig]"
    )
    return [stage], "sig"


def _finish_stages(in_label: str, vw: int, vh: int, opts: ClipOptions, work_dir: Path) -> list[str]:
    cine_stages, cap_in = effects.cinematic_stages(opts.cinematic, in_label, vw, vh)
    sig_stages, sig_in = _signature_stages(cap_in, opts.signature, vw, vh, work_dir)
    return cine_stages + sig_stages + [_caption_stage(sig_in, opts, work_dir)]


def _build_crop_filter_complex(width: int, height: int, opts: ClipOptions, work_dir: Path) -> str:
    """-filter_complex graph for crop mode: cover+crop with bicubic scaling, cinematic FX, then captions."""
    stages = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase:flags=bicubic,"
        f"crop={width}:{height}[v0]"
    ]
    stages += _finish_stages("v0", width, height, opts, work_dir)
    return ";".join(stages)


def _build_square_filter_complex(opts: ClipOptions, work_dir: Path) -> str:
    """-filter_complex graph for square mode with bicubic scaling."""
    s = _SQUARE_INNER
    w, h = _SQUARE_CANVAS
    mx, my = (w - s) // 2, (h - s) // 2

    stages = [
        "[0:v]split[base][fg]",
        f"[base]scale={w}:{h}:force_original_aspect_ratio=increase:flags=bicubic,"
        f"crop={w}:{h},drawbox=0:0:iw:ih:black:t=fill[bg]",
        f"[fg]scale={s}:{s}:force_original_aspect_ratio=increase:flags=bicubic,"
        f"crop={s}:{s}[fgsq]",
    ]

    cine_stages, sq_cine = effects.cinematic_stages(opts.cinematic, "fgsq", s, s)
    stages += cine_stages

    stages += [
        f"[{sq_cine}]format=yuva420p[sq]",
        f"[1:v]format=gray,scale={s}:{s}[m]",
        "[sq][m]alphamerge[r]",
        f"[bg][r]overlay={mx}:{my}[ov]",
    ]
    last = "ov"

    if opts.bar_text and opts.bar_text.strip():
        lines = [ln.strip() for ln in opts.bar_text.split("\n") if ln.strip()][:3]
        font_size = max(28, int(round(h * 0.040)))
        line_h = int(round(font_size * 1.3))
        block_h = line_h * len(lines)
        start_y = max(16, my - block_h - 22)
        col = (opts.bar_text_color or "#FFFFFF").replace("#", "0x")
        anim = (opts.bar_text_anim or "none").lower()
        alpha_expr = ":alpha='if(lt(t\\,0.5)\\,t/0.5\\,1)'" if anim == "fade" else ""
        for li, ln in enumerate(lines):
            base_y = start_y + li * line_h
            y = (f"'{base_y}+40*(1-min(t/0.45\\,1))'" if anim == "slide" else str(base_y))
            stages.append(
                f"[{last}]drawtext=fontfile={_rel_for_filter(_BAR_FONT, work_dir)}:"
                f"text='{_escape_drawtext(ln)}':"
                f"fontcolor={col}:fontsize={font_size}:x=(w-text_w)/2:y={y}{alpha_expr}:"
                f"borderw=3:bordercolor=black@0.85[ttl{li}]"
            )
            last = f"ttl{li}"

    sig_stages, last = _signature_stages(last, opts.signature, w, h, work_dir)
    stages += sig_stages
    stages.append(_caption_stage(last, opts, work_dir))
    return ";".join(stages)


def _music_audio_graph(mus_idx: int, volume: float, duck: float = 70.0) -> str:
    base = max(0.0, min(1.0, (volume if volume is not None else 35) / 100.0 * 0.7))
    d = max(0.0, min(1.0, (duck if duck is not None else 70) / 100.0))
    ratio = 1.0 + d * 19.0
    return (
        f"[0:a]asplit=2[__v1][__v2];"
        f"[{mus_idx}:a]volume={base:.3f},aresample=async=1[__m];"
        f"[__m][__v2]sidechaincompress=threshold=0.02:ratio={ratio:.2f}:attack=15:release=300[__md];"
        f"[__v1][__md]amix=inputs=2:duration=first:normalize=0[aout]"
    )


# Dynamic hardware encoder discovery (NVENC / QSV / AMF / CPU fallback).
_cached_encoder_args: Optional[list[str]] = None


def _test_ffmpeg_encoder(v_args: list[str]) -> bool:
    try:
        # Note: NVENC requires surface sizes >= 128x128. Using s=256x256 to ensure NVENC init succeeds.
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
            *v_args, "-frames:v", "1", "-f", "null", "-"
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, creationflags=flags
        )
        if proc.returncode == 0:
            return True
        logger.debug("Encoder test failed for %s (exit code %d): %s", " ".join(v_args), proc.returncode, proc.stderr)
        return False
    except Exception as exc:
        logger.debug("Encoder test exception for %s: %s", " ".join(v_args), exc)
        return False


def get_encoder_args() -> list[str]:
    """Dynamically probe and return the optimal video/audio encoder flags."""
    global _cached_encoder_args
    if _cached_encoder_args is not None:
        return _cached_encoder_args

    candidates = [
        ("NVIDIA NVENC (p4 HQ)", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-pix_fmt", "yuv420p"]),
        ("NVIDIA NVENC (p4 VBR)", ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "20", "-b:v", "0", "-pix_fmt", "yuv420p"]),
        ("NVIDIA NVENC (medium)", ["-c:v", "h264_nvenc", "-preset", "medium", "-pix_fmt", "yuv420p"]),
        ("NVIDIA NVENC (default)", ["-c:v", "h264_nvenc", "-pix_fmt", "yuv420p"]),
        ("Intel QSV", ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "20", "-pix_fmt", "nv12"]),
        ("AMD AMF", ["-c:v", "h264_amf", "-quality", "speed", "-qp_i", "20", "-qp_p", "20", "-pix_fmt", "yuv420p"]),
    ]

    for name, v_args in candidates:
        if _test_ffmpeg_encoder(v_args):
            logger.info("⚡ Hardware Acceleration Detected & Active: %s", name)
            _cached_encoder_args = [*v_args, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
            return _cached_encoder_args

    logger.info("⚡ Hardware acceleration unavailable. Using CPU encoding (libx264 - medium).")
    _cached_encoder_args = [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "0", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    ]
    return _cached_encoder_args


def generate_clip(source_mp4: Path, start: float, end: float, opts: ClipOptions) -> Path:
    """Cut [start, end] from `source_mp4`, reframe + caption it, return the mp4."""
    import time
    t0 = time.time()
    duration = max(0.1, end - start)

    out_dir = (CLIPS_DIR / opts.clip_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{opts.index}.mp4"

    src = str(Path(source_mp4).resolve())

    has_music = opts.music_path is not None and Path(opts.music_path).is_file()

    if opts.fit_mode == FitMode.SQUARE:
        radius = _SQUARE_RADIUS if opts.square_corners != "square" else 0
        mask = ensure_rounded_mask(radius=radius)
        fc = _build_square_filter_complex(opts, out_dir)
        inputs = ["-ss", f"{start:.3f}", "-i", src, "-loop", "1", "-i", str(mask.resolve())]
        music_idx = 2
        tail = ["-shortest"]
    else:
        width, height = target_size(opts.aspect_ratio, opts.fit_mode)
        fc = _build_crop_filter_complex(width, height, opts, out_dir)
        inputs = ["-ss", f"{start:.3f}", "-i", src]
        music_idx = 1
        tail = []

    if has_music:
        seek = ["-ss", f"{max(0.0, opts.music_start):.2f}"] if opts.music_start and opts.music_start > 0 else []
        inputs += ["-stream_loop", "-1", *seek, "-i", str(Path(opts.music_path).resolve())]
        fc = fc + ";" + _music_audio_graph(music_idx, opts.music_volume, opts.music_duck)
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "0:a?"]

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-t", f"{duration:.3f}",
        "-filter_complex", fc,
        "-map", "[outv]", *audio_map,
        *get_encoder_args(),
        *tail,
        str(out_path),
    ]

    logger.info("Rendering clip %d (cwd=%s): %s", opts.index, out_dir, " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ClipGenerationError(
            "ffmpeg was not found on PATH. Install it (winget/brew/apt) — it "
            "does the cutting, reframing, and caption burning."
        ) from exc
    except Exception as exc:
        raise ClipGenerationError(f"Failed to run ffmpeg: {exc}") from exc

    if proc.returncode != 0 or not out_path.exists():
        # Fallback to CPU libx264 if hardware encoder failed at runtime
        logger.warning("FFmpeg render failed with preferred args. Retrying with CPU libx264 fallback...")
        fallback_args = [
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "0", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        ]
        cmd_fallback = [
            "ffmpeg", "-y",
            *inputs,
            "-t", f"{duration:.3f}",
            "-filter_complex", fc,
            "-map", "[outv]", *audio_map,
            *fallback_args,
            *tail,
            str(out_path),
        ]
        proc = subprocess.run(
            cmd_fallback,
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    if proc.returncode != 0 or not out_path.exists():
        tail = (proc.stderr or "").strip().splitlines()[-12:]
        raise ClipGenerationError(
            "ffmpeg failed to render the clip:\n" + "\n".join(tail)
        )

    render_time = time.time() - t0
    realtime = duration / max(0.001, render_time)
    logger.info("✅ Clip %d rendered in %.2fs (%.2fx realtime)", opts.index, render_time, realtime)

    return out_path

