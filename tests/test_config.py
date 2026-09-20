from ek_agent.config import SERVICE, config_path


def test_service_name() -> None:
    assert SERVICE == "ek-platform-agent"
    assert config_path().name == "config.json"
