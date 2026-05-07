"""Tests for the onboarding wizard screen."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from devsynapse.screens.onboarding import ONBOARDING_STEPS, OnboardingScreen
from devsynapse.tui import DevSynapseTUI


class TestOnboardingSteps:
    def test_has_five_steps(self):
        assert len(ONBOARDING_STEPS) == 5

    def test_first_step_is_welcome(self):
        assert ONBOARDING_STEPS[0]["id"] == "welcome"
        assert "Bem-vindo" in ONBOARDING_STEPS[0]["title"]

    def test_last_step_is_complete(self):
        assert ONBOARDING_STEPS[-1]["id"] == "complete"
        assert "Pronto" in ONBOARDING_STEPS[-1]["title"]

    def test_all_steps_have_title_and_description(self):
        for step in ONBOARDING_STEPS:
            assert "title" in step
            assert "description" in step
            assert len(step["title"]) > 0
            assert len(step["description"]) > 0

    def test_steps_have_unique_ids(self):
        ids = [step["id"] for step in ONBOARDING_STEPS]
        assert len(ids) == len(set(ids))


class TestOnboardingScreen:
    def test_initial_state(self):
        screen = OnboardingScreen()
        assert screen.current_step == 0
        assert screen.selected_provider == "openrouter"
        assert screen.api_key == ""
        assert screen.selected_theme == "dark"

    def test_css_is_defined(self):
        screen = OnboardingScreen()
        assert screen.CSS is not None
        assert "#onboarding-container" in screen.CSS

    def test_bindings_defined(self):
        screen = OnboardingScreen()
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in screen.BINDINGS]
        assert "escape" in binding_keys


class TestOnboardingCompletion:
    def test_onboarding_completed_saved_to_ui_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVSYNAPSE_HOME", str(tmp_path))
        monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(tmp_path / "config" / ".env"))

        from devsynapse.tui_preferences import (
            load_tui_preferences,
            save_tui_preferences,
        )

        ui_config = tmp_path / "config" / "ui.json"
        ui_config.parent.mkdir(parents=True, exist_ok=True)
        ui_config.write_text('{"theme": "dark", "onboarding_completed": false}\n')

        prefs = load_tui_preferences(ui_config)
        assert prefs.onboarding_completed is False

        save_tui_preferences(onboarding_completed=True, config_file=ui_config)
        prefs = load_tui_preferences(ui_config)
        assert prefs.onboarding_completed is True

        data = json.loads(ui_config.read_text())
        assert data["onboarding_completed"] is True

    def test_onboarding_completed_defaults_to_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVSYNAPSE_HOME", str(tmp_path))
        monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(tmp_path / "config" / ".env"))

        from devsynapse.tui_preferences import load_tui_preferences

        ui_config = tmp_path / "config" / "ui.json"
        ui_config.parent.mkdir(parents=True, exist_ok=True)
        ui_config.write_text('{"theme": "dark"}\n')

        prefs = load_tui_preferences(ui_config)
        assert prefs.onboarding_completed is False

    @pytest.mark.asyncio
    async def test_onboarding_saves_provider_credentials(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVSYNAPSE_HOME", str(tmp_path / "runtime"))
        monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(tmp_path / "runtime" / "config" / ".env"))
        monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(tmp_path / "runtime" / "data"))
        monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(tmp_path / "runtime" / "logs"))
        monkeypatch.setenv("OPENROUTER_API_KEY", "")

        import config.settings as app_settings

        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = OnboardingScreen()
            await app.push_screen(screen)
            await pilot.pause()

            app._save_provider_credentials = AsyncMock()
            screen.selected_provider = "openrouter"
            screen.api_key = "sk-test"

            screen._complete_onboarding()
            await pilot.pause()

            app._save_provider_credentials.assert_awaited_once_with("openrouter", "sk-test")
            assert app.ui_preferences.onboarding_completed is True
