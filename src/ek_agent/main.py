from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .backend import BackendClient
from .codex import installed, login
from .config import get_access_token, load, save, set_access_token
from .worker import Worker


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EK Platform Agent")
        self.root.geometry("520x300")
        values = load()
        self.api = tk.StringVar(value=values.get("api_url", ""))
        self.token = tk.StringVar(value="")
        self.status = tk.StringVar(value="Desconectado")
        self.worker: Worker | None = None
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="EK Platform Agent", font=("TkDefaultFont", 16, "bold")).pack()
        ttk.Label(frame, text="API del backend").pack(anchor="w", pady=(18, 0))
        ttk.Entry(frame, textvariable=self.api).pack(fill="x")
        ttk.Label(frame, text="Token Cognito de la aplicación").pack(anchor="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.token, show="*").pack(fill="x")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=16)
        ttk.Button(buttons, text="Conectar ChatGPT", command=self.connect_codex).pack(side="left")
        ttk.Button(buttons, text="Iniciar agente", command=self.start_worker).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Detener", command=self.stop_worker).pack(side="left")
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
                    message = "ChatGPT conectado. Configura la API y pulsa Iniciar agente."
                else:
                    message = f"El login de ChatGPT terminó con código {return_code}."
                self.root.after(0, self.status.set, message)

            threading.Thread(target=wait_for_login, daemon=True).start()
        except RuntimeError as error:
            messagebox.showerror("Codex", str(error))

    def start_worker(self) -> None:
        token = self.token.get() or get_access_token()
        if not self.api.get() or not token:
            messagebox.showwarning("Configuración", "Indica la API y el token Cognito")
            return
        set_access_token(token)
        save({"api_url": self.api.get()})
        client = BackendClient(self.api.get(), token)
        self.worker = Worker(client, self._notify)
        self.worker.start()
        self.status.set("Agente conectado")

    def stop_worker(self) -> None:
        if self.worker:
            self.worker.stop()
        self.status.set("Agente detenido")

    def _notify(self, message: str) -> None:
        self.root.after(0, self.status.set, message)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
