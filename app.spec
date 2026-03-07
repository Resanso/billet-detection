# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Billet Detection System
# Run: pyinstaller app.spec

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

# ── Collect all assets from heavy packages ──────────────────────────────────
pyside6_datas,    pyside6_bins,    pyside6_hidden    = collect_all("PySide6")
inference_datas,  inference_bins,  inference_hidden  = collect_all("inference")
sv_datas,         sv_bins,         sv_hidden          = collect_all("supervision")
onnx_datas,       onnx_bins,       onnx_hidden        = collect_all("onnxruntime")
cv2_datas,        cv2_bins,        cv2_hidden         = collect_all("cv2")

# ── Explicitly bundle Qt input + platform plugins (fixes typing in macOS bundle)
import glob, site
_site = site.getsitepackages()[0]
_qt_plugins = os.path.join(_site, "PySide6", "Qt", "plugins")

def _plugin_datas(plugin_dir_name):
    src = os.path.join(_qt_plugins, plugin_dir_name)
    dst = os.path.join("PySide6", "Qt", "plugins", plugin_dir_name)
    return (src, dst) if os.path.isdir(src) else None

_extra_plugin_dirs = [
    "platforminputcontexts",   # REQUIRED: keyboard input in text fields
    "platforms",               # REQUIRED: window system
    "styles",                  # optional: native look
    "imageformats",            # optional: PNG/JPEG support
]
extra_plugin_datas = [
    _plugin_datas(d) for d in _extra_plugin_dirs
    if _plugin_datas(d) is not None
]

datas    = pyside6_datas  + inference_datas + sv_datas + onnx_datas + cv2_datas \
           + extra_plugin_datas
binaries = pyside6_bins   + inference_bins  + sv_bins  + onnx_bins  + cv2_bins

hidden_imports = (
    pyside6_hidden + inference_hidden + sv_hidden + onnx_hidden + cv2_hidden
    + [
        "cv2",
        # PySide6 core modules used explicitly
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        # Requests / urllib stack
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        # Flask web server
        "flask",
        "flask.templating",
        "werkzeug",
        "werkzeug.serving",
        "jinja2",
        "itsdangerous",
        "click",
        # pyngrok tunnel
        "pyngrok",
        "pyngrok.ngrok",
        "pyngrok.conf",
        # Local modules
        "web_server",
        "tunnel",
        # Inference / Roboflow SDK internals
        "inference.core",
        "inference.models",
        "inference.core.models",
        "inference.core.registries",
        # Supervision
        "supervision.detection.core",
        "supervision.tracker.byte_tracker.core",
        # OpenCV optional codecs
        "cv2.gapi",
    ]
)

# ── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_qt_plugins.py"],
    excludes=[
        # Trim build size — not used in this app
        "matplotlib",
        "tkinter",
        "scipy",
        "pandas",
        "IPython",
        "notebook",
        "jupyter",
        "torch",
        "torchvision",
        "ultralytics",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── One-directory bundle (recommended for first build) ───────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # keep binaries separate (one-dir mode)
    name="BilletDetection",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # compress binaries (requires UPX installed)
    console=True,                   # keep console ON to see errors (set False after stable)
    icon=None, # "assets/icon.ico" if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BilletDetection",
)

# ── macOS .app bundle (only active on macOS) ─────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BilletDetection.app",
        icon=None,                  # set path to .icns if you have one
        bundle_identifier="com.billetdetection.app",
        info_plist={
            "NSCameraUsageDescription": "Kamera digunakan untuk deteksi billet.",
            "NSHighResolutionCapable":  True,
        },
    )
