"""Launch and manage game processes (Proton or plain Wine)."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from gi.repository import Gio, GLib

from . import config, proton
from .models import Game


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
        ws = proton.wineserver_for(game.runner if game else "wine", game.proton_version if game else "")
        if ws:
            env = dict(os.environ)
            if game:
                prefix = self._prefix_for(game)
                if game.runner == "proton":
                    env["STEAM_COMPAT_DATA_PATH"] = prefix
                else:
                    env["WINEPREFIX"] = prefix
            try:
                subprocess_env_launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.NONE)
                for key, value in env.items():
                    subprocess_env_launcher.setenv(key, value, True)
                subprocess_env_launcher.spawnv([str(ws), "-k"])
            except Exception:
                pass

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
        try:
            process.wait_finish(result)
            code = process.get_exit_status()
        except Exception:
            code = 0

        elapsed = 0
        if current:
            elapsed = int(time.monotonic() - current.started_at)
        self.current = None

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
