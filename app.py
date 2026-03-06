"""
Billet Detection System — GUI
Built with PySide6 + OpenCV (replaces tkinter which crashes on this macOS build).
"""
import sys
import os
import cv2
import time
import queue
import threading
from pathlib import Path
from urllib.parse import urlparse
import requests

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QSlider, QCheckBox, QLineEdit, QRadioButton, QButtonGroup,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QScrollArea,
    QTextEdit, QSizePolicy, QFrame, QSpacerItem, QMessageBox, QComboBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QPalette

STYLESHEET = """
QMainWindow, QWidget#root { background: #1e1e2e; }

QWidget {
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "SF Pro Text", sans-serif;
    font-size: 13px;
}

QWidget#sidebar {
    background: #2a2a3e;
    border-radius: 8px;
}

QGroupBox {
    background: #2a2a3e;
    border: 1px solid #3a3a50;
    border-radius: 6px;
    margin-top: 8px;
    padding: 6px;
    font-weight: bold;
    font-size: 12px;
    color: #a6adc8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #7c6af7;
}

QLabel { background: transparent; }
QLabel#muted { color: #6c7086; font-size: 11px; }
QLabel#fps_label {
    background: rgba(0,0,0,180);
    color: #5dba7a;
    font-family: monospace;
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
}

QLineEdit {
    background: #313150;
    border: 1px solid #4a4a6a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
    selection-background-color: #7c6af7;
}
QLineEdit:focus { border-color: #7c6af7; }

QTextEdit {
    background: #252535;
    border: 1px solid #3a3a50;
    border-radius: 4px;
    color: #a6adc8;
    font-family: "Courier New", monospace;
    font-size: 11px;
}

QSlider::groove:horizontal {
    background: #313150; height: 4px; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #7c6af7; width: 14px; height: 14px;
    border-radius: 7px; margin: -5px 0;
}
QSlider::sub-page:horizontal { background: #7c6af7; border-radius: 2px; }

QCheckBox { color: #a6adc8; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #4a4a6a; border-radius: 3px; background: #313150;
}
QCheckBox::indicator:checked { background: #7c6af7; border-color: #7c6af7; }

QRadioButton { color: #a6adc8; spacing: 6px; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #4a4a6a; border-radius: 7px; background: #313150;
}
QRadioButton::indicator:checked { background: #7c6af7; border-color: #7c6af7; }

QPushButton { border-radius: 5px; padding: 8px 16px; font-weight: bold; border: none; }
QPushButton#btn_start  { background: #5dba7a; color: white; }
QPushButton#btn_start:hover   { background: #4daa6a; }
QPushButton#btn_start:disabled { background: #3a5a3a; color: #6a8a6a; }
QPushButton#btn_stop   { background: #e45c5c; color: white; }
QPushButton#btn_stop:hover    { background: #cc4444; }
QPushButton#btn_stop:disabled { background: #5a3a3a; color: #8a6a6a; }
QPushButton#btn_capture { background: #e4b45c; color: white; }
QPushButton#btn_capture:hover    { background: #cc9944; }
QPushButton#btn_capture:disabled { background: #5a4a2a; color: #8a7a5a; }
QPushButton#btn_led_off {
    background: #3a3a50; color: #a6adc8; border: 1px solid #4a4a6a;
}
QPushButton#btn_led_off:hover { background: #4a4a60; }
QPushButton#btn_led_on {
    background: #f5e642; color: #1e1e2e; font-weight: bold;
    border: 1px solid #d4c420;
}
QPushButton#btn_led_on:hover { background: #e0d030; }

QScrollBar:vertical { background: #1e1e2e; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #4a4a6a; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QComboBox {
    background: #313150; border: 1px solid #4a4a6a; border-radius: 4px;
    padding: 4px 8px; color: #cdd6f4;
}
QComboBox:focus { border-color: #7c6af7; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #313150; border: 1px solid #4a4a6a;
    color: #cdd6f4; selection-background-color: #7c6af7;
}
"""


# ─────────────────────────────────────────────
#  ESP32-CAM HTTP CONTROL HELPERS
# ─────────────────────────────────────────────
def _base_url(stream_url: str) -> str:
    """Extract base URL (scheme + host, no port, no path) from stream URL."""
    p = urlparse(stream_url)
    return f"{p.scheme}://{p.hostname}"

def esp32_set_resolution(base_url: str, index: int) -> bool:
    """
    Send framesize index to ESP32-CAM.
    Valid indices: 0=QQVGA 3=HQVGA 4=QVGA 5=CIF 6=VGA 7=SVGA 8=XGA 9=SXGA 10=UXGA
    """
    try:
        r = requests.get(
            f"{base_url}/control?var=framesize&val={index}", timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"[esp32_set_resolution] {e}")
        return False

def esp32_set_quality(base_url: str, value: int) -> bool:
    """Send JPEG quality (10=best … 63=worst) to ESP32-CAM."""
    try:
        value = max(10, min(63, value))
        r = requests.get(
            f"{base_url}/control?var=quality&val={value}", timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"[esp32_set_quality] {e}")
        return False

def esp32_set_led(base_url: str, intensity: int) -> bool:
    """
    Kontrol LED Flash ESP32-CAM.
    intensity: 0 = mati, 1–255 = nyala (makin besar makin terang).
    Menggunakan endpoint: GET /control?var=led_intensity&val=VALUE
    """
    try:
        intensity = max(0, min(255, intensity))
        r = requests.get(
            f"{base_url}/control?var=led_intensity&val={intensity}", timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"[esp32_set_led] {e}")
        return False


# ─────────────────────────────────────────────
#  WORKER SIGNALS
# ─────────────────────────────────────────────
class WorkerSignals(QObject):
    frame_ready   = Signal(object)
    log_message   = Signal(str)
    stats_update  = Signal(dict)
    fps_update    = Signal(float)
    capture_done  = Signal(str)   # label class of saved photo
    error         = Signal(str)
    stopped       = Signal()


# ─────────────────────────────────────────────
#  CAMERA WORKER THREAD
# ─────────────────────────────────────────────
class CameraWorker(QThread):
    def __init__(self, url: str, mode: str, config: dict):
        super().__init__()
        self.url   = url
        self.mode  = mode
        self.cfg   = config
        self.sig   = WorkerSignals()
        self._stop = threading.Event()
        self.confidence  = config["confidence"]
        self.iou         = config["iou"]
        self.max_sat     = config["max_sat"]
        self.use_filter  = config["use_filter"]
        self.flip        = config["flip"]
        self.do_capture       = threading.Event()
        self.img_count        = 0
        self.label_class      = config.get("label_class", "billet")
        self.auto_capture     = config.get("auto_capture", False)
        self.auto_interval_ms = config.get("auto_interval_ms", 3000)
        self._model           = None
        self._tracker    = None
        self._box_ann    = None
        self._lbl_ann    = None
        self._frame_times: list[float] = []

    def request_stop(self):
        self._stop.set()

    def run(self):
        # ── Send resolution + quality to ESP32-CAM via HTTP before opening stream ──
        base = _base_url(self.url)
        fs_idx = self.cfg.get("framesize_idx", 6)   # default VGA
        quality = self.cfg.get("quality", 10)        # default best quality
        self.sig.log_message.emit(
            f"Mengatur kamera: framesize={fs_idx}, quality={quality} …")
        esp32_set_resolution(base, fs_idx)
        esp32_set_quality(base, quality)

        cap = cv2.VideoCapture(self.url)
        if not cap.isOpened():
            self.sig.error.emit(f"Tidak dapat membuka stream:\n{self.url}")
            self.sig.stopped.emit()
            return
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.sig.log_message.emit(
            f"Kamera terhubung — mode: {self.mode} | resolusi: {actual_w}×{actual_h}")
        try:
            if self.mode == "test":
                self._run_test(cap)
            elif self.mode == "capture":
                self._run_capture(cap)
            else:
                self._run_detection(cap)
        finally:
            cap.release()
            self.sig.stopped.emit()

    def _calc_fps(self):
        now = time.time()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t < 3.0]
        if len(self._frame_times) > 1:
            fps = (len(self._frame_times) - 1) / (
                self._frame_times[-1] - self._frame_times[0])
            self.sig.fps_update.emit(fps)

    def _maybe_flip(self, frame):
        return cv2.flip(frame, -1) if self.flip else frame

    def _run_test(self, cap):
        while not self._stop.is_set():
            ret, frame = cap.read()
            if not ret:
                self.sig.log_message.emit("Koneksi terputus (test).")
                break
            frame = self._maybe_flip(frame)
            cv2.putText(frame, "TEST KAMERA", (10, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 2)
            self.sig.frame_ready.emit(frame)
            self._calc_fps()

    def _run_capture(self, cap):
        out_dir = self.cfg.get("dataset_dir", "dataset_esp32")
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        last_auto   = time.time()
        flash_left  = 0          # countdown frames for SAVED flash

        while not self._stop.is_set():
            ret, frame = cap.read()
            if not ret:
                self.sig.log_message.emit("Koneksi terputus (capture).")
                break
            frame = self._maybe_flip(frame)

            # ── Auto-capture trigger ──
            if self.auto_capture:
                now = time.time()
                if now - last_auto >= self.auto_interval_ms / 1000.0:
                    self.do_capture.set()
                    last_auto = now

            # ── Save photo ──
            if self.do_capture.is_set():
                self.do_capture.clear()
                cls   = (self.label_class or "billet").strip() or "billet"
                # Save inside sub-folder named after class
                cls_dir = os.path.join(out_dir, cls)
                Path(cls_dir).mkdir(parents=True, exist_ok=True)
                fname = os.path.join(cls_dir, f"{cls}_{self.img_count:04d}.jpg")
                cv2.imwrite(fname, frame)
                self.img_count += 1
                flash_left = 10
                self.sig.log_message.emit(f"📸 [{cls}] disimpan → {fname}")
                self.sig.capture_done.emit(cls)

            # ── Overlay ──
            display  = frame.copy()
            h, w     = display.shape[:2]
            cls_now  = (self.label_class or "billet").strip()
            mode_txt = ("AUTO " if self.auto_capture else "") + "CAPTURE"
            bar      = display.copy()
            cv2.rectangle(bar, (0, 0), (w, 38), (0, 0, 0), -1)
            cv2.addWeighted(bar, 0.55, display, 0.45, 0, display)
            cv2.putText(display,
                        f"{mode_txt}  |  Kelas: {cls_now}  |  Total: {self.img_count}  |  [S] Ambil",
                        (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 210, 255), 1,
                        cv2.LINE_AA)

            if flash_left > 0:
                flash_left -= 1
                overlay = display.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (0, 255, 80), -1)
                cv2.addWeighted(overlay, 0.18, display, 0.82, 0, display)
                txt  = f"SAVED!  [{cls_now}]"
                tw   = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 1.4, 2)[0][0]
                cv2.putText(display, txt,
                            ((w - tw) // 2, h // 2),
                            cv2.FONT_HERSHEY_DUPLEX, 1.4, (0, 255, 80), 2, cv2.LINE_AA)

            self.sig.frame_ready.emit(display)
            self._calc_fps()

    def _run_detection(self, cap):
        try:
            from inference import get_model
            import supervision as sv
        except ImportError as e:
            self.sig.error.emit(f"Import error: {e}")
            return

        mid = self.cfg.get("model_id", "billet-detection-5znfl/2")
        key = self.cfg.get("api_key", "")
        self.sig.log_message.emit(f"Memuat model: {mid} …")
        try:
            self._model   = get_model(model_id=mid, api_key=key)
            self._tracker = sv.ByteTrack()
            self._box_ann = sv.BoxAnnotator()
            self._lbl_ann = sv.LabelAnnotator()
            self.sig.log_message.emit("Model siap. Deteksi dimulai.")
        except Exception as e:
            self.sig.error.emit(f"Gagal memuat model: {e}")
            return

        class_counts: dict[str, int] = {}
        while not self._stop.is_set():
            ret, frame = cap.read()
            if not ret:
                self.sig.log_message.emit("Koneksi terputus (deteksi).")
                break
            frame = self._maybe_flip(frame)

            conf       = self.confidence
            iou        = self.iou
            max_sat    = self.max_sat
            use_filter = self.use_filter

            try:
                results    = self._model.infer(frame, confidence=conf, iou_threshold=iou)[0]
                detections = sv.Detections.from_inference(results)
                detections = self._tracker.update_with_detections(detections)
            except Exception as e:
                self.sig.log_message.emit(f"Inferensi error: {e}")
                self.sig.frame_ready.emit(frame)
                continue

            if use_filter and len(detections) > 0:
                valid = []
                for i, xyxy in enumerate(detections.xyxy):
                    cn = detections.data["class_name"][i]
                    if cn == "billet":
                        x1, y1, x2, y2 = map(int, xyxy)
                        h_f, w_f = frame.shape[:2]
                        roi = frame[max(0,y1):min(h_f,y2), max(0,x1):min(w_f,x2)]
                        if roi.size > 0:
                            avg_s = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:,:,1].mean()
                            if avg_s < max_sat:
                                valid.append(i)
                    else:
                        valid.append(i)
                detections = detections[valid]

            labels = []
            class_counts.clear()
            if len(detections) > 0:
                for cn, cf in zip(detections.data["class_name"], detections.confidence):
                    labels.append(f"{cn} {cf:.2f}")
                    class_counts[cn] = class_counts.get(cn, 0) + 1

            annotated = self._box_ann.annotate(scene=frame, detections=detections)
            if labels:
                annotated = self._lbl_ann.annotate(
                    scene=annotated, detections=detections, labels=labels)

            self.sig.frame_ready.emit(annotated)
            self._calc_fps()
            self.sig.stats_update.emit(dict(class_counts))


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Billet Detection System")
        self.resize(1150, 720)
        self.setMinimumSize(850, 580)
        self.setStyleSheet(STYLESHEET)
        self._worker: CameraWorker | None = None
        self._img_count    = 0
        self._class_counts: dict[str, int] = {}
        self._build_ui()

    def _build_ui(self):
        central = QWidget(); central.setObjectName("root")
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._make_header())
        body = QWidget()
        hbox = QHBoxLayout(body)
        hbox.setContentsMargins(10, 8, 10, 8)
        hbox.setSpacing(10)
        hbox.addWidget(self._make_sidebar(), 0)
        hbox.addWidget(self._make_video_area(), 1)
        vbox.addWidget(body, 1)

        # ── Realtime slider → worker (set up once, guarded by None check) ──
        self.sl_conf[0].valueChanged.connect(
            lambda v: self._worker and setattr(self._worker, "confidence", v / 100.0))
        self.sl_iou[0].valueChanged.connect(
            lambda v: self._worker and setattr(self._worker, "iou", v / 100.0))
        self.sl_sat[0].valueChanged.connect(
            lambda v: self._worker and setattr(self._worker, "max_sat", float(v)))
        self.cb_filter.stateChanged.connect(
            lambda v: self._worker and setattr(self._worker, "use_filter", bool(v)))
        self.cb_flip.stateChanged.connect(
            lambda v: self._worker and setattr(self._worker, "flip", bool(v)))
        self.statusBar().setStyleSheet(
            "background:#2a2a3e; color:#a6adc8; font-size:11px;")
        self.statusBar().showMessage("Siap.")

    def _make_header(self):
        w = QWidget()
        w.setStyleSheet("background:#2a2a3e;")
        w.setFixedHeight(48)
        h = QHBoxLayout(w)
        h.setContentsMargins(20, 0, 20, 0)
        title = QLabel("🔩  Billet Detection System")
        title.setStyleSheet(
            "font-size:16px; font-weight:bold; color:#cdd6f4; background:transparent;")
        sub = QLabel("Real-time Quality Inspection via ESP32-CAM")
        sub.setStyleSheet("color:#6c7086; font-size:12px; background:transparent;")
        h.addWidget(title); h.addSpacing(12); h.addWidget(sub); h.addStretch()
        return w

    def _make_sidebar(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(295)
        scroll.setStyleSheet(
            "QScrollArea { background:#2a2a3e; border:none; } "
            "QScrollArea > QWidget > QWidget { background:#2a2a3e; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget(); inner.setObjectName("sidebar")
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(6)

        # Mode
        grp_mode = QGroupBox("Mode")
        vm = QVBoxLayout(grp_mode)
        self.rb_detection = QRadioButton("Deteksi Cacat (AI)")
        self.rb_capture   = QRadioButton("Capture Dataset")
        self.rb_test      = QRadioButton("Test Kamera")
        self.rb_detection.setChecked(True)
        self._mode_group  = QButtonGroup()
        for i, rb in enumerate([self.rb_detection, self.rb_capture, self.rb_test]):
            self._mode_group.addButton(rb, i); vm.addWidget(rb)
        vbox.addWidget(grp_mode)

        # Kamera
        grp_cam = QGroupBox("Kamera / Sumber")
        vc = QVBoxLayout(grp_cam)
        vc.addWidget(QLabel("ESP32 URL:"))
        self.le_url = QLineEdit("http://billet.local:81/stream")
        vc.addWidget(self.le_url)
        vc.addWidget(QLabel("Resolusi (framesize):"))
        self.cb_resolution = QComboBox()
        # (label, ESP32 framesize index)
        self._resolutions = [
            ("QQVGA  — 160×120",    0),
            ("HQVGA  — 240×176",    3),
            ("QVGA   — 320×240",    4),
            ("CIF    — 400×296",    5),
            ("VGA    — 640×480   (~25 fps)",  6),
            ("SVGA   — 800×600   (~15 fps)",  7),
            ("XGA    — 1024×768  (~10 fps)",  8),
            ("SXGA   — 1280×1024 (~6 fps)",   9),
            ("UXGA   — 1600×1200 (~4 fps)",  10),
        ]
        for label, _ in self._resolutions:
            self.cb_resolution.addItem(label)
        self.cb_resolution.setCurrentIndex(4)  # default: VGA
        vc.addWidget(self.cb_resolution)
        vc.addWidget(QLabel("JPEG Quality (10=tajam, 63=kecil):"))
        self.sl_quality, _ = self._make_slider(
            "Quality", 10, 63, 10, lambda v: str(v))
        vc.addLayout(self.sl_quality[2])
        self.cb_flip = QCheckBox("Flip Video (180°)")
        vc.addWidget(self.cb_flip)
        vbox.addWidget(grp_cam)

        # LED Flash
        grp_led = QGroupBox("LED Flash ESP32-CAM")
        vled = QVBoxLayout(grp_led)
        self._led_on = False
        self.btn_led = QPushButton("💡  LED: MATI")
        self.btn_led.setObjectName("btn_led_off")
        self.btn_led.setCheckable(True)
        self.btn_led.clicked.connect(self._toggle_led)
        vled.addWidget(self.btn_led)
        self.sl_led, _ = self._make_slider(
            "Intensitas", 0, 255, 255, lambda v: str(v))
        # Live-update intensitas saat LED sedang nyala
        self.sl_led[0].valueChanged.connect(self._on_led_slider)
        vled.addLayout(self.sl_led[2])
        hint = QLabel("⚠️  Kamera harus dalam jaringan WiFi yang sama")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        vled.addWidget(hint)
        vbox.addWidget(grp_led)

        # AI Model
        grp_ai = QGroupBox("AI Model (Roboflow)")
        va = QVBoxLayout(grp_ai)
        va.addWidget(QLabel("API Key:"))
        self.le_api = QLineEdit("aWLCG4AiKBek0ujLpfPc")
        self.le_api.setEchoMode(QLineEdit.Password)
        va.addWidget(self.le_api)
        va.addWidget(QLabel("Model ID:"))
        self.le_model = QLineEdit("billet-detection-5znfl/2")
        va.addWidget(self.le_model)
        self.sl_conf, _ = self._make_slider(
            "Confidence", 1, 100, 50, lambda v: f"{v/100:.2f}")
        self.sl_iou, _  = self._make_slider(
            "Overlap", 1, 100, 40, lambda v: f"{v/100:.2f}")
        va.addLayout(self.sl_conf[2]); va.addLayout(self.sl_iou[2])
        vbox.addWidget(grp_ai)

        # Colour filter
        grp_flt = QGroupBox("Filter Warna Metalik")
        vf = QVBoxLayout(grp_flt)
        self.cb_filter = QCheckBox("Aktifkan filter saturasi")
        self.cb_filter.setChecked(True)
        vf.addWidget(self.cb_filter)
        self.sl_sat, _ = self._make_slider(
            "Max Saturasi", 20, 255, 120, lambda v: str(v))
        vf.addLayout(self.sl_sat[2])
        vbox.addWidget(grp_flt)

        # Capture Dataset
        grp_ds = QGroupBox("Capture Dataset")
        vd = QVBoxLayout(grp_ds)

        # ── Folder ──
        vd.addWidget(QLabel("Folder simpan:"))
        row_folder = QHBoxLayout()
        self.le_dataset_dir = QLineEdit("dataset_esp32")
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(32)
        btn_browse.setToolTip("Pilih folder")
        btn_browse.clicked.connect(self._browse_folder)
        row_folder.addWidget(self.le_dataset_dir)
        row_folder.addWidget(btn_browse)
        vd.addLayout(row_folder)

        # ── Label / Kelas ──
        vd.addWidget(QLabel("Label kelas:"))
        self._label_classes = ["billet", "baret", "oksidasi", "Custom…"]
        self.cb_label_class  = QComboBox()
        for c in self._label_classes:
            self.cb_label_class.addItem(c)
        vd.addWidget(self.cb_label_class)
        self.le_custom_label = QLineEdit()
        self.le_custom_label.setPlaceholderText("Nama kelas custom…")
        self.le_custom_label.setVisible(False)
        self.cb_label_class.currentIndexChanged.connect(
            lambda i: self.le_custom_label.setVisible(
                i == len(self._label_classes) - 1))
        vd.addWidget(self.le_custom_label)

        # ── Auto-capture ──
        self.cb_auto_capture = QCheckBox("Auto-capture (timer otomatis)")
        vd.addWidget(self.cb_auto_capture)
        self.sl_auto_interval, _ = self._make_slider(
            "Interval", 1, 30, 3, lambda v: f"{v} dtk")
        self.sl_auto_interval[0].setEnabled(False)
        self.cb_auto_capture.stateChanged.connect(
            lambda v: self.sl_auto_interval[0].setEnabled(bool(v)))
        vd.addLayout(self.sl_auto_interval[2])

        # ── Per-class stats ──
        self.lbl_photo_count = QLabel("Total tersimpan: 0")
        self.lbl_photo_count.setObjectName("muted")
        vd.addWidget(self.lbl_photo_count)
        self._capture_stats_widget = QWidget()
        self._capture_stats_widget.setStyleSheet("background:transparent;")
        self._capture_stats_layout = QVBoxLayout(self._capture_stats_widget)
        self._capture_stats_layout.setContentsMargins(0, 2, 0, 0)
        self._capture_stats_layout.setSpacing(2)
        vd.addWidget(self._capture_stats_widget)

        vbox.addWidget(grp_ds)

        # Stats
        grp_stats = QGroupBox("Statistik Deteksi")
        self._stats_layout = QVBoxLayout(grp_stats)
        lbl = QLabel("(Belum ada deteksi)")
        lbl.setObjectName("muted")
        self._stats_layout.addWidget(lbl)
        vbox.addWidget(grp_stats)

        # Log
        grp_log = QGroupBox("Log")
        vl = QVBoxLayout(grp_log)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(110)
        vl.addWidget(self.log_box)
        vbox.addWidget(grp_log)

        # Buttons
        self.btn_start = QPushButton("▶  Mulai")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self._start)

        self.btn_stop = QPushButton("■  Berhenti")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)

        self.btn_capture = QPushButton("📸  Ambil Foto  [S]")
        self.btn_capture.setObjectName("btn_capture")
        self.btn_capture.setEnabled(False)
        self.btn_capture.clicked.connect(self._manual_capture)

        for btn in [self.btn_start, self.btn_stop, self.btn_capture]:
            vbox.addWidget(btn)

        vbox.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _make_slider(self, label: str, lo: int, hi: int, init: int, fmt):
        row = QHBoxLayout()
        lbl_name = QLabel(label + ":")
        lbl_name.setFixedWidth(100)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi); sl.setValue(init)
        lbl_val = QLabel(fmt(init))
        lbl_val.setFixedWidth(40)
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_val.setStyleSheet("color:#5cb8e4; background:transparent;")
        sl.valueChanged.connect(lambda v: lbl_val.setText(fmt(v)))
        row.addWidget(lbl_name); row.addWidget(sl); row.addWidget(lbl_val)
        return (sl, lbl_val, row), lbl_val

    def _make_video_area(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background:black;")
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setText(
            "<span style='color:#6c7086; font-size:16px;'>"
            "📷  Kamera belum dihubungkan<br><br>"
            "<span style='font-size:13px;'>Klik ▶ Mulai untuk memulai</span>"
            "</span>")

        container = QWidget()
        container.setStyleSheet("background:black;")
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ci = QVBoxLayout(container)
        ci.setContentsMargins(0, 0, 0, 0)
        ci.addWidget(self.video_label)

        self.fps_label = QLabel("FPS: --")
        self.fps_label.setObjectName("fps_label")
        self.fps_label.setParent(container)
        self.fps_label.move(6, 6)
        self.fps_label.resize(90, 22)
        self.fps_label.raise_()

        v.addWidget(container, 1)
        return w

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S:
            self._manual_capture()
        super().keyPressEvent(event)

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_box.append(
            f"<span style='color:#6c7086;'>[{ts}]</span> {msg}")
        self.statusBar().showMessage(msg)

    def _start(self):
        url = self.le_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL kosong",
                                "Isi URL ESP32-CAM terlebih dahulu.")
            return

        if self.rb_detection.isChecked():
            mode = "detection"
        elif self.rb_capture.isChecked():
            mode = "capture"
        else:
            mode = "test"

        _res = self._resolutions[self.cb_resolution.currentIndex()]
        config = {
            "api_key":        self.le_api.text().strip(),
            "model_id":       self.le_model.text().strip(),
            "confidence":     self.sl_conf[0].value() / 100.0,
            "iou":            self.sl_iou[0].value()  / 100.0,
            "max_sat":        float(self.sl_sat[0].value()),
            "use_filter":     self.cb_filter.isChecked(),
            "flip":           self.cb_flip.isChecked(),
            "dataset_dir":       self.le_dataset_dir.text().strip() or "dataset_esp32",
            "label_class":        self._get_label_class(),
            "auto_capture":       self.cb_auto_capture.isChecked(),
            "auto_interval_ms":   self.sl_auto_interval[0].value() * 1000,
            "framesize_idx":      _res[1],
            "quality":            self.sl_quality[0].value(),
        }

        self._worker = CameraWorker(url, mode, config)
        self._worker.sig.frame_ready.connect(self._on_frame)
        self._worker.sig.log_message.connect(self._log)
        self._worker.sig.fps_update.connect(self._on_fps)
        self._worker.sig.stats_update.connect(self._on_stats)
        self._worker.sig.error.connect(self._on_error)
        self._worker.sig.stopped.connect(self._on_worker_stopped)

        self._worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_capture.setEnabled(mode == "capture")
        self.video_label.setText("")
        self._log(f"Memulai — mode: {mode}, URL: {url}")

        if mode == "capture":
            self._class_counts.clear()
            self._update_capture_stats()
            self._worker.sig.capture_done.connect(self._on_capture_done)
            # Live-update label class & auto settings
            self.cb_label_class.currentIndexChanged.connect(
                lambda _: setattr(self._worker, "label_class",
                                   self._get_label_class()))
            self.le_custom_label.textChanged.connect(
                lambda _: setattr(self._worker, "label_class",
                                   self._get_label_class()))
            self.cb_auto_capture.stateChanged.connect(
                lambda v: setattr(self._worker, "auto_capture", bool(v)))
            self.sl_auto_interval[0].valueChanged.connect(
                lambda v: setattr(self._worker, "auto_interval_ms", v * 1000))

    def _stop(self):
        if self._worker:
            self._worker.request_stop()

    def _on_worker_stopped(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_capture.setEnabled(False)
        self.fps_label.setText("FPS: --")
        self.video_label.setText(
            "<span style='color:#6c7086; font-size:16px;'>"
            "📷  Kamera belum dihubungkan<br><br>"
            "<span style='font-size:13px;'>Klik ▶ Mulai untuk memulai</span>"
            "</span>")
        self._log("Dihentikan.")

    def _on_error(self, msg: str):
        self._log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)

    def _manual_capture(self):
        if self._worker and self.rb_capture.isChecked():
            self._worker.do_capture.set()

    def _toggle_led(self):
        """Kirim perintah LED ke ESP32-CAM langsung via HTTP (non-blocking)."""
        url = self.le_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL kosong",
                                "Isi URL ESP32-CAM terlebih dahulu.")
            self.btn_led.setChecked(False)
            return

        self._led_on = not self._led_on
        intensity = self.sl_led[0].value() if self._led_on else 0

        if self._led_on:
            self.btn_led.setText("💡  LED: NYALA")
            self.btn_led.setObjectName("btn_led_on")
        else:
            self.btn_led.setText("💡  LED: MATI")
            self.btn_led.setObjectName("btn_led_off")
        # Re-apply stylesheet so objectName change takes effect
        self.btn_led.setStyleSheet(self.styleSheet())

        base = _base_url(url)
        # Run in background thread — do not block the UI
        threading.Thread(
            target=esp32_set_led, args=(base, intensity), daemon=True
        ).start()
        status = f"NYALA (intensitas={intensity})" if self._led_on else "MATI"
        self._log(f"LED {status}")

    def _on_led_slider(self, value: int):
        """Kirim intensitas baru secara real-time jika LED sedang nyala."""
        if not self._led_on:
            return
        url = self.le_url.text().strip()
        if not url:
            return
        base = _base_url(url)
        threading.Thread(
            target=esp32_set_led, args=(base, value), daemon=True
        ).start()

    def _on_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        lw = self.video_label.width()
        lh = self.video_label.height()
        self.video_label.setPixmap(
            pix.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # img_count is now updated via capture_done signal

    def _on_fps(self, fps: float):
        self.fps_label.setText(f"FPS: {fps:.1f}")

    def _on_stats(self, counts: dict):
        while self._stats_layout.count():
            item = self._stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # remove sublayout items
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not counts:
            lbl = QLabel("(Tidak ada deteksi saat ini)")
            lbl.setObjectName("muted")
            self._stats_layout.addWidget(lbl)
            return

        color_map = {
            "billet":   "#5cb8e4",
            "baret":    "#e4b45c",
            "oksidasi": "#e45c5c",
        }
        for cls, cnt in sorted(counts.items()):
            row = QHBoxLayout()
            col = color_map.get(cls.lower(), "#cdd6f4")
            lbl = QLabel(f"● {cls}")
            lbl.setStyleSheet(f"color:{col}; background:transparent;")
            val = QLabel(str(cnt))
            val.setStyleSheet(
                f"color:{col}; font-weight:bold; background:transparent;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            self._stats_layout.addLayout(row)

    # ── Capture helpers ──────────────────────────

    def _get_label_class(self) -> str:
        idx = self.cb_label_class.currentIndex()
        if idx == len(self._label_classes) - 1:
            return self.le_custom_label.text().strip() or "billet"
        return self._label_classes[idx]

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Pilih folder dataset",
            self.le_dataset_dir.text() or os.getcwd())
        if folder:
            self.le_dataset_dir.setText(folder)

    def _on_capture_done(self, label: str):
        self._class_counts[label] = self._class_counts.get(label, 0) + 1
        self._img_count = sum(self._class_counts.values())
        self._update_capture_stats()

    def _update_capture_stats(self):
        total = sum(self._class_counts.values())
        self.lbl_photo_count.setText(f"Total tersimpan: {total}")
        # Clear & rebuild per-class rows
        while self._capture_stats_layout.count():
            item = self._capture_stats_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        color_map = {"billet": "#5cb8e4", "baret": "#e4b45c",
                     "oksidasi": "#e45c5c"}
        for cls, cnt in sorted(self._class_counts.items()):
            row = QHBoxLayout()
            col = color_map.get(cls.lower(), "#cdd6f4")
            lbl = QLabel(f"● {cls}")
            lbl.setStyleSheet(
                f"color:{col}; background:transparent; font-size:12px;")
            val = QLabel(str(cnt))
            val.setStyleSheet(
                f"color:{col}; font-weight:bold; background:transparent;"
                f" font-size:12px;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            self._capture_stats_layout.addLayout(row)

    def closeEvent(self, event):
        self._stop()
        if self._worker:
            self._worker.wait(3000)
        event.accept()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
