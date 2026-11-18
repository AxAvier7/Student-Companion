"""Ventana principal de Student Support."""

from __future__ import annotations

import logging
import queue
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

from ..config import (
    DATA_DIR,
    DATABASE_PATH,
    ICON_PATH,
    ICON_PNG_PATH,
    LOG_PATH,
    MESSAGE_CUTOFF_LABEL,
    SESSION_PATH,
    Settings,
)
from ..database import Database, sender_key
from ..telegram_service import TelegramService
from .dialogs import ChannelBrowserDialog, LoginDialog, TeacherDialog, ask_text
from .utils import (
    center_window,
    compact_text,
    format_datetime,
    format_size,
    media_label,
    open_path,
    open_url,
    table_media_label,
)

log = logging.getLogger(__name__)

APP_VERSION = "1.0"
TITLE_FONT = ("Segoe UI Semibold", 19)
SUBTITLE_FONT = ("Segoe UI", 9)
SECTION_FONT = ("Segoe UI Semibold", 10)
BODY_FONT = ("Segoe UI", 10)
SMALL_FONT = ("Segoe UI", 9)
TREE_FONT = ("Segoe UI", 9)

TYPE_FILTERS = {
    "Todos": "all",
    "Documentos": "document",
    "Imágenes": "image",
    "Vídeos": "video",
    "Audio": "audio",
    "Texto": "text",
    "Enlaces": "link",
    "Otros": "other",
}


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.settings = Settings.load()
        self.db = Database(DATABASE_PATH)
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        self.tabs: dict[int, SubjectTab] = {}
        self._sync_active = False
        self._authorized = False
        self._closing = False
        self._login_dialog: LoginDialog | None = None
        self._account_name = ""

        self.title("Student Support · Contenido de Telegram")
        self.geometry("1280x800")
        self.minsize(1000, 640)
        self._set_window_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.report_callback_exception = self._report_callback_exception

        self._configure_style()
        self._build_menu()
        self._build_header()
        self._build_content()
        self._build_statusbar()

        self._purge_outdated_messages()

        self.service = TelegramService(
            self.db, self.settings, SESSION_PATH, self.queue.put
        )
        self.service.start()

        self.reload_subjects()
        self._update_account("Sin conexión", "#b3261e")

        self.after(100, self._poll)
        self.after(350, self._startup_connection)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _set_window_icon(self) -> None:
        try:
            if ICON_PATH.exists():
                self.iconbitmap(default=str(ICON_PATH))
        except tk.TclError:
            log.debug("No se pudo aplicar el icono .ico", exc_info=True)
        try:
            if ICON_PNG_PATH.exists():
                self._icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH))
                self.iconphoto(True, self._icon_image)
        except tk.TclError:
            log.debug("No se pudo aplicar el icono PNG", exc_info=True)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=23, font=TREE_FONT)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))
        style.configure("TLabelframe.Label", font=SECTION_FONT)
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 9),
            padding=(14, 6),
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Nueva asignatura…",
            accelerator="Ctrl+N",
            command=self.add_subject,
        )
        file_menu.add_command(
            label="Abrir carpeta de descargas",
            command=self.open_downloads_root,
        )
        file_menu.add_command(
            label="Cambiar carpeta de descargas…",
            command=self.change_downloads_dir,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Salir", accelerator="Ctrl+Q", command=self._on_close)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        telegram_menu = tk.Menu(menubar, tearoff=0)
        telegram_menu.add_command(
            label="Iniciar sesión…",
            command=self.show_login,
        )
        telegram_menu.add_command(
            label="Sincronizar todo",
            accelerator="F5",
            command=lambda: self.start_sync(None),
        )
        telegram_menu.add_command(
            label="Cancelar sincronización",
            command=self.cancel_sync,
        )
        telegram_menu.add_separator()
        telegram_menu.add_command(
            label="Cerrar sesión de Telegram",
            command=self.logout,
        )
        menubar.add_cascade(label="Telegram", menu=telegram_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Cómo funciona", command=self.show_help)
        help_menu.add_command(label="Acerca de", command=self.show_about)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        self.config(menu=menubar)
        self.bind_all("<Control-n>", lambda _event: self.add_subject())
        self.bind_all("<Control-q>", lambda _event: self._on_close())
        self.bind_all("<F5>", lambda _event: self.start_sync(None))

    def _build_header(self) -> None:
        header = ttk.Frame(self, padding=(16, 12, 16, 10))
        header.pack(fill="x")

        titles = ttk.Frame(header)
        titles.pack(side="left", anchor="w")
        tk.Label(
            titles,
            text="Student Support",
            font=TITLE_FONT,
            foreground="#1d2733",
        ).pack(anchor="w")
        self.account_label = tk.Label(
            titles,
            text="● Sin conexión",
            font=SUBTITLE_FONT,
            foreground="#b3261e",
        )
        self.account_label.pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header)
        actions.pack(side="right", anchor="e")

        ttk.Button(
            actions, text="Nueva asignatura", command=self.add_subject
        ).pack(side="left", padx=(0, 6))
        self.sync_all_button = ttk.Button(
            actions,
            text="Sincronizar todo",
            command=lambda: self.start_sync(None),
        )
        self.sync_all_button.pack(side="left", padx=(0, 6))
        ttk.Button(
            actions, text="Abrir descargas", command=self.open_downloads_root
        ).pack(side="left", padx=(0, 6))

        self.login_button = ttk.Button(
            actions, text="Iniciar sesión", command=self.show_login
        )
        self.login_button.pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

    def _build_content(self) -> None:
        self.content = ttk.Frame(self, padding=(12, 10, 12, 10))
        self.content.pack(fill="both", expand=True)
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.content)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.empty_frame = ttk.Frame(self.content)
        self.empty_frame.grid(row=0, column=0, sticky="nsew")
        inner = ttk.Frame(self.empty_frame)
        inner.place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(
            inner,
            text="Todavía no hay asignaturas",
            font=("Segoe UI Semibold", 17),
            foreground="#39424f",
        ).pack()
        ttk.Label(
            inner,
            text=(
                "Crea una asignatura, busca sus canales o grupos de Telegram\n"
                "y descarga su contenido desde el 01/08/2026 en tu ordenador."
            ),
            font=BODY_FONT,
            justify="center",
            foreground="#5b6572",
        ).pack(pady=(8, 16))
        ttk.Button(
            inner, text="Crear la primera asignatura", command=self.add_subject
        ).pack()

    def _build_statusbar(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill="x")
        status = ttk.Frame(self, padding=(14, 7))
        status.pack(fill="x")
        status.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Listo")
        ttk.Label(
            status, textvariable=self.status_var, font=SMALL_FONT, foreground="#39424f"
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            status,
            text=f"Solo mensajes desde el {MESSAGE_CUTOFF_LABEL}",
            font=SMALL_FONT,
            foreground="#7b8694",
        ).grid(row=0, column=1, sticky="e", padx=(8, 12))

        self.progress = ttk.Progressbar(
            status, orient="horizontal", mode="determinate", length=230, maximum=1
        )
        self.cancel_button = ttk.Button(
            status, text="Cancelar", command=self.cancel_sync
        )
        self.progress.grid(row=0, column=2, sticky="e", padx=(8, 8))
        self.cancel_button.grid(row=0, column=3, sticky="e")
        self.progress.grid_remove()
        self.cancel_button.grid_remove()

    # ------------------------------------------------------------------
    # Estado general
    # ------------------------------------------------------------------
    def _purge_outdated_messages(self) -> None:
        """Borra del índice y del disco lo anterior al límite configurado."""
        try:
            deleted, paths = self.db.purge_messages_before()
        except Exception:
            log.exception("No se pudieron eliminar los mensajes anteriores al límite")
            return

        removed_files = 0
        for raw in paths:
            try:
                Path(raw).unlink(missing_ok=True)
                removed_files += 1
            except OSError:
                log.exception("No se pudo borrar el archivo antiguo %s", raw)

        if deleted or removed_files:
            log.info(
                "Limpieza inicial: %s mensajes y %s archivos anteriores al %s",
                deleted,
                removed_files,
                MESSAGE_CUTOFF_LABEL,
            )
            self._set_status(
                f"Eliminados {deleted} mensajes y {removed_files} archivos "
                f"anteriores al {MESSAGE_CUTOFF_LABEL}."
            )
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _update_account(self, text: str, color: str) -> None:
        self.account_label.configure(text=f"● {text}", foreground=color)

    def _show_login_button(self, visible: bool) -> None:
        if visible:
            if not self.login_button.winfo_ismapped():
                self.login_button.pack(side="left")
        else:
            self.login_button.pack_forget()

    def _set_progress_visible(self, visible: bool) -> None:
        if visible:
            self.progress.grid()
            self.cancel_button.grid()
        else:
            self.progress.grid_remove()
            self.cancel_button.grid_remove()

    def _set_sync_ui(self, active: bool) -> None:
        self._sync_active = active
        if active:
            self.sync_all_button.state(["disabled"])
        else:
            self.sync_all_button.state(["!disabled"])

        for tab in self.tabs.values():
            tab.set_syncing(active)

    def _startup_connection(self) -> None:
        if self.settings.has_credentials:
            try:
                self.service.connect_saved()
            except RuntimeError as exc:
                self._show_error(str(exc))
        else:
            self.show_login()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                try:
                    self._handle_event(kind, payload)
                except Exception:
                    log.exception("Error procesando el evento %s", kind)
        except queue.Empty:
            pass

        if not self._closing:
            self.after(80, self._poll)

    # ------------------------------------------------------------------
    # Eventos del servicio
    # ------------------------------------------------------------------
    def _handle_event(self, kind: str, payload: Any) -> None:
        if kind == "auth_state":
            state = payload.get("state")
            detail = payload.get("detail") or "Desconectado"
            if state == "connecting":
                self._update_account(detail, "#9a6700")
            elif state == "offline":
                self._update_account(detail, "#b3261e")
                self._authorized = False
                self._show_login_button(True)
            return

        if kind == "auth_ok":
            self._authorized = True
            name = payload.get("name") or "cuenta de Telegram"
            username = payload.get("username")
            self._account_name = name
            suffix = f" (@{username})" if username else ""
            self._update_account(f'Conectado como {name}{suffix}', "#1a7f37")
            self._show_login_button(False)
            self._set_status("Conectado a Telegram. Todo listo para sincronizar.")
            return

        if kind == "auth_failed":
            self._authorized = False
            self._update_account("Sin conexión", "#b3261e")
            self._show_login_button(True)
            self._show_error(payload.get("message") or "No se pudo conectar.")
            return

        if kind == "need_login":
            if not self._authorized:
                self.show_login()
            return

        if kind == "login_cancelled":
            self._set_status("Inicio de sesión cancelado.")
            return

        if kind == "logged_out":
            self._authorized = False
            self._update_account("Sin conexión", "#b3261e")
            self._show_login_button(True)
            self._set_status("Has cerrado la sesión de Telegram. Tus descargas siguen disponibles.")
            return

        if kind == "prompt":
            value = ask_text(
                self,
                payload.get("title") or "Telegram",
                payload.get("message") or "",
                password=bool(payload.get("password")),
            )
            self.service.resolve_prompt(payload.get("key") or "", value)
            return

        if kind == "future":
            callback, result, error = payload
            try:
                callback(result, error)
            except Exception:
                log.exception("Error en una respuesta asíncrona")
            return

        if kind == "sync_started":
            total = int(payload.get("total_channels") or 0)
            self._set_sync_ui(True)
            self._set_progress_visible(True)
            self.progress.configure(maximum=max(1, total), value=0)
            self._set_status(f"Sincronizando {total} canal(es)…")
            return

        if kind == "sync_channel_started":
            index = int(payload.get("index") or 0)
            total = int(payload.get("total_channels") or 0)
            self.progress.configure(maximum=max(1, total), value=max(0, index - 1))
            title = payload.get("title") or ""
            messages = int(payload.get("total_messages") or 0)
            self._set_status(
                f"[{index}/{total}] {title} · {messages} mensajes en el canal"
            )
            return

        if kind == "sync_progress":
            index = int(payload.get("index") or 0)
            total = int(payload.get("total_channels") or 0)
            self.progress.configure(maximum=max(1, total), value=max(0, index - 1))
            title = payload.get("title") or ""
            processed = int(payload.get("processed") or 0)
            new_messages = int(payload.get("new_messages") or 0)
            self._set_status(
                f"[{index}/{total}] {title} · {processed} procesados, "
                f"{new_messages} nuevos"
            )
            return

        if kind == "download_progress":
            name = compact_text(payload.get("file_name") or "", 52)
            received = int(payload.get("received") or 0)
            total = int(payload.get("total") or 0)
            if total:
                percent = min(100, int(received * 100 / total))
                self._set_status(f"Descargando {name} · {percent}%")
            else:
                self._set_status(f"Descargando {name}…")
            return

        if kind == "sync_channel_finished":
            index = int(payload.get("index") or 0)
            total = int(payload.get("total_channels") or 0)
            self.progress.configure(maximum=max(1, total), value=index)
            title = payload.get("title") or ""
            new_messages = int(payload.get("new_messages") or 0)
            repaired = int(payload.get("repaired") or 0)
            errors = int(payload.get("errors") or 0)
            message = f"[{index}/{total}] {title}: {new_messages} nuevos"
            if repaired:
                message += f", {repaired} recuperados"
            if errors:
                message += f", {errors} errores"
            self._set_status(message)
            self._refresh_subject(int(payload.get("subject_id") or 0), full=True)
            return

        if kind == "sync_repair":
            self._set_status(
                f"«{payload.get('title')}»: recuperando "
                f"{payload.get('missing')} archivo(s) que faltaban en disco…"
            )
            return

        if kind == "sync_channel_error":
            self._set_status(
                f"Error en «{payload.get('title')}»: {payload.get('message')}"
            )
            return

        if kind == "sync_error":
            self._set_sync_ui(False)
            self._set_progress_visible(False)
            self._show_error(payload.get("message") or "Error sincronizando.")
            return

        if kind == "sync_finished":
            self._set_sync_ui(False)
            self._set_progress_visible(False)
            cancelled = bool(payload.get("cancelled"))
            new_messages = int(payload.get("new_messages") or 0)
            repaired = int(payload.get("repaired") or 0)
            errors = int(payload.get("errors") or 0)
            seconds = payload.get("seconds") or 0
            custom = payload.get("message") or ""

            if cancelled:
                self._set_status(
                    f"Sincronización cancelada · {new_messages} mensajes nuevos"
                )
            elif custom:
                self._set_status(custom)
            else:
                detail = f"{new_messages} mensajes nuevos"
                if repaired:
                    detail += f" · {repaired} archivos recuperados"
                detail += f" · {errors} errores"
                self._set_status(
                    f"Sincronización completada en {seconds} s · {detail}"
                )

            self._refresh_all_tabs()
            if errors and not cancelled:
                messagebox.showwarning(
                    "Sincronización con incidencias",
                    f"{errors} mensaje(s) o canal(es) no se pudieron procesar. "
                    "Consulta data/student_support.log para más detalles.",
                    parent=self,
                )
            return

    # ------------------------------------------------------------------
    # Asignaturas
    # ------------------------------------------------------------------
    def reload_subjects(self, select_id: int | None = None) -> None:
        current_id = select_id if select_id is not None else self.current_subject_id()

        for tab in list(self.tabs.values()):
            tab.destroy()
        self.tabs.clear()

        subjects = self.db.subjects()
        for subject in subjects:
            tab = SubjectTab(self.notebook, self, subject)
            self.tabs[int(subject["id"])] = tab
            self.notebook.add(tab, text=subject["name"])

        if subjects:
            self.notebook.grid()
            self.empty_frame.grid_remove()
            target = self.tabs.get(current_id) if current_id is not None else None
            if target is None:
                target = self.tabs[int(subjects[0]["id"])]
            self.notebook.select(target)
        else:
            self.notebook.grid_remove()
            self.empty_frame.grid()

    def current_subject_id(self) -> int | None:
        try:
            selected = self.notebook.select()
        except tk.TclError:
            return None
        if not selected:
            return None

        widget = self.nametowidget(selected)
        for subject_id, tab in self.tabs.items():
            if tab is widget:
                return subject_id
        return None

    def _refresh_subject(self, subject_id: int, *, full: bool = False) -> None:
        tab = self.tabs.get(subject_id)
        if tab is None:
            return
        if full:
            tab.refresh_all()
        else:
            tab.refresh_channels()

    def _refresh_all_tabs(self) -> None:
        current = self.current_subject_id()
        for subject_id, tab in self.tabs.items():
            tab.refresh_channels()
            if subject_id == current:
                tab.refresh_messages()

    def add_subject(self) -> None:
        if not self._ensure_online():
            return

        dialog = ChannelBrowserDialog(self, self._search_channels, mode="subject")
        self.wait_window(dialog)
        if not dialog.result:
            return

        name = dialog.result["name"]
        peers = dialog.result["channels"]

        try:
            subject_id = self.db.add_subject(name)
        except sqlite3.IntegrityError:
            self._show_error(f"Ya existe una asignatura llamada «{name}».")
            return
        except ValueError as exc:
            self._show_error(str(exc))
            return

        added = 0
        errors: list[str] = []
        for peer in peers:
            try:
                if self.db.add_channel(subject_id, peer):
                    added += 1
            except ValueError as exc:
                errors.append(str(exc))

        self.reload_subjects(subject_id)
        self._set_status(
            f"Asignatura «{name}» creada" + (f" con {added} canal(es)." if added else ".")
        )

        if errors:
            messagebox.showwarning(
                "Algunos canales no se añadieron",
                "\n".join(errors[:8]),
                parent=self,
            )

        if added and messagebox.askyesno(
            "Descargar contenido",
            f"¿Quieres descargar ahora el contenido de «{name}» "
            f"publicado desde el {MESSAGE_CUTOFF_LABEL}?",
            parent=self,
        ):
            self.start_sync(subject_id)

    def add_channels(self, subject: dict[str, Any]) -> None:
        if not self._ensure_online():
            return

        existing = {int(channel["id"]) for channel in self.db.channels(subject["id"])}
        dialog = ChannelBrowserDialog(
            self,
            self._search_channels,
            mode="channels",
            subject_name=subject["name"],
            exclude_ids=existing,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        added = 0
        errors: list[str] = []
        for peer in dialog.result["channels"]:
            try:
                if self.db.add_channel(subject["id"], peer):
                    added += 1
                    self._set_status(
                        f"«{peer.get('title')}» añadido a «{subject['name']}»."
                    )
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            messagebox.showwarning(
                "Algunos canales no se añadieron",
                "\n".join(errors[:8]),
                parent=self,
            )

        tab = self.tabs.get(int(subject["id"]))
        if tab is not None:
            tab.refresh_channels()

        if added and messagebox.askyesno(
            "Sincronizar",
            f"¿Descargar ahora el contenido de {added} canal(es) nuevo(s)?",
            parent=self,
        ):
            self.start_sync(int(subject["id"]))

    def rename_subject(self, subject: dict[str, Any]) -> None:
        new_name = simpledialog.askstring(
            "Renombrar asignatura",
            "Nuevo nombre:",
            initialvalue=subject["name"],
            parent=self,
        )
        if not new_name or new_name.strip() == subject["name"]:
            return

        try:
            self.db.rename_subject(int(subject["id"]), new_name)
        except sqlite3.IntegrityError:
            self._show_error(f"Ya existe una asignatura llamada «{new_name.strip()}».")
            return
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.reload_subjects(int(subject["id"]))
        self._set_status(f"Asignatura renombrada a «{new_name.strip()}».")

    def delete_subject(self, subject: dict[str, Any]) -> None:
        if not messagebox.askyesno(
            "Eliminar asignatura",
            f"¿Eliminar «{subject['name']}» y todo su índice de mensajes?\n\n"
            "Los archivos ya descargados no se borrarán del disco.",
            parent=self,
            icon="warning",
        ):
            return

        self.db.delete_subject(int(subject["id"]))
        self.reload_subjects()
        self._set_status(f"Asignatura «{subject['name']}» eliminada del índice.")

    # ------------------------------------------------------------------
    # Sincronización y conexión
    # ------------------------------------------------------------------
    def _ensure_online(self) -> bool:
        if self._authorized:
            return True
        messagebox.showinfo(
            "Telegram",
            "Primero inicia sesión en Telegram. Después podrás buscar canales "
            "y descargar su contenido.",
            parent=self,
        )
        self.show_login()
        return False

    def show_login(self) -> None:
        if self._login_dialog is not None and self._login_dialog.winfo_exists():
            self._login_dialog.lift()
            return

        if self._authorized:
            messagebox.showinfo(
                "Telegram",
                f"Ya estás conectado como {self._account_name or 'tu cuenta'}.",
                parent=self,
            )
            return

        dialog = LoginDialog(self, self.settings)
        self._login_dialog = dialog
        self.wait_window(dialog)
        self._login_dialog = None

        if not dialog.result:
            return

        api_id, api_hash, phone = dialog.result
        self.settings.api_id = api_id
        self.settings.api_hash = api_hash
        self.settings.phone = phone
        try:
            self.settings.save()
        except OSError as exc:
            self._show_error(f"No se pudo guardar la configuración: {exc}")

        self._update_account("Conectando con Telegram…", "#9a6700")
        try:
            started = self.service.login(api_id, api_hash, phone)
        except RuntimeError as exc:
            self._show_error(str(exc))
            return

        if not started:
            self._set_status("Ya hay una conexión en curso.")
        else:
            self._set_status("Solicitando el código de verificación a Telegram…")

    def logout(self) -> None:
        if not self._authorized:
            self._set_status("No hay ninguna sesión iniciada.")
            return

        if not messagebox.askyesno(
            "Cerrar sesión",
            "¿Cerrar la sesión de Telegram en este equipo?\n\n"
            "Tus descargas y asignaturas se conservan; tendrás que volver a "
            "introducir el código la próxima vez.",
            parent=self,
            icon="warning",
        ):
            return

        self.service.logout()
        self._set_status("Cerrando la sesión de Telegram…")

    def start_sync(self, subject_id: int | None) -> None:
        if not self._authorized:
            messagebox.showinfo(
                "Telegram",
                "Inicia sesión en Telegram antes de sincronizar.",
                parent=self,
            )
            self.show_login()
            return

        if self._sync_active:
            return

        try:
            started = self.service.start_sync(subject_id)
        except RuntimeError as exc:
            self._show_error(str(exc))
            return

        if not started:
            return

        self._set_sync_ui(True)
        self._set_progress_visible(True)
        self.progress.configure(maximum=1, value=0)
        self._set_status("Preparando la sincronización…")

    def cancel_sync(self) -> None:
        if self._sync_active:
            self.service.cancel_sync()
            self._set_status("Cancelando la sincronización…")

    # ------------------------------------------------------------------
    # Búsqueda / carpetas / ayuda
    # ------------------------------------------------------------------
    def _search_channels(
        self, query: str, done: Callable[[Any, Exception | None], None]
    ) -> None:
        if not self._authorized:
            done(None, RuntimeError("Inicia sesión en Telegram para buscar canales."))
            return
        try:
            self.service.submit(self.service.search_channels(query), done)
        except RuntimeError as exc:
            done(None, exc)

    def open_downloads_root(self) -> None:
        path = self.settings.download_path()
        path.mkdir(parents=True, exist_ok=True)
        try:
            open_path(path)
        except OSError as exc:
            self._show_error(f"No se pudo abrir la carpeta: {exc}")

    def open_subject_folder(self, subject: dict[str, Any]) -> None:
        path = self.settings.download_path() / subject["folder_name"]
        if not path.is_dir():
            messagebox.showinfo(
                "Sin archivos",
                "Todavía no se ha descargado ningún archivo de esta asignatura.",
                parent=self,
            )
            return
        try:
            open_path(path)
        except OSError as exc:
            self._show_error(f"No se pudo abrir la carpeta: {exc}")

    def change_downloads_dir(self) -> None:
        selected = filedialog.askdirectory(
            title="Carpeta para las descargas",
            initialdir=str(self.settings.download_path()),
            parent=self,
        )
        if not selected:
            return

        self.settings.downloads_dir = selected
        try:
            self.settings.save()
        except OSError as exc:
            self._show_error(f"No se pudo guardar la configuración: {exc}")
            return
        self._set_status(
            f"Carpeta de descargas: {selected} (los archivos anteriores no se mueven)"
        )

    def show_help(self) -> None:
        messagebox.showinfo(
            "Cómo funciona",
            "1. Inicia sesión con tu cuenta de Telegram (api_id y api_hash de "
            "my.telegram.org).\n\n"
            "2. Crea una asignatura y busca sus canales o grupos por nombre, "
            "@usuario o enlace t.me.\n\n"
            "3. Pulsa «Sincronizar» para descargar mensajes y archivos. La primera "
            f"vez se revisa el historial desde el {MESSAGE_CUTOFF_LABEL} y las "
            "siguientes solo lo nuevo.\n\n"
            f"Solo se conservan los mensajes publicados desde el {MESSAGE_CUTOFF_LABEL}: "
            "al abrir la app se eliminan del índice y del disco los anteriores.\n\n"
            "4. Usa el desplegable «Tipo» para ver solo documentos, imágenes, "
            "vídeos, audio, texto o enlaces.\n\n"
            "5. Marca profesores con el botón derecho sobre un mensaje o en "
            "«Opciones → Profesores…». Activa «Solo profesores» para ver solo sus "
            "mensajes; se combina con la búsqueda y el tipo.\n\n"
            "6. Haz doble clic en un mensaje con archivo para abrirlo con el "
            "programa predeterminado de Windows.\n\n"
            "Todo se guarda en la carpeta de descargas, en subcarpetas por "
            "asignatura y canal, y se indexa en una base de datos SQLite.",
            parent=self,
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            "Acerca de Student Support",
            f"Student Support {APP_VERSION}\n"
            "Recopilador de contenido de canales de Telegram para estudiantes.\n\n"
            f"Datos: {DATA_DIR}\n"
            f"Descargas: {self.settings.download_path()}\n"
            f"Registro: {LOG_PATH}",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        messagebox.showerror("Error", message, parent=self)

    def _report_callback_exception(self, exc, value, tb) -> None:
        log.exception("Error no controlado en la interfaz", exc_info=(exc, value, tb))
        try:
            messagebox.showerror(
                "Error inesperado",
                f"{value}\n\nLos detalles se han guardado en:\n{LOG_PATH}",
                parent=self,
            )
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        if self._closing:
            return

        if self._sync_active:
            if not messagebox.askyesno(
                "Salir",
                "Hay una sincronización en curso. ¿Detenerla y salir?",
                parent=self,
                icon="warning",
            ):
                return
            self.service.cancel_sync()

        self._closing = True
        self._set_status("Cerrando…")
        try:
            self.service.stop()
        except Exception:
            log.exception("Error cerrando el servicio de Telegram")
        self.destroy()


class SubjectTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: MainWindow, subject: dict[str, Any]) -> None:
        super().__init__(parent, padding=10)

        self.app = app
        self.db = app.db
        self.subject = subject
        self.subject_id = int(subject["id"])

        self.channel_filter: int | None = None
        self.display_limit = 800
        self._rows: dict[str, dict[str, Any]] = {}
        self._channels: dict[int, dict[str, Any]] = {}
        self._selected_row: dict[str, Any] | None = None
        self._search_job: str | None = None
        self._suppress_channel_event = False

        self._build()
        self.refresh_channels()
        self.refresh_messages()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build(self) -> None:
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 10, 0), width=245)
        left.pack_propagate(False)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        paned.add(right, weight=4)

        self._build_channel_panel(left)
        self._build_message_panel(right)

    def _build_channel_panel(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Canales",
            font=SECTION_FONT,
            foreground="#1d2733",
        ).pack(anchor="w")
        ttk.Label(
            parent,
            text="Selecciona un canal para filtrar.",
            font=SMALL_FONT,
            foreground="#5b6572",
        ).pack(anchor="w", pady=(0, 6))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        self.channel_tree = ttk.Treeview(
            tree_frame, columns=("canal", "n"), show="headings", selectmode="browse"
        )
        self.channel_tree.heading("canal", text="Canal")
        self.channel_tree.heading("n", text="N")
        self.channel_tree.column("canal", width=180, anchor="w", stretch=True)
        self.channel_tree.column("n", width=50, anchor="e", stretch=False)
        self.channel_tree.tag_configure("all", font=("Segoe UI Semibold", 9))

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.channel_tree.yview
        )
        self.channel_tree.configure(yscrollcommand=scrollbar.set)
        self.channel_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.channel_tree.bind("<<TreeviewSelect>>", self._on_channel_select)

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(
            buttons,
            text="Añadir",
            command=lambda: self.app.add_channels(self.subject),
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            buttons, text="Quitar", command=self._remove_channel
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_message_panel(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 6))

        ttk.Label(toolbar, text="Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24)
        self.search_entry.pack(side="left", padx=(6, 6))
        self.search_entry.bind("<Return>", lambda _event: self._apply_search())
        self.search_var.trace_add("write", lambda *_: self._schedule_search())
        ttk.Button(toolbar, text="Limpiar", command=self._clear_search).pack(side="left")

        ttk.Label(toolbar, text="Tipo:").pack(side="left", padx=(12, 0))
        self.type_var = tk.StringVar(value="Todos")
        self.type_combo = ttk.Combobox(
            toolbar,
            textvariable=self.type_var,
            values=list(TYPE_FILTERS),
            state="readonly",
            width=12,
        )
        self.type_combo.pack(side="left", padx=(6, 0))
        self.type_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._apply_filters()
        )

        self.teacher_var = tk.BooleanVar(value=False)
        self.teacher_check = ttk.Checkbutton(
            toolbar,
            text="Solo profesores",
            variable=self.teacher_var,
            command=self._apply_filters,
        )
        self.teacher_check.pack(side="left", padx=(12, 0))

        ttk.Button(
            toolbar, text="Opciones", command=self._open_options_menu
        ).pack(side="right")
        self.sync_button = ttk.Button(
            toolbar,
            text="Sincronizar",
            command=lambda: self.app.start_sync(self.subject_id),
        )
        self.sync_button.pack(side="right", padx=(0, 6))
        self.more_button = ttk.Button(
            toolbar, text="Cargar más", command=self.load_more
        )
        self.more_button.pack(side="right", padx=(0, 6))

        self.count_var = tk.StringVar(value="")
        ttk.Label(
            toolbar,
            textvariable=self.count_var,
            font=SMALL_FONT,
            foreground="#5b6572",
        ).pack(side="right", padx=(6, 10))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        columns = ("fecha", "remitente", "canal", "tipo", "mensaje", "archivo")
        self.message_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "fecha": ("Fecha", 132),
            "remitente": ("Quién lo subió", 140),
            "canal": ("Canal", 125),
            "tipo": ("Tipo", 85),
            "mensaje": ("Mensaje", 240),
            "archivo": ("Archivo", 220),
        }
        for key, (text, width) in headings.items():
            self.message_tree.heading(key, text=text)
            self.message_tree.column(
                key,
                width=width,
                anchor="w",
                stretch=key in ("mensaje", "archivo"),
            )

        vertical = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.message_tree.yview
        )
        horizontal = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.message_tree.xview
        )
        self.message_tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.message_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.message_tree.bind("<<TreeviewSelect>>", self._on_message_select)
        self.message_tree.bind("<Double-1>", self._on_message_open)
        self.message_tree.bind("<Return>", self._on_message_open)
        self.message_tree.bind("<Button-3>", self._on_message_context)
        self.message_tree.bind(
            "<Control-c>", lambda _event: self._copy_text()
        )

        self._build_detail(parent)

    def _build_detail(self, parent: ttk.Frame) -> None:
        detail = ttk.LabelFrame(parent, text="Detalle del mensaje", padding=8)
        detail.pack(fill="x", pady=(8, 0))

        text_frame = ttk.Frame(detail)
        text_frame.pack(fill="x")

        self.detail_text = tk.Text(
            text_frame,
            height=8,
            wrap="word",
            font=BODY_FONT,
            relief="solid",
            borderwidth=1,
            background="#fbfbfc",
            padx=8,
            pady=6,
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.detail_text.yview
        )
        self.detail_text.configure(yscrollcommand=scrollbar.set)
        self.detail_text.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.detail_text.tag_configure("meta", foreground="#4a5563")
        self.detail_text.tag_configure("body", font=("Segoe UI", 10))

        actions = ttk.Frame(detail)
        actions.pack(fill="x", pady=(6, 0))

        self.open_file_button = ttk.Button(
            actions, text="Abrir archivo", command=self._open_selected_file
        )
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(
            actions, text="Abrir carpeta", command=self._open_selected_folder
        )
        self.open_folder_button.pack(side="left", padx=(6, 0))
        self.copy_button = ttk.Button(
            actions, text="Copiar texto", command=self._copy_text
        )
        self.copy_button.pack(side="left", padx=(6, 0))
        self.telegram_button = ttk.Button(
            actions, text="Ver en Telegram", command=self._open_in_telegram
        )
        self.telegram_button.pack(side="left", padx=(6, 0))

        self._set_detail_buttons(False, False)

    # ------------------------------------------------------------------
    # Canales
    # ------------------------------------------------------------------
    def refresh_channels(self) -> None:
        channels = self.db.channels(self.subject_id)
        counts = self.db.channel_counts(self.subject_id)
        self._channels = {int(channel["id"]): channel for channel in channels}

        previous = self.channel_filter
        self._suppress_channel_event = True

        self.channel_tree.delete(*self.channel_tree.get_children())
        total = sum(counts.values())
        self.channel_tree.insert(
            "",
            "end",
            iid="all",
            values=("Todos los canales", total),
            tags=("all",),
        )

        for channel in channels:
            channel_id = int(channel["id"])
            self.channel_tree.insert(
                "",
                "end",
                iid=str(channel_id),
                values=(channel["title"], counts.get(channel_id, 0)),
            )

        target = str(previous) if previous is not None else "all"
        if not self.channel_tree.exists(target):
            target = "all"
            self.channel_filter = None
            self._selected_row = None

        self.channel_tree.selection_set(target)
        self.channel_tree.focus(target)
        self._suppress_channel_event = False

    def _on_channel_select(self, _event: tk.Event) -> None:
        if self._suppress_channel_event:
            return

        selection = self.channel_tree.selection()
        if not selection:
            return

        selected = selection[0]
        new_filter = None if selected == "all" else int(selected)
        if new_filter == self.channel_filter:
            return

        self.channel_filter = new_filter
        self.display_limit = 800
        self.refresh_messages()

    def _remove_channel(self) -> None:
        selection = self.channel_tree.selection()
        if not selection or selection[0] == "all":
            messagebox.showinfo(
                "Quitar canal",
                "Selecciona primero un canal concreto en la lista.",
                parent=self,
            )
            return

        channel_id = int(selection[0])
        channel = self._channels.get(channel_id)
        if not channel:
            return

        if not messagebox.askyesno(
            "Quitar canal",
            f"¿Quitar «{channel['title']}» de «{self.subject['name']}»?\n\n"
            "Se eliminarán sus mensajes del índice, pero los archivos ya "
            "descargados no se borrarán del disco.",
            parent=self,
            icon="warning",
        ):
            return

        self.db.remove_channel(channel_id)
        self.channel_filter = None
        self.refresh_channels()
        self.refresh_messages()
        self.app._set_status(f"Canal «{channel['title']}» quitado de la asignatura.")

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        self.refresh_channels()
        self.refresh_messages()

    def refresh_messages(self) -> None:
        search = self.search_var.get().strip()
        media_filter = TYPE_FILTERS.get(self.type_var.get(), "all")
        teacher_only = bool(self.teacher_var.get())
        total = self.db.count_messages(
            self.subject_id,
            self.channel_filter,
            search,
            media_filter,
            teacher_only,
        )
        rows = self.db.messages(
            self.subject_id,
            self.channel_filter,
            search,
            self.display_limit,
            media_filter,
            teacher_only,
        )

        filtered = bool(search) or media_filter != "all" or teacher_only
        teacher_keys = self.db.teacher_keys(self.subject_id)

        self.message_tree.delete(*self.message_tree.get_children())
        self._rows.clear()
        self._selected_row = None

        for message in rows:
            iid = f"{int(message['channel_id'])}:{int(message['message_id'])}"
            self._rows[iid] = message
            preview = compact_text(message.get("text"), 260)
            if not preview and message.get("media_type"):
                preview = f"[{media_label(message.get('media_type'))}]"

            sender_name = message.get("sender_name") or "—"
            if sender_key(message) in teacher_keys:
                sender_name = f"★ {sender_name}"

            file_name = message.get("file_name") or "—"
            self.message_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    format_datetime(message.get("date")),
                    sender_name,
                    message.get("channel_title") or "—",
                    table_media_label(
                        message.get("media_type"), message.get("file_name")
                    ),
                    preview,
                    file_name,
                ),
            )

        if rows:
            first = f"{int(rows[0]['channel_id'])}:{int(rows[0]['message_id'])}"
            self.message_tree.selection_set(first)
            self.message_tree.focus(first)
            self.message_tree.see(first)
        else:
            if filtered:
                if teacher_only:
                    self._set_detail_text(
                        "No hay mensajes de profesores con estos filtros.\n\n"
                        "Marca profesores en Opciones → Profesores… o con el botón "
                        "derecho sobre un mensaje."
                    )
                else:
                    self._set_detail_text(
                        "No hay mensajes que coincidan con el filtro.\n\n"
                        "Prueba con otro tipo de contenido o limpia la búsqueda."
                    )
            else:
                self._set_detail_text(
                    "Sin mensajes que mostrar.\n\n"
                    "Pulsa «Sincronizar» para descargar el contenido del canal."
                )
            self._set_detail_buttons(False, False)

        suffix = " (filtrado)" if filtered else ""
        if total > len(rows):
            self.count_var.set(f"Mostrando {len(rows)} de {total}{suffix}")
            self.more_button.state(["!disabled"])
        else:
            self.count_var.set(
                f"{total} mensaje{'s' if total != 1 else ''}{suffix}"
            )
            self.more_button.state(["disabled"])

    def _apply_filters(self) -> None:
        self.display_limit = 800
        self.refresh_messages()

    def load_more(self) -> None:
        self.display_limit += 800
        self.refresh_messages()

    def _schedule_search(self) -> None:
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except tk.TclError:
                pass
        self._search_job = self.after(350, self._apply_search)

    def _apply_search(self) -> None:
        self._search_job = None
        self.display_limit = 800
        self.refresh_messages()

    def _clear_search(self) -> None:
        self.search_var.set("")

    def _on_message_select(self, _event: tk.Event) -> None:
        selection = self.message_tree.selection()
        if not selection:
            self._selected_row = None
            self._set_detail_buttons(False, False)
            return

        row = self._rows.get(selection[0])
        self._selected_row = row
        if row is None:
            return

        file_path = row.get("file_path")
        exists = bool(file_path and Path(file_path).exists())
        has_folder = self._channel_folder_exists(row)
        self._set_detail_buttons(exists, has_folder or bool(file_path))
        self._show_detail(row, exists)

    def _show_detail(self, row: dict[str, Any], file_exists: bool) -> None:
        lines: list[str] = []
        lines.append(
            f"Canal: {row.get('channel_title') or '—'} · "
            f"Remitente: {row.get('sender_name') or '—'}"
        )
        lines.append(
            f"Fecha: {format_datetime(row.get('date'))} · "
            f"Tipo: {media_label(row.get('media_type'), row.get('file_name'))}"
        )

        if row.get("file_name"):
            size = format_size(row.get("file_size"))
            suffix = f" · {size}" if size else ""
            missing = "" if file_exists else " · archivo no encontrado"
            lines.append(f"Archivo: {row['file_name']}{suffix}{missing}")
        if row.get("permalink"):
            lines.append(f"Enlace: {row['permalink']}")

        header = "\n".join(lines)
        body = row.get("text") or ""
        if not body:
            if row.get("media_type"):
                body = "(Este mensaje no tiene texto; contiene un archivo o contenido multimedia.)"
            else:
                body = "(Sin texto)"

        self._set_detail_text(f"{header}\n\n{'─' * 60}\n{body}", header=header, body=body)

    def _set_detail_text(
        self, text: str, *, header: str | None = None, body: str | None = None
    ) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")

        if header is not None and body is not None:
            self.detail_text.insert("end", header + "\n\n", "meta")
            self.detail_text.insert("end", "─" * 60 + "\n", "meta")
            self.detail_text.insert("end", body, "body")
        else:
            self.detail_text.insert("end", text, "body")

        self.detail_text.configure(state="disabled")

    def _set_detail_buttons(self, file_ok: bool, folder_ok: bool) -> None:
        for button, enabled in (
            (self.open_file_button, file_ok),
            (self.open_folder_button, folder_ok),
            (self.copy_button, self._selected_row is not None),
            (
                self.telegram_button,
                bool(self._selected_row and self._selected_row.get("permalink")),
            ),
        ):
            if enabled:
                button.state(["!disabled"])
            else:
                button.state(["disabled"])

    # ------------------------------------------------------------------
    # Acciones sobre archivos
    # ------------------------------------------------------------------
    def _channel_folder_exists(self, row: dict[str, Any]) -> bool:
        channel = self._channels.get(int(row["channel_id"]))
        if not channel:
            return False
        folder = (
            self.app.settings.download_path()
            / self.subject["folder_name"]
            / channel["folder_name"]
        )
        return folder.is_dir()

    def _open_selected_file(self) -> None:
        row = self._selected_row
        if not row:
            return

        file_path = row.get("file_path")
        if not file_path:
            messagebox.showinfo(
                "Sin archivo",
                "Este mensaje no tiene un archivo descargable.",
                parent=self,
            )
            return

        try:
            open_path(file_path)
        except FileNotFoundError:
            if messagebox.askyesno(
                "Archivo no encontrado",
                "El archivo ya no está en la carpeta de descargas.\n\n"
                "¿Quieres volver a sincronizar esta asignatura para descargarlo?",
                parent=self,
            ):
                self.app.start_sync(self.subject_id)
        except OSError as exc:
            messagebox.showerror(
                "No se pudo abrir",
                f"{exc}\n\nArchivo: {file_path}",
                parent=self,
            )

    def _open_selected_folder(self) -> None:
        row = self._selected_row
        if not row:
            return

        file_path = row.get("file_path")
        folder: Path | None = None
        if file_path:
            candidate = Path(file_path).parent
            if candidate.is_dir():
                folder = candidate

        if folder is None:
            channel = self._channels.get(int(row["channel_id"]))
            if channel:
                candidate = (
                    self.app.settings.download_path()
                    / self.subject["folder_name"]
                    / channel["folder_name"]
                )
                if candidate.is_dir():
                    folder = candidate

        if folder is None:
            messagebox.showinfo(
                "Sin carpeta",
                "Todavía no hay archivos descargados de este canal.",
                parent=self,
            )
            return

        try:
            open_path(folder)
        except OSError as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc), parent=self)

    def _copy_text(self) -> None:
        row = self._selected_row
        if not row:
            return
        text = row.get("text") or ""
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.app._set_status("Texto del mensaje copiado al portapapeles.")

    def _open_in_telegram(self) -> None:
        row = self._selected_row
        if not row or not row.get("permalink"):
            return
        open_url(row["permalink"])

    def _on_message_open(self, _event: tk.Event) -> None:
        row = self._selected_row
        if not row or not row.get("file_path"):
            return
        self._open_selected_file()

    def _on_message_context(self, event: tk.Event) -> None:
        row_id = self.message_tree.identify_row(event.y)
        if not row_id:
            return
        self.message_tree.selection_set(row_id)
        self.message_tree.focus(row_id)
        self._on_message_select(event)

        row = self._rows.get(row_id)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Abrir archivo", command=self._open_selected_file)
        menu.add_command(label="Abrir carpeta", command=self._open_selected_folder)
        menu.add_separator()
        menu.add_command(label="Copiar texto", command=self._copy_text)
        menu.add_command(
            label="Ver en Telegram", command=self._open_in_telegram
        )
        menu.add_separator()

        key = sender_key(row) if row else ""
        name = (row.get("sender_name") if row else "") or "este remitente"
        if key and self.db.is_teacher(self.subject_id, key):
            menu.add_command(
                label=f"Quitar a {name} de profesores",
                command=self._unmark_teacher,
            )
        elif key:
            menu.add_command(
                label=f"Marcar a {name} como profesor",
                command=self._mark_teacher,
            )
        else:
            menu.add_command(
                label="Marcar como profesor",
                command=self._mark_teacher,
                state="disabled",
            )
        menu.add_command(
            label="Gestionar profesores…", command=self._manage_teachers
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _mark_teacher(self) -> None:
        row = self._selected_row
        if not row:
            return
        key = sender_key(row)
        if not key:
            messagebox.showinfo(
                "Sin remitente",
                "Este mensaje no tiene un remitente identificable.",
                parent=self,
            )
            return
        name = row.get("sender_name") or "Profesor"
        if self.db.add_teacher(self.subject_id, key, name):
            self.app._set_status(f"«{name}» marcado como profesor.")
        self.refresh_messages()

    def _unmark_teacher(self) -> None:
        row = self._selected_row
        if not row:
            return
        key = sender_key(row)
        if not key:
            return
        name = row.get("sender_name") or "Profesor"
        self.db.remove_teacher(self.subject_id, key)
        self.app._set_status(f"«{name}» ya no está marcado como profesor.")
        self.refresh_messages()

    def _manage_teachers(self) -> None:
        dialog = TeacherDialog(self, self.db, self.subject)
        self.wait_window(dialog)
        self.refresh_messages()

    # ------------------------------------------------------------------
    # Opciones de la asignatura
    # ------------------------------------------------------------------
    def _open_options_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Sincronizar esta asignatura",
            command=lambda: self.app.start_sync(self.subject_id),
        )
        menu.add_command(
            label="Añadir canales…",
            command=lambda: self.app.add_channels(self.subject),
        )
        menu.add_command(
            label="Abrir carpeta de la asignatura",
            command=lambda: self.app.open_subject_folder(self.subject),
        )
        menu.add_separator()
        menu.add_command(label="Profesores…", command=self._manage_teachers)
        menu.add_separator()
        menu.add_command(
            label="Renombrar asignatura…",
            command=lambda: self.app.rename_subject(self.subject),
        )
        menu.add_command(
            label="Eliminar asignatura…",
            command=lambda: self.app.delete_subject(self.subject),
        )

        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def set_syncing(self, active: bool) -> None:
        if active:
            self.sync_button.state(["disabled"])
        else:
            self.sync_button.state(["!disabled"])
