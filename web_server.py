"""
web_server.py — MJPEG HTTP streaming server for Billet Detection System.

Runs in a background thread alongside the PySide6 desktop app.
Endpoints:
  GET /            → simple HTML viewer page
  GET /stream      → MJPEG video stream (multipart/x-mixed-replace)
  GET /api/stats   → JSON latest detection stats
  GET /api/status  → JSON server status
"""

import io
import threading
import time
import logging
from typing import Optional

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template_string

log = logging.getLogger("web_server")

# ── Shared frame buffer ──────────────────────────────────────────────────────
_lock        = threading.Lock()
_jpeg_bytes: Optional[bytes] = None
_stats: dict = {}
_last_update  = 0.0

_PLACEHOLDER: Optional[bytes] = None   # generated once on first request


def _make_placeholder() -> bytes:
    """Create a blank 640×480 placeholder JPEG when no camera is active."""
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Waiting for camera...", (140, 240),
                    cv2.FONT_HERSHEY_DUPLEX, 1.0, (100, 100, 100), 2)
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        _PLACEHOLDER = buf.tobytes()
    return _PLACEHOLDER


def push_frame(bgr_frame: np.ndarray, quality: int = 70) -> None:
    """Called from the PySide6 _on_frame slot to update the shared JPEG."""
    global _jpeg_bytes, _last_update
    ok, buf = cv2.imencode(".jpg", bgr_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        data = buf.tobytes()
        with _lock:
            _jpeg_bytes = data
            _last_update = time.time()


def push_stats(counts: dict) -> None:
    """Called whenever detection stats update."""
    global _stats
    with _lock:
        _stats = dict(counts)


# ── HTML template ────────────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Billet Detection — Live View</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1e1e2e; color: #cdd6f4;
         font-family: "Segoe UI", sans-serif; display: flex;
         flex-direction: column; align-items: center; min-height: 100vh;
         padding: 20px; gap: 16px; }
  h1   { font-size: 1.4rem; color: #cdd6f4; }
  h1 span { color: #7c6af7; }
  .subtitle { color: #6c7086; font-size: 0.85rem; }
  .video-wrap { position: relative; width: 100%; max-width: 880px;
                background: #000; border-radius: 10px; overflow: hidden;
                border: 1px solid #3a3a50; }
  .video-wrap img { width: 100%; display: block; }
  .badge { position: absolute; top: 8px; left: 10px;
           background: rgba(0,0,0,.65); color: #5dba7a;
           font-size: 0.75rem; padding: 2px 8px; border-radius: 4px;
           font-family: monospace; }
  .stats { width: 100%; max-width: 880px; background: #2a2a3e;
           border-radius: 10px; padding: 16px;
           border: 1px solid #3a3a50; display: flex; flex-wrap: wrap; gap: 12px; }
  .stat  { background: #313150; border-radius: 8px; padding: 10px 18px;
           min-width: 120px; text-align: center; }
  .stat .label { font-size: 0.75rem; color: #6c7086; }
  .stat .value { font-size: 1.5rem; font-weight: bold; color: #7c6af7; }
  footer { color: #45475a; font-size: 0.75rem; }
</style>
</head>
<body>
  <h1>🔩 Billet Detection — <span>Live View</span></h1>
  <p class="subtitle">Real-time Quality Inspection via ESP32-CAM</p>
  <div class="video-wrap">
    <img src="/stream" alt="live stream">
    <span class="badge" id="fps">● LIVE</span>
  </div>
  <div class="stats" id="stats-box">
    <p style="color:#6c7086; font-size:.85rem;">Menunggu data deteksi…</p>
  </div>
  <footer>Billet Detection System — Web View</footer>
<script>
  async function refreshStats() {
    try {
      const r = await fetch('/api/stats');
      const d = await r.json();
      const box = document.getElementById('stats-box');
      const entries = Object.entries(d.counts || {});
      if (entries.length === 0) {
        box.innerHTML = '<p style="color:#6c7086;font-size:.85rem;">Tidak ada deteksi aktif.</p>';
      } else {
        box.innerHTML = entries.map(([k,v]) =>
          `<div class="stat"><div class="label">${k}</div><div class="value">${v}</div></div>`
        ).join('');
      }
    } catch(e) {}
  }
  setInterval(refreshStats, 1000);
  refreshStats();
</script>
</body>
</html>"""


# ── Flask app ─────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
flask_app.config["ENV"] = "production"
# Suppress Flask dev-server output
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@flask_app.route("/")
def index():
    return render_template_string(_HTML)


@flask_app.route("/stream")
def stream():
    def generate():
        while True:
            with _lock:
                data = _jpeg_bytes
            if data is None:
                data = _make_placeholder()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            )
            time.sleep(0.033)   # ~30 fps cap for web clients

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@flask_app.route("/api/stats")
def api_stats():
    with _lock:
        counts = dict(_stats)
        last   = _last_update
    return jsonify({
        "counts":       counts,
        "last_update":  last,
        "active":       (time.time() - last) < 5.0 if last else False,
    })


@flask_app.route("/api/status")
def api_status():
    return jsonify({"status": "ok", "service": "BilletDetection"})


# ── Server lifecycle ──────────────────────────────────────────────────────────
_server_thread: Optional[threading.Thread] = None
_port: int = 5000


def start(port: int = 5000) -> int:
    """Start the Flask server in a background daemon thread. Returns the port."""
    global _server_thread, _port
    _port = port
    if _server_thread and _server_thread.is_alive():
        return _port

    def _run():
        flask_app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)

    _server_thread = threading.Thread(target=_run, name="flask-web", daemon=True)
    _server_thread.start()
    log.info("Web server started on port %d", port)
    return port


def local_url(port: Optional[int] = None) -> str:
    return f"http://localhost:{port or _port}"
