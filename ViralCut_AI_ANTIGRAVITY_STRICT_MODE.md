# ViralCut AI — Antigravity STRICT MODE

## 0. ABSOLUTE RULE

STRICT MODE = ON.

When a task is marked `DONE`, `VERIFIED`, or `LOCKED`:
- NEVER modify it.
- NEVER refactor it.
- NEVER improve it unless explicitly requested.
- NEVER touch files outside the current task scope.
- If a new change would affect locked functionality, STOP and report the conflict.

A verified working component is more important than a cleaner implementation.

## 1. TASK PROTOCOL

For every new task:
1. Identify the exact error/request.
2. Identify the minimum files required.
3. Read the relevant code before editing.
4. Make the smallest possible change.
5. Do not modify unrelated functionality.
6. Run syntax/import validation.
7. Start/test the affected component.
8. Verify the original functionality still works.
9. Only then mark the task VERIFIED.
10. Report exactly which files changed.

NEVER:
- Rewrite large files unnecessarily.
- Redesign working architecture.
- Add speculative features.
- Change APIs without explicit instruction.
- Modify downloader, Whisper, FFmpeg, captions, GPU, or frontend just because they are nearby.

## 2. LOCKED COMPONENTS

### A — Colab / T4 GPU
STATUS: LOCKED
- NVIDIA Tesla T4 support must remain.
- CUDA must remain enabled.
- Faster-Whisper must remain on CUDA/float16.
- FFmpeg NVENC must remain available.
- Do not replace GPU execution with CPU.

### B — NVENC
STATUS: LOCKED
- `h264_nvenc` is active.
- Do not replace it with `libx264` unless explicitly requested.

### C — Whisper
STATUS: LOCKED
Current configuration:
- Faster-Whisper
- medium
- CUDA
- float16

Do not change model/device/compute type unless explicitly requested.

### D — Download → Transcribe handoff
STATUS: LOCKED
- `.part` / `.ytdl` temporary files must NEVER enter transcription.
- Only the completed final video path may enter transcription.
- FFprobe validation must occur before transcription.

### E — Caption frontend payload
STATUS: LOCKED
The frontend must send the complete effective caption configuration, including:
caption_style, font_family, primary_color, highlight_color, font_scale, animation, position, pos_x, pos_y, rotation, bold, uppercase, underline, strikethrough, karaoke, tracking, max_lines, max_chars, outline_width, outline_color, shadow_enabled, shadow_distance, shadow_color, shadow_opacity, background_enabled, background_color, background_opacity, glow_enabled, glow_color, glow_intensity.

Do not reduce this payload.

### F — Backend caption merge
STATUS: LOCKED
Do not rewrite caption merging unless the current task specifically concerns it. Optional request overrides should not accidentally erase preset values.

### G — Frontend build/sync
STATUS: LOCKED
Keep the frontend build/sync mechanism. Do not manually edit generated/minified bundles.

## 3. CURRENT VERIFIED FACTS

Latest Colab logs confirm:
- T4 detected.
- NVENC active.
- Whisper medium loaded on CUDA.
- FastAPI starts successfully.
- `/health` returns 200.
- Frontend loads.
- Android downloader fallback succeeds.
- Final `.mp4` is returned.
- FFprobe sees video and audio.
- No `.part` file enters transcription.
- Faster-Whisper successfully processes the source.
- Caption configuration reaches the backend.

Therefore, DO NOT reopen these components while fixing the current error.

## 4. CURRENT ACTIVE BUG

The latest confirmed failure is:

`app/captions.py` inside `build_ass()`:

```text
NameError: name 'logger' is not defined
```

Trace:
```text
app/jobs.py -> captions.build_ass()
app/captions.py -> logger.info(...)
NameError: name 'logger' is not defined
```

### REQUIRED FIX SCOPE

Only fix the missing logger definition/import in `app/captions.py`.

Preferred minimal implementation:

```python
import logging

logger = logging.getLogger(__name__)
```

Place it consistently with the existing module structure.

DO NOT:
- rewrite `build_ass()`
- change ASS styling
- change caption presets
- change caption payloads
- change FFmpeg
- change jobs.py
- change downloader.py
- change transcriber.py
- change frontend code

unless a new error is independently proven after this fix.

## 5. VALIDATION

After every fix:

```bash
python -m py_compile app/captions.py
python -m py_compile app/jobs.py
python -m py_compile app/main.py
```

Then start the server.

For caption changes verify:
- selected style reaches backend
- font reaches backend
- colors reach backend
- position reaches backend
- max_lines/max_chars reach backend
- ASS is generated
- FFmpeg burns ASS
- final MP4 is produced

Do not mark DONE from code inspection alone.

## 6. LOCK VERIFIED TASKS

When a task is genuinely verified, record:

```text
[LOCKED]
Task:
Files:
Verification:
Date:
```

Once LOCKED, do not modify it for unrelated tasks.

If a future task conflicts with locked functionality, report:

`CONFLICT: Requested change touches LOCKED functionality. I will not modify it without explicit authorization.`

## 7. ERROR-ONLY MODE

For an error:

ERROR
→ exact traceback
→ root cause
→ minimum affected file
→ minimum patch
→ syntax validation
→ runtime validation
→ regression check

One real error at a time. Do not fix hypothetical errors.

## 8. NO SCOPE CREEP

Example:
`Fix logger is not defined`

means ONLY fix the logger problem.

It does NOT mean:
- optimize downloader
- redesign captions
- change Whisper
- change GPU settings
- change FFmpeg
- change React
- add features
- refactor the repository

## 9. BEFORE EDITING

Before editing any file, determine:
- Is it part of a locked component?
- Is it actually required for the current error?
- Can the fix be made somewhere smaller?

If not required: DO NOT EDIT.

## 10. FINAL REPORT

Use:

```text
STATUS: FIXED / NOT FIXED

ROOT CAUSE:
<one sentence>

CHANGED FILES:
- <file>

UNCHANGED LOCKED FILES:
- <important locked components>

VALIDATION:
- Syntax: PASS/FAIL
- Server startup: PASS/FAIL
- Runtime test: PASS/FAIL

REGRESSION:
<what was verified>

NEXT ERROR:
<only if a new real error exists>
```

Never claim DONE unless runtime verification passed.

## 11. GOLDEN RULE

**DO NOT BREAK WORKING CODE WHILE FIXING BROKEN CODE.**

Minimal patch.
Exact scope.
Runtime verification.
Lock verified work.
