from config.settings import AppSettings
from core.desktop_conversation import has_provider_key


def test_has_provider_key_detects_configured_provider():
    settings = AppSettings()
    settings.deepseek_api_key = None
    settings.openrouter_api_key = None
    settings.opencode_zen_api_key = None
    settings.opencode_go_api_key = None

    assert has_provider_key(settings) is False

    settings.openrouter_api_key = "sk-test"

    assert has_provider_key(settings) is True
