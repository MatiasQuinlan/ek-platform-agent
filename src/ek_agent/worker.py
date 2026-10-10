from __future__ import annotations

import inspect
import json
import threading
from collections.abc import Callable
from typing import Any

from .backend import BackendClient
from .codex import ExecutionInterface, create_executor
from .config import get_thread_id, set_thread_id


class Worker:
    def __init__(
        self,
        client: BackendClient,
        notify: Callable[[str], None],
        executor: ExecutionInterface | None = None,
    ) -> None:
        self.client = client
        self.notify = notify
        self.executor = executor or create_executor()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.executor.close()

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
                    sequence = 0

                    def publish(event: dict[str, Any], current_job: dict[str, Any] = job) -> None:
                        nonlocal sequence
                        sequence += 1
                        self.client.post_event(current_job, sequence, event)

                    conversation_id = str(job.get("conversationId", ""))
                    stored_thread_id = get_thread_id(conversation_id)
                    # Keep custom/legacy test executors and the original exec
                    # adapter compatible while allowing app-server executors
                    # to receive persistence and streaming hooks.
                    try:
                        parameters = inspect.signature(self.executor.execute).parameters
                    except (TypeError, ValueError):
                        parameters = {}
                    kwargs: dict[str, Any] = {}
                    accepts_kwargs = any(
                        parameter.kind is inspect.Parameter.VAR_KEYWORD
                        for parameter in parameters.values()
                    )
                    if "on_event" in parameters or accepts_kwargs:
                        kwargs["on_event"] = publish
                    elif "event_callback" in parameters:
                        kwargs["event_callback"] = publish
                    elif "callback" in parameters:
                        kwargs["callback"] = publish
                    if "thread_id" in parameters or accepts_kwargs:
                        kwargs["thread_id"] = stored_thread_id
                    output = self.executor.execute(prompt, **kwargs)
                    thread_id = getattr(self.executor, "thread_id", None)
                    if conversation_id and thread_id:
                        set_thread_id(conversation_id, thread_id)
                    try:
                        result: dict[str, Any] = json.loads(output)
                    except json.JSONDecodeError:
                        result = {"title": "AI draft", "content": output, "citations": []}
                    self.client.complete(job, result)
                    self.notify("Trabajo completado")
            except Exception as error:  # noqa: BLE001 - keep the tray agent alive
                self.notify(f"Agente: {error}")
            self._stop.wait(3)
