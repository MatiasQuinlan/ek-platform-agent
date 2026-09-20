from __future__ import annotations

import json
import os
from pathlib import Path

import keyring

SERVICE = "ek-platform-agent"


def config_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = root / "ek-platform-agent"
    path.mkdir(parents=True, exist_ok=True)
    return path / "config.json"


def load() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def save(values: dict[str, str]) -> None:
    config_path().write_text(json.dumps(values, indent=2), encoding="utf-8")


def get_access_token() -> str | None:
    return keyring.get_password(SERVICE, "cognito-access-token")


def set_access_token(token: str) -> None:
    keyring.set_password(SERVICE, "cognito-access-token", token)
