#!/usr/bin/env python3
"""
ClipForge GPU Render Stress Test — Minimal Colab Deployment Script
===================================================================
Drop this single file into a Colab cell or run it as-is.
It bootstraps its own minimal app/ package; no full project checkout needed.

Usage:
    # In a Colab code cell:
    exec(open('clipforge_stress_colab.py').read())

    # Or directly via terminal:
    python clipforge_stress_colab.py

    # To use a real MP4 instead of the synthetic source:
    SOURCE_VIDEO = '/content/my_podcast.mp4'  # edit below
"""

# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIG — edit here before running
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_VIDEO   = None      # path to ≥180s 1080p MP4, or None for auto-generated
CLIP_DURATION  = 30.0      # seconds per test clip
NUM_CLIPS      = 6         # number of clips per pass
WORKER_CONFIGS = [1, 2, 3] # worker counts to test (4 auto-added if VRAM ≥ 6 GB)
TARGET_W       = 1080
TARGET_H       = 1920

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 0 — SETUP: install deps + write minimal app/ package
# ═══════════════════════════════════════════════════════════════════════════════
import os, subprocess, sys
from pathlib import Path
import textwrap

ROOT_DIR = Path('/content/clipforge_stress')
APP_DIR  = ROOT_DIR / 'app'
APP_DIR.mkdir(parents=True, exist_ok=True)

# ── Install FFmpeg if missing ─────────────────────────────────────────────────
r = subprocess.run(['ffmpeg', '-version'], capture_output=True)
if r.returncode != 0:
    print('Installing FFmpeg...')
    subprocess.run(['apt-get', 'update', '-qq'], check=True)
    subprocess.run(['apt-get', 'install', '-y', '-qq', 'ffmpeg'], check=True)

# ── Install pydantic if missing ───────────────────────────────────────────────
try:
    import pydantic
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pydantic>=2.0'], check=True)

# ── Write app/__init__.py ─────────────────────────────────────────────────────
(APP_DIR / '__init__.py').write_text('__version__ = "0.1.0"\n')

# ── Write app/paths.py ────────────────────────────────────────────────────────
(APP_DIR / 'paths.py').write_text(textwrap.dedent('''
    from pathlib import Path
    ROOT_DIR        = Path(__file__).resolve().parent.parent
    DOWNLOADS_DIR   = ROOT_DIR / "downloads"
    TRANSCRIPTS_DIR = ROOT_DIR / "transcripts"
    CLIPS_DIR       = ROOT_DIR / "clips"
    ASSETS_DIR      = ROOT_DIR / "assets"
    FONTS_DIR       = ASSETS_DIR / "fonts"
    MASKS_DIR       = ASSETS_DIR / "masks"
    MUSIC_DIR       = ASSETS_DIR / "music"
    STATIC_DIR      = ROOT_DIR / "static"
    def ensure_dirs():
        for d in (DOWNLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR, ASSETS_DIR,
                  FONTS_DIR, MASKS_DIR, MUSIC_DIR, STATIC_DIR):
            d.mkdir(parents=True, exist_ok=True)
    ensure_dirs()
''').strip())

# ── Write app/models.py ───────────────────────────────────────────────────────
(APP_DIR / 'models.py').write_text(textwrap.dedent('''
    from __future__ import annotations
    from enum import Enum
    class AspectRatio(str, Enum):
        NINE_16   = "9:16"
        SIXTEEN_9 = "16:9"
    class FitMode(str, Enum):
        CROP   = "crop"
        SQUARE = "square"
    class ClipGenerationError(RuntimeError): pass
''').strip())

# ── Write app/effects.py ──────────────────────────────────────────────────────
(APP_DIR / 'effects.py').write_text(textwrap.dedent('''
    from __future__ import annotations
    from typing import List, Tuple

    COLOR_GRADES = {
        "none": "",
        "warm": "eq=saturation=1.10,colorbalance=rm=0.06:gm=0.02:bm=-0.06:rh=0.05:bh=-0.06",
        "cool": "eq=saturation=1.05,colorbalance=rm=-0.05:bm=0.06:bh=0.06",
        "vibrant": "eq=saturation=1.35:contrast=1.08:brightness=0.01",
        "bw": "hue=s=0,eq=contrast=1.10",
    }
    _GRAD_BANDS = 8

    def _f(x, lo, hi): return lo + max(0.0, min(100.0, float(x))) / 100.0 * (hi - lo)
    def _on(cfg, key): return bool(cfg.get(key))
    def _num(cfg, key, default):
        v = cfg.get(key)
        try: return float(v) if v is not None else float(default)
        except: return float(default)

    def _gradient_bands(vw, vh, height_pct, strength, top):
        h_grad = max(1, int(vh * max(0.0, min(0.8, height_pct / 100.0))))
        n, step, m = _GRAD_BANDS, h_grad / _GRAD_BANDS, max(0.0, min(0.96, strength / 100.0))
        base = 0 if top else (vh - h_grad)
        boxes = []
        for k in range(n):
            y = base + int(round(k * step)); h = base + int(round((k + 1) * step)) - y
            if h <= 0: continue
            frac = (k + 0.5) / n; eased = frac * frac * (3.0 - 2.0 * frac)
            alpha = m * eased if not top else m * (1.0 - eased)
            if alpha <= 0.002: continue
            boxes.append(f"drawbox=x=0:y={y}:w=iw:h={h}:color=black@{alpha:.4f}:t=fill")
        return ",".join(boxes)

    def cinematic_stages(cfg, in_label, vw, vh):
        if not cfg: return [], in_label
        stages, cur, idx = [], in_label, 0
        def push(filters):
            nonlocal cur, idx
            nxt = f"cine{idx}"; stages.append(f"[{cur}]{filters}[{nxt}]"); cur, idx = nxt, idx + 1
        grade = COLOR_GRADES.get(str(cfg.get("color_grade") or "none"))
        if grade: push(grade)
        if _on(cfg, "vignette"):
            ang = _f(_num(cfg, "vignette_strength", 50), 0.45, 1.25); push(f"vignette=angle={ang:.3f}")
        if _on(cfg, "bottom_gradient"):
            bands = _gradient_bands(vw, vh, _num(cfg, "bottom_gradient_height", 25), _num(cfg, "bottom_gradient_strength", 70), False)
            if bands: push(bands)
        if _on(cfg, "top_gradient"):
            bands = _gradient_bands(vw, vh, _num(cfg, "top_gradient_height", 20), _num(cfg, "top_gradient_strength", 60), True)
            if bands: push(bands)
        if _on(cfg, "letterbox"):
            bh = max(1, int(vh * _f(_num(cfg, "letterbox_size", 50), 0.05, 0.14)))
            push(f"drawbox=x=0:y=0:w=iw:h={bh}:color=black:t=fill,drawbox=x=0:y=ih-{bh}:w=iw:h={bh}:color=black:t=fill")
        return stages, cur
''').strip())

# ── Write app/captions.py ─────────────────────────────────────────────────────
(APP_DIR / 'captions.py').write_text(textwrap.dedent('''
    from __future__ import annotations
    from pathlib import Path
    from typing import List

    _BASE = {
        "font_family": "Roboto", "bold": True, "font_size": 90,
        "primary_color": "#FFFFFF", "highlight_color": "#FFD400",
        "outline_color": "#000000", "outline": 5, "shadow": 1,
        "position": "bottom", "karaoke": False, "uppercase": True,
        "animation": "none", "tracking": 0, "underline": False,
        "strikethrough": False, "max_lines": 2, "max_chars": 22,
        "background_enabled": False, "background_color": "#000000", "trending": False,
    }
    def _P(label, **kw):
        d = dict(_BASE); d["label"] = label; d.update(kw); return d

    STYLE_PRESETS = {
        "bold_white":     _P("Bold White", highlight_color="#FFFFFF", font_size=96, max_chars=20),
        "karaoke_yellow": _P("Karaoke Yellow", karaoke=True, font_size=92, highlight_color="#FFE600"),
        "minimal":        _P("Minimal", bold=False, uppercase=False, font_size=64, outline=1, shadow=2, max_chars=28),
        "hormozi_yellow": _P("Hormozi Yellow", trending=True, font_family="Montserrat",
                             animation="highlight", highlight_color="#FFD400", font_size=94,
                             outline=6, position="center", max_lines=2, max_chars=16),
        "beast_red":      _P("Beast Pop", trending=True, font_family="Anton", bold=False,
                             animation="highlight", highlight_color="#FF3B30", font_size=108,
                             outline=7, position="center", max_lines=2, max_chars=15),
    }
    DEFAULT_PRESET = "bold_white"
    def get_preset(pid): return STYLE_PRESETS.get(pid, STYLE_PRESETS[DEFAULT_PRESET])

    def _hex_to_ass(hex_color, alpha=0):
        h = (hex_color or "").lstrip("#")
        if len(h) != 6: h = "FFFFFF"
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H{max(0, min(255, int(alpha))):02X}{b}{g}{r}".upper()

    def _fmt_time(seconds):
        if seconds < 0: seconds = 0.0
        cs_total = int(round(seconds * 100))
        cs, s_total = cs_total % 100, cs_total // 100
        s, m, h = s_total % 60, (s_total // 60) % 60, s_total // 3600
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _ass_escape(text):
        return text.replace("\\\\", "\\\\\\\\").replace("{", "(").replace("}", ")").replace("\\n", " ").strip()

    def _line_len(line): return sum(len(w["word"]) for w in line) + (len(line) - 1) if line else 0

    def _group_events(words, max_chars, max_lines, max_span=2.5):
        events, cur_lines = [], [[]]
        def flush():
            nonlocal cur_lines
            filled = [ln for ln in cur_lines if ln]
            if filled:
                flat = [w for ln in filled for w in ln]
                events.append({"start": flat[0]["start"], "end": flat[-1]["end"], "lines": filled})
            cur_lines = [[]]
        for w in words:
            start = cur_lines[0][0]["start"] if cur_lines[0] else None
            if start is not None and (w["end"] - start) > max_span: flush()
            cur_line = cur_lines[-1]
            tentative = _line_len(cur_line) + (1 if cur_line else 0) + len(w["word"])
            if cur_line and tentative > max_chars:
                if len(cur_lines) < max_lines: cur_lines.append([w])
                else: flush(); cur_lines = [[w]]
            else: cur_line.append(w)
        flush(); return events

    def _tok(word, uppercase):
        t = _ass_escape(word); return t.upper() if uppercase else t

    def _plain_text(lines, uppercase):
        return "\\\\N".join(" ".join(_tok(w["word"], uppercase) for w in ln if w["word"]) for ln in lines)

    def build_ass(words, style_preset, video_w, video_h, out_path,
                  clip_start=0.0, overrides=None, fit_mode=None):
        preset = get_preset(style_preset)
        cfg = dict(preset)
        if overrides:
            for k, v in overrides.items():
                if v is not None: cfg[k] = v
        scale = video_h / 1920.0
        font_size = max(12, int(round(cfg["font_size"] * float(cfg.get("font_scale", 1.0) or 1.0) * scale)))
        outline = max(0, int(round(cfg.get("outline_width", cfg["outline"]) * scale)))
        shadow_on = cfg.get("shadow_enabled")
        if shadow_on is None: shadow_on = cfg["shadow"] > 0
        shadow = max(0, int(round(cfg.get("shadow_distance", cfg["shadow"]) * scale))) if shadow_on else 0
        bg_on = bool(cfg.get("background_enabled"))
        border_style = 3 if bg_on else 1
        margin_v = int(round(video_h * 0.08))
        primary = _hex_to_ass(cfg["primary_color"])
        highlight = _hex_to_ass(cfg["highlight_color"])
        outline_col = _hex_to_ass(cfg["outline_color"]) if not bg_on else _hex_to_ass(cfg.get("background_color", "#000000"))
        sh_alpha = int(round((100 - float(cfg.get("shadow_opacity", 75) or 75)) / 100 * 255))
        back_col = _hex_to_ass(cfg.get("shadow_color", "#000000"), alpha=sh_alpha)
        bold_flag = -1 if cfg["bold"] else 0
        underline_flag = -1 if cfg.get("underline") else 0
        strike_flag = -1 if cfg.get("strikethrough") else 0
        spacing = max(0, int(round(float(cfg.get("tracking", 0) or 0) * scale)))
        alignment = {"top": 8, "center": 5, "bottom": 2}.get(cfg.get("position", "bottom"), 2)
        style_primary, style_secondary = (highlight, primary) if cfg["karaoke"] else (primary, primary)
        header = (
            f"[Script Info]\\nScriptType: v4.00+\\nPlayResX: {video_w}\\nPlayResY: {video_h}\\n"
            f"WrapStyle: 2\\nScaledBorderAndShadow: yes\\n\\n[V4+ Styles]\\n"
            f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            f"Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            f"Alignment, MarginL, MarginR, MarginV, Encoding\\n"
            f"Style: Default,{cfg[\\'font_family\\']},{font_size},{style_primary},{style_secondary},{outline_col},"
            f"{back_col},{bold_flag},0,{underline_flag},{strike_flag},100,100,{spacing},0,"
            f"{border_style},{outline},{shadow},{alignment},60,60,{margin_v},1\\n\\n"
            f"[Events]\\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\\n"
        )
        max_lines = int(cfg.get("max_lines") or 1)
        max_chars = int(cfg.get("max_chars") or 22)
        events = _group_events(words, max_chars=max_chars, max_lines=max_lines)
        rows = []
        for ev in events:
            start = max(0.0, ev["start"] - clip_start); end = ev["end"] - clip_start
            if end <= 0: continue
            text = _plain_text(ev["lines"], cfg["uppercase"])
            rows.append(f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}")
        Path(out_path).write_text(header + "\\n".join(rows) + "\\n", encoding="utf-8")
        return out_path
''').strip())

# ── Write app/clipper.py ──────────────────────────────────────────────────────
(APP_DIR / 'clipper.py').write_text(textwrap.dedent(r'''
    from __future__ import annotations
    import logging, os, subprocess, time
    from dataclasses import dataclass
    from pathlib import Path
    from typing import Optional
    from . import effects
    from .models import AspectRatio, ClipGenerationError, FitMode
    from .paths import CLIPS_DIR, FONTS_DIR, MASKS_DIR

    logger = logging.getLogger(__name__)
    _TARGETS = {AspectRatio.NINE_16: (1080, 1920), AspectRatio.SIXTEEN_9: (1920, 1080)}
    _SQUARE_CANVAS, _SQUARE_INNER, _SQUARE_RADIUS = (1080, 1920), 1020, 60

    def target_size(aspect_ratio, fit_mode):
        if fit_mode == FitMode.SQUARE: return _SQUARE_CANVAS
        return _TARGETS[aspect_ratio]

    def ensure_rounded_mask(size=_SQUARE_INNER, radius=_SQUARE_RADIUS):
        path = MASKS_DIR / f"rounded_{size}_{radius}.png"
        if path.exists(): return path
        MASKS_DIR.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=white:s={size}x{size}:d=0.1", "-frames:v", "1", str(path)]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0 or not path.exists():
            raise ClipGenerationError("Could not generate rounded mask")
        return path

    _BAR_FONT = FONTS_DIR / "Roboto-Bold.ttf"

    @dataclass
    class ClipOptions:
        aspect_ratio: AspectRatio
        fit_mode: FitMode
        ass_path: Path
        clip_id: str
        index: int
        square_corners: str = "round"
        bar_text: Optional[str] = None
        bar_text_color: str = "#FFFFFF"
        bar_text_anim: str = "none"
        cinematic: Optional[dict] = None
        music_path: Optional[Path] = None
        music_volume: float = 35.0
        music_duck: float = 70.0
        music_start: float = 0.0
        signature: Optional[dict] = None

    def _rel(target, start_dir):
        return os.path.relpath(str(target), str(start_dir)).replace("\\", "/")

    def _ass_filter(opts, work_dir):
        return f"ass={_rel(opts.ass_path, work_dir)}:fontsdir={_rel(FONTS_DIR, work_dir)}"

    def _caption_stage(in_label, opts, work_dir):
        return f"[{in_label}]{_ass_filter(opts, work_dir)}[outv]"

    def _finish_stages(in_label, vw, vh, opts, work_dir):
        cine_stages, cap_in = effects.cinematic_stages(opts.cinematic, in_label, vw, vh)
        return cine_stages + [_caption_stage(cap_in, opts, work_dir)]

    def _build_crop_filter(width, height, opts, work_dir):
        stages = [f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase:flags=bicubic,crop={width}:{height}[v0]"]
        stages += _finish_stages("v0", width, height, opts, work_dir)
        return ";".join(stages)

    _cached_encoder_args = None

    def _test_enc(v_args):
        try:
            cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.04",
                   *v_args, "-frames:v", "1", "-f", "null", "-"]
            return subprocess.run(cmd, capture_output=True, timeout=4).returncode == 0
        except: return False

    def get_encoder_args():
        global _cached_encoder_args
        if _cached_encoder_args is not None: return _cached_encoder_args
        candidates = [
            ("NVIDIA NVENC (HQ)", ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-rc", "vbr", "-cq", "20", "-b:v", "0", "-pix_fmt", "yuv420p"]),
            ("NVIDIA NVENC",      ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-b:v", "8M", "-maxrate", "12M", "-bufsize", "16M", "-pix_fmt", "yuv420p"]),
            ("Intel QSV",         ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "20", "-pix_fmt", "nv12"]),
            ("AMD AMF",           ["-c:v", "h264_amf", "-quality", "speed", "-qp_i", "20", "-qp_p", "20", "-pix_fmt", "yuv420p"]),
        ]
        for name, v_args in candidates:
            if _test_enc(v_args):
                print(f"Encoder: {name}")
                _cached_encoder_args = [*v_args, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
                return _cached_encoder_args
        print("No hardware encoder. Using CPU libx264.")
        _cached_encoder_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "0",
                                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
        return _cached_encoder_args

    def generate_clip(source_mp4, start, end, opts):
        t0 = time.time()
        duration = max(0.1, end - start)
        out_dir = (CLIPS_DIR / opts.clip_id).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{opts.index}.mp4"
        src = str(Path(source_mp4).resolve())
        width, height = target_size(opts.aspect_ratio, opts.fit_mode)
        fc = _build_crop_filter(width, height, opts, out_dir)
        inputs = ["-ss", f"{start:.3f}", "-i", src]
        cmd = ["ffmpeg", "-y", *inputs, "-t", f"{duration:.3f}",
               "-filter_complex", fc, "-map", "[outv]", "-map", "0:a?",
               *get_encoder_args(), str(out_path)]
        logger.debug("FFmpeg: %s", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(out_dir), capture_output=True, text=True, errors="replace")
        if proc.returncode != 0 or not out_path.exists():
            fb = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "0",
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
            cmd_fb = ["ffmpeg", "-y", *inputs, "-t", f"{duration:.3f}",
                      "-filter_complex", fc, "-map", "[outv]", "-map", "0:a?", *fb, str(out_path)]
            proc = subprocess.run(cmd_fb, cwd=str(out_dir), capture_output=True, text=True, errors="replace")
        if proc.returncode != 0 or not out_path.exists():
            raise ClipGenerationError("ffmpeg failed:\n" + (proc.stderr or "")[-500:])
        elapsed = time.time() - t0
        logger.info("Clip %d: %.2fs (%.2fx realtime)", opts.index, elapsed, duration / max(0.001, elapsed))
        return out_path
''').strip())

print("Minimal app/ package written.")

# ─── Download Roboto Bold font ────────────────────────────────────────────────
import urllib.request
sys.path.insert(0, str(ROOT_DIR))

# Reload paths so FONTS_DIR resolves to /content/clipforge_stress/assets/fonts/
if 'app.paths' in sys.modules: del sys.modules['app.paths']
if 'app' in sys.modules: del sys.modules['app']

from app.paths import FONTS_DIR
FONT_PATH = FONTS_DIR / 'Roboto-Bold.ttf'
if not FONT_PATH.exists():
    print('Downloading Roboto-Bold.ttf...')
    urllib.request.urlretrieve(
        'https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Bold.ttf',
        str(FONT_PATH)
    )
    print(f'Font saved: {FONT_PATH}')
else:
    print(f'Font present: {FONT_PATH}')

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — IMPORT BOOTSTRAPPED APP
# ═══════════════════════════════════════════════════════════════════════════════
# Clear any prior imports from this session
for mod in list(sys.modules.keys()):
    if mod == 'app' or mod.startswith('app.'):
        del sys.modules[mod]

from app.clipper import ClipOptions, generate_clip, get_encoder_args
from app.models  import AspectRatio, FitMode
from app.paths   import CLIPS_DIR
from app         import captions

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
import json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

def _run(cmd, timeout=6):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def _duration(path):
    try:
        r = _run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(path)])
        return float(json.loads(r.stdout).get('format', {}).get('duration', 0))
    except:
        return 0.0

def _gpu_snapshot():
    try:
        r = _run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total',
                  '--format=csv,noheader,nounits'])
        if r.returncode == 0:
            parts = [x.strip() for x in r.stdout.strip().splitlines()[0].split(',')]
            if len(parts) >= 3:
                return int(parts[0]), int(parts[1]), int(parts[2])
    except:
        pass
    return -1, -1, -1


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ENVIRONMENT PROBE
# ═══════════════════════════════════════════════════════════════════════════════
print('=' * 62)
print('CLIPFORGE GPU STRESS TEST — ENVIRONMENT')
print('=' * 62)

gpu_name, vram_total = 'N/A', 0
util, used, total = _gpu_snapshot()
if total > 0:
    vram_total = total
    try:
        r = _run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader,nounits'])
        parts = [x.strip() for x in r.stdout.strip().splitlines()[0].split(',')]
        gpu_name = parts[0]; vram_total = int(parts[1])
        print(f'GPU        : {gpu_name}')
        print(f'VRAM total : {parts[1]} MB')
        print(f'VRAM free  : {parts[2]} MB')
    except:
        pass

cuda_ok = False
try:
    import torch
    cuda_ok = torch.cuda.is_available()
    if cuda_ok and gpu_name == 'N/A':
        gpu_name = torch.cuda.get_device_name(0)
except:
    pass
print(f'CUDA       : {"YES" if cuda_ok else "NO"}')

ffmpeg_ver = 'N/A'
try:
    r = _run(['ffmpeg', '-version'])
    if r.returncode == 0:
        ffmpeg_ver = r.stdout.splitlines()[0]
except:
    pass
print(f'FFmpeg     : {ffmpeg_ver}')

nvenc_listed = False
try:
    r = _run(['ffmpeg', '-hide_banner', '-encoders'])
    nvenc_listed = r.returncode == 0 and 'h264_nvenc' in r.stdout
except:
    pass
print(f'NVENC listed: {"YES" if nvenc_listed else "NO"}')

nvenc_ok, nvenc_fail = False, ''
if nvenc_listed:
    r = _run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=0.04',
              '-c:v', 'h264_nvenc', '-preset', 'p4', '-frames:v', '1', '-f', 'null', '-'], timeout=8)
    if r.returncode == 0:
        nvenc_ok = True
    else:
        nvenc_fail = '\n'.join(r.stderr.strip().splitlines()[-3:])
else:
    nvenc_fail = 'h264_nvenc not listed in FFmpeg encoder list'
print(f'NVENC test : {"PASS" if nvenc_ok else "FAIL"}')
if nvenc_fail:
    print(f'  Reason   : {nvenc_fail}')

enc_args = get_encoder_args()
active_enc = next((a for a in enc_args if any(x in a for x in ['nvenc', 'libx264', 'qsv', 'amf'])), 'N/A')
print(f'Active enc : {active_enc}')
print(f'Full args  : {" ".join(enc_args)}')
print('=' * 62)

if not nvenc_ok:
    print('\nNVENC not available. Test will run with CPU libx264.\n')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SOURCE VIDEO
# ═══════════════════════════════════════════════════════════════════════════════
def get_source(user_path):
    if user_path and Path(user_path).is_file():
        return Path(user_path).resolve()
    src = ROOT_DIR / 'stress_test_source' / 'stress_source_1080p.mp4'
    src.parent.mkdir(parents=True, exist_ok=True)
    total = int(NUM_CLIPS * CLIP_DURATION + 10)
    if not src.exists():
        print(f'Generating {total}s synthetic 1080p source...')
        r = subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'testsrc2=size=1920x1080:rate=30:duration={total}',
            '-f', 'lavfi', '-i', f'sine=frequency=440:duration={total}',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-b:a', '128k', str(src),
        ], capture_output=True)
        if r.returncode != 0 or not src.exists():
            raise RuntimeError('Cannot generate source. Set SOURCE_VIDEO to a valid MP4 path.')
        print(f'Generated: {src.name}')
    return src.resolve()

source = get_source(SOURCE_VIDEO)
src_dur = _duration(source)
print(f'\nSource: {source.name}  ({src_dur:.0f}s)')
assert src_dur >= NUM_CLIPS * CLIP_DURATION, f'Source too short ({src_dur:.0f}s)'

print(f'\nTarget: {TARGET_W}x{TARGET_H} | bicubic scaling | AAC 192k')
print(f'h264_nvenc: {"YES" if "h264_nvenc" in enc_args else "NO (CPU fallback)"}')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — BUILD ASS SUBTITLES
# ═══════════════════════════════════════════════════════════════════════════════
def make_ass(out_path, clip_start, duration):
    VOCAB = ['This', 'is', 'a', 'GPU', 'render', 'stress', 'test', 'for',
             'ClipForge', 'NVENC', 'h264', 'accelerated', 'encoding', 'fast']
    words, t, idx = [], 0.0, 0
    while t + 0.4 < duration:
        words.append({'word': VOCAB[idx % len(VOCAB)], 'start': clip_start + t, 'end': clip_start + t + 0.4})
        t += 0.5; idx += 1
    captions.build_ass(words=words, style_preset='bold_white',
                       video_w=TARGET_W, video_h=TARGET_H,
                       out_path=out_path, clip_start=clip_start, fit_mode='crop')

step = src_dur / (NUM_CLIPS + 1)
base_dir = CLIPS_DIR / 'stress_test'
base_dir.mkdir(parents=True, exist_ok=True)

clips_cfg = []
for i in range(NUM_CLIPS):
    cs = step * (i + 0.5)
    ap = base_dir / f'sub_{i}.ass'
    make_ass(ap, cs, CLIP_DURATION)
    clips_cfg.append({'start': cs, 'ass_path': ap})
print(f'Built {NUM_CLIPS} ASS subtitle files.')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — RENDER PASS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════
ASPECT = AspectRatio.NINE_16
FIT    = FitMode.CROP

def run_pass(nw, pass_id):
    clip_times = [0.0] * NUM_CLIPS
    peak_vram = 0
    gpu_utils = []

    def _render(idx, cfg):
        nonlocal peak_vram
        opts = ClipOptions(
            aspect_ratio=ASPECT, fit_mode=FIT,
            ass_path=cfg['ass_path'],
            clip_id=pass_id + f'_c{idx}', index=0,
            cinematic=None, music_path=None,
        )
        t0 = time.perf_counter()
        generate_clip(source, cfg['start'], cfg['start'] + CLIP_DURATION, opts)
        elapsed = time.perf_counter() - t0
        _, used, _ = _gpu_snapshot()
        if used > peak_vram: peak_vram = used
        util, _, _ = _gpu_snapshot()
        gpu_utils.append(util)
        return elapsed

    wall_start = time.perf_counter()
    if nw == 1:
        for i, cfg in enumerate(clips_cfg):
            clip_times[i] = _render(i, cfg)
    else:
        with ThreadPoolExecutor(max_workers=nw) as ex:
            futs = {ex.submit(_render, i, cfg): i for i, cfg in enumerate(clips_cfg)}
            for f in as_completed(futs):
                clip_times[futs[f]] = f.result()
    wall_total = time.perf_counter() - wall_start

    valid = [u for u in gpu_utils if u >= 0]
    return {
        'nw': nw, 'clip_times': clip_times, 'wall_total': wall_total,
        'avg_clip': sum(clip_times) / len(clip_times),
        'min_clip': min(clip_times), 'max_clip': max(clip_times),
        'peak_vram_mb': peak_vram,
        'avg_gpu': int(sum(valid) / len(valid)) if valid else -1,
        'clips_per_min': NUM_CLIPS / (wall_total / 60) if wall_total > 0 else 0,
        'vid_rtf': (NUM_CLIPS * CLIP_DURATION) / wall_total if wall_total > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — RUN ALL PASSES
# ═══════════════════════════════════════════════════════════════════════════════
wlist = list(WORKER_CONFIGS)
if vram_total == 0 or vram_total >= 6000:
    wlist.append(4)
else:
    print(f'VRAM {vram_total}MB < 6GB: skipping 4-worker test.')

results = []
for nw in wlist:
    pid = f'st_w{nw}'
    for i in range(NUM_CLIPS):
        (CLIPS_DIR / (pid + f'_c{i}')).mkdir(parents=True, exist_ok=True)
    print(f'\n{"-"*55}\nPASS: {nw} WORKER(S)\n{"-"*55}')
    pr = run_pass(nw, pid)
    results.append(pr)
    for ci, ct in enumerate(pr['clip_times']):
        print(f'  Clip {ci+1}: {ct:.2f}s  ({CLIP_DURATION/ct:.2f}x realtime)')
    print(f'  Total    : {pr["wall_total"]:.1f}s')
    print(f'  Avg/clip : {pr["avg_clip"]:.1f}s')
    print(f'  Clps/min : {pr["clips_per_min"]:.1f}')
    print(f'  Vid-s/s  : {pr["vid_rtf"]:.2f}x')
    if pr['peak_vram_mb'] > 0:
        print(f'  Pk VRAM  : {pr["peak_vram_mb"]} MB')
    if pr['avg_gpu'] >= 0:
        print(f'  Avg GPU  : {pr["avg_gpu"]}%')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — OUTPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
last_pid = f'st_w{wlist[-1]}'
print(f'\nOUTPUT VALIDATION (last pass: {wlist[-1]} workers)')
all_ok = True
for i in range(NUM_CLIPS):
    op = (CLIPS_DIR / (last_pid + f'_c{i}')).resolve() / '0.mp4'
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(op)],
            capture_output=True, text=True
        )
        data    = json.loads(r.stdout)
        streams = data.get('streams', [])
        fmt     = data.get('format', {})
        v = next((s for s in streams if s.get('codec_type') == 'video'), {})
        a = next((s for s in streams if s.get('codec_type') == 'audio'), {})
        w, h  = int(v.get('width', 0)), int(v.get('height', 0))
        dur   = float(fmt.get('duration', 0))
        sz    = op.stat().st_size / (1024 * 1024) if op.exists() else 0
        issues = []
        if w != TARGET_W or h != TARGET_H: issues.append(f'res {w}x{h}')
        if not a: issues.append('no audio')
        if dur < CLIP_DURATION * 0.8: issues.append(f'dur {dur:.1f}s')
        ok = not issues
        if not ok: all_ok = False
        detail = (f'{w}x{h} | {v.get("codec_name")} | {a.get("codec_name","none")} | {dur:.1f}s | {sz:.1f}MB'
                  if ok else str(issues))
        print(f'  [{"OK" if ok else "FAIL"}] Clip {i+1}: {detail}')
    except Exception as e:
        all_ok = False
        print(f'  [FAIL] Clip {i+1}: {e}')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — BENCHMARK TABLE + FINAL RESULT
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('=' * 62)
print('CLIPFORGE GPU STRESS TEST')
print('=' * 62)
print(f'GPU  : {gpu_name}')
print(f'NVENC: {"YES" if nvenc_ok else "NO (CPU)"}')
print(f'Clips: {NUM_CLIPS} x {CLIP_DURATION:.0f}s = {NUM_CLIPS*CLIP_DURATION:.0f}s total')
print(f'Res  : {TARGET_W}x{TARGET_H}')
print()
print(f'{"WORKERS":<8} | {"TOTAL":>9} | {"AVG CLIP":>9} | {"CLIPS/MIN":>10} | {"VID-SEC/S":>10} | {"PEAK VRAM":>10}')
print(f'{"-"*8}-+-{"-"*9}-+-{"-"*9}-+-{"-"*10}-+-{"-"*10}-+-{"-"*10}')
for r in results:
    vs = f'{r["peak_vram_mb"]} MB' if r['peak_vram_mb'] > 0 else 'N/A'
    print(f'{r["nw"]:<8} | {r["wall_total"]:>8.1f}s | {r["avg_clip"]:>8.1f}s | '
          f'{r["clips_per_min"]:>9.1f}  | {r["vid_rtf"]:>9.2f}x | {vs:>10}')

best     = min(results, key=lambda x: x['wall_total'])
best_rtf = (NUM_CLIPS * CLIP_DURATION) / best['wall_total']

print()
print('=' * 62)
print('FINAL RESULT')
print('=' * 62)
print('OLD BASELINE:')
print('  ~102.4 sec / 30s clip  (libx264 preset medium, Lanczos, sequential)')
print()
print('BEST CONFIGURATION:')
print(f'  {best["nw"]} worker(s)')
print('BEST SINGLE-CLIP TIME:')
print(f'  {results[0]["min_clip"]:.1f}s  (1-worker pass, fastest clip)')
print('TOTAL 6-CLIP TIME:')
print(f'  {best["wall_total"]:.1f}s  ({best["wall_total"]/60:.2f} min)')
print('THROUGHPUT:')
print(f'  {best["clips_per_min"]:.1f} clips/min')
print('REALTIME THROUGHPUT:')
print(f'  {best_rtf:.2f}x  ({NUM_CLIPS*CLIP_DURATION:.0f} video-sec in {best["wall_total"]:.1f} real sec)')
print('PEAK VRAM:')
print(f'  {best["peak_vram_mb"]} MB' if best['peak_vram_mb'] > 0 else '  N/A')
print('NVENC:')
print(f'  {"PASS" if nvenc_ok else "NOT AVAILABLE (CPU fallback used)"}')
print('OUTPUT VALIDATION:')
print(f'  {"PASS" if all_ok else "FAIL"}')
print('RECOMMENDED PRODUCTION WORKERS:')
print(f'  {best["nw"]}')
print('=' * 62)
