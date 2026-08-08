// Minimal phone-frame wrapper used in clip cards (Review & Export screens).
// Unlike PhonePreview (the full interactive mockup with caption overlays),
// this is just a native <video> inside a small rounded frame — used when we
// already have a rendered clip file, not a live preview.
export default function ClipPhone({ src }) {
  return (
    <div className="clip-phone">
      <video src={src} controls preload="metadata" />
    </div>
  );
}
