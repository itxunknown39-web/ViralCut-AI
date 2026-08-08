# ViralCut AI — by Kamran AI

An AI-powered, local-first video clipping, reframing, and styled captioning toolkit.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/itxunknown39-web/ViralCut-AI/blob/main/ViralCut_AI_Colab.ipynb)
[![Local AI Processing](https://img.shields.io/badge/Local--First-100%25-00C9FF?style=flat-square)](#privacylocal-processing-explanation)
[![Hardware Acceleration](https://img.shields.io/badge/Hardware%20Accel-NVENC%20%7C%20QSV%20%7C%20AMF-008BFF?style=flat-square)](#gpu-and-cpu-behavior)
[![License Status](https://img.shields.io/badge/License-See%20Section-lightgrey?style=flat-square)](#license)

ViralCut AI transforms long-form video content or YouTube links into engaging vertical Shorts and Reels with animated, creator-styled captions, visual effects, and reframed layouts — operating **entirely on your local machine** (or in a free GPU Google Colab session) without external cloud AI subscriptions or API keys.

---

## Documentation Screenshots

*(Place screenshot images inside the `docs/` folder to preview the dashboard interface)*

```
docs/
├── dashboard.png
├── generation.png
└── captions.png
```

---

## Short Feature Overview

- 🔒 **100% Local-First Processing**: No OpenAI, Anthropic, or external API keys required. All speech recognition, clip analysis, and rendering occur locally.
- ⚡ **Hardware Accelerated Rendering**: Automatic detection and utilization of NVIDIA NVENC (`h264_nvenc`), Intel QSV (`h264_qsv`), or AMD AMF (`h264_amf`) GPU encoders, with an optimized multi-threaded CPU fallback (`libx264`).
- 🎙️ **Word-Level AI Transcription**: Powered by `faster-whisper` and CTranslate2 with VAD (Voice Activity Detection) and automatic language detection (with Hinglish transliteration support).
- 🧠 **Intelligent Local Virality Selector**: Heuristic clip analysis scoring density of speech, hook keywords, sentence completeness, and target duration (optional local Ollama integration).
- 🎨 **18 Creator Caption Presets**: Built-in ASS subtitle builder supporting Hormozi-style active word highlighting, MrBeast Pop, Karaoke Yellow, Boxed TikTok, Word Reveal, and custom font uploads.
- 📐 **Smart Reframing & Aspect Ratios**: Native 9:16 vertical Shorts/Reels output with blurred background + sharp foreground, or "Rounded Reel" mode (1:1 rounded square on 9:16 canvas).
- 🎵 **Reels-Style Audio Mixing & Ducking**: Background music integration with automatic sidechain compression that ducks music under voice speech.
- 🎬 **Cinematic Video Effects**: Color grading presets (Teal & Orange, Warm, Cool, Vintage), smooth highlights glow bloom, film grain, vignette, and gradient scrims.

---

## What the Application Does

ViralCut AI ingests a source video (from a local file upload or video URL via `yt-dlp`), transcribes the audio track to generate precise word-level timestamps, analyzes the transcript to select optimal highlight windows, reframes the video to 9:16 or 16:9 formats, burns styled ASS captions into the video stream, applies optional cinematic effects and background audio ducking, and exports production-ready `.mp4` clips.

---

## Input → Processing → Output Workflow

```
[ Input Source ]
  ├── YouTube / Video URL (yt-dlp)
  └── Local File Upload (.mp4, .mov, .mkv)
         │
         ▼
[ Local Speech Recognition ]
  └── faster-whisper (Word-Level Timestamps + Language Detection)
         │
         ▼
[ Highlight Window Analysis ]
  └── Local Heuristic Selector (Speech Density + Hooks + Completeness)
         │
         ▼
[ Subtitle & Graphic Generation ]
  └── ASS Subtitle Builder (Creator Presets + Word Highlighting + Custom Fonts)
         │
         ▼
[ FFmpeg Reframing & Render Engine ]
  ├── Crop / Reframing (9:16 Vertical Canvas)
  ├── Cinematic Effects (Glow + Gradients + Color Grades)
  ├── Audio Sidechain Ducking (Background Music)
  └── GPU Encoder (NVENC / QSV / AMF / CPU Fallback)
         │
         ▼
[ Output Distribution ]
  ├── Individual Rendered .mp4 Clips
  └── Real-Time Web Dashboard Preview & Download
```

---

## Real Usage Examples

### 1. Run in Google Colab (One-Click GPU Launcher)

Run ViralCut AI directly in Google Colab with free T4 GPU acceleration:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/itxunknown39-web/ViralCut-AI/blob/main/ViralCut_AI_Colab.ipynb)

1. Click the **Open In Colab** badge above.
2. Go to **Runtime → Change runtime type → T4 GPU**.
3. Select **Runtime → Run all**.
4. The notebook automatically clones the repository, sets up FFmpeg and dependencies, launches the FastAPI server, and displays your temporary public Cloudflare URL (`trycloudflare.com`).

---

### 2. Web Application Interface (Local PC)
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Python Pipeline API Execution
Execute the pipeline programmatically in Python:
```python
from app.downloader import download_video
from app.transcriber import transcribe_video
from app.selector import select_clips
from app.captions import build_ass
from app.clipper import generate_clip, ClipOptions
from app.models import AspectRatio, FitMode
from pathlib import Path

# 1. Download source video
source_path = download_video("https://www.youtube.com/watch?v=EXAMPLE")

# 2. Transcribe locally with Whisper
transcript = transcribe_video(source_path, clip_id="job_001", device="auto")

# 3. Select highlight clips
windows = select_clips(transcript, num_clips=3, clip_length=30.0)

# 4. Render clips
for idx, win in enumerate(windows):
    ass_path = Path(f"clips/job_001/{idx}.ass")
    build_ass(
        words=[w for w in transcript["words"] if win["start"] <= w["start"] <= win["end"]],
        style_preset="hormozi_green",
        video_w=1080,
        video_h=1920,
        out_path=ass_path,
        clip_start=win["start"]
    )
    
    opts = ClipOptions(
        aspect_ratio=AspectRatio.NINE_16,
        fit_mode=FitMode.CROP,
        ass_path=ass_path,
        clip_id="job_001",
        index=idx
    )
    output_mp4 = generate_clip(source_path, win["start"], win["end"], opts)
    print(f"Rendered clip {idx + 1}: {output_mp4}")
```

### 3. Pipeline Performance Benchmark
Run the built-in benchmark script to measure real elapsed wall-clock processing time:
```bash
python benchmark_pipeline.py
```

---

## Supported Aspect Ratios & Fit Modes

| Mode | Canvas Resolution | Aspect Ratio | Layout Behavior |
| :--- | :--- | :--- | :--- |
| **9:16 Vertical Crop** | 1080 x 1920 | 9:16 | Centers and crops the source video to cover the vertical canvas. |
| **16:9 Landscape** | 1920 x 1080 | 16:9 | Maintains original landscape widescreen dimensions. |
| **9:16 Square Reel** | 1080 x 1920 | 9:16 | Renders a 1:1 rounded square video container (1020x1020) centered on a 9:16 canvas with soft anti-aliased corners and optional top title text. |

---

## Creator Caption Presets

ViralCut AI includes 18 built-in caption presets configured for short-form video engagement:

| Preset Key | Preset Name | Animation / Style Features |
| :--- | :--- | :--- |
| `bold_white` | Bold White | Clean bold white text with black outline. |
| `karaoke_yellow` | Karaoke Yellow | Syllable-by-syllable karaoke color fill. |
| `hormozi_green` | Hormozi Green | Active word highlight in neon green (`#27E36B`) on Montserrat. |
| `hormozi_yellow` | Hormozi Yellow | Active word highlight in vivid yellow (`#FFD400`) on Montserrat. |
| `beast_red` | Beast Pop | Heavy pop typography with bright red highlight on Anton. |
| `one_word_punch` | One-Word Punch | Single word display at a time with pop-in scaling animation. |
| `word_reveal` | Word Reveal | Progressive fade & scale-in reveal per word. |
| `boxed_tiktok` | Boxed TikTok | Dark semi-transparent background box behind text. |
| `comic_bangers` | Comic Punch | Comic-book styled yellow and white typography on Bangers. |
| `serif_elegant` | Serif Elegant | Elegant classic editorial typography on DM Serif Display. |

---

## GPU and CPU Behavior

ViralCut AI automatically detects and utilizes available hardware acceleration for both speech recognition and video encoding:

- **Whisper Speech Recognition (`faster-whisper`)**:
  - **GPU (`cuda`)**: Uses NVIDIA CUDA with `float16` compute precision when a CUDA GPU is present.
  - **CPU (`cpu`)**: Falls back to CPU execution with quantized `int8` precision.
- **FFmpeg Video Encoding**:
  - Probes system hardware before rendering and selects the fastest available encoder:
    1. **NVIDIA NVENC**: `h264_nvenc`
    2. **Intel QSV**: `h264_qsv`
    3. **AMD AMF**: `h264_amf`
    4. **CPU Fallback**: `libx264` (with `-preset ultrafast -threads 0` multi-threading).

---

## Installation Guide

### Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **Node.js** (Optional, only for rebuilding the frontend): 18.x or higher
- **FFmpeg**: Required on system PATH

### Installing FFmpeg

#### Windows
```powershell
winget install Gyan.FFmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install -y ffmpeg
```

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/itxunknown39-web/ViralCut-AI.git
   cd ViralCut-AI
   ```

2. **Create and activate a Python virtual environment**:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## First-Run Behavior

On the initial execution:
1. **Directory Structure Setup**: Automatically creates runtime workspace directories (`downloads/`, `transcripts/`, `clips/`, `assets/fonts/`, `assets/masks/`, `assets/music/`).
2. **Core Font Provisioning**: Downloads standard Google Fonts (Roboto, Montserrat, Anton, Poppins, etc.) into `assets/fonts/`.
3. **Whisper Model Initialization**: Downloads the `medium` Whisper model weights (~1.5 GB) on first transcription request and caches them locally.

---

## Usage Guide

### Running the Web Server
Launch the FastAPI application server:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open `http://127.0.0.1:8000` in your web browser.

### Bypassing YouTube Cookie Requirements
If YouTube requires sign-in verification for a video:
1. Export a Netscape format `cookies.txt` file from your browser.
2. Upload `cookies.txt` in the UI settings or place it in the application root, or set the environment variable:
   ```bash
   export VIRALCUT_COOKIES_FILE="/path/to/cookies.txt"
   ```

---

## API Documentation

FastAPI provides an interactive OpenAPI document at `http://127.0.0.1:8000/docs`.

### Key Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | GET | Returns server health status and active compute device. |
| `/api/devices` | GET | Reports available compute devices (CUDA/CPU) and GPU name. |
| `/api/caption-styles` | GET | Returns available caption style presets for UI preview. |
| `/api/upload` | POST | Uploads a local video file (`multipart/form-data`). |
| `/api/prefetch` | POST | Starts background pre-downloading of a video URL. |
| `/api/pretranscribe` | POST | Starts background pre-transcription of a video file. |
| `/api/generate` | POST | Submits a clip generation job and returns a `job_id`. |
| `/api/progress/{job_id}`| GET | Server-Sent Events (SSE) endpoint streaming real-time progress. |
| `/api/history` | GET | Retrieves past clip generation records. |

---

## Project Structure

```
ViralCut-AI/
├── app/                        # Backend Python Application
│   ├── main.py                 # FastAPI application routes & lifecycle
│   ├── jobs.py                 # Asynchronous job queue & SSE progress runner
│   ├── downloader.py           # yt-dlp downloader & cookie validation
│   ├── transcriber.py          # faster-whisper model loader & transcription
│   ├── selector.py             # Local heuristic clip window selection
│   ├── captions.py             # ASS subtitle builder & caption presets
│   ├── clipper.py              # FFmpeg video reframing & render pipeline
│   ├── effects.py              # Cinematic filtergraph effects
│   ├── models.py               # Pydantic data schemas
│   ├── fonts.py                # Font manager
│   ├── history.py              # History manager
│   └── paths.py                # Workspace directory paths
├── web/                        # React / Vite Web Frontend
│   ├── src/                    # UI Components & Pages
│   │   ├── App.jsx             # Main Shell & Sidebar
│   │   ├── pages/Create.jsx    # Clip Creation Workflow Page
│   │   └── styles.css          # Design System Stylesheet (#00C9FF cyan theme)
│   └── dist/                   # Production Web Assets
├── static/                     # Legacy static fallback UI
├── docs/                       # Documentation screenshots
├── benchmark_pipeline.py       # Performance benchmark utility
├── publish_to_github.py        # Automated publishing & security audit script
├── requirements.txt            # Python dependencies
└── README.md                   # Repository documentation
```

---

## Privacy / Local-Processing Explanation

ViralCut AI is designed as a **local-first** application. Your media files, transcripts, and generated video content are processed entirely on your machine:
- No video or audio bytes are sent to third-party cloud AI vendors.
- Transcription is performed locally via `faster-whisper` CTranslate2 models.
- Video reframing and subtitle burning occur locally using FFmpeg.

---

## Troubleshooting

### 1. `ffmpeg was not found on PATH`
Ensure FFmpeg is installed and accessible in your system terminal by running `ffmpeg -version`.

### 2. CUDA / cuBLAS DLL Missing on Windows
If `cublas64_12.dll` or `cudnn64_9.dll` is missing, ensure NVIDIA CUDA Toolkit 12 and matching cuDNN libraries are installed, or switch the compute device dropdown to `CPU`.

### 3. YouTube Sign-in / Bot Verification Error
If yt-dlp encounters a YouTube bot check:
- Provide a `cookies.txt` file via the upload option or set `VIRALCUT_COOKIES_FILE`.
- Ensure `yt-dlp` is updated to the latest release (`pip install -U yt-dlp`).

---

## Performance Considerations

- **GPU Acceleration**: NVIDIA NVENC encoding renders 1080p clips in seconds compared to CPU encoding.
- **Glow Bloom Optimization**: Highlight bloom blurring is performed at half-resolution before screening, providing a 4x speedup.
- **Gradient Scrim Optimization**: Gradient dark scrims use 8 smoothstep bands to eliminate unnecessary filter graph evaluation overhead.

---

## Roadmap

- [ ] Dynamic multi-speaker speaker diarization.
- [ ] Auto-tracking facial crop centering for dynamic speaker framing.
- [ ] Custom ASS subtitle animation timeline editor.
- [ ] Batch folder import for bulk video clipping.

---

## Contributing

Contributions, bug reports, and feature requests are welcome. Please open an issue or submit a pull request on GitHub.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## Credits & Attribution

ViralCut AI integrates and builds upon open-source software libraries and frameworks:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: Video fetching and Netscape cookie parsing engine.
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)**: CTranslate2 reimplementation of OpenAI's Whisper model.
- **[FFmpeg](https://ffmpeg.org/)**: Multimedia framework for video scaling, filtering, subtitle burning, and encoding.
- **[indic-transliteration](https://github.com/indic-transliteration/indic_transliteration_py)**: Transliteration utilities for Hindustani/Hinglish text support.
- **[FastAPI](https://fastapi.tiangolo.com/)**: High-performance web framework for Python APIs.
- **[React](https://react.dev/) & [Vite](https://vitejs.dev/)**: Web UI frontend framework and bundler.

*Notice: ViralCut AI is an independent open-source project and is not affiliated with OpenAI, Google, or YouTube.*

---

## License

Users should review the repository's licensing status and third-party dependency licenses (such as LGPL/GPL for FFmpeg and MIT/Apache-2.0 for Python libraries) when distributing or modifying this software.
