"""Base de datos SQLite con el índice de asignaturas, canales y mensajes."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import MESSAGE_CUTOFF_ISO
from .paths import sanitize_component, unique_component

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    folder_name TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    id             INTEGER PRIMARY KEY,
    subject_id     INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    username       TEXT,
    access_hash    INTEGER,
    peer_type      TEXT NOT NULL,
    folder_name    TEXT NOT NULL,
    last_synced_id INTEGER NOT NULL DEFAULT 0,
    last_sync_at   TEXT,
    added_at       TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_channels_subject
    ON channels(subject_id, id);

CREATE TABLE IF NOT EXISTS messages (
    channel_id  INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    message_id  INTEGER NOT NULL,
    subject_id  INTEGER NOT NULL,
    date        TEXT NOT NULL,
    sender_id   INTEGER,
    sender_name TEXT,
    text        TEXT,
    media_type  TEXT,
    file_name   TEXT,
    file_path   TEXT,
    file_size   INTEGER,
    mime_type   TEXT,
    grouped_id  INTEGER,
    post_author TEXT,
    permalink   TEXT,
    PRIMARY KEY (channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_subject_date
    ON messages(subject_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_messages_channel_date
    ON messages(channel_id, date DESC);

CREATE TABLE IF NOT EXISTS teachers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id   INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    sender_key   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    UNIQUE (subject_id, sender_key)
);

CREATE INDEX IF NOT EXISTS idx_teachers_subject
    ON teachers(subject_id);
"""

_MESSAGE_FIELDS = (
    "channel_id",
    "message_id",
    "subject_id",
    "date",
    "sender_id",
    "sender_name",
    "text",
    "media_type",
    "file_name",
    "file_path",
    "file_size",
    "mime_type",
    "grouped_id",
    "post_author",
    "permalink",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sender_key(record: dict[str, Any]) -> str:
    """Identifica de forma estable al autor de un mensaje.

    En los canales con firma se usa el nombre del autor; en los grupos, el
    identificador de usuario de Telegram.
    """
    author = (record.get("post_author") or "").strip()
    if author:
        return f"author:{author}"

    sender_id = record.get("sender_id")
    if sender_id is not None:
        return f"user:{int(sender_id)}"
    return ""


_SENDER_KEY_SQL = """
    CASE
        WHEN m.post_author IS NOT NULL AND TRIM(m.post_author) <> ''
            THEN 'author:' || m.post_author
        WHEN m.sender_id IS NOT NULL THEN 'user:' || m.sender_id
        ELSE ''
    END
""".strip()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(_SCHEMA)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # Asignaturas
    # ------------------------------------------------------------------
    def subjects(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM subjects ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def subject(self, subject_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
        return dict(row) if row else None

    def add_subject(self, name: str) -> int:
        cleaned = " ".join((name or "").split())
        if not cleaned:
            raise ValueError("El nombre de la asignatura no puede estar vacío.")

        taken = {row["folder_name"] for row in self.subjects()}
        folder = unique_component(
            sanitize_component(cleaned, fallback="Asignatura", max_length=50), taken
        )

        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO subjects (name, folder_name, created_at) VALUES (?, ?, ?)",
                (cleaned, folder, _now()),
            )
            return int(cursor.lastrowid)

    def rename_subject(self, subject_id: int, name: str) -> None:
        cleaned = " ".join((name or "").split())
        if not cleaned:
            raise ValueError("El nombre de la asignatura no puede estar vacío.")
        with self._connection() as connection:
            connection.execute(
                "UPDATE subjects SET name = ? WHERE id = ?", (cleaned, subject_id)
            )

    def delete_subject(self, subject_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))

    # ------------------------------------------------------------------
    # Canales
    # ------------------------------------------------------------------
    def channels(self, subject_id: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT c.*, s.name AS subject_name, s.folder_name AS subject_folder
            FROM channels c
            JOIN subjects s ON s.id = c.subject_id
        """
        parameters: tuple[Any, ...] = ()
        if subject_id is not None:
            query += " WHERE c.subject_id = ?"
            parameters = (subject_id,)
        query += " ORDER BY c.title COLLATE NOCASE"

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def channel(self, channel_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT c.*, s.name AS subject_name, s.folder_name AS subject_folder
                FROM channels c
                JOIN subjects s ON s.id = c.subject_id
                WHERE c.id = ?
                """,
                (channel_id,),
            ).fetchone()
        return dict(row) if row else None

    def channel_owner(self, channel_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT c.id, c.subject_id, s.name AS subject_name
                FROM channels c
                JOIN subjects s ON s.id = c.subject_id
                WHERE c.id = ?
                """,
                (channel_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_channel(self, subject_id: int, peer: dict[str, Any]) -> bool:
        """Añade un canal a una asignatura. Devuelve False si ya existía."""
        owner = self.channel_owner(int(peer["id"]))
        if owner:
            if owner["subject_id"] == subject_id:
                return False
            raise ValueError(
                f"Ese canal ya está en la asignatura «{owner['subject_name']}»."
            )

        subject = self.subject(subject_id)
        if not subject:
            raise ValueError("La asignatura no existe.")

        taken = {channel["folder_name"] for channel in self.channels(subject_id)}
        folder = unique_component(
            sanitize_component(
                peer.get("title") or "Canal", fallback="Canal", max_length=50
            ),
            taken,
        )

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO channels
                    (id, subject_id, title, username, access_hash, peer_type,
                     folder_name, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    int(peer["id"]),
                    subject_id,
                    peer.get("title") or "Canal",
                    peer.get("username") or None,
                    peer.get("access_hash"),
                    peer.get("peer_type") or "channel",
                    folder,
                    _now(),
                ),
            )
        return True

    def remove_channel(self, channel_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM channels WHERE id = ?", (channel_id,))

    def set_channel_synced(
        self, channel_id: int, last_synced_id: int, synced_at: str | None = None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE channels
                SET last_synced_id = ?, last_sync_at = ?
                WHERE id = ?
                """,
                (int(last_synced_id), synced_at or _now(), channel_id),
            )

    def update_channel_meta(
        self, channel_id: int, title: str, username: str | None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE channels SET title = ?, username = ? WHERE id = ?",
                (title, username, channel_id),
            )

    # ------------------------------------------------------------------
    # Profesores
    # ------------------------------------------------------------------
    def teachers(self, subject_id: int) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM teachers
                WHERE subject_id = ?
                ORDER BY display_name COLLATE NOCASE
                """,
                (subject_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_teacher(
        self, subject_id: int, sender_key_value: str, display_name: str
    ) -> bool:
        """Marca a un remitente como profesor. Devuelve False si ya lo era."""
        key = (sender_key_value or "").strip()
        if not key:
            return False
        name = " ".join((display_name or "").split()) or "Profesor"
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO teachers
                    (subject_id, sender_key, display_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (subject_id, key, name, _now()),
            )
            return cursor.rowcount > 0

    def remove_teacher(self, subject_id: int, sender_key_value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM teachers WHERE subject_id = ? AND sender_key = ?",
                (subject_id, (sender_key_value or "").strip()),
            )

    def teacher_keys(self, subject_id: int) -> set[str]:
        return {teacher["sender_key"] for teacher in self.teachers(subject_id)}

    def is_teacher(self, subject_id: int, sender_key_value: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM teachers WHERE subject_id = ? AND sender_key = ?",
                (subject_id, (sender_key_value or "").strip()),
            ).fetchone()
        return row is not None

    def message_senders(self, subject_id: int) -> list[dict[str, Any]]:
        """Remitentes presentes en los mensajes, para elegir profesores."""
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    {_SENDER_KEY_SQL} AS sender_key,
                    COALESCE(
                        NULLIF(TRIM(m.post_author), ''),
                        NULLIF(TRIM(m.sender_name), ''),
                        'Desconocido'
                    ) AS display_name,
                    COUNT(*) AS total,
                    MAX(m.date) AS last_date
                FROM messages m
                WHERE m.subject_id = ? AND m.date >= ?
                GROUP BY sender_key
                HAVING sender_key <> ''
                ORDER BY display_name COLLATE NOCASE
                """,
                (subject_id, MESSAGE_CUTOFF_ISO),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------
    def get_message(self, channel_id: int, message_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM messages WHERE channel_id = ? AND message_id = ?",
                (channel_id, message_id),
            ).fetchone()
        return dict(row) if row else None

    def insert_message(self, record: dict[str, Any]) -> bool:
        columns = ", ".join(_MESSAGE_FIELDS)
        placeholders = ", ".join("?" for _ in _MESSAGE_FIELDS)
        values = tuple(record.get(field) for field in _MESSAGE_FIELDS)
        with self._connection() as connection:
            cursor = connection.execute(
                f"INSERT OR IGNORE INTO messages ({columns}) VALUES ({placeholders})",
                values,
            )
            return cursor.rowcount > 0

    def update_message_file(
        self,
        channel_id: int,
        message_id: int,
        file_path: str | None,
        file_name: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE messages
                SET file_path = ?, file_name = COALESCE(?, file_name)
                WHERE channel_id = ? AND message_id = ?
                """,
                (file_path, file_name, channel_id, message_id),
            )

    @staticmethod
    def _type_clause(media_filter: str) -> str | None:
        kind = (media_filter or "all").lower()
        if kind in ("", "all", "todos"):
            return None
        if kind == "document":
            return "m.media_type = 'document'"
        if kind == "image":
            return "m.media_type IN ('photo', 'sticker')"
        if kind == "video":
            return "m.media_type IN ('video', 'video_note', 'gif')"
        if kind == "audio":
            return "m.media_type IN ('audio', 'voice')"
        if kind == "text":
            return "m.media_type IS NULL"
        if kind == "link":
            return (
                "(m.text LIKE '%http://%' OR m.text LIKE '%https://%'"
                " OR m.text LIKE '%www.%' OR m.text LIKE '%t.me/%'"
                " OR m.text LIKE '%telegram.me/%')"
            )
        if kind == "other":
            return (
                "m.media_type IS NOT NULL AND m.media_type NOT IN "
                "('document', 'photo', 'sticker', 'video', 'video_note', "
                "'gif', 'audio', 'voice')"
            )
        return None

    @classmethod
    def _search_clause(
        cls,
        subject_id: int,
        channel_id: int | None,
        search: str,
        media_filter: str = "all",
        teacher_only: bool = False,
    ) -> tuple[str, list[Any]]:
        where = ["m.subject_id = ?", "m.date >= ?"]
        parameters: list[Any] = [subject_id, MESSAGE_CUTOFF_ISO]

        if channel_id is not None:
            where.append("m.channel_id = ?")
            parameters.append(channel_id)

        if teacher_only:
            where.append(
                f"""
                EXISTS (
                    SELECT 1 FROM teachers t
                    WHERE t.subject_id = m.subject_id
                      AND t.sender_key = {_SENDER_KEY_SQL}
                )
                """.strip()
            )

        type_clause = cls._type_clause(media_filter)
        if type_clause:
            where.append(type_clause)

        term = (search or "").strip()
        if term:
            like = f"%{term}%"
            where.append(
                "(m.text LIKE ? OR m.sender_name LIKE ? OR m.file_name LIKE ? OR m.post_author LIKE ?)"
            )
            parameters.extend([like, like, like, like])

        return " AND ".join(where), parameters

    def messages(
        self,
        subject_id: int,
        channel_id: int | None = None,
        search: str = "",
        limit: int = 800,
        media_filter: str = "all",
        teacher_only: bool = False,
    ) -> list[dict[str, Any]]:
        where, parameters = self._search_clause(
            subject_id, channel_id, search, media_filter, teacher_only
        )
        query = f"""
            SELECT m.*, c.title AS channel_title
            FROM messages m
            JOIN channels c ON c.id = m.channel_id
            WHERE {where}
            ORDER BY m.date DESC, m.message_id DESC
            LIMIT ?
        """
        parameters.append(max(1, int(limit)))

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def count_messages(
        self,
        subject_id: int,
        channel_id: int | None = None,
        search: str = "",
        media_filter: str = "all",
        teacher_only: bool = False,
    ) -> int:
        where, parameters = self._search_clause(
            subject_id, channel_id, search, media_filter, teacher_only
        )
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM messages m WHERE {where}", parameters
            ).fetchone()
        return int(row["total"]) if row else 0

    def channel_counts(self, subject_id: int) -> dict[int, int]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT channel_id, COUNT(*) AS total
                FROM messages
                WHERE subject_id = ? AND date >= ?
                GROUP BY channel_id
                """,
                (subject_id, MESSAGE_CUTOFF_ISO),
            ).fetchall()
        return {int(row["channel_id"]): int(row["total"]) for row in rows}

    def file_rows(self, channel_id: int) -> list[dict[str, Any]]:
        """Mensajes con archivo asociado, para detectar descargas perdidas."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT message_id, file_name, file_path, file_size, mime_type
                FROM messages
                WHERE channel_id = ? AND file_path IS NOT NULL AND date >= ?
                """,
                (channel_id, MESSAGE_CUTOFF_ISO),
            ).fetchall()
        return [dict(row) for row in rows]

    def purge_messages_before(
        self, subject_id: int | None = None
    ) -> tuple[int, list[str]]:
        """Elimina del índice los mensajes anteriores al límite.

        Devuelve el número de mensajes borrados y las rutas de sus archivos
        para que quien llame pueda eliminarlos del disco.
        """
        where = "date < ?"
        parameters: list[Any] = [MESSAGE_CUTOFF_ISO]
        if subject_id is not None:
            where += " AND subject_id = ?"
            parameters.append(subject_id)

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT file_path FROM messages
                WHERE {where} AND file_path IS NOT NULL
                """,
                parameters,
            ).fetchall()
            cursor = connection.execute(
                f"DELETE FROM messages WHERE {where}", parameters
            )
            deleted = max(0, int(cursor.rowcount))

        paths = [str(row["file_path"]) for row in rows if row["file_path"]]
        return deleted, paths

    def total_messages(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM messages").fetchone()
        return int(row["total"]) if row else 0
