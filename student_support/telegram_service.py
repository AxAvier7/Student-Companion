"""Servicio de Telegram (Telethon) ejecutado en un hilo con su propio event loop."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from telethon import TelegramClient, errors, functions, types

from .config import MESSAGE_CUTOFF, MESSAGE_CUTOFF_UTC, Settings
from .database import Database
from .paths import media_filename, sanitize_component

log = logging.getLogger(__name__)

_USERNAME_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?@?([A-Za-z0-9_]{4,})/?$",
    re.IGNORECASE,
)
_AT_PATTERN = re.compile(r"^@([A-Za-z0-9_]{4,})$")
_INVITE_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)(.+)$",
    re.IGNORECASE,
)

_MEDIA_LABELS = {
    "MessageMediaGeo": "location",
    "MessageMediaGeoLive": "location",
    "MessageMediaContact": "contact",
    "MessageMediaPoll": "poll",
    "MessageMediaDice": "dice",
    "MessageMediaVenue": "location",
}


class LoginCancelled(Exception):
    """El usuario cerró un diálogo de inicio de sesión."""


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _is_outdated(moment: datetime | None) -> bool:
    """True si el mensaje es anterior al límite configurado."""
    if moment is None:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment < MESSAGE_CUTOFF


def _entity_name(entity: Any) -> str:
    if entity is None:
        return "Desconocido"

    title = getattr(entity, "title", None)
    if title:
        return str(title)

    first = getattr(entity, "first_name", None) or ""
    last = getattr(entity, "last_name", None) or ""
    full = f"{first} {last}".strip()
    if full:
        return full

    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"

    return "Desconocido"


def _friendly_error(exc: BaseException) -> str:
    if isinstance(exc, errors.ApiIdInvalidError):
        return "El api_id o el api_hash no son válidos. Revisa los datos de my.telegram.org."
    if isinstance(exc, errors.PhoneNumberInvalidError):
        return "El número de teléfono no es válido. Incluye el prefijo del país (por ejemplo +34)."
    if isinstance(exc, errors.PhoneCodeInvalidError):
        return "El código de verificación no es correcto. Inténtalo de nuevo."
    if isinstance(exc, errors.PhoneCodeExpiredError):
        return "El código de verificación ha caducado. Solicita uno nuevo."
    if isinstance(exc, errors.SessionPasswordNeededError):
        return "La cuenta tiene verificación en dos pasos."
    if isinstance(exc, errors.PasswordHashInvalidError):
        return "La contraseña de verificación en dos pasos no es correcta."
    if isinstance(exc, errors.FloodWaitError):
        return f"Telegram ha pedido esperar {exc.seconds} segundos antes de volver a intentarlo."
    if isinstance(exc, errors.AuthKeyUnregisteredError):
        return "La sesión guardada ya no es válida. Inicia sesión de nuevo."
    if isinstance(exc, errors.UserDeactivatedError):
        return "La cuenta de Telegram está desactivada."
    if isinstance(exc, (ConnectionError, asyncio.TimeoutError, OSError)):
        return "No se pudo conectar con Telegram. Comprueba tu conexión a internet."
    return str(exc) or exc.__class__.__name__


class TelegramService:
    """Puente entre la interfaz Tkinter y Telethon.

    Todas las operaciones de red se ejecutan en un hilo aparte con su propio
    event loop. Los resultados se comunican a la interfaz mediante ``post``,
    que debe ser seguro entre hilos (se usa una ``queue.Queue``).
    """

    def __init__(
        self,
        database: Database,
        settings: Settings,
        session_path: Path,
        post: Callable[[tuple[str, Any]], None],
    ) -> None:
        self.database = database
        self.settings = settings
        self.session_path = Path(session_path)
        self._post = post

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: TelegramClient | None = None
        self._ready = threading.Event()

        self._authorized = False
        self._auth_busy = False
        self._sync_running = False
        self._cancel_requested = False

        self._prompts: dict[str, concurrent.futures.Future] = {}
        self._sender_cache: dict[int, str] = {}
        self._entity_cache: dict[int, Any] = {}

    # ------------------------------------------------------------------
    # Infraestructura
    # ------------------------------------------------------------------
    @property
    def is_authorized(self) -> bool:
        return self._authorized

    @property
    def sync_running(self) -> bool:
        return self._sync_running

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop, name="telegram-event-loop", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.close()
            except Exception:
                log.exception("Error cerrando el event loop de Telegram")

    def stop(self) -> None:
        loop = self._loop
        if not loop:
            return

        try:
            future = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
            future.result(timeout=6)
        except Exception:
            log.exception("Error desconectando de Telegram")

        loop.call_soon_threadsafe(loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

    async def _shutdown(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                log.exception("Error cerrando el cliente de Telegram")
            self._client = None

    def emit(self, kind: str, payload: Any) -> None:
        try:
            self._post((kind, payload))
        except Exception:
            log.exception("No se pudo enviar el evento %s a la interfaz", kind)

    def submit(
        self,
        coroutine: Any,
        callback: Callable[[Any, Exception | None], None] | None = None,
    ) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            coroutine.close()
            raise RuntimeError("El servicio de Telegram no está iniciado.")

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)

        if callback is not None:

            def finished(done: concurrent.futures.Future) -> None:
                try:
                    result = done.result()
                except Exception as exc:  # noqa: BLE001 - se informa en la interfaz
                    self.emit("future", (callback, None, exc))
                else:
                    self.emit("future", (callback, result, None))

            future.add_done_callback(finished)

    # ------------------------------------------------------------------
    # Inicio de sesión
    # ------------------------------------------------------------------
    def connect_saved(self) -> bool:
        if self._auth_busy:
            return False
        if not self.settings.has_credentials:
            self.emit("need_login", {})
            return False

        self._auth_busy = True
        try:
            self.submit(
                self._connect_saved(
                    int(self.settings.api_id or 0),
                    self.settings.api_hash,
                )
            )
        except RuntimeError:
            self._auth_busy = False
            raise
        return True

    def login(self, api_id: int, api_hash: str, phone: str) -> bool:
        if self._auth_busy:
            return False

        self._auth_busy = True
        try:
            self.submit(self._login(api_id, api_hash, phone))
        except RuntimeError:
            self._auth_busy = False
            raise
        return True

    async def _get_client(self, api_id: int, api_hash: str) -> TelegramClient:
        if self._client is None:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            self._client = TelegramClient(
                str(self.session_path),
                api_id,
                api_hash,
                device_model="Student Support",
                system_version="Windows",
                app_version="1.0",
                lang_code="es",
                connection_retries=3,
                request_retries=3,
                timeout=25,
            )
        if not self._client.is_connected():
            await self._client.connect()
        return self._client

    async def _connect_saved(self, api_id: int, api_hash: str) -> None:
        try:
            self.emit(
                "auth_state",
                {"state": "connecting", "detail": "Conectando con Telegram…"},
            )
            client = await self._get_client(api_id, api_hash)

            if await client.is_user_authorized():
                await self._announce_login(client)
            else:
                self._authorized = False
                self.emit(
                    "auth_state",
                    {"state": "offline", "detail": "Sin sesión iniciada"},
                )
                self.emit("need_login", {"reason": "No hay una sesión guardada."})
        except Exception as exc:  # noqa: BLE001 - se informa en la interfaz
            log.exception("Error al conectar con la sesión guardada")
            self._authorized = False
            self.emit("auth_state", {"state": "offline", "detail": "Desconectado"})
            self.emit("auth_failed", {"message": _friendly_error(exc)})
        finally:
            self._auth_busy = False

    async def _login(self, api_id: int, api_hash: str, phone: str) -> None:
        try:
            self.emit(
                "auth_state",
                {"state": "connecting", "detail": "Conectando con Telegram…"},
            )
            client = await self._get_client(api_id, api_hash)

            if await client.is_user_authorized():
                await self._announce_login(client)
                return

            sent = await client.send_code_request(phone)
            code = await self._ask(
                "code",
                "Código de verificación",
                (
                    f"Telegram ha enviado un código a {phone}.\n\n"
                    "Escríbelo aquí (revisa los mensajes de Telegram, no solo SMS)."
                ),
                password=False,
            )

            if not code:
                raise LoginCancelled()

            code = re.sub(r"\s+", "", code)
            try:
                await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=sent.phone_code_hash,
                )
            except errors.SessionPasswordNeededError:
                password = await self._ask(
                    "password",
                    "Verificación en dos pasos",
                    "Tu cuenta tiene contraseña de verificación en dos pasos. Escríbela:",
                    password=True,
                )
                if not password:
                    raise LoginCancelled()
                await client.sign_in(password=password)

            await self._announce_login(client)

        except LoginCancelled:
            self._authorized = False
            self.emit(
                "auth_state",
                {"state": "offline", "detail": "Inicio de sesión cancelado"},
            )
            self.emit("login_cancelled", {})
        except Exception as exc:  # noqa: BLE001 - se informa en la interfaz
            log.exception("Error durante el inicio de sesión")
            self._authorized = False
            self.emit("auth_state", {"state": "offline", "detail": "Desconectado"})
            self.emit("auth_failed", {"message": _friendly_error(exc)})
        finally:
            self._auth_busy = False

    async def _announce_login(self, client: TelegramClient) -> None:
        me = await client.get_me()
        self._authorized = True
        self.emit(
            "auth_ok",
            {
                "id": getattr(me, "id", None),
                "name": _entity_name(me),
                "username": getattr(me, "username", None),
                "phone": getattr(me, "phone", None),
            },
        )

    async def _ask(
        self, key: str, title: str, message: str, password: bool = False
    ) -> str | None:
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._prompts[key] = future
        self.emit(
            "prompt",
            {
                "key": key,
                "title": title,
                "message": message,
                "password": password,
            },
        )
        try:
            value = await asyncio.wrap_future(future)
        finally:
            self._prompts.pop(key, None)
        return value

    def resolve_prompt(self, key: str, value: str | None) -> None:
        future = self._prompts.get(key)
        if future is not None and not future.done():
            future.set_result(value)

    def logout(self) -> None:
        self.submit(self._logout())

    async def _logout(self) -> None:
        client = self._client
        if client is not None:
            try:
                await client.log_out()
            except Exception:
                log.exception("Error cerrando la sesión de Telegram")
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self._client = None

        self._authorized = False
        self._sender_cache.clear()
        self._entity_cache.clear()
        self.emit("auth_state", {"state": "offline", "detail": "Sesión cerrada"})
        self.emit("logged_out", {})

    # ------------------------------------------------------------------
    # Búsqueda de canales
    # ------------------------------------------------------------------
    async def search_channels(self, query: str) -> list[dict[str, Any]]:
        client = self._client
        if client is None or not self._authorized:
            raise RuntimeError("No has iniciado sesión en Telegram.")

        text = (query or "").strip()
        if len(text) < 2:
            raise ValueError("Escribe al menos dos caracteres para buscar.")

        invite = _INVITE_PATTERN.match(text)
        if invite:
            raise ValueError(
                "Los enlaces de invitación privados no se pueden buscar sin unirte. "
                "Prueba con el nombre del grupo o con su @usuario."
            )

        direct = _USERNAME_PATTERN.match(text) or _AT_PATTERN.match(text)
        if direct:
            username = direct.group(1)
            entity = await client.get_entity(username)
            peer = self._entity_to_peer(entity, "Enlace directo")
            if peer is None:
                raise ValueError("Ese enlace no corresponde a un canal o grupo.")
            return [peer]

        normalized_query = _normalize(text)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        candidates: list[tuple[Any, str]] = []

        try:
            dialogs = await client.get_dialogs(limit=500)
        except Exception:
            log.exception("No se pudieron listar los chats")
            dialogs = []

        for dialog in dialogs:
            title = _normalize(getattr(dialog, "name", "") or "")
            username = _normalize(getattr(dialog.entity, "username", "") or "")
            if normalized_query in title or (username and normalized_query in username):
                candidates.append((dialog.entity, "Mis chats"))

        for entity, source in candidates:
            peer = self._entity_to_peer(entity, source)
            if peer is None:
                continue
            key = f"{peer['peer_type']}:{peer['id']}"
            if key in seen:
                continue
            seen.add(key)
            results.append(peer)

        if len(results) < 15:
            try:
                found = await client(
                    functions.contacts.SearchRequest(q=text, limit=25)
                )
            except errors.FloodWaitError:
                raise
            except Exception:
                log.exception("Falló la búsqueda global de canales")
                found = None

            if found is not None:
                for entity in list(found.chats) + list(found.users):
                    peer = self._entity_to_peer(entity, "Búsqueda global")
                    if peer is None:
                        continue
                    key = f"{peer['peer_type']}:{peer['id']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(peer)

        results.sort(key=lambda item: (item["source"] != "Mis chats", item["title"].casefold()))
        return results[:40]

    @staticmethod
    def _entity_to_peer(entity: Any, source: str) -> dict[str, Any] | None:
        if isinstance(entity, types.ChannelForbidden):
            return None
        if not isinstance(entity, (types.Channel, types.Chat)):
            return None
        if getattr(entity, "deactivated", False):
            return None
        if getattr(entity, "left", False):
            return None
        if entity.__class__.__name__ == "ChatForbidden":
            return None

        peer_type = "channel" if isinstance(entity, types.Channel) else "chat"
        return {
            "id": int(entity.id),
            "access_hash": getattr(entity, "access_hash", None),
            "peer_type": peer_type,
            "title": _entity_name(entity),
            "username": getattr(entity, "username", None),
            "members": getattr(entity, "participants_count", None),
            "source": source,
        }

    # ------------------------------------------------------------------
    # Sincronización
    # ------------------------------------------------------------------
    def start_sync(self, subject_id: int | None = None) -> bool:
        if self._sync_running:
            return False
        if not self._authorized:
            raise RuntimeError("No has iniciado sesión en Telegram.")

        self._sync_running = True
        self._cancel_requested = False
        try:
            self.submit(self._sync_impl(subject_id))
        except RuntimeError:
            self._sync_running = False
            raise
        return True

    def cancel_sync(self) -> None:
        self._cancel_requested = True

    async def _sync_impl(self, subject_id: int | None) -> None:
        started = time.monotonic()
        summary = {
            "channels": 0,
            "new_messages": 0,
            "repaired": 0,
            "errors": 0,
            "cancelled": False,
            "seconds": 0.0,
            "message": "",
        }

        try:
            channels = self.database.channels(subject_id)
            summary["total_channels"] = len(channels)
            self.emit(
                "sync_started",
                {
                    "subject_id": subject_id,
                    "total_channels": len(channels),
                },
            )

            if not channels:
                summary["message"] = (
                    "No hay canales que sincronizar. Añade canales a la asignatura."
                )
                return

            for index, channel in enumerate(channels, start=1):
                if self._cancel_requested:
                    summary["cancelled"] = True
                    break

                try:
                    result = await self._sync_channel(channel, index, len(channels))
                except Exception as exc:  # noqa: BLE001 - un canal no debe romper el resto
                    log.exception("Error sincronizando el canal %s", channel.get("title"))
                    summary["errors"] += 1
                    self.emit(
                        "sync_channel_error",
                        {
                            "channel_id": channel["id"],
                            "subject_id": channel["subject_id"],
                            "title": channel["title"],
                            "message": _friendly_error(exc),
                        },
                    )
                    continue

                summary["channels"] += 1
                summary["new_messages"] += result["new_messages"]
                summary["repaired"] += result.get("repaired", 0)
                summary["errors"] += result["errors"]

                self.emit(
                    "sync_channel_finished",
                    {
                        "channel_id": channel["id"],
                        "subject_id": channel["subject_id"],
                        "title": channel["title"],
                        "index": index,
                        "total_channels": len(channels),
                        "new_messages": result["new_messages"],
                        "repaired": result.get("repaired", 0),
                        "errors": result["errors"],
                        "processed": result["processed"],
                        "cancelled": result["cancelled"],
                    },
                )

                if result["cancelled"]:
                    summary["cancelled"] = True
                    break

        except Exception as exc:  # noqa: BLE001 - se informa en la interfaz
            log.exception("Error general durante la sincronización")
            summary["errors"] += 1
            self.emit("sync_error", {"message": _friendly_error(exc)})
        finally:
            self._sync_running = False
            summary["seconds"] = round(time.monotonic() - started, 1)
            self.emit("sync_finished", summary)

    async def _resolve_entity(self, channel: dict[str, Any]) -> Any:
        channel_id = int(channel["id"])
        cached = self._entity_cache.get(channel_id)
        if cached is not None:
            return cached

        client = self._client
        assert client is not None

        entity = None
        username = channel.get("username")
        if username:
            try:
                entity = await client.get_entity(username)
            except Exception:
                log.debug("No se pudo resolver @%s", username)

        if entity is None:
            peer_type = channel.get("peer_type") or "channel"
            if peer_type == "channel" and channel.get("access_hash") is not None:
                entity = types.InputPeerChannel(
                    channel_id=channel_id,
                    access_hash=int(channel["access_hash"]),
                )
            elif peer_type == "chat":
                entity = types.InputPeerChat(chat_id=channel_id)
            else:
                entity = await client.get_entity(channel_id)

        self._entity_cache[channel_id] = entity
        return entity

    async def _sync_channel(
        self, channel: dict[str, Any], index: int, total_channels: int
    ) -> dict[str, int | bool]:
        client = self._client
        if client is None:
            raise RuntimeError("Sin conexión con Telegram.")

        channel_id = int(channel["id"])
        subject_id = int(channel["subject_id"])
        entity = await self._resolve_entity(channel)

        total_messages = 0
        try:
            probe = await client.get_messages(entity, limit=0)
            total_messages = int(getattr(probe, "total", 0) or 0)
        except Exception:
            log.debug("No se pudo obtener el total de mensajes", exc_info=True)

        resolved_title = _entity_name(entity)
        if resolved_title == "Desconocido":
            resolved_title = channel.get("title") or "Canal"
        resolved_username = getattr(entity, "username", None) or channel.get("username")
        if (
            resolved_title != channel.get("title")
            or resolved_username != channel.get("username")
        ):
            try:
                self.database.update_channel_meta(
                    channel_id, resolved_title, resolved_username
                )
            except Exception:
                log.exception("No se pudo actualizar el título del canal")

        self.emit(
            "sync_channel_started",
            {
                "channel_id": channel_id,
                "subject_id": subject_id,
                "title": resolved_title,
                "index": index,
                "total_channels": total_channels,
                "total_messages": total_messages,
            },
        )

        subject_folder = channel.get("subject_folder") or channel.get("subject_name") or "Asignatura"
        channel_folder = channel.get("folder_name") or resolved_title
        destination = (
            self.settings.download_path()
            / sanitize_component(str(subject_folder), "Asignatura")
            / sanitize_component(str(channel_folder), "Canal")
        )

        last_synced_id = int(channel.get("last_synced_id") or 0)
        max_seen_id = last_synced_id

        processed = 0
        new_messages = 0
        error_count = 0
        cancelled = False
        last_progress = 0.0

        repaired, repair_errors = await self._repair_missing_files(
            entity,
            channel=channel,
            destination=destination,
            subject_id=subject_id,
            channel_id=channel_id,
        )
        error_count += repair_errors

        offset_date = (
            MESSAGE_CUTOFF_UTC - timedelta(seconds=1) if last_synced_id == 0 else None
        )

        async for message in client.iter_messages(
            entity,
            min_id=last_synced_id,
            reverse=True,
            wait_time=0,
            offset_date=offset_date,
        ):
            if self._cancel_requested:
                cancelled = True
                break

            message_id = int(message.id)

            if _is_outdated(getattr(message, "date", None)):
                continue

            if message_id > max_seen_id:
                max_seen_id = message_id

            if getattr(message, "action", None) is not None:
                continue

            processed += 1

            try:
                added = await self._store_message(
                    message,
                    channel=channel,
                    entity=entity,
                    destination=destination,
                    subject_id=subject_id,
                    channel_id=channel_id,
                )
                if added:
                    new_messages += 1
            except Exception:
                log.exception(
                    "Error guardando el mensaje %s del canal %s",
                    message_id,
                    resolved_title,
                )
                error_count += 1

            now = time.monotonic()
            if now - last_progress >= 0.4:
                last_progress = now
                self.emit(
                    "sync_progress",
                    {
                        "channel_id": channel_id,
                        "subject_id": subject_id,
                        "title": resolved_title,
                        "index": index,
                        "total_channels": total_channels,
                        "processed": processed,
                        "new_messages": new_messages,
                        "errors": error_count,
                        "total_messages": total_messages,
                    },
                )

        try:
            self.database.set_channel_synced(channel_id, max_seen_id)
        except Exception:
            log.exception("No se pudo guardar el estado de sincronización")

        return {
            "processed": processed,
            "new_messages": new_messages,
            "repaired": repaired,
            "errors": error_count,
            "cancelled": cancelled,
        }

    async def _repair_missing_files(
        self,
        entity: Any,
        *,
        channel: dict[str, Any],
        destination: Path,
        subject_id: int,
        channel_id: int,
    ) -> tuple[int, int]:
        """Vuelve a descargar archivos indexados que ya no están en disco."""
        client = self._client
        if client is None:
            return 0, 0

        try:
            rows = self.database.file_rows(channel_id)
        except Exception:
            log.exception("No se pudo comprobar los archivos descargados")
            return 0, 0

        missing = [
            row for row in rows if not (row.get("file_path") and Path(row["file_path"]).exists())
        ]
        if not missing:
            return 0, 0

        self.emit(
            "sync_repair",
            {
                "channel_id": channel_id,
                "subject_id": subject_id,
                "title": channel.get("title") or "Canal",
                "missing": len(missing),
            },
        )

        repaired = 0
        errors = 0

        for start in range(0, len(missing), 100):
            if self._cancel_requested:
                break

            chunk = missing[start : start + 100]
            ids = [int(row["message_id"]) for row in chunk]
            try:
                fetched = await client.get_messages(entity, ids=ids)
            except Exception:
                log.exception("No se pudieron recuperar mensajes para reparar archivos")
                errors += len(chunk)
                continue

            if fetched is None:
                continue
            if not isinstance(fetched, list):
                fetched = [fetched]

            for message in fetched:
                if message is None or getattr(message, "action", None) is not None:
                    continue
                try:
                    await self._store_message(
                        message,
                        channel=channel,
                        entity=entity,
                        destination=destination,
                        subject_id=subject_id,
                        channel_id=channel_id,
                    )
                    expected = next(
                        (
                            row["file_path"]
                            for row in chunk
                            if int(row["message_id"]) == int(message.id)
                        ),
                        None,
                    )
                    if expected and Path(expected).exists():
                        repaired += 1
                    else:
                        errors += 1
                except Exception:
                    log.exception("Error reparando el archivo del mensaje %s", message.id)
                    errors += 1

        return repaired, errors

    async def _store_message(
        self,
        message: Any,
        *,
        channel: dict[str, Any],
        entity: Any,
        destination: Path,
        subject_id: int,
        channel_id: int,
    ) -> bool:
        sent_at = getattr(message, "date", None) or datetime.now(timezone.utc)
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        if sent_at < MESSAGE_CUTOFF:
            return False

        media = self._describe_media(message)
        has_file = bool(media.get("has_file"))

        existing = self.database.get_message(channel_id, int(message.id))
        if existing is not None:
            if not has_file:
                return False
            existing_path = existing.get("file_path")
            if existing_path and Path(existing_path).exists():
                return False

        sender_name = await self._sender_name(message)
        local_date = sent_at.astimezone()
        text = getattr(message, "message", None) or ""
        post_author = getattr(message, "post_author", None) or None

        file_path: str | None = None
        file_name: str | None = None
        file_size = media.get("size")
        mime_type = media.get("mime_type")

        if has_file:
            destination.mkdir(parents=True, exist_ok=True)
            file_name = media_filename(
                local_date,
                int(message.id),
                media.get("file_name"),
                media.get("kind"),
                mime_type,
            )
            target = destination / file_name
            downloaded = await self._download(
                message, target, file_name, expected_size=file_size
            )
            if downloaded is not None:
                file_path = str(downloaded)
                file_name = downloaded.name
            else:
                file_name = None

        permalink = None
        username = getattr(entity, "username", None) or channel.get("username")
        if username:
            permalink = f"https://t.me/{username}/{message.id}"
        elif channel.get("peer_type") == "channel":
            permalink = f"https://t.me/c/{channel_id}/{message.id}"

        record = {
            "channel_id": channel_id,
            "message_id": int(message.id),
            "subject_id": subject_id,
            "date": sent_at.astimezone(timezone.utc).isoformat(),
            "sender_id": getattr(message, "sender_id", None),
            "sender_name": sender_name,
            "text": text,
            "media_type": media.get("kind"),
            "file_name": file_name,
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "grouped_id": getattr(message, "grouped_id", None),
            "post_author": post_author,
            "permalink": permalink,
        }

        if existing is not None:
            if file_path:
                self.database.update_message_file(
                    channel_id, int(message.id), file_path, file_name
                )
            return False

        return self.database.insert_message(record)

    async def _download(
        self,
        message: Any,
        target: Path,
        display_name: str,
        expected_size: int | None = None,
    ) -> Path | None:
        client = self._client
        if client is None:
            return None

        # Reutiliza el archivo si ya existe y su tamaño coincide: evita
        # volver a descargar tras reconstruir el índice.
        if target.exists() and expected_size:
            try:
                if target.stat().st_size == int(expected_size):
                    return target
            except OSError:
                pass

        state = {"last": 0.0}

        def progress(received: int, total: int) -> None:
            now = time.monotonic()
            if now - state["last"] < 0.5 and (not total or received < total):
                return
            state["last"] = now
            self.emit(
                "download_progress",
                {
                    "file_name": display_name,
                    "received": received,
                    "total": total,
                },
            )

        try:
            result = await client.download_media(
                message, file=str(target), progress_callback=progress
            )
        except Exception:
            log.exception("No se pudo descargar %s", display_name)
            return None

        if not result:
            return None

        downloaded = Path(result)
        return downloaded if downloaded.exists() else None

    async def _sender_name(self, message: Any) -> str:
        post_author = getattr(message, "post_author", None)
        if post_author:
            return str(post_author)

        sender_id = getattr(message, "sender_id", None)
        if sender_id is None:
            return "Desconocido"

        cached = self._sender_cache.get(int(sender_id))
        if cached:
            return cached

        sender = getattr(message, "sender", None)
        if sender is None:
            try:
                sender = await message.get_sender()
            except Exception:
                sender = None

        name = _entity_name(sender) if sender is not None else f"ID {sender_id}"
        self._sender_cache[int(sender_id)] = name
        return name

    @staticmethod
    def _describe_media(message: Any) -> dict[str, Any]:
        photo = getattr(message, "photo", None)
        if photo is not None:
            size = 0
            for candidate in getattr(photo, "sizes", []) or []:
                candidate_size = getattr(candidate, "size", 0) or 0
                if not candidate_size:
                    progressive = getattr(candidate, "sizes", None)
                    if isinstance(progressive, (list, tuple)):
                        numeric = [int(item) for item in progressive if isinstance(item, int)]
                        if numeric:
                            candidate_size = max(numeric)
                if candidate_size > size:
                    size = candidate_size
            return {
                "kind": "photo",
                "file_name": None,
                "mime_type": "image/jpeg",
                "size": size or None,
                "has_file": True,
            }

        document = getattr(message, "document", None)
        if document is not None:
            mime_type = getattr(document, "mime_type", None)
            file_name: str | None = None
            kind = "document"

            attributes = getattr(document, "attributes", []) or []
            audio_attribute = None
            has_sticker = False
            has_animated = False
            has_video = False
            video_is_round = False

            for attribute in attributes:
                if isinstance(attribute, types.DocumentAttributeFilename):
                    if attribute.file_name:
                        file_name = attribute.file_name
                elif isinstance(attribute, types.DocumentAttributeAudio):
                    audio_attribute = attribute
                elif isinstance(attribute, types.DocumentAttributeSticker):
                    has_sticker = True
                elif isinstance(attribute, types.DocumentAttributeAnimated):
                    has_animated = True
                elif isinstance(attribute, types.DocumentAttributeVideo):
                    has_video = True
                    video_is_round = bool(
                        getattr(attribute, "round_message", False)
                    )

            if has_sticker:
                kind = "sticker"
            elif has_animated:
                kind = "gif"
            elif audio_attribute is not None:
                kind = "voice" if getattr(audio_attribute, "voice", False) else "audio"
                if not file_name:
                    title = getattr(audio_attribute, "title", None)
                    performer = getattr(audio_attribute, "performer", None)
                    if title and performer:
                        file_name = f"{performer} - {title}"
                    elif title:
                        file_name = str(title)
            elif has_video:
                kind = "video_note" if video_is_round else "video"

            return {
                "kind": kind,
                "file_name": file_name,
                "mime_type": mime_type,
                "size": getattr(document, "size", None),
                "has_file": True,
            }

        media_object = getattr(message, "media", None)
        if media_object is not None:
            kind = _MEDIA_LABELS.get(type(media_object).__name__)
            if kind:
                return {
                    "kind": kind,
                    "file_name": None,
                    "mime_type": None,
                    "size": None,
                    "has_file": False,
                }

        return {
            "kind": None,
            "file_name": None,
            "mime_type": None,
            "size": None,
            "has_file": False,
        }
