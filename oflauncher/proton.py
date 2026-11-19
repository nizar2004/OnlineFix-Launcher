"""Proton / Wine discovery and GE-Proton download management."""

from __future__ import annotations

import re
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

from . import config

GE_RELEASES_API = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
USER_AGENT = "OnlineFix-Linux-Launcher-Python/0.1"


def compat_dir() -> Path:
    d = Path.home() / ".steam" / "steam" / "compatibilitytools.d"
    return d


def ensure_compat_dir() -> Path:
    d = compat_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_protons() -> List[str]:
    """Names of installed Proton builds in compatibilitytools.d, newest first."""
    d = compat_dir()
    names: List[str] = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if p.is_dir() and (p / "proton").exists():
                names.append(p.name)
    # Newest first: sort by the version tuple inside the name.
    def sort_key(name: str):
        nums = re.findall(r"(\d+)", name)
        return ([int(n) for n in nums[:4]], name)

    return sorted(names, key=sort_key, reverse=True)


def resolve_proton(version: str = "") -> Optional[Path]:
    """Return the `proton` script for a version name; empty = newest."""
    installed = list_protons()
    if not installed:
        return None
    if not version or version == "GE-Proton Latest":
        chosen = installed[0]
    else:
        chosen = version if version in installed else None
        if chosen is None:
            # Try prefix match (e.g. "GE-Proton9" matches "GE-Proton9-27").
            matches = [n for n in installed if n.startswith(version)]
            chosen = matches[0] if matches else installed[0]
    path = compat_dir() / chosen / "proton"
    return path if path.exists() else None


def system_wine() -> Optional[str]:
    return shutil.which("wine")


def wineserver_for(runner: str, proton_version: str = "") -> Optional[Path]:
    if runner == "proton":
        resolved = resolve_proton(proton_version)
        if resolved:
            ws = resolved.parent / "files" / "bin" / "wineserver"
            if ws.exists():
                return ws
        ws = shutil.which("wineserver")
        return Path(ws) if ws else None
    ws = shutil.which("wineserver")
    return Path(ws) if ws else None


def latest_ge_info() -> Optional[dict]:
    """Fetch info about the newest GE-Proton release: {tag, name, url}."""
    req = urllib.request.Request(
        GE_RELEASES_API, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = __import__("json").loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".tar.gz") or name.endswith(".tar.xz"):
            return {
                "tag": data.get("tag_name", ""),
                "name": name,
                "url": asset.get("browser_download_url", ""),
                "size": asset.get("size", 0),
            }
    return None


def download_and_install(
    url: str,
    progress: Callable[[float, str], None],
    done: Callable[[bool, str], None],
    cancelled: Callable[[], bool],
) -> None:
    """Download a GE-Proton tarball and extract it into compatibilitytools.d.

    Runs synchronously — call it from a worker thread.
    """
    ensure_compat_dir()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
            read = 0
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                if cancelled():
                    tmp.close()
                    Path(tmp.name).unlink(missing_ok=True)
                    done(False, "Cancelled")
                    return
                tmp.write(chunk)
                read += len(chunk)
                if total:
                    progress(read / total, f"{read // 1048576} / {total // 1048576} MB")
                else:
                    progress(0.0, f"{read // 1048576} MB")
            tmp.close()

        progress(1.0, "Extracting…")
        with tarfile.open(tmp.name, "r:*") as tar:
            tar.extractall(path=compat_dir(), filter="data")
        Path(tmp.name).unlink(missing_ok=True)
        done(True, "Installed")
    except Exception as exc:  # pragma: no cover - network dependent
        done(False, str(exc))
