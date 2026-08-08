import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { Icons } from "./Icons.jsx";

// Linear interpolation between the two keyframes bracketing t — mirrors the
// backend's ffmpeg crop-x/y/zoom expressions (app/clipper.py::_crop_filter)
// exactly, so the live preview here matches the eventual render.
function interpAt(keyframes, t) {
  const norm = (k) => ({ pos_x: k.pos_x, pos_y: k.pos_y, zoom: k.zoom ?? 100 });
  if (!keyframes.length) return { pos_x: 50, pos_y: 50, zoom: 100 };
  const pts = [...keyframes].sort((a, b) => a.time - b.time);
  if (t <= pts[0].time) return norm(pts[0]);
  const last = pts[pts.length - 1];
  if (t >= last.time) return norm(last);
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (t >= a.time && t <= b.time) {
      const f = b.time > a.time ? (t - a.time) / (b.time - a.time) : 0;
      const az = a.zoom ?? 100, bz = b.zoom ?? 100;
      return {
        pos_x: a.pos_x + (b.pos_x - a.pos_x) * f,
        pos_y: a.pos_y + (b.pos_y - a.pos_y) * f,
        zoom: az + (bz - az) * f,
      };
    }
  }
  return norm(last);
}

function upsertKeyframe(keyframes, time, pos) {
  const EPS = 0.05;
  const idx = keyframes.findIndex((k) => Math.abs(k.time - time) < EPS);
  const kf = {
    time: Math.max(0, +time.toFixed(2)),
    pos_x: Math.round(pos.pos_x * 10) / 10,
    pos_y: Math.round(pos.pos_y * 10) / 10,
    zoom: Math.round(Math.max(40, Math.min(100, pos.zoom ?? 100)) * 10) / 10,
  };
  const next = idx >= 0 ? keyframes.map((k, i) => (i === idx ? kf : k)) : [...keyframes, kf];
  return next.sort((a, b) => a.time - b.time);
}

const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;

// Reframe Editor — opens the clip's original (uncropped) source segment in a
// dedicated timeline so the crop position AND size can be manually keyframed.
// Saving re-renders this ONE clip immediately; interpolation between points is
// smooth/linear, not a discrete jump.
export default function ReframeEditor({ clipId, clip, targetAspect, initialKeyframes, onClose, onSaved }) {
  const videoRef = useRef(null);
  const [keyframes, setKeyframes] = useState(
    initialKeyframes && initialKeyframes.length ? initialKeyframes : [{ time: 0, pos_x: 50, pos_y: 50, zoom: 100 }]
  );
  const [curTime, setCurTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [natural, setNatural] = useState(null); // { w, h } of the source video
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dragRef = useRef(null);
  const stageRef = useRef(null);

  const duration = Math.max(0.1, clip.end - clip.start);
  const srcUrl = api.clipSourceUrl ? api.clipSourceUrl(clipId, clip.index) : `/api/clips/${clipId}/source/${clip.index}`;

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onMeta = () => { setNatural({ w: v.videoWidth, h: v.videoHeight }); v.currentTime = clip.start; };
    const onTime = () => {
      let rel = v.currentTime - clip.start;
      if (rel >= duration) { v.pause(); setPlaying(false); rel = duration; v.currentTime = clip.start + duration; }
      if (rel < 0) rel = 0;
      setCurTime(rel);
    };
    const onPause = () => setPlaying(false);
    v.addEventListener("loadedmetadata", onMeta);
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("pause", onPause);
    if (v.readyState >= 1) onMeta();
    return () => {
      v.removeEventListener("loadedmetadata", onMeta);
      v.removeEventListener("timeupdate", onTime);
      v.removeEventListener("pause", onPause);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipId, clip.index]);

  function seek(rel) {
    const clamped = Math.max(0, Math.min(duration, rel));
    setCurTime(clamped);
    const v = videoRef.current;
    if (v) { try { v.currentTime = clip.start + clamped; } catch { /* not seekable yet */ } }
  }

  function togglePlay() {
    const v = videoRef.current;
    if (!v) return;
    if (playing) { v.pause(); setPlaying(false); }
    else { v.play(); setPlaying(true); }
  }

  const current = useMemo(() => interpAt(keyframes, curTime), [keyframes, curTime]);

  // Compute overlay rect (the crop rectangle shown on top of the video)
  const overlay = useMemo(() => {
    if (!natural) return null;
    const zoom = (current.zoom ?? 100) / 100;
    const srcAr = natural.w / natural.h;
    // target aspect: 9/16 or 16/9 etc
    let ar = targetAspect;
    if (typeof ar === "string") {
      const [a, b] = ar.split(":").map(Number);
      ar = a / b;
    }
    // crop width and height as fractions of source
    let cw, ch;
    if (srcAr > ar) { ch = zoom; cw = ch * ar / srcAr; }
    else { cw = zoom; ch = cw * srcAr / ar; }
    const cx = (current.pos_x / 100) * (1 - cw) + cw / 2;
    const cy = (current.pos_y / 100) * (1 - ch) + ch / 2;
    return { left: `${(cx - cw / 2) * 100}%`, top: `${(cy - ch / 2) * 100}%`, width: `${cw * 100}%`, height: `${ch * 100}%` };
  }, [natural, current, targetAspect]);

  function handleStageClick(e) {
    if (!stageRef.current || !natural) return;
    const rect = stageRef.current.getBoundingClientRect();
    const rx = (e.clientX - rect.left) / rect.width;
    const ry = (e.clientY - rect.top) / rect.height;
    const pos_x = Math.max(0, Math.min(100, rx * 100));
    const pos_y = Math.max(0, Math.min(100, ry * 100));
    setKeyframes((kf) => upsertKeyframe(kf, curTime, { ...current, pos_x, pos_y }));
  }

  function removeKeyframe(t) {
    setKeyframes((kf) => kf.filter((k) => Math.abs(k.time - t) > 0.01));
  }

  async function save() {
    setSaving(true); setError("");
    try {
      const result = await api.rerender(clipId, clip.index, keyframes);
      onSaved && onSaved(clip.index, keyframes, result);
      onClose();
    } catch (e) {
      setError(e.message || "Re-render failed.");
      setSaving(false);
    }
  }

  return (
    <div className="reframe-overlay">
      <div className="reframe-modal">
        <div className="reframe-header">
          <h2>Reframe clip</h2>
          <button className="btn btn-ghost" onClick={onClose}>✕ Close</button>
        </div>

        {error && <div className="error">{error}</div>}

        {/* Video stage */}
        <div className="reframe-stage" ref={stageRef} onClick={handleStageClick} style={{ cursor: "crosshair" }}>
          <video ref={videoRef} src={srcUrl} preload="metadata" style={{ width: "100%", display: "block" }} />
          {overlay && (
            <div className="reframe-crop" style={{ position: "absolute", ...overlay, border: "2px solid var(--accent)", pointerEvents: "none" }} />
          )}
        </div>

        {/* Playback controls */}
        <div className="reframe-controls">
          <button className="btn" onClick={togglePlay}>{playing ? "⏸" : "▶"}</button>
          <input
            type="range" min={0} max={duration} step={0.033} value={curTime}
            onChange={(e) => seek(+e.target.value)}
            style={{ flex: 1 }}
          />
          <span style={{ fontSize: 12, opacity: 0.7 }}>{fmt(curTime)} / {fmt(duration)}</span>
        </div>

        {/* Zoom control */}
        <div className="row" style={{ gap: 12, alignItems: "center", marginTop: 10 }}>
          <label className="fieldlabel" style={{ marginBottom: 0, whiteSpace: "nowrap" }}>Zoom ({Math.round(current.zoom ?? 100)}%)</label>
          <input type="range" min={40} max={100} step={1} value={current.zoom ?? 100}
            onChange={(e) => setKeyframes((kf) => upsertKeyframe(kf, curTime, { ...current, zoom: +e.target.value }))}
            style={{ flex: 1 }} />
        </div>

        {/* Keyframes list */}
        <div style={{ marginTop: 14 }}>
          <div className="fieldlabel">Keyframes ({keyframes.length})</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
            {keyframes.map((kf) => (
              <div key={kf.time} className={"kf-chip" + (Math.abs(kf.time - curTime) < 0.05 ? " active" : "")}
                onClick={() => seek(kf.time)} style={{ cursor: "pointer", display: "flex", gap: 4, alignItems: "center" }}>
                <span style={{ fontSize: 11 }}>{fmt(kf.time)}</span>
                {keyframes.length > 1 && (
                  <button style={{ border: "none", background: "none", cursor: "pointer", padding: 0, opacity: 0.6, fontSize: 10 }}
                    onClick={(e) => { e.stopPropagation(); removeKeyframe(kf.time); }}>✕</button>
                )}
              </div>
            ))}
          </div>
          <p className="fieldlabel" style={{ marginTop: 6, opacity: 0.6 }}>Click on the video to set the crop position at the current time. A keyframe is added automatically.</p>
        </div>

        {/* Actions */}
        <div className="wizard-nav" style={{ marginTop: 16 }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? "Re-rendering…" : "Save & Re-render"}
          </button>
        </div>
      </div>
    </div>
  );
}
