"""Download the source video with yt-dlp (the only video-fetch network call).

We use the yt-dlp *Python API* rather than shelling out so failures surface as
exceptions we can translate into a clean 400. The server must never crash on a
bad or blocked URL.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .models import InvalidVideoURLError
from .paths import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Strip ANSI colour codes yt-dlp sometimes embeds in its error strings.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Browsers we'll borrow cookies from (in order) when YouTube throws up a
# sign-in / "confirm you're not a bot" wall. Override with env vars below.
_DEFAULT_BROWSERS = ["chrome", "edge", "brave", "firefox", "opera", "vivaldi"]
_COOKIE_FILE_ENV = "CLIPFORGE_COOKIES_FILE"       # path to a cookies.txt
_COOKIE_BROWSER_ENV = "CLIPFORGE_COOKIES_BROWSER"  # force one browser, e.g. "chrome"


def _needs_cookies(reason: str) -> bool:
    """True when a failure reason looks like a sign-in / bot / cookie wall —
    used to add a helpful cookie hint to the final error message.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "sign in", "not a bot", "cookie", "log in", "login", "consent",
        "age", "members-only", "account", "authentication",
    ))


def _is_terminal(reason: str) -> bool:
    """True when no retry (other client / cookies) can possibly help, so we stop
    early instead of grinding through every fallback for a dead/blocked link.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "unavailable", "been removed", "does not exist", "no longer",
        "unsupported url", "not available in your", "is not a valid",
        "deleted", "terminated",
    ))


# YouTube player clients to fall back through. Different clients are served by
# different endpoints, and the cookie-free mobile/TV ones frequently slip past
# the "confirm you're not a bot" wall the default web client trips.
_PLAYER_CLIENTS = ["android", "ios", "mweb", "tv", "web_creator"]


def _download_attempts(base_opts: dict) -> list[tuple[str, dict]]:
    """Ordered (label, ydl_opts) attempts.

    Order is cheapest-and-most-likely first:
      1. explicit cookies file or forced browser (only if configured by user/env),
      2. the plain default pass (fast for public videos),
      3. cookie-free alternate YouTube player clients (android, ios, mweb, tv, web_creator),
      4. browser cookies as a last-resort fallback on Windows/desktop (skipped on Colab/Linux).
    """
    cookie_file = os.environ.get("VIRALCUT_COOKIES_FILE") or os.environ.get(_COOKIE_FILE_ENV)
    forced = os.environ.get("VIRALCUT_COOKIES_BROWSER") or os.environ.get(_COOKIE_BROWSER_ENV)

    attempts: list[tuple[str, dict]] = []
    if cookie_file and os.path.exists(cookie_file):
        attempts.append(("cookies file", {**base_opts, "cookiefile": cookie_file}))
    if forced:
        b = forced.strip().lower()
        attempts.append((f"{b} cookies", {**base_opts, "cookiesfrombrowser": (b,)}))

    attempts.append(("default", dict(base_opts)))

    for client in _PLAYER_CLIENTS:
        attempts.append((
            f"{client} client",
            {**base_opts, "extractor_args": {"youtube": {"player_client": [client]}}},
        ))

    # Auto-try desktop browser cookies only when on Windows/desktop PC where browser profile databases exist,
    # avoiding unnecessary missing browser database probing/errors on headless Linux/Colab.
    if not forced and sys.platform == "win32":
        for b in _DEFAULT_BROWSERS:
            attempts.append((f"{b} cookies", {**base_opts, "cookiesfrombrowser": (b,)}))

    return attempts


def _clean_ydl_error(raw: str) -> str:
    """Turn a raw yt-dlp DownloadError string into one short, readable line."""
    text = _ANSI_RE.sub("", raw or "").strip()
    line = text.splitlines()[0] if text else ""
    line = re.sub(r"^ERROR:\s*", "", line).strip()
    line = re.split(r";\s*(please report|you might want)", line, maxsplit=1)[0].strip()
    line = re.sub(r"^\[[^\]]+\]\s*[^:]*:\s*", "", line)
    return line[:300]


def probe_source_info(filepath: Path) -> dict:
    """Probe video file once and return key stream metadata."""
    import json, subprocess
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(filepath)
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            v = next((s for s in streams if s.get("codec_type") == "video"), {})
            a = next((s for s in streams if s.get("codec_type") == "audio"), {})
            size_mb = filepath.stat().st_size / (1024 * 1024) if filepath.exists() else 0
            info = {
                "width": int(v.get("width", 0)),
                "height": int(v.get("height", 0)),
                "codec": v.get("codec_name", "unknown"),
                "fps": v.get("r_frame_rate", "30/1"),
                "bitrate_kbps": int(fmt.get("bit_rate", 0)) // 1000 if fmt.get("bit_rate") else 0,
                "audio_codec": a.get("codec_name", "none"),
                "size_mb": round(size_mb, 1),
                "duration": float(fmt.get("duration", 0)),
            }
            logger.info(
                "📹 Source Video Probed: %dx%d | Codec=%s | FPS=%s | Audio=%s | Size=%.1fMB | Dur=%.1fs",
                info["width"], info["height"], info["codec"], info["fps"],
                info["audio_codec"], info["size_mb"], info["duration"]
            )
            return info
    except Exception as exc:
        logger.warning("Could not probe source metadata for %s: %s", filepath, exc)
    return {}


def _is_temp_file(path: Path) -> bool:
    """True if path points to a temporary download file (.part, .ytdl, etc.)."""
    name_lower = path.name.lower()
    return (
        name_lower.endswith((".part", ".ytdl", ".temp", ".tmp"))
        or ".part-frag" in name_lower
        or ".part." in name_lower
        or name_lower.endswith(".part")
    )


def _find_completed_path(clip_uuid: str) -> Optional[Path]:
    """Find the non-temporary, completed output file for clip_uuid in DOWNLOADS_DIR."""
    expected_path = DOWNLOADS_DIR / f"{clip_uuid}.mp4"
    if expected_path.exists() and expected_path.stat().st_size > 0 and not _is_temp_file(expected_path):
        return expected_path

    candidates = [
        p for p in DOWNLOADS_DIR.glob(f"{clip_uuid}.*")
        if p.is_file() and p.stat().st_size > 0 and not _is_temp_file(p)
    ]
    if candidates:
        mp4_candidates = [p for p in candidates if p.suffix.lower() == ".mp4"]
        return mp4_candidates[0] if mp4_candidates else candidates[0]

    return None


def download_video(
    url: str, progress_hook: Optional[Callable[[dict], None]] = None
) -> Path:
    """Download `url` to downloads/<uuid>.mp4 and return the file path."""
    import time

    if not url or not url.strip():
        raise InvalidVideoURLError("No video URL was provided.")

    clip_uuid = uuid.uuid4().hex
    out_template = str(DOWNLOADS_DIR / f"{clip_uuid}.%(ext)s")

    # HD download strategy:
    # 1. Prefer H.264/AVC 1080p for optimal CPU decoding performance prior to GPU NVENC rendering.
    # 2. Fall back to any 1080p codec.
    # 3. Fall back to best video/audio up to 1080p.
    # 4. Fall back to best available. Max resolution capped at 1080p (no unnecessary 4K downloads).
    preferred_format = (
        "bestvideo[height<=1080][vcodec^=avc1]+bestaudio/"
        "bestvideo[height<=1080]+bestaudio/"
        "best[height<=1080]/"
        "bestvideo+bestaudio/"
        "best"
    )

    base_opts = {
        "format": preferred_format,
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 15,
        "continuedl": True,
        "nocheckcertificate": True,
    }
    if progress_hook is not None:
        base_opts["progress_hooks"] = [progress_hook]

    last_reason = ""
    last_exc: Optional[Exception] = None
    ok = False
    for label, opts in _download_attempts(base_opts):
        logger.info(
            "[DOWNLOAD]\nClient: %s\nFormat selector: %s",
            label, opts.get("format")
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url.strip()])
            ok = True
            logger.info("[DOWNLOAD ATTEMPT SUCCESS] Client: %s", label)
            break
        except Exception as exc:  # noqa: BLE001
            last_reason = _clean_ydl_error(str(exc))
            last_exc = exc
            logger.warning("[DOWNLOAD ATTEMPT FAILED] Client: %s | Reason: %s", label, last_reason)
            if _is_terminal(last_reason):
                break

    if not ok:
        msg = ("Could not download that video. Check the URL is correct, public, "
               "and reachable from this machine.")
        if last_reason:
            msg += f"\nReason: {last_reason}"
        if _needs_cookies(last_reason):
            msg += (
                "\n\nThis video is behind YouTube's sign-in / bot check. Make sure "
                "you're logged into YouTube in your browser, then close the browser "
                "and try again. To pin a browser set VIRALCUT_COOKIES_BROWSER "
                "(chrome/edge/firefox), or point VIRALCUT_COOKIES_FILE at a cookies.txt."
            )
        raise InvalidVideoURLError(msg) from last_exc

    # Atomic completion wait: Poll briefly for temporary files to finish postprocessing/renaming.
    final_path: Optional[Path] = None
    for _ in range(15):
        final_path = _find_completed_path(clip_uuid)
        if final_path:
            break
        time.sleep(0.2)

    if not final_path or _is_temp_file(final_path):
        raise InvalidVideoURLError(
            "The download completed but no valid output file was produced or the file remained incomplete (.part)."
        )

    info = probe_source_info(final_path)
    if not info or info.get("width", 0) == 0:
        raise InvalidVideoURLError(
            "The downloaded video file is invalid or corrupt (ffprobe failed to validate streams)."
        )

    logger.info(
        "[DOWNLOAD COMPLETE]\nPath: %s\nSize: %.1f MB\nResolution: %dx%d\nCodec: %s",
        final_path, info.get("size_mb", 0.0), info.get("width", 0), info.get("height", 0), info.get("codec", "unknown")
    )

    logger.info(
        "[FFPROBE VALIDATION]\nVideo stream: present (%dx%d, %s, %s fps)\nAudio stream: %s (%s)\nDuration: %.1fs",
        info.get("width", 0), info.get("height", 0), info.get("codec", "unknown"), info.get("fps", "unknown"),
        "present" if info.get("audio_codec", "none") != "none" else "absent", info.get("audio_codec", "none"), info.get("duration", 0.0)
    )

    return final_path

