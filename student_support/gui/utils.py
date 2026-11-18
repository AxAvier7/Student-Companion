"""Funciones auxiliares de la interfaz."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

_MEDIA_LABELS = {
    "photo": "Imagen",
    "video": "Vídeo",
    "audio": "Audio",
    "voice": "Nota de voz",
    "document": "Documento",
    "sticker": "Sticker",
    "gif": "GIF",
    "video_note": "Vídeo circular",
    "poll": "Encuesta",
    "contact": "Contacto",
    "location": "Ubicación",
    "dice": "Dado",
}


def open_path(path: str | Path) -> None:
    """Abre un archivo o carpeta con la aplicación predeterminada del sistema."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"No se encuentra: {target}")

    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


def open_url(url: str) -> None:
    webbrowser.open(url, new=2)


def format_datetime(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return str(value)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%d/%m/%Y %H:%M")


def format_size(size: int | None) -> str:
    if not size:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def media_label(media_type: str | None, file_name: str | None = None) -> str:
    if not media_type:
        return "Texto"
    base = _MEDIA_LABELS.get(media_type, media_type.capitalize())
    if media_type == "document" and file_name:
        suffix = Path(file_name).suffix.lower().lstrip(".")
        if suffix:
            return f"{base} ({suffix.upper()})"
    return base


def table_media_label(media_type: str | None, file_name: str | None = None) -> str:
    """Etiqueta corta para la tabla (PDF, DOCX, Imagen…)."""
    if media_type == "document" and file_name:
        suffix = Path(file_name).suffix.lower().lstrip(".")
        if suffix:
            return suffix.upper()
    return media_label(media_type, file_name)


def compact_text(value: str | None, max_length: int = 240) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def center_window(window, parent=None) -> None:
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()

    if parent is not None and parent.winfo_exists():
        parent.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 3)
    else:
        x = max(0, (window.winfo_screenwidth() - width) // 2)
        y = max(0, (window.winfo_screenheight() - height) // 3)

    window.geometry(f"+{x}+{y}")
