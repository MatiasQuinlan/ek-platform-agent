from ek_agent import config
from ek_agent.config import SERVICE, config_path


def test_service_name() -> None:
    assert SERVICE == "ek-platform-agent"
    assert config_path().name == "config.json"


def test_thread_ids_use_keyring_and_are_conversation_scoped(monkeypatch) -> None:
    values = {}
    monkeypatch.setattr(
        config.keyring, "get_password", lambda service, user: values.get((service, user))
    )
    monkeypatch.setattr(
        config.keyring,
        "set_password",
        lambda service, user, value: values.__setitem__((service, user), value),
    )

    config.set_thread_id("conversation-1", "thread-1")
    assert config.get_thread_id("conversation-1") == "thread-1"
    assert config.get_thread_id("conversation-2") is None
    assert values == {(SERVICE, "codex-thread:conversation-1"): "thread-1"}
