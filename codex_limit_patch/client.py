from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any


class CodexAppServerError(RuntimeError):
    pass


def find_codex_binary(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env_value = os.environ.get("CODEX_BIN")
    if env_value:
        return env_value
    found = shutil.which("codex")
    if found:
        return found
    if sys.platform.startswith("win"):
        candidates = sorted(
            Path(r"C:\Program Files\WindowsApps").glob(
                r"OpenAI.Codex_*\app\resources\codex.exe"
            ),
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    raise CodexAppServerError(
        "Could not find codex binary. Put codex on PATH or set CODEX_BIN."
    )


class CodexAppServerClient:
    def __init__(self, codex_bin: str | None = None, timeout_sec: float = 45.0):
        self.codex_bin = find_codex_binary(codex_bin)
        self.timeout_sec = timeout_sec

    def read_rate_limits(self) -> dict[str, Any]:
        proc = subprocess.Popen(
            [self.codex_bin, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdout_queue: Queue[tuple[str, str]] = Queue()

        def reader(stream: Any, name: str) -> None:
            for line in stream:
                stdout_queue.put((name, line.rstrip("\n")))

        threading.Thread(target=reader, args=(proc.stdout, "stdout"), daemon=True).start()
        threading.Thread(target=reader, args=(proc.stderr, "stderr"), daemon=True).start()

        try:
            self._send(proc, {
                "method": "initialize",
                "id": 0,
                "params": {
                    "clientInfo": {
                        "name": "codex_limit_patch",
                        "title": "Codex Limit Patch",
                        "version": "0.1.0",
                    }
                },
            })
            self._wait_for_id(stdout_queue, 0)
            self._send(proc, {"method": "initialized"})
            self._send(proc, {"method": "account/rateLimits/read", "id": 1})
            return self._wait_for_id(stdout_queue, 1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _send(self, proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
        if proc.stdin is None:
            raise CodexAppServerError("app-server stdin is not available")
        proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        proc.stdin.flush()

    def _wait_for_id(self, queue: Queue[tuple[str, str]], request_id: int) -> dict[str, Any]:
        deadline = time.time() + self.timeout_sec
        last_stderr: list[str] = []
        while time.time() < deadline:
            try:
                name, line = queue.get(timeout=0.5)
            except Empty:
                continue
            if name == "stderr":
                last_stderr.append(line)
                last_stderr = last_stderr[-5:]
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == request_id:
                if "error" in payload:
                    raise CodexAppServerError(str(payload["error"]))
                return payload
        suffix = f" Last stderr: {' | '.join(last_stderr)}" if last_stderr else ""
        raise CodexAppServerError(
            f"Timed out waiting for app-server response id={request_id}.{suffix}"
        )
