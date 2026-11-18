"""Configuración persistente de la aplicación."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _resolve_base_dir() -> Path:
    override = os.environ.get("STUDENT_SUPPORT_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


BASE_DIR = _resolve_base_dir()
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"
ICON_PNG_PATH = ASSETS_DIR / "icon.png"
CONFIG_PATH = DATA_DIR / "config.json"
SESSION_PATH = DATA_DIR / "telegram"
LOG_PATH = DATA_DIR / "student_support.log"
DATABASE_PATH = DATA_DIR / "student_support.db"
DEFAULT_DOWNLOADS_DIR = BASE_DIR / "Descargas Telegram"

# Solo se conservan los mensajes publicados desde esta fecha (hora local).
# Lo anterior se ignora al sincronizar y se borra del índice y del disco.
MESSAGE_CUTOFF_LOCAL = datetime(2026, 8, 1, 0, 0)
MESSAGE_CUTOFF = MESSAGE_CUTOFF_LOCAL.astimezone()
MESSAGE_CUTOFF_UTC = MESSAGE_CUTOFF.astimezone(timezone.utc)
MESSAGE_CUTOFF_ISO = MESSAGE_CUTOFF_UTC.isoformat(timespec="seconds")
MESSAGE_CUTOFF_LABEL = "01/08/2026"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    api_id: int | None = None
    api_hash: str = ""
    phone: str = ""
    downloads_dir: str = str(DEFAULT_DOWNLOADS_DIR)

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_id and self.api_hash and self.phone)

    def download_path(self) -> Path:
        path = Path(self.downloads_dir).expanduser()
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    @classmethod
    def load(cls) -> "Settings":
        ensure_directories()
        if not CONFIG_PATH.exists():
            return cls()

        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()

        api_id = raw.get("api_id")
        try:
            api_id = int(api_id) if api_id not in (None, "") else None
        except (TypeError, ValueError):
            api_id = None

        downloads_dir = str(raw.get("downloads_dir") or DEFAULT_DOWNLOADS_DIR)
        return cls(
            api_id=api_id,
            api_hash=str(raw.get("api_hash") or "").strip(),
            phone=str(raw.get("phone") or "").strip(),
            downloads_dir=downloads_dir,
        )

    def save(self) -> None:
        ensure_directories()
        payload = {
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "phone": self.phone,
            "downloads_dir": self.downloads_dir,
        }
        temporary = CONFIG_PATH.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(CONFIG_PATH)
