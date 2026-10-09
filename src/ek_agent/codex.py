from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


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
