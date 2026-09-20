from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from .backend import BackendClient
from .codex import execute


class Worker:
    def __init__(self, client: BackendClient, notify: Callable[[str], None]) -> None:
        self.client = client
        self.notify = notify
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self.client.next_job()
                if job:
                    self.notify(f"Procesando {job.get('jobId', '')}")
                    context = json.dumps(job.get("contextBundle", {}), ensure_ascii=False)
                    prompt = (
                        "Actúa como asistente editorial de EK Platform. Usa solo el contexto "
                        f"del cliente autorizado. Devuelve JSON con title, content y citations. "
                        f"Solicitud: {job['query']} Contexto: {context}"
                    )
                    output = execute(prompt)
                    try:
                        result: dict[str, Any] = json.loads(output)
                    except json.JSONDecodeError:
                        result = {"title": "AI draft", "content": output, "citations": []}
                    self.client.complete(job, result)
                    self.notify("Trabajo completado")
            except Exception as error:  # noqa: BLE001 - keep the tray agent alive
                self.notify(f"Agente: {error}")
            self._stop.wait(3)
