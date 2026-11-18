"""Punto de entrada de Student Support."""

from __future__ import annotations

import ctypes
import logging
import sys
import traceback
from tkinter import messagebox


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        pass


def _configure_logging() -> None:
    from student_support.config import LOG_PATH, ensure_directories

    ensure_directories()
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_PATH, encoding="utf-8")
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> None:
    _enable_dpi_awareness()
    _configure_logging()

    try:
        from student_support.gui.main_window import MainWindow

        app = MainWindow()
        app.mainloop()
    except Exception:
        logging.exception("Error fatal al iniciar Student Support")
        try:
            messagebox.showerror(
                "Student Support",
                "No se pudo iniciar la aplicación.\n\n"
                "Consulta el registro para más detalles:\n"
                "data/student_support.log\n\n"
                + traceback.format_exc(limit=2),
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
