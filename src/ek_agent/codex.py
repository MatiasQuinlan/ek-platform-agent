from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from typing import Any, Protocol


def _codex_path() -> str | None:
    configured = os.environ.get("EK_CODEX_PATH")
    candidates = [configured] if configured else []
    resolved = shutil.which("codex")
    if resolved:
        candidates.append(resolved)
    home = Path.home()
    candidates.extend(
        [
            str(path)
            for root in (
                home / ".nvm/versions/node",
                home / ".codex/packages/app-server-daemon/releases",
            )
            if root.exists()
            for path in root.glob("*/bin/codex")
        ]
    )
    candidates.append(str(home / ".codex/plugins/.plugin-appserver/codex-cli/bin/codex"))
    cache_root = home / "Library/Caches/com.openai.codex/org.sparkle-project.Sparkle/Installation"
    if cache_root.exists():
        candidates.extend(str(path) for path in cache_root.glob("*/**/codex") if path.is_file())
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def installed() -> bool:
    return _codex_path() is not None


def login() -> subprocess.Popen[str]:
    command = _codex_path()
    if not command:
        raise RuntimeError("Codex CLI no está instalado o no está en PATH")
    return subprocess.Popen([command, "login"], text=True)


def execute(prompt: str) -> str:
    command = _codex_path()
    if not command:
        raise RuntimeError("Codex CLI no está instalado o no está en PATH")
    result = subprocess.run(
        [
            command,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    return result.stdout.strip()


class ExecutionInterface(Protocol):
    """The local execution boundary used by the background worker."""

    def execute(self, prompt: str) -> str: ...

    def close(self) -> None: ...


class CodexExecExecutor:
    """Compatibility adapter for the original one-shot CLI invocation."""

    def execute(self, prompt: str) -> str:
        return execute(prompt)

    def close(self) -> None:
        return


class AppServerError(RuntimeError):
    pass


class PersistentCodexExecutor:
    """A small JSONL client for the local Codex app-server process.

    The process owns the user's Codex session. No backend access token is ever put
    in this protocol; callers pass only the editorial prompt and its context.
    """

    def __init__(self, command: str | None = None, *, popen: Any = subprocess.Popen) -> None:
        self.command = command or _codex_path()
        if not self.command:
            raise RuntimeError("Codex CLI no está instalado o no está en PATH")
        self._popen = popen
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._next_id = 0
        self._thread_id: str | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _start(self) -> None:
        self._process = self._popen(
            [self.command, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._thread_id = None
        self._request(
            "initialize", {"clientInfo": {"name": "ek-platform-agent", "version": "0.1.0"}}
        )
        self._notify("initialized", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, value: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise AppServerError("Codex app-server no está iniciado")
        self._process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _lines(self) -> Iterator[dict[str, Any]]:
        if not self._process or not self._process.stdout:
            raise AppServerError("Codex app-server no está iniciado")
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise AppServerError("Codex app-server terminó inesperadamente")
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        for value in self._lines():
            if value.get("id") != request_id:
                continue
            if "error" in value:
                raise AppServerError(str(value["error"]))
            result = value.get("result", {})
            return result if isinstance(result, dict) else {}
        raise AppServerError(f"Sin respuesta para {method}")

    def _ensure_thread(self) -> None:
        if self._thread_id:
            return
        self.start_thread()

    def start_thread(self) -> str:
        """Create a new server-side conversation and return its identifier."""
        result = self._request("thread/start", {})
        thread = result.get("thread", result)
        self._thread_id = thread.get("id") if isinstance(thread, dict) else None
        if not self._thread_id:
            raise AppServerError("Codex app-server no devolvió thread id")
        return self._thread_id

    def resume_thread(self, thread_id: str) -> str:
        """Resume an existing conversation, useful after an app restart."""
        result = self._request("thread/resume", {"threadId": thread_id})
        thread = result.get("thread", result)
        resumed_id = thread.get("id") if isinstance(thread, dict) else None
        if not resumed_id:
            raise AppServerError("Codex app-server no pudo reanudar el thread")
        self._thread_id = resumed_id
        return resumed_id

    @staticmethod
    def _event_text(value: dict[str, Any]) -> str:
        params = value.get("params", {})
        item = params.get("item", {}) if isinstance(params, dict) else {}
        for candidate in (
            params.get("delta") if isinstance(params, dict) else None,
            params.get("text") if isinstance(params, dict) else None,
            item.get("text") if isinstance(item, dict) else None,
            item.get("content") if isinstance(item, dict) else None,
        ):
            if isinstance(candidate, str):
                return candidate
        if isinstance(item, dict) and isinstance(item.get("content"), list):
            return "".join(
                part.get("text", "") for part in item["content"] if isinstance(part, dict)
            )
        return ""

    def _turn(self, prompt: str) -> str:
        if not self._thread_id:
            raise AppServerError("Codex thread no está iniciado")
        self._next_id += 1
        request_id = self._next_id
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "turn/start",
                "params": {
                    "threadId": self._thread_id,
                    "input": [{"type": "text", "text": prompt}],
                },
            }
        )
        chunks: list[str] = []
        response_seen = False
        for value in self._lines():
            if value.get("id") == request_id:
                response_seen = True
                if "error" in value:
                    raise AppServerError(str(value["error"]))
                continue
            method = value.get("method", "")
            if method in {"item/agentMessage/delta", "item/agent_message/delta"}:
                chunks.append(self._event_text(value))
            if method in {"turn/completed", "turn/failed"}:
                if method == "turn/failed":
                    raise AppServerError(str(value.get("params", {})))
                if not chunks:
                    chunks.append(self._event_text(value))
                break
        if not response_seen:
            raise AppServerError("Sin respuesta para turn/start")
        return "".join(chunks).strip()

    def execute(self, prompt: str) -> str:
        with self._lock:
            for attempt in range(2):
                try:
                    if not self.is_running:
                        self._start()
                    self._ensure_thread()
                    return self._turn(prompt)
                except (AppServerError, OSError, BrokenPipeError):
                    self.restart()
                    if attempt == 1:
                        raise
        raise AssertionError("unreachable")

    def restart(self) -> None:
        self.close()
        time.sleep(0.05)

    def close(self) -> None:
        process, self._process = self._process, None
        self._thread_id = None
        if not process:
            return
        try:
            if process.poll() is None and process.stdin:
                process.stdin.write(
                    json.dumps({"jsonrpc": "2.0", "method": "shutdown", "params": {}}) + "\n"
                )
                process.stdin.flush()
                process.wait(timeout=2)
        except (OSError, BrokenPipeError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def create_executor() -> ExecutionInterface:
    enabled = os.environ.get("EK_CODEX_APP_SERVER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return PersistentCodexExecutor() if enabled else CodexExecExecutor()
