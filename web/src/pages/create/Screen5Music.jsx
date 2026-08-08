import Music from "../../components/Music.jsx";
import PhonePreview from "../../components/PhonePreview.jsx";

// Screen 5 — Background Music. Choose a track, set volume, ducking, and the
// start offset. Mood suggestion from the transcript (if ready) surfaces here.
export default function Screen5Music({
  studio, language, media, sourceReady, aspect, fit, barText, signature, setSig, videoRef,
  tracks, musicTrack, musicVolume, musicDuck, musicStart, musicSuggest,
  onTrack, onVolume, onDuck, onStart, onMusicUpload, onRefresh,
  onBack, onNext,
}) {
  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="card w3-left">
          <div className="card-h"><h2>Background music</h2></div>
          <Music
            tracks={tracks} track={musicTrack} volume={musicVolume}
            duck={musicDuck} musicStart={musicStart} suggest={musicSuggest}
            onTrack={onTrack} onVolume={onVolume} onDuck={onDuck}
            onStart={onStart} onUpload={onMusicUpload} onRefresh={onRefresh}
          />
        </div>

        <div className="w3-preview">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            signature={signature} setSig={setSig} videoRef={videoRef}
            overrides={studio.overrides} setOverride={studio.setOverride} />
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn btn-primary" onClick={onNext}>Next →</button>
      </div>
    </div>
  );
}
