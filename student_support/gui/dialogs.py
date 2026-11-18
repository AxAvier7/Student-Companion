"""Diálogos de la aplicación: inicio de sesión, búsqueda de canales y prompts."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from ..config import Settings
from .utils import center_window, open_url

_TITLE_FONT = ("Segoe UI Semibold", 14)
_BODY_FONT = ("Segoe UI", 10)
_SMALL_FONT = ("Segoe UI", 9)


def ask_text(
    parent: tk.Misc,
    title: str,
    message: str,
    *,
    password: bool = False,
    initial: str = "",
) -> str | None:
    """Pequeño diálogo modal para pedir un texto (código, contraseña…)."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    container = ttk.Frame(dialog, padding=18)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=message,
        wraplength=430,
        justify="left",
        font=_BODY_FONT,
    ).pack(anchor="w")

    value = tk.StringVar(value=initial)
    entry = ttk.Entry(
        container, textvariable=value, width=40, show="•" if password else ""
    )
    entry.pack(fill="x", pady=(12, 14))

    result = {"value": None}

    def accept() -> None:
        result["value"] = value.get().strip()
        dialog.destroy()

    buttons = ttk.Frame(container)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right")
    ttk.Button(buttons, text="Aceptar", command=accept).pack(
        side="right", padx=(0, 8)
    )

    dialog.bind("<Return>", lambda _event: accept())
    dialog.bind("<Escape>", lambda _event: dialog.destroy())

    center_window(dialog, parent)
    dialog.grab_set()
    entry.focus_set()
    entry.selection_range(0, "end")
    parent.wait_window(dialog)
    return result["value"]


class LoginDialog(tk.Toplevel):
    """Pide api_id, api_hash y teléfono para crear la sesión de Telethon."""

    def __init__(self, parent: tk.Misc, settings: Settings) -> None:
        super().__init__(parent)
        self.result: tuple[int, str, str] | None = None
        self.title("Conectar con Telegram")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._settings = settings
        self._build()
        center_window(self, parent)
        self.grab_set()
        self.api_id_entry.focus_set()

    def _build(self) -> None:
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container, text="Conectar con Telegram", font=_TITLE_FONT
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        intro = (
            "La aplicación usa tu propia cuenta de Telegram para leer los canales "
            "en los que ya participas. Necesitas un api_id y un api_hash gratuitos:\n"
            "my.telegram.org → API development tools → crea una aplicación."
        )
        ttk.Label(
            container, text=intro, wraplength=500, justify="left", font=_BODY_FONT
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 6))

        link = tk.Label(
            container,
            text="Abrir my.telegram.org",
            fg="#0a5bd6",
            cursor="hand2",
            font=_SMALL_FONT,
        )
        link.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 14))
        link.bind("<Button-1>", lambda _event: open_url("https://my.telegram.org"))

        ttk.Label(container, text="api_id", font=_BODY_FONT).grid(
            row=3, column=0, sticky="w", pady=(0, 4)
        )
        self.api_id_var = tk.StringVar(
            value=str(self._settings.api_id) if self._settings.api_id else ""
        )
        self.api_id_entry = ttk.Entry(container, textvariable=self.api_id_var, width=52)
        self.api_id_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(container, text="api_hash", font=_BODY_FONT).grid(
            row=5, column=0, sticky="w", pady=(0, 4)
        )
        self.api_hash_var = tk.StringVar(value=self._settings.api_hash)
        ttk.Entry(container, textvariable=self.api_hash_var, width=52).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )

        ttk.Label(container, text="Número de teléfono", font=_BODY_FONT).grid(
            row=7, column=0, sticky="w", pady=(0, 4)
        )
        self.phone_var = tk.StringVar(value=self._settings.phone)
        ttk.Entry(container, textvariable=self.phone_var, width=52).grid(
            row=8, column=0, columnspan=2, sticky="ew"
        )
        ttk.Label(
            container,
            text="Incluye el prefijo del país, por ejemplo +34 600 123 456.",
            font=_SMALL_FONT,
            foreground="#555555",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 16))

        buttons = ttk.Frame(container)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(
            buttons, text="Guardar y conectar", command=self._accept
        ).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

    def _accept(self) -> None:
        raw_api_id = self.api_id_var.get().strip()
        api_hash = self.api_hash_var.get().strip()
        phone = re.sub(r"[\s\-().]", "", self.phone_var.get().strip())

        try:
            api_id = int(raw_api_id)
        except ValueError:
            messagebox.showwarning(
                "Datos incompletos",
                "El api_id debe ser un número. Puedes verlo en my.telegram.org.",
                parent=self,
            )
            return

        if api_id <= 0:
            messagebox.showwarning(
                "Datos incompletos", "El api_id no es válido.", parent=self
            )
            return

        if len(api_hash) < 8:
            messagebox.showwarning(
                "Datos incompletos",
                "Escribe el api_hash completo que aparece en my.telegram.org.",
                parent=self,
            )
            return

        if phone.startswith("00"):
            phone = f"+{phone[2:]}"

        if not phone.startswith("+") or not phone[1:].isdigit():
            messagebox.showwarning(
                "Teléfono no válido",
                "Escribe el número en formato internacional, por ejemplo +34600123456.",
                parent=self,
            )
            return

        self.result = (api_id, api_hash, phone)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class TeacherDialog(tk.Toplevel):
    """Marca o desmarca remitentes de una asignatura como profesores."""

    def __init__(
        self,
        parent: tk.Misc,
        database: Any,
        subject: dict[str, Any],
    ) -> None:
        super().__init__(parent)
        self.db = database
        self.subject = subject
        self.subject_id = int(subject["id"])

        self.title(f"Profesores · {subject['name']}")
        self.transient(parent)
        self.geometry("760x540")
        self.minsize(640, 420)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._rows: dict[str, dict[str, Any]] = {}
        self._build()
        self._reload()
        center_window(self, parent)
        self.grab_set()

    def _build(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Profesores", font=_TITLE_FONT).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Selecciona a los miembros que imparten la asignatura. Sus mensajes "
                "se podrán ver con el filtro «Solo profesores», combinado con la "
                "búsqueda y el tipo de contenido."
            ),
            font=_BODY_FONT,
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True)

        columns = ("nombre", "tipo", "mensajes")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "nombre": ("Miembro", 420),
            "tipo": ("Tipo de autor", 130),
            "mensajes": ("Mensajes", 90),
        }
        for key, (text, width) in headings.items():
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w", stretch=key == "nombre")
        self.tree.column("mensajes", anchor="e")
        self.tree.tag_configure("teacher", font=("Segoe UI Semibold", 9))

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._update_buttons())
        self.tree.bind("<Double-1>", lambda _event: self._toggle())

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            container,
            textvariable=self.status_var,
            font=_SMALL_FONT,
            foreground="#555555",
        ).pack(anchor="w", pady=(8, 6))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cerrar", command=self.destroy).pack(side="right")
        self.remove_button = ttk.Button(
            buttons, text="Quitar de profesores", command=self._remove
        )
        self.remove_button.pack(side="right", padx=(0, 8))
        self.add_button = ttk.Button(
            buttons, text="Marcar como profesor", command=self._add
        )
        self.add_button.pack(side="right", padx=(0, 8))

        self._update_buttons()

    def _selected(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._rows.get(selection[0])

    def _reload(self) -> None:
        teachers = {item["sender_key"]: item for item in self.db.teachers(self.subject_id)}
        senders = {item["sender_key"]: item for item in self.db.message_senders(self.subject_id)}

        # Incluye profesores marcados sin mensajes visibles actualmente.
        for key, teacher in teachers.items():
            senders.setdefault(
                key,
                {
                    "sender_key": key,
                    "display_name": teacher["display_name"],
                    "total": 0,
                    "last_date": None,
                },
            )

        self._rows: dict[str, dict[str, Any]] = {}
        self.tree.delete(*self.tree.get_children())

        ordered = sorted(
            senders.values(),
            key=lambda item: (item["sender_key"] not in teachers, item["display_name"].lower()),
        )
        for sender in ordered:
            key = sender["sender_key"]
            is_teacher = key in teachers
            self._rows[key] = sender
            total = int(sender.get("total") or 0)
            self.tree.insert(
                "",
                "end",
                iid=key,
                values=(
                    f"★ {sender['display_name']}" if is_teacher else sender["display_name"],
                    "Firma del canal" if key.startswith("author:") else "Usuario",
                    total if total else "—",
                ),
                tags=("teacher",) if is_teacher else (),
            )

        self.status_var.set(
            f"{len(teachers)} profesor(es) marcado(s) de "
            f"{len(senders)} remitente(s). Haz doble clic para cambiar."
        )

        children = self.tree.get_children()
        if children:
            selection = self.tree.selection()
            target = selection[0] if selection else children[0]
            self.tree.selection_set(target)
            self.tree.focus(target)
            self.tree.see(target)

        self._update_buttons()

    def _update_buttons(self) -> None:
        sender = self._selected()
        if sender is None:
            self.add_button.state(["disabled"])
            self.remove_button.state(["disabled"])
            return

        is_teacher = self.db.is_teacher(self.subject_id, sender["sender_key"])
        self.add_button.state(["disabled"] if is_teacher else ["!disabled"])
        self.remove_button.state(["!disabled"] if is_teacher else ["disabled"])

    def _add(self) -> None:
        sender = self._selected()
        if sender is None:
            return
        self.db.add_teacher(
            self.subject_id, sender["sender_key"], sender["display_name"]
        )
        self._reload()
        self.tree.selection_set(sender["sender_key"])

    def _remove(self) -> None:
        sender = self._selected()
        if sender is None:
            return
        self.db.remove_teacher(self.subject_id, sender["sender_key"])
        self._reload()
        self.tree.selection_set(sender["sender_key"])

    def _toggle(self) -> None:
        sender = self._selected()
        if sender is None:
            return
        if self.db.is_teacher(self.subject_id, sender["sender_key"]):
            self._remove()
        else:
            self._add()


class ChannelBrowserDialog(tk.Toplevel):
    """Busca canales/grupos en Telegram y permite seleccionar varios."""

    def __init__(
        self,
        parent: tk.Misc,
        search: Callable[[str, Callable[[Any, Exception | None], None]], None],
        *,
        mode: str = "subject",
        subject_name: str | None = None,
        exclude_ids: set[int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.search = search
        self.mode = mode
        self.exclude_ids = exclude_ids or set()
        self.result: dict[str, Any] | None = None

        self._results: dict[str, dict[str, Any]] = {}
        self._searching = False

        self.title("Nueva asignatura" if mode == "subject" else "Añadir canales")
        self.transient(parent)
        self.geometry("880x580")
        self.minsize(720, 460)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build(subject_name)
        center_window(self, parent)
        self.grab_set()
        self.query_entry.focus_set()

    def _build(self, subject_name: str | None) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        if self.mode == "subject":
            ttk.Label(container, text="Nueva asignatura", font=_TITLE_FONT).pack(
                anchor="w"
            )
            ttk.Label(
                container,
                text=(
                    "Escribe un nombre para la asignatura y busca sus canales o grupos "
                    "de Telegram por el nombre oficial."
                ),
                font=_BODY_FONT,
                wraplength=800,
            ).pack(anchor="w", pady=(2, 10))

            name_row = ttk.Frame(container)
            name_row.pack(fill="x", pady=(0, 12))
            ttk.Label(name_row, text="Asignatura:", font=_BODY_FONT).pack(side="left")
            self.name_var = tk.StringVar()
            ttk.Entry(name_row, textvariable=self.name_var).pack(
                side="left", fill="x", expand=True, padx=(8, 0)
            )
        else:
            ttk.Label(container, text="Añadir canales", font=_TITLE_FONT).pack(
                anchor="w"
            )
            subtitle = (
                f"Busca canales o grupos para añadirlos a «{subject_name}»."
                if subject_name
                else "Busca canales o grupos de Telegram."
            )
            ttk.Label(
                container, text=subtitle, font=_BODY_FONT, wraplength=800
            ).pack(anchor="w", pady=(2, 12))
            self.name_var = None

        search_row = ttk.Frame(container)
        search_row.pack(fill="x")
        ttk.Label(search_row, text="Buscar:", font=_BODY_FONT).pack(side="left")
        self.query_var = tk.StringVar()
        self.query_entry = ttk.Entry(search_row, textvariable=self.query_var)
        self.query_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.query_entry.bind("<Return>", lambda _event: self._search())
        self.search_button = ttk.Button(
            search_row, text="Buscar", command=self._search
        )
        self.search_button.pack(side="left")

        hint = (
            "Puedes escribir el nombre, un @usuario o un enlace t.me. "
            "Si no aparece, prueba con el nombre oficial completo o el @usuario. "
            "Debes ser miembro del canal o grupo para descargar su contenido."
        )
        ttk.Label(
            container,
            text=hint,
            font=_SMALL_FONT,
            foreground="#555555",
            wraplength=820,
        ).pack(anchor="w", pady=(6, 8))

        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True)

        columns = ("titulo", "usuario", "tipo", "miembros", "origen")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "titulo": ("Canal o grupo", 320),
            "usuario": ("Usuario", 140),
            "tipo": ("Tipo", 80),
            "miembros": ("Miembros", 80),
            "origen": ("Origen", 150),
        }
        for key, (text, width) in headings.items():
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w", stretch=key == "titulo")
        self.tree.column("miembros", anchor="e")

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status_var = tk.StringVar(
            value="Busca el canal por su nombre y selecciona los resultados."
        )
        ttk.Label(
            container,
            textvariable=self.status_var,
            font=_SMALL_FONT,
            foreground="#555555",
        ).pack(anchor="w", pady=(8, 6))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancelar", command=self._cancel).pack(side="right")
        action_text = (
            "Crear asignatura" if self.mode == "subject" else "Añadir seleccionados"
        )
        ttk.Button(buttons, text=action_text, command=self._accept).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _event: self._cancel())
        if self.name_var is not None:
            self.name_var.trace_add("write", lambda *_: self._validate_name())

    def _validate_name(self) -> None:
        if self.name_var is not None:
            name = self.name_var.get().strip()
            if name:
                self.status_var.set(
                    "Busca ahora los canales de la asignatura y selecciónalos."
                )

    def _search(self) -> None:
        if self._searching:
            return

        query = self.query_var.get().strip()
        if len(query) < 2:
            self.status_var.set("Escribe al menos dos caracteres para buscar.")
            return

        self._searching = True
        self.search_button.state(["disabled"])
        self.status_var.set("Buscando en Telegram…")
        self.tree.delete(*self.tree.get_children())
        self._results.clear()

        try:
            self.search(query, self._on_results)
        except Exception as exc:  # noqa: BLE001
            self._searching = False
            self.search_button.state(["!disabled"])
            self.status_var.set(f"Error: {exc}")

    def _on_results(self, results: Any, error: Exception | None) -> None:
        if not self.winfo_exists():
            return

        self._searching = False
        self.search_button.state(["!disabled"])

        if error is not None:
            self.status_var.set(f"No se pudo buscar: {error}")
            return

        filtered = [
            item for item in (results or []) if int(item["id"]) not in self.exclude_ids
        ]

        if not filtered:
            self.status_var.set(
                "No se encontraron canales nuevos. Prueba con el nombre oficial "
                "completo, un @usuario o un enlace t.me."
            )
            return

        for item in filtered:
            iid = f"{item['peer_type']}:{item['id']}"
            if iid in self._results:
                continue
            self._results[iid] = item
            username = f"@{item['username']}" if item.get("username") else "—"
            members = item.get("members")
            member_text = f"{members:,}".replace(",", ".") if members else ""
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    item.get("title") or "(sin título)",
                    username,
                    "Canal" if item["peer_type"] == "channel" else "Grupo",
                    member_text,
                    item.get("source") or "",
                ),
            )

        self.status_var.set(
            f"{len(filtered)} resultado(s). Selecciona uno o varios con Ctrl o Mayús."
        )

    def _selected_peers(self) -> list[dict[str, Any]]:
        selected = []
        for iid in self.tree.selection():
            item = self._results.get(iid)
            if item:
                selected.append(item)
        return selected

    def _accept(self) -> None:
        selected = self._selected_peers()

        if self.mode == "subject":
            assert self.name_var is not None
            name = self.name_var.get().strip()
            if not name:
                messagebox.showwarning(
                    "Falta el nombre",
                    "Escribe un nombre para la asignatura.",
                    parent=self,
                )
                return

            if not selected:
                if not messagebox.askyesno(
                    "Sin canales",
                    "No has seleccionado ningún canal. ¿Crear la asignatura vacía "
                    "y añadir canales más tarde?",
                    parent=self,
                ):
                    return

            self.result = {"name": name, "channels": selected}
        else:
            if not selected:
                messagebox.showwarning(
                    "Sin canales",
                    "Selecciona al menos un canal o grupo.",
                    parent=self,
                )
                return
            self.result = {"channels": selected}

        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
