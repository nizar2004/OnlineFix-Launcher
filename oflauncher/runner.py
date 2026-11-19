"""Launch and manage game processes (Proton or plain Wine)."""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from gi.repository import Gio, GLib

from . import config, proton
from .models import Game

# Marker files/lines used to recognise a running game from *any* launcher
# instance (the file lets a second `onlinefix-launcher --kill` find it).
RUNNING_FILE = config.STATE_DIR / "running.json"

# Command-line fragments that identify a game process even when the game was
# never added to the library.
GAME_PROCESS_MARKERS = (
    "wineserver",
    "wine-preloader",
    "wine64-preloader",
    "wine-preloader",
    "proton waitforexitandrun",
    "/proton",
    "proton run",
)


def _child_pids(pid: int) -> List[int]:
    """Direct children of pid, from /proc (no external deps)."""
    children: List[int] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = (proc / "stat").read_text()
            # field 4 (1-indexed) is ppid; comm may contain spaces → split after last ')'
            ppid = int(stat.rpartition(")")[2].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        if ppid == pid:
            children.append(int(proc.name))
    return children


def _process_start_time(pid: int) -> Optional[int]:
    """Kernel start time of a pid — used to detect PID reuse."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return int(stat.rpartition(")")[2].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True


def kill_process_tree(pid: int, sig: int = signal.SIGTERM) -> None:
    """Kill a process and all of its descendants."""
    try:
        descendants: List[int] = []
        stack = [pid]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            kids = _child_pids(current)
            stack.extend(kids)
            descendants.extend(kids)
        for target in reversed(descendants + [pid]):
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                continue
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cross-instance state
# ---------------------------------------------------------------------------
def _write_running_state(pid: int, game: Game) -> None:
    """Remember the running game so another instance can stop it."""
    try:
        RUNNING_FILE.parent.mkdir(parents=True, exist_ok=True)
        RUNNING_FILE.write_text(
            json.dumps(
                {
                    "pid": pid,
                    "name": game.name,
                    "executable": game.executable,
                    "game_dir": game.game_dir,
                    "runner": game.runner,
                    "proton_version": game.proton_version,
                    "prefix": game.prefix_path,
                    "start_time": _process_start_time(pid),
                    "launched_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _read_running_state() -> Optional[Dict]:
    try:
        if not RUNNING_FILE.exists():
            return None
        return json.loads(RUNNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_running_state(pid: Optional[int] = None) -> None:
    try:
        data = _read_running_state() or {}
        if pid is None or int(data.get("pid", 0)) == pid:
            RUNNING_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _kill_wineserver(runner_name: str, proton_version: str, prefix: str) -> None:
    """Ask wineserver to shut the prefix down gracefully."""
    ws = proton.wineserver_for(runner_name or "wine", proton_version or "")
    if not ws:
        return
    env = dict(os.environ)
    if prefix:
        if runner_name == "proton":
            env["STEAM_COMPAT_DATA_PATH"] = prefix
        else:
            env["WINEPREFIX"] = prefix
    try:
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.NONE)
        for key, value in env.items():
            launcher.setenv(key, value, True)
        launcher.spawnv([str(ws), "-k"])
    except Exception:
        pass


def kill_recorded_game() -> Optional[str]:
    """Kill the game started by this launcher — from any process.

    Works even when the game was removed from the library, because the PID
    and its prefix are stored on disk while the game runs.
    """
    data = _read_running_state()
    if not data:
        return None

    pid = int(data.get("pid", 0) or 0)
    if pid <= 0:
        _clear_running_state()
        return None

    # Guard against PID reuse: the recorded start time must still match.
    recorded_start = data.get("start_time")
    current_start = _process_start_time(pid)
    if recorded_start is not None and current_start is not None and int(recorded_start) != int(current_start):
        _clear_running_state()
        return None

    if not _pid_alive(pid):
        _clear_running_state()
        return None

    name = str(data.get("name") or "the running game")
    _kill_wineserver(
        str(data.get("runner") or "wine"),
        str(data.get("proton_version") or ""),
        str(data.get("prefix") or ""),
    )
    kill_process_tree(pid, signal.SIGTERM)
    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    if _pid_alive(pid):
        kill_process_tree(pid, signal.SIGKILL)
    _clear_running_state(pid)
    return name


def find_game_processes() -> List[Dict[str, str]]:
    """Find Wine/Proton processes that are running right now.

    Used to stop games that the launcher does not know about (for example a
    game that was started before it was added to the library).
    """
    found: List[Dict[str, str]] = []
    own = os.getpid()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        if pid == own:
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        cmd = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if not cmd:
            continue
        low = cmd.lower()
        if not any(marker in low for marker in GAME_PROCESS_MARKERS):
            continue
        # Never touch the launcher itself or a shell that merely mentions it.
        if "onlinefix-launcher" in low or "oflauncher" in low:
            continue
        try:
            comm = (proc / "comm").read_text().strip()
        except OSError:
            comm = cmd.split()[0]
        found.append({"pid": str(pid), "name": comm, "cmdline": cmd[:180]})
    return found


def kill_game_processes() -> int:
    """Kill every Wine/Proton process found on the system."""
    processes = find_game_processes()
    for entry in processes:
        try:
            kill_process_tree(int(entry["pid"]), signal.SIGTERM)
        except Exception:
            continue
    time.sleep(0.6)
    for entry in processes:
        try:
            pid = int(entry["pid"])
        except ValueError:
            continue
        if _pid_alive(pid):
            kill_process_tree(pid, signal.SIGKILL)
    _clear_running_state()
    return len(processes)


class GameProcess:
    """A running game and its log pipe."""

    def __init__(self, game: Game, process: Gio.Subprocess, debug: bool, started_at: float):
        self.game_name = game.name
        self.process = process
        self.debug = debug
        self.started_at = started_at


class Runner:
    """Spawns games and streams their output to a callback."""

    def __init__(self) -> None:
        self.current: Optional[GameProcess] = None
        self.on_output: Callable[[str], None] = lambda line: None
        self.on_exit: Callable[[str, int], None] = lambda name, code: None
        self.on_state: Callable[[bool], None] = lambda running: None

    # -- state -------------------------------------------------------------
    @property
    def running(self) -> bool:
        proc = self.current
        return bool(proc and proc.process.get_if_running())

    # -- environment -------------------------------------------------------
    def _env(self, game: Game, debug: bool) -> Dict[str, str]:
        env = dict(os.environ)
        overrides = game.effective_overrides()
        if overrides:
            env["WINEDLLOVERRIDES"] = overrides
        if debug:
            env["WINEDEBUG"] = "+loaddll,+err,+seh"
        else:
            env.setdefault("WINEDEBUG", "-all")
        for key, value in game.parse_extra_env().items():
            env[key] = value
        return env

    def _argv(self, game: Game, debug: bool) -> List[str]:
        exe = game.executable
        if game.runner == "proton":
            proton_bin = proton.resolve_proton(game.proton_version)
            if not proton_bin:
                raise RuntimeError("No Proton build found in compatibilitytools.d")
            prefix = self._prefix_for(game)
            self._pending_env = {
                "STEAM_COMPAT_DATA_PATH": prefix,
                "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(Path.home() / ".steam" / "steam"),
            }
            return [str(proton_bin), "run", exe]
        wine = proton.system_wine()
        if not wine:
            raise RuntimeError("Wine was not found on PATH")
        prefix = self._prefix_for(game)
        self._pending_env = {"WINEPREFIX": prefix}
        return [wine, exe]

    def _prefix_for(self, game: Game) -> str:
        if game.prefix_path:
            return game.prefix_path
        base = game.game_dir or config.settings.get("installs_dir") or str(config.DATA_DIR / "Games")
        return str(Path(base) / "Prefix")

    # -- control -----------------------------------------------------------
    def start(self, game: Game, debug: bool = False) -> None:
        if self.running:
            raise RuntimeError("A game is already running")
        if not game.executable or not Path(game.executable).exists():
            raise RuntimeError("Game executable not found")

        env = self._env(game, debug)
        argv = self._argv(game, debug)
        env.update(getattr(self, "_pending_env", {}))

        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        for key, value in env.items():
            launcher.setenv(key, value, True)
        cwd = game.game_dir or str(Path(game.executable).parent)
        if Path(cwd).is_dir():
            launcher.set_cwd(cwd)

        self.on_state(True)
        process = launcher.spawnv(argv)
        started_at = time.monotonic()
        self.current = GameProcess(game, process, debug, started_at)
        _write_running_state(process.get_identifier() or 0, game)

        self._pipe_lines(process.get_stdout_pipe(), self.on_output)
        self._pipe_lines(process.get_stderr_pipe(), self.on_output)

        process.wait_async(None, self._on_exit)

    def stop(self) -> None:
        """Kill the running game: graceful wineserver shutdown, then the whole
        process tree (SIGTERM, then SIGKILL for anything that survives)."""
        proc = self.current
        if not proc:
            return

        game = self._game_by_name(proc.game_name)
        pid = proc.process.get_identifier() or 0

        # 1. Ask wineserver to shut the prefix down gracefully.
        if game:
            _kill_wineserver(game.runner, game.proton_version, self._prefix_for(game))
        else:
            data = _read_running_state() or {}
            _kill_wineserver(
                str(data.get("runner") or "wine"),
                str(data.get("proton_version") or ""),
                str(data.get("prefix") or ""),
            )

        # 2. Make sure the launcher's own child tree is dead.
        if pid > 0:
            kill_process_tree(pid, signal.SIGTERM)

            def hard_kill() -> bool:
                if proc.process.get_if_running():
                    kill_process_tree(pid, signal.SIGKILL)
                return False

            GLib.timeout_add(3000, hard_kill)
        else:
            try:
                proc.process.force_exit()
            except Exception:
                pass
        _clear_running_state(pid)

    # -- internals -----------------------------------------------------------
    def _game_by_name(self, name: str):
        from . import library

        return library.library.get(name)

    def _pipe_lines(self, stream: Gio.InputStream | None, cb) -> None:
        if stream is None:
            return
        data_stream = Gio.DataInputStream.new(stream)

        def read_line(_source, result):
            try:
                line, _len = data_stream.read_line_finish_utf8(result)
            except Exception:
                line = None
            if line is None:
                return
            if line:
                cb(line)
            data_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)

        data_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)

    def _on_exit(self, process: Gio.Subprocess, result) -> None:
        current = self.current
        name = current.game_name if current else "?"
        pid = current.process.get_identifier() if current else None
        try:
            process.wait_finish(result)
            code = process.get_exit_status()
        except Exception:
            code = 0

        elapsed = 0
        if current:
            elapsed = int(time.monotonic() - current.started_at)
        self.current = None
        _clear_running_state(pid)

        def finish() -> bool:
            try:
                lib = self._game_by_name(name)
                if lib is not None and elapsed > 5:
                    from . import library

                    library.library.touch_played(name, elapsed)
            except Exception:
                pass
            self.on_exit(name, code)
            self.on_state(False)
            return False

        GLib.idle_add(finish)


runner = Runner()
