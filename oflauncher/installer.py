"""Archive extraction and post-download game installation helpers."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple


def _unique_dest(base: Path) -> Path:
    dest = base
    n = 2
    while dest.exists():
        dest = base.with_name(f"{base.name} ({n})")
        n += 1
    return dest


def extract_archive(archive: str, dest: Path, progress: Optional[Callable[[float], None]] = None) -> Tuple[bool, str]:
    """Extract zip / rar / 7z archives into dest. Returns (ok, message)."""
    src = Path(archive)
    if not src.exists():
        return False, "Archive not found"
    dest = _unique_dest(dest)
    dest.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    try:
        if suffix == ".zip":
            with zipfile.ZipFile(src) as zf:
                members = zf.infolist()
                total = len(members)
                for i, member in enumerate(members):
                    zf.extract(member, path=dest)
                    if progress and i % 25 == 0:
                        progress(i / max(1, total))
            return True, str(dest)

        if suffix == ".rar":
            unrar = shutil.which("unrar")
            if unrar:
                proc = subprocess.run(
                    [unrar, "x", "-y", "-o+", str(src), str(dest) + "/"],
                    capture_output=True, text=True,
                )
                return (proc.returncode == 0, proc.stderr.strip() or str(dest))
            return _extract_with_bsdtar(src, dest)

        if suffix in (".7z", ".cb7"):
            sevenzip = shutil.which("7z") or shutil.which("7za")
            if sevenzip:
                proc = subprocess.run(
                    [sevenzip, "x", "-y", f"-o{dest}", str(src)],
                    capture_output=True, text=True,
                )
                return (proc.returncode == 0, proc.stderr.strip() or str(dest))
            return False, "Install p7zip to extract .7z archives"

        return _extract_with_bsdtar(src, dest)
    except Exception as exc:
        return False, str(exc)


def _extract_with_bsdtar(src: Path, dest: Path) -> Tuple[bool, str]:
    bsdtar = shutil.which("bsdtar") or shutil.which("tar")
    if not bsdtar:
        return False, "No archive tool available"
    proc = subprocess.run(
        [bsdtar, "-xf", str(src), "-C", str(dest)],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return True, str(dest)
    return False, (proc.stderr.strip() or "Extraction failed")


def find_main_executable(folder: str) -> Optional[str]:
    """Heuristic: the largest .exe in the top two levels of the folder."""
    root = Path(folder)
    if not root.is_dir():
        return None
    candidates: list[tuple[int, str]] = []
    for pattern in ("*.exe", "*/*.exe"):
        for exe in root.glob(pattern):
            try:
                candidates.append((exe.stat().st_size, str(exe)))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
