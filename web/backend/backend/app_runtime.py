from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LogBuffer:
    def __init__(self, capacity: int = 200) -> None:
        self.capacity = capacity
        self.lines: list[str] = []
        self.total = 0
        self.run_id = 0
        self._lock = threading.Lock()

    def append(self, line: str) -> None:
        with self._lock:
            if len(self.lines) >= self.capacity:
                self.lines.pop(0)
            self.lines.append(line.rstrip("\n"))
            self.total += 1

    def reset(self) -> None:
        with self._lock:
            self.lines = []
            self.total = 0
            self.run_id += 1

    def snapshot(self, offset: int = 0, run_id: int | None = None) -> dict[str, Any]:
        with self._lock:
            if run_id is not None and run_id != self.run_id:
                offset = 0
            if offset < 0:
                offset = 0
            buffered_start = max(self.total - len(self.lines), 0)
            if offset < buffered_start:
                lines = list(self.lines)
            else:
                start = max(offset - buffered_start, 0)
                lines = self.lines[start:]
            return {
                "logs": lines,
                "log_total": self.total,
                "log_run_id": self.run_id,
            }


@dataclass(slots=True)
class RuntimeState:
    status: str = "stopped"
    pid: int | None = None
    boot_default_model: str = ""
    boot_signature: str = ""
    last_error: str = ""


class GatewayRuntime:
    def __init__(self, config_path: Path, project_root: Path | None = None) -> None:
        self.config_path = config_path
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.logs = LogBuffer(400)
        self.state = RuntimeState()
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def _python_executable(self) -> str:
        if sys.platform == "win32":
            candidates = [
                self.project_root / "web" / "backend" / ".venv" / "Scripts" / "python.exe",
                self.project_root / ".venv" / "Scripts" / "python.exe",
            ]
        else:
            candidates = [
                self.project_root / "web" / "backend" / ".venv" / "bin" / "python",
                self.project_root / ".venv" / "bin" / "python",
            ]

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return sys.executable

    def _command(self) -> list[str]:
        return [
            self._python_executable(),
            "-m",
            "miniclaw.cli.commands",
            "gateway",
            "--config",
            str(self.config_path),
        ]

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        repo_root = str(self.project_root)
        current_pythonpath = env.get("PYTHONPATH", "").strip()
        if current_pythonpath:
            entries = current_pythonpath.split(os.pathsep)
            if repo_root not in entries:
                env["PYTHONPATH"] = os.pathsep.join([repo_root, *entries])
        else:
            env["PYTHONPATH"] = repo_root
        env["MINICLAW_CONFIG"] = str(self.config_path)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return env

    def _creationflags(self) -> int:
        if sys.platform != "win32":
            return 0
        return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    def _stream_logs(self, process: subprocess.Popen[str]) -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            self.logs.append(line)

    def _watch_process(self, process: subprocess.Popen[str]) -> None:
        return_code = process.wait()
        with self._lock:
            if self._process is not process:
                return
            self._process = None
            self.state.pid = None
            if self.state.status in {"stopping", "restarting"}:
                self.state.status = "stopped"
                self.state.last_error = ""
            elif return_code == 0:
                self.state.status = "stopped"
                self.state.last_error = ""
            else:
                self.state.status = "error"
                self.state.last_error = f"gateway exited with code {return_code}"

    def _mark_running_if_alive(self) -> None:
        time.sleep(1.0)
        with self._lock:
            if self._process and self._process.poll() is None and self.state.status == "starting":
                self.state.status = "running"
                self.state.last_error = ""

    def start(self, boot_default_model: str, boot_signature: str) -> dict[str, Any]:
        with self._lock:
            if self._process and self._process.poll() is None:
                return {"status": "ok", "pid": self._process.pid}

            self.logs.reset()
            process = subprocess.Popen(
                self._command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=self._creationflags(),
                cwd=str(self.project_root),
                env=self._environment(),
            )
            self._process = process
            self.state.status = "starting"
            self.state.pid = process.pid
            self.state.boot_default_model = boot_default_model
            self.state.boot_signature = boot_signature
            self.state.last_error = ""

            threading.Thread(target=self._stream_logs, args=(process,), daemon=True).start()
            threading.Thread(target=self._watch_process, args=(process,), daemon=True).start()
            threading.Thread(target=self._mark_running_if_alive, daemon=True).start()
            return {"status": "ok", "pid": process.pid}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if not process or process.poll() is not None:
                self._process = None
                self.state.status = "stopped"
                self.state.pid = None
                return {"status": "ok"}
            self.state.status = "stopping"

        try:
            process.terminate()
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        with self._lock:
            self._process = None
            self.state.status = "stopped"
            self.state.pid = None
            self.state.last_error = ""
        return {"status": "ok"}

    def restart(self, boot_default_model: str, boot_signature: str) -> dict[str, Any]:
        with self._lock:
            if self._process and self._process.poll() is None:
                self.state.status = "restarting"
        self.stop()
        return self.start(boot_default_model=boot_default_model, boot_signature=boot_signature)

    def status(self) -> RuntimeState:
        with self._lock:
            if self._process and self._process.poll() is not None:
                self._process = None
                self.state.pid = None
                if self.state.status not in {"error", "stopped"}:
                    self.state.status = "stopped"
            return RuntimeState(
                status=self.state.status,
                pid=self.state.pid,
                boot_default_model=self.state.boot_default_model,
                boot_signature=self.state.boot_signature,
                last_error=self.state.last_error,
            )
