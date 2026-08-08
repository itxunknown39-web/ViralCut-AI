// SignaturePane — watermark/signature overlay controls.
// Lets the user toggle a text watermark and drag it across the phone preview
// (the preview itself handles the drag-to-reposition via setSig). This pane
// only surfaces the text content, toggle, size, colour and opacity sliders.
export default function SignaturePane({ signature, setSig }) {
  const { enabled, text, size, color, opacity } = signature;

  return (
    <div className="sig-pane">
      <div className="row" style={{ alignItems: "center", gap: 10, marginBottom: 10 }}>
        <label className="toggle-label">
          <input type="checkbox" checked={enabled} onChange={(e) => setSig("enabled", e.target.checked)} />
          <span>Show watermark</span>
        </label>
      </div>

      {enabled && (
        <>
          <label className="fieldlabel">Watermark text</label>
          <input
            type="text" className="cmd-input" style={{ marginBottom: 10 }}
            placeholder="@ViralCutAI" value={text}
            onChange={(e) => setSig("text", e.target.value)}
            maxLength={60}
          />

          <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label className="fieldlabel">Size ({size}px)</label>
              <input type="range" min={12} max={72} value={size}
                onChange={(e) => setSig("size", +e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 100 }}>
              <label className="fieldlabel">Opacity ({opacity}%)</label>
              <input type="range" min={10} max={100} value={opacity}
                onChange={(e) => setSig("opacity", +e.target.value)} />
            </div>
          </div>

          <label className="swatch" style={{ marginTop: 10 }}>
            Colour
            <input type="color" value={color} onChange={(e) => setSig("color", e.target.value)} />
          </label>

          <p className="fieldlabel" style={{ marginTop: 10, opacity: 0.65 }}>
            Drag the watermark on the preview to reposition it.
          </p>
        </>
      )}
    </div>
  );
}
