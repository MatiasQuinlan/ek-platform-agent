from __future__ import annotations

import shutil
import subprocess


def installed() -> bool:
    return shutil.which("codex") is not None


def login() -> subprocess.Popen[str]:
    if not installed():
        raise RuntimeError("Codex CLI no está instalado o no está en PATH")
    return subprocess.Popen(["codex", "login"], text=True)


def execute(prompt: str) -> str:
    if not installed():
        raise RuntimeError("Codex CLI no está instalado o no está en PATH")
    result = subprocess.run(
        [
            "codex",
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
