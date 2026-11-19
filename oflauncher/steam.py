"""Steam integration: store search and cover art download."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

USER_AGENT = "OnlineFix-Linux-Launcher-Python/0.1"
TIMEOUT = 15

SEARCH_URL = "https://steamcommunity.com/actions/SearchApps/{term}"
COVER_URLS = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
]


def _http_get(url: str, timeout: int = TIMEOUT) -> Optional[bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return None


def search(term: str) -> List[Tuple[int, str]]:
    """Search the Steam store; returns [(appid, name), ...]. Runs synchronously."""
    term = (term or "").strip()
    if not term:
        return []
    from urllib.parse import quote

    data = _http_get(SEARCH_URL.format(term=quote(term)))
    if not data:
        return []
    try:
        items = json.loads(data.decode("utf-8", "replace"))
        return [(int(i["appid"]), str(i.get("name", ""))) for i in items][:8]
    except Exception:
        return []


def download_cover(app_id: int, dest: Path) -> Optional[Path]:
    """Download the best available artwork for a Steam app id."""
    if app_id <= 0:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    for template in COVER_URLS:
        data = _http_get(template.format(appid=app_id))
        if data and len(data) > 1024 and data[:6] in (b"\x89PNG\r\n", b"\xff\xd8\xff"):
            suffix = ".png" if data[:4] == b"\x89PNG" else ".jpg"
            path = dest.with_suffix(suffix)
            path.write_bytes(data)
            return path
    return None


def search_and_fetch_cover(term: str, dest: Path) -> Tuple[Optional[int], Optional[Path]]:
    """Convenience: search once, download the cover of the first hit."""
    results = search(term)
    if not results:
        return None, None
    app_id, _name = results[0]
    return app_id, download_cover(app_id, dest)


def fetch_in_thread(
    term: str,
    dest: Path,
    on_done: Callable[[Optional[int], Optional[Path]], None],
) -> None:
    """Run the search+download in a thread, deliver via GLib.idle_add."""

    def worker() -> None:
        try:
            result = search_and_fetch_cover(term, dest)
        except Exception:
            result = (None, None)
        from gi.repository import GLib

        GLib.idle_add(_deliver, on_done, result)

    threading.Thread(target=worker, daemon=True).start()


def _deliver(on_done, result) -> bool:
    on_done(*result)
    return False  # do not repeat idle callback
