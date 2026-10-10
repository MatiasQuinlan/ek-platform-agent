import io
import json

from ek_agent import codex


class FakeProcess:
    def __init__(self, lines: list[dict]) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("".join(json.dumps(line) + "\n" for line in lines))
        self.stderr = io.StringIO()
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


def test_persistent_executor_initializes_thread_and_collects_turn_deltas() -> None:
    process = FakeProcess(
        [
            {"jsonrpc": "2.0", "id": 1, "result": {}},
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "result": {"thread": {"id": "thread-1"}}},
            {"jsonrpc": "2.0", "id": 3, "result": {"turn": {"id": "turn-1"}}},
            {"jsonrpc": "2.0", "method": "item/agentMessage/delta", "params": {"delta": "Hola "}},
            {"jsonrpc": "2.0", "method": "item/agentMessage/delta", "params": {"delta": "mundo"}},
            {"jsonrpc": "2.0", "method": "turn/completed", "params": {}},
        ]
    )
    launched = []

    def popen(*args, **kwargs):
        launched.append((args, kwargs))
        return process

    executor = codex.PersistentCodexExecutor("codex", popen=popen)

    assert executor.execute("prompt") == "Hola mundo"
    assert launched[0][0] == (["codex", "app-server", "--listen", "stdio://"],)
    requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
    assert [request.get("method") for request in requests] == [
        "initialize",
        "initialized",
        "thread/start",
        "turn/start",
    ]
    assert "access_token" not in process.stdin.getvalue()
    executor.close()
    assert json.loads(process.stdin.getvalue().splitlines()[-1])["method"] == "shutdown"


def test_executor_factory_uses_legacy_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EK_CODEX_APP_SERVER", raising=False)
    assert isinstance(codex.create_executor(), codex.CodexExecExecutor)


def test_executor_factory_uses_app_server_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("EK_CODEX_APP_SERVER", "true")
    monkeypatch.setattr(codex, "_codex_path", lambda: "/usr/local/bin/codex")
    executor = codex.create_executor()
    assert isinstance(executor, codex.PersistentCodexExecutor)
    executor.close()
