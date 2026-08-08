import { useState } from "react";
import { captionLineStyle, effectiveCfg } from "../../caption.js";
import Customizer from "../../components/Customizer.jsx";
import PhonePreview from "../../components/PhonePreview.jsx";
import Transcript from "../../components/Transcript.jsx";
import { Icons } from "../../components/Icons.jsx";

function Chip({ label, cfg, active, trending, custom, onClick, onDelete }) {
  const words = (label || "Aa").split(/\s+/).slice(0, 2);
  const style = captionLineStyle(cfg, { fontPx: 16, scale: 0.16 });
  const hl = (cfg.animation === "highlight" || cfg.karaoke) ? words.length - 1 : -1;
  return (
    <button type="button" className={"chip" + (active ? " active" : "")} onClick={onClick}>
      {custom ? <span className="tag custom">Custom</span> : trending ? <span className="tag">Trending</span> : null}
      {custom && <span className="chip-del" onClick={(e) => { e.stopPropagation(); onDelete(); }}>✕</span>}
      <span className="stage"><span className="sample" style={style}>
        {words.map((w, i) => <span key={i} style={{ color: i === hl ? (cfg.highlight_color || "#FFD400") : undefined }}>{w} </span>)}
      </span></span>
      <span className="name">{label}</span>
    </button>
  );
}

function SaveBlock({ s, open, setOpen }) {
  const [name, setName] = useState("");
  const commit = () => { if (s.saveCurrentPreset(name)) { setOpen(false); setName(""); } };
  if (!open) return null;
  return (
    <div className="save-form">
      <input type="text" placeholder="Name your style…" value={name} maxLength={40} autoFocus
        onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setOpen(false); }} />
      <button className="btn btn-primary" onClick={commit}>Save</button>
      <button className="btn" onClick={() => setOpen(false)}>✕</button>
    </div>
  );
}

// Screen 3 — Transcription & Caption Styles. Transcription already started in
// the background the moment Screen 2 was entered (usePrep); this screen just
// surfaces its progress alongside the full style picker (built-in themes,
// live customizer, and saveable custom presets — unchanged from before).
export default function Screen3Captions({
  studio, language, onFontUpload, media, prepView, sourceReady,
  transcript, curTime, seekTo, aspect, fit, barText, signature, setSig, videoRef,
  onBack, onNext,
}) {
  const [tab, setTab] = useState("styles");
  const [saveOpen, setSaveOpen] = useState(false);

  const s = studio;
  // effectiveCfg(presets, styleId, overrides)
  const cfg = effectiveCfg(s.presets, s.styleId, s.overrides);

  // Combine built-in presets with user presets
  const allPresets = [
    ...(s.presets || []).filter((p) => p.trending),
    ...(s.presets || []).filter((p) => !p.trending),
    ...(s.userPresets || []).map((up) => ({ ...up, custom: true })),
  ];

  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="card w3-left" style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          <div className="card-h" style={{ marginBottom: 0 }}>
            <h2>Caption style</h2>
            {tab === "customize" && (
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <SaveBlock s={s} open={saveOpen} setOpen={setSaveOpen} />
                {!saveOpen && <button className="btn" style={{ fontSize: 12, padding: "4px 10px" }} onClick={() => setSaveOpen(true)}>Save preset</button>}
              </div>
            )}
          </div>

          <div className="cc-tabs" style={{ margin: "0 0 12px" }}>
            <button className={"cc-tab" + (tab === "styles" ? " active" : "")} onClick={() => setTab("styles")}>Styles</button>
            <button className={"cc-tab" + (tab === "transcript" ? " active" : "")} onClick={() => setTab("transcript")}>Transcript</button>
            <button className={"cc-tab" + (tab === "customize" ? " active" : "")} onClick={() => setTab("customize")}>Customize</button>
          </div>

          <div className="cc-body" style={{ flex: 1, overflow: "auto" }}>
            {tab === "styles" && (
              <div className="chips">
                {allPresets.map((p) => (
                  <Chip
                    key={p.id} label={p.label} cfg={p} active={s.activeKey === p.id || s.styleId === p.id}
                    trending={p.trending} custom={p.custom}
                    onClick={() => p.custom ? s.selectUserPreset(p) : s.selectPreset(p.id)}
                    onDelete={() => s.removeUserPreset(p.id)}
                  />
                ))}
              </div>
            )}
            {tab === "transcript" && (
              <Transcript state={transcript} onSeek={seekTo} currentTime={curTime} />
            )}
            {tab === "customize" && (
              <Customizer studio={studio} onFontUpload={onFontUpload} />
            )}
          </div>
        </div>

        <div className="w3-preview">
          <PhonePreview cfg={s.cfg} cinematic={s.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            signature={signature} setSig={setSig} videoRef={videoRef}
            overrides={s.overrides} setOverride={s.setOverride} />

          {prepView && (
            <div className={"prep prep-" + (prepView.phase || "idle")}>
              <div className="prep-row">
                <span className="prep-msg">
                  {["downloading", "transcribing", "downloaded", "idle"].includes(prepView.phase) && <span className="spinner" />}
                  {prepView.phase === "ready" && <span className="prep-ok">✓</span>}
                  {prepView.phase === "error" && <span className="prep-ok" style={{ color: "var(--danger)" }}>!</span>}
                  {prepView.message || "Preparing video…"}
                </span>
                {prepView.pct != null && <span className="prep-pct">{prepView.pct}%</span>}
              </div>
              <div className="track"><div className={"fill" + (prepView.pct == null ? " indeterminate" : "")} style={prepView.pct == null ? {} : { width: prepView.pct + "%" }} /></div>
            </div>
          )}
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn btn-primary" onClick={onNext}>Next →</button>
      </div>
    </div>
  );
}
