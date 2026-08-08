import { Icons } from "../../components/Icons.jsx";

// Screen 1 — Video Input. Only a URL paste or a file upload; nothing else to
// decide here. Choosing either lights up "Continue", which is the sole way
// forward (auto-advance to Screen 2 the moment a source is picked).
export default function Screen1Input({
  source, setSource, url, setUrl, upload, upPct, drag, setDrag, fileRef,
  doUpload, onClear, sourceReady, error, onContinue,
}) {
  const uploading = source === "upload" && upPct != null && !upload;
  const fileChosen = source === "upload" && (upload || upPct != null);

  return (
    <>
      <div className="landing">
        <div className="brand-hero">
          <span className="brand-mark"><Icons.bolt /></span>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.1 }}>
            <span className="brand-word">ViralCut AI</span>
            <span className="brand-by-hero">by Kamran AI</span>
          </div>
        </div>
        <span className="eyebrow"><span className="eyebrow-dot" />100% local AI pipeline · no API keys</span>
        <h1 className="landing-title">Turn any video into <span className="grad">captioned shorts</span></h1>
        <p className="landing-sub">
          Paste a link or drop a file — ViralCut AI finds the best moments, reframes them
          vertical, and burns on styled captions, right on your own machine.
        </p>

        <div
          className={"cmdbar" + (drag ? " drag" : "")}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); doUpload(e.dataTransfer.files[0]); }}
        >
          <input ref={fileRef} type="file" accept="video/*" hidden onChange={(e) => doUpload(e.target.files[0])} />
          <button className="cmd-upload" onClick={() => fileRef.current?.click()} title="Upload a video file">
            <Icons.upload /><span>Upload</span>
          </button>

          {fileChosen ? (
            <div className="cmd-file">
              <span className="cmd-file-name">{uploading ? `Uploading… ${upPct}%` : `✓ ${upload?.filename}`}</span>
              <button className="cmd-clear" onClick={onClear} title="Remove">✕</button>
            </div>
          ) : (
            <input
              className="cmd-input"
              type="text"
              placeholder="Paste a YouTube or video link…"
              value={url}
              onChange={(e) => { setSource("url"); setUrl(e.target.value); }}
              onKeyDown={(e) => { if (e.key === "Enter" && sourceReady) onContinue(); }}
            />
          )}

          <button className="cmd-go" disabled={!sourceReady} onClick={onContinue}>
            <Icons.bolt /> Generate
          </button>
        </div>

        {error && <div className="error landing-error">{error}</div>}

        <div className="landing-hints">
          {["Drag & drop a file onto the bar", "9:16 & 1:1 square", "19 caption styles", "Background music"].map((h) => (
            <span className="hint-chip" key={h}><span className="hc-check"><Icons.check /></span>{h}</span>
          ))}
        </div>
      </div>
    </>
  );
}
