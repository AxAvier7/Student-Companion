"""Utilidades para construir nombres de carpetas y archivos seguros."""

from __future__ import annotations

import mimetypes
import re
import unicodedata
from datetime import datetime
from pathlib import Path

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
_WHITESPACE = re.compile(r"\s+")

_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Algunas extensiones que mimetypes devuelve de forma poco habitual.
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/x-wav": ".wav",
    "audio/wav": ".wav",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/msword": ".doc",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/rtf": ".rtf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/x-7z-compressed": ".7z",
    "application/x-rar-compressed": ".rar",
}

_DEFAULT_EXTENSIONS = {
    "photo": ".jpg",
    "sticker": ".webp",
    "voice": ".ogg",
    "video_note": ".mp4",
    "gif": ".mp4",
}


def sanitize_component(value: str, fallback: str = "Sin nombre", max_length: int = 80) -> str:
    """Convierte un texto en un nombre válido de archivo/carpeta en Windows."""
    text = unicodedata.normalize("NFC", value or "")
    text = _INVALID_CHARS.sub("_", text)
    text = _WHITESPACE.sub(" ", text).strip(" .")

    if len(text) > max_length:
        text = text[:max_length].rstrip(" .")

    if not text:
        return fallback

    if text.upper() in _RESERVED_NAMES:
        text = f"_{text}"

    return text


def unique_component(candidate: str, taken: set[str]) -> str:
    """Añade un sufijo numérico si el nombre ya está ocupado."""
    existing = {name.casefold() for name in taken}
    if candidate.casefold() not in existing:
        return candidate

    counter = 2
    while f"{candidate} ({counter})".casefold() in existing:
        counter += 1
    return f"{candidate} ({counter})"


def extension_for(kind: str | None, mime_type: str | None) -> str:
    mime = (mime_type or "").lower().strip()
    if mime in _MIME_EXTENSIONS:
        return _MIME_EXTENSIONS[mime]

    if mime:
        guessed = mimetypes.guess_extension(mime)
        if guessed:
            return guessed.lower()

    return _DEFAULT_EXTENSIONS.get(kind or "", ".bin")


def _split_original_name(original_name: str | None) -> tuple[str, str]:
    if not original_name:
        return "", ""

    name = original_name.replace("\\", "/").rsplit("/", 1)[-1]
    path = Path(name)
    stem = path.stem if path.suffix else path.name
    extension = path.suffix.lower()

    if not extension or len(extension) > 12:
        extension = ""

    return stem, extension


def media_filename(
    local_date: datetime,
    message_id: int,
    original_name: str | None,
    kind: str | None,
    mime_type: str | None,
) -> str:
    """Nombre ordenable y único dentro de un canal.

    Ejemplo: ``2026-02-12_18-30_45871_Tema 3 - apuntes.pdf``
    """
    stem, extension = _split_original_name(original_name)
    if not extension:
        extension = extension_for(kind, mime_type)

    base = f"{local_date:%Y-%m-%d_%H-%M}_{message_id}"
    clean_stem = sanitize_component(stem, fallback="", max_length=55)
    if clean_stem:
        base = f"{base}_{clean_stem}"

    return f"{base}{extension}"
