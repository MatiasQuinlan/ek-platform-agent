from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageDraw

from .backend import BackendClient
from .codex import installed, login
from .cognito import login as cognito_login
from .config import get_access_token, load, save, set_access_token
from .worker import Worker

logger = logging.getLogger(__name__)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EK Platform Agent")
        self.root.geometry("520x300")
        values = load()
        self.api = tk.StringVar(
            value=values.get(
                "api_url",
                "https://8a6tlv6z2a.execute-api.us-east-1.amazonaws.com/production",
            )
        )
        self.token = tk.StringVar(value="")
        self.status = tk.StringVar(value="Desconectado")
        self.worker: Worker | None = None
        self.tray: pystray.Icon | None = None
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._start_tray()
        if get_access_token():
            self.start_worker()
            self.hide_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="EK Platform Agent", font=("TkDefaultFont", 16, "bold")).pack()
        ttk.Label(frame, text="API del backend").pack(anchor="w", pady=(18, 0))
        ttk.Entry(frame, textvariable=self.api).pack(fill="x")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=16)
        ttk.Button(buttons, text="Conectar ChatGPT", command=self.connect_codex).pack(side="left")
        ttk.Button(buttons, text="Conectar cuenta EK", command=self.connect_backend).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Iniciar agente", command=self.start_worker).pack(side="left")
        ttk.Button(buttons, text="Detener", command=self.stop_worker).pack(side="left", padx=8)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        if not installed():
            self.status.set("Instala Codex CLI antes de conectar ChatGPT")

    def connect_codex(self) -> None:
        try:
            process = login()
            self.status.set("Completa el login de ChatGPT en el navegador...")

            def wait_for_login() -> None:
                return_code = process.wait()
                if return_code == 0:
                    self.root.after(
                        0, self.status.set, "ChatGPT conectado. Abriendo login de EK Platform..."
                    )
                    try:
                        token = cognito_login()
                        set_access_token(token)
                        self.root.after(0, self.token.set, token)
                        self.root.after(0, self.start_worker)
                    except Exception as error:  # noqa: BLE001 - show login errors to the user
                        error_text = str(error)
                        self.root.after(
                            0,
                            lambda: messagebox.showerror("Cuenta EK Platform", error_text),
                        )
                else:
                    message = f"El login de ChatGPT terminó con código {return_code}."
                    self.root.after(0, self.status.set, message)

            threading.Thread(target=wait_for_login, daemon=True).start()
        except RuntimeError as error:
            messagebox.showerror("Codex", str(error))

    def connect_backend(self) -> None:
        try:
            token = cognito_login()
            set_access_token(token)
            self.token.set(token)
            self.start_worker()
        except Exception as error:  # noqa: BLE001 - show login errors to the user
            messagebox.showerror("Cuenta EK Platform", str(error))

    def start_worker(self) -> None:
        try:
            token = self.token.get() or get_access_token()
            if not self.api.get() or not token:
                messagebox.showwarning("Configuración", "Indica la API y el token Cognito")
                return
            set_access_token(token)
            save({"api_url": self.api.get()})
            if self.worker and self.worker.is_running:
                self.status.set("Agente conectado")
                return
            client = BackendClient(self.api.get(), token)
            self.worker = Worker(client, self._notify)
            self.worker.start()
            self.status.set("Agente conectado")
        except Exception as error:
            logger.exception("No se pudo iniciar el agente")
            self.status.set(f"Error al iniciar: {error}")
            messagebox.showerror("EK Platform Agent", str(error))

    def stop_worker(self) -> None:
        if self.worker:
            self.worker.stop()
        self.status.set("Agente detenido")

    def hide_window(self) -> None:
        self.root.withdraw()

    def show_window(self) -> None:
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _start_tray(self) -> None:
        image = Image.new("RGBA", (64, 64), (29, 78, 216, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill=(255, 255, 255, 255))
        draw.text((22, 17), "EK", fill=(29, 78, 216, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar ventana", lambda _icon, _item: self.show_window()),
            pystray.MenuItem(
                "Iniciar agente", lambda _icon, _item: self.root.after(0, self.start_worker)
            ),
            pystray.MenuItem(
                "Detener agente", lambda _icon, _item: self.root.after(0, self.stop_worker)
            ),
            pystray.MenuItem("Salir", lambda _icon, _item: self.root.after(0, self.quit)),
        )
        self.tray = pystray.Icon("ek-platform-agent", image, "EK Platform Agent", menu)
        if sys.platform == "darwin":
            # AppKit requires its event loop to share the main Tk loop.
            self.tray.run_detached()
        else:
            threading.Thread(target=self.tray.run, name="tray", daemon=True).start()

    def quit(self) -> None:
        self.stop_worker()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def _notify(self, message: str) -> None:
        self.root.after(0, self.status.set, message)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
