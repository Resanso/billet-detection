# rthook_qt_plugins.py
# PyInstaller runtime hook — MUST run before any Qt import.
# Sets QT_PLUGIN_PATH so PySide6 can find platforminputcontexts
# (required for keyboard input in text fields on macOS/Windows bundles).

import os
import sys

if getattr(sys, "frozen", False):
    # sys._MEIPASS = dist/BilletDetection/_internal  (one-dir mode)
    meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    # Try both possible plugin locations
    for candidate in [
        os.path.join(meipass, "PySide6", "Qt", "plugins"),
        os.path.join(meipass, "Qt", "plugins"),
        os.path.join(os.path.dirname(sys.executable), "_internal", "PySide6", "Qt", "plugins"),
    ]:
        if os.path.isdir(candidate):
            os.environ["QT_PLUGIN_PATH"]              = candidate
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(candidate, "platforms")
            break
