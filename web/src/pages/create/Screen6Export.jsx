import ClipPhone from "../../components/ClipPhone.jsx";

// Screen 7 (file: Screen6Export.jsx) — Final Export. Each clip has a proper
// download link and a copy-link action. "Download all" staggers downloads so
// browsers don't block them.
export default function Screen6Export({ clips, onBack, onRestart }) {
  function downloadAll() {
    clips.forEach((c, i) => {
      setTimeout(() => {
        const a = document.createElement("a");
        a.href = c.url; a.download = c.filename || `clip-${i + 1}.mp4`;
        document.body.appendChild(a); a.click(); a.remove();
      }, i * 400);
    });
  }

  return (
    <div className="wizard-screen">
      <div className="card">
        <div className="card-h">
          <h2>All done — {clips.length} clip{clips.length === 1 ? "" : "s"} ready</h2>
          {clips.length > 1 && (
            <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={downloadAll}>
              Download all
            </button>
          )}
        </div>

        {clips.length > 0 ? (
          <div className="clips">
            {clips.map((c, idx) => (
              <div className="clip" key={c.url}>
                <ClipPhone src={c.url} />
                <div className="meta">
                  <h3>{c.title}</h3>
                  <div className="sub">{(c.end - c.start).toFixed(1)}s · {c.start.toFixed(1)}–{c.end.toFixed(1)}s</div>
                  <div className="acts">
                    <a href={c.url} download={c.filename || `clip-${idx + 1}.mp4`}>Download</a>
                    <button onClick={() => navigator.clipboard.writeText(location.origin + c.url)}>Copy link</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: "32px 0", textAlign: "center", opacity: 0.5 }}>
            <p>No clips to export. Go back and generate some first.</p>
          </div>
        )}

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <button className="btn btn-ghost" onClick={onRestart}>
            ← Start a new video
          </button>
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
      </div>
    </div>
  );
}
