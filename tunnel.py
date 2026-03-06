"""
tunnel.py — Public tunnel wrapper for Billet Detection System.

Uses cloudflared (Cloudflare Tunnel) — no account needed.
Auto-downloads the binary on first use if not installed.

Usage:
    import tunnel
    public_url = tunnel.open(port=5000)
    tunnel.close()
"""

import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger("tunnel")

_public_url: Optional[str] = None
_proc: Optional[subprocess.Popen] = None


# ─────────────────────────────────────────────────────────────────────────────
#  AUTO-DOWNLOAD cloudflared binary
# ─────────────────────────────────────────────────────────────────────────────

def _cloudflared_download_url() -> str:
    system  = platform.system().lower()   # darwin / linux / windows
    machine = platform.machine().lower()  # x86_64 / arm64 / aarch64

    if system == "darwin":
        arch = "arm64" if "arm" in machine or "aarch" in machine else "amd64"
        return (f"https://github.com/cloudflare/cloudflared/releases/latest"
                f"/download/cloudflared-darwin-{arch}.tgz")
    elif system == "linux":
        arch = "arm64" if "aarch" in machine or "arm" in machine else "amd64"
        return (f"https://github.com/cloudflare/cloudflared/releases/latest"
                f"/download/cloudflared-linux-{arch}")
    else:  # windows
        return ("https://github.com/cloudflare/cloudflared/releases/latest"
                "/download/cloudflared-windows-amd64.exe")


def _local_bin_dir() -> Path:
    """Directory where we store the auto-downloaded cloudflared binary."""
    if getattr(sys, "frozen", False):
        # Running inside PyInstaller bundle → write next to the executable
        return Path(sys.executable).parent
    return Path(__file__).parent / ".bin"


def _get_cloudflared() -> Optional[str]:
    """
    Return path to cloudflared executable.
    Checks PATH first, then local .bin/, then downloads automatically.
    """
    # 1. Already in PATH?
    cf = shutil.which("cloudflared")
    if cf:
        return cf

    # 2. Previously auto-downloaded?
    local_dir = _local_bin_dir()
    suffix     = ".exe" if platform.system() == "Windows" else ""
    local_bin  = local_dir / f"cloudflared{suffix}"
    if local_bin.exists():
        return str(local_bin)

    # 3. Download it
    log.info("cloudflared not found — downloading binary …")
    try:
        url = _cloudflared_download_url()
        local_dir.mkdir(parents=True, exist_ok=True)
        tmp = local_dir / "cf_tmp"

        log.info("Downloading from %s", url)
        urllib.request.urlretrieve(url, str(tmp))

        if url.endswith(".tgz"):
            import tarfile
            with tarfile.open(str(tmp), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("cloudflared"):
                        member.name = f"cloudflared{suffix}"
                        tar.extract(member, path=str(local_dir))
                        break
            tmp.unlink(missing_ok=True)
        else:
            tmp.rename(local_bin)

        # Make executable on Unix
        if platform.system() != "Windows":
            local_bin.chmod(local_bin.stat().st_mode | stat.S_IEXEC)

        log.info("cloudflared downloaded to %s", local_bin)
        return str(local_bin)

    except Exception as e:
        log.error("Failed to download cloudflared: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  OPEN / CLOSE
# ─────────────────────────────────────────────────────────────────────────────

def _drain(proc: subprocess.Popen):
    try:
        for _ in proc.stdout:  # type: ignore[union-attr]
            pass
    except Exception:
        pass


def open(port: int = 5000, authtoken: Optional[str] = None) -> Optional[str]:
    """
    Open a public Cloudflare tunnel to *port*.
    No account or authtoken needed.
    Returns the public HTTPS URL, or None on failure.
    """
    global _proc, _public_url

    cf = _get_cloudflared()
    if not cf:
        return None

    try:
        _proc = subprocess.Popen(
            [cf, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as e:
        log.error("Failed to start cloudflared: %s", e)
        return None

    url: Optional[str] = None
    deadline = time.time() + 30
    for line in _proc.stdout:  # type: ignore[union-attr]
        log.debug("cloudflared: %s", line.rstrip())
        match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            break
        if time.time() > deadline:
            break

    if url:
        _public_url = url
        log.info("Tunnel open: %s → localhost:%d", url, port)
        threading.Thread(target=_drain, args=(_proc,), daemon=True).start()
    else:
        _proc.terminate()
        _proc = None
        log.warning("cloudflared started but URL not detected")

    return url


def close() -> None:
    global _proc, _public_url
    if _proc is not None:
        try:
            _proc.terminate()
            _proc.wait(timeout=3)
        except Exception:
            pass
        _proc = None
    _public_url = None
    log.info("Tunnel closed.")


def current_url() -> Optional[str]:
    return _public_url
