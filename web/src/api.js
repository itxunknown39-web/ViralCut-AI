// Thin API client for the FastAPI backend. All paths are proxied by Vite in dev
// (see vite.config.js) so these are plain same-origin fetches.

async function jget(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function jpost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${path} → ${r.status}`);
  return data;
}

export const api = {
  health: () => jget("/health"),
  devices: () => jget("/api/devices"),
  captionStyles: () => jget("/api/caption-styles"),
  fonts: () => jget("/api/fonts"),
  history: () => jget("/api/history"),
  generate: (payload) => jpost("/api/generate", payload),
  cancel: (jobId) => jpost(`/api/cancel/${jobId}`, {}),
  musicSuggest: (sourceId, language) => jget(`/api/music-suggest/${sourceId}` + (language ? `?language=${encodeURIComponent(language)}` : "")),
  transcript: (sourceId, language) => jget(`/api/transcript/${sourceId}` + (language ? `?language=${encodeURIComponent(language)}` : "")),
  result: (jobId) => jget(`/api/result/${jobId}`),
  prefetch: (video_url) => jpost("/api/prefetch", { video_url }),
  prefetchStatus: (id) => jget(`/api/prefetch/${id}`),
  pretranscribe: (source_id, device, language) => jpost("/api/pretranscribe", { source_id, device, language }),
  pretranscribeStatus: (id) => jget(`/api/pretranscribe/${id}`),
  deleteClip: async (clipId, index) => {
    const r = await fetch(`/api/clip/${clipId}/${index}`, { method: "DELETE" });
    return r.ok;
  },
  music: () => jget("/api/music"),
  uploadMusic: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/music/upload", { method: "POST", body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Music upload failed.");
    return d; // { name, file }
  },
  uploadFont: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/fonts/upload", { method: "POST", body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Font upload failed.");
    return d; // { family, file }
  },
  // Returns the URL of the uncropped source segment for a rendered clip.
  // Used by ReframeEditor to load the full-frame video before keyframing.
  clipSourceUrl: (jobId, clipIndex) => `/api/clip/${jobId}/${clipIndex}/source`,

  // Re-render a single clip with new reframe keyframes.
  rerender: (jobId, clipIndex, keyframes) => jpost(`/api/clip/${jobId}/${clipIndex}/rerender`, { keyframes }),

  upload: async (file, onProgress) =>
    new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/upload");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch {}
        if (xhr.status === 200 && d.upload_id) resolve(d);
        else reject(new Error(d.detail || "Upload failed."));
      };
      xhr.onerror = () => reject(new Error("Upload failed — network error."));
      xhr.send(fd);
    }),
};

// Subscribe to a job's Server-Sent Events with automatic HTTP polling fallback. Returns a close() fn.
export function streamProgress(jobId, onSnap, onError) {
  let closed = false;
  let es = null;
  let pollTimer = null;
  let highestProgress = 0;
  let consecutiveFailures = 0;

  function safeOnSnap(snap) {
    if (!snap) return;
    if (typeof snap.progress === "number") {
      highestProgress = Math.max(highestProgress, snap.progress);
      snap.progress = highestProgress;
    }
    onSnap(snap);
  }

  async function pollResult() {
    if (closed) return;
    try {
      const r = await fetch(`/api/result/${jobId}`);
      if (r.ok) {
        consecutiveFailures = 0;
        const snap = await r.json();
        safeOnSnap(snap);
        if (snap.status === "done" || snap.status === "error" || snap.status === "cancelled") {
          cleanup();
          return;
        }
      } else if (r.status === 404) {
        cleanup();
        if (onError) onError(new Error("Job not found."));
        return;
      } else {
        consecutiveFailures++;
      }
    } catch {
      consecutiveFailures++;
    }

    if (consecutiveFailures > 10) {
      cleanup();
      if (onError) onError(new Error("Lost connection to the progress stream."));
      return;
    }

    if (!closed) {
      pollTimer = setTimeout(pollResult, 1500);
    }
  }

  function startSSE() {
    if (closed) return;
    try {
      es = new EventSource(`/api/progress/${jobId}`);
      es.onmessage = (ev) => {
        try {
          const snap = JSON.parse(ev.data);
          safeOnSnap(snap);
          if (snap.status === "done" || snap.status === "error" || snap.status === "cancelled") {
            cleanup();
          }
        } catch {}
      };
      es.onerror = () => {
        if (es) {
          es.close();
          es = null;
        }
        if (!closed && !pollTimer) {
          pollResult();
        }
      };
    } catch {
      if (!closed && !pollTimer) {
        pollResult();
      }
    }
  }

  // Check current status immediately, then start SSE stream
  fetch(`/api/result/${jobId}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((snap) => {
      if (closed) return;
      if (snap) {
        safeOnSnap(snap);
        if (snap.status === "done" || snap.status === "error" || snap.status === "cancelled") {
          return;
        }
      }
      startSSE();
    })
    .catch(() => {
      if (!closed) startSSE();
    });

  function cleanup() {
    closed = true;
    if (es) {
      es.close();
      es = null;
    }
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  return cleanup;
}
