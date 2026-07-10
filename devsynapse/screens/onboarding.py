"""Onboarding wizard screen for first-time DevSynapse AI users."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ONBOARDING_STEPS = [
    {
        "id": "welcome",
        "title": "Bem-vindo ao DevSynapse AI!",
        "description": "Seu copiloto local para projetos e repositórios.",
    },
    {
        "id": "provider",
        "title": "Escolha seu Provedor LLM",
        "description": "Selecione o provedor que deseja usar.",
    },
    {
        "id": "api_key",
        "title": "Configure sua API Key",
        "description": "Cole a chave de API do provedor selecionado.",
    },
    {
        "id": "theme",
        "title": "Personalize sua Experiência",
        "description": "Escolha o tema visual que prefere.",
    },
    {
        "id": "complete",
        "title": "Tudo Pronto!",
        "description": "DevSynapse AI está configurado e pronto para uso.",
    },
]


class OnboardingScreen(Screen):
    """Wizard interativo de primeira configuração."""

    CSS = """
    OnboardingScreen {
        align: center middle;
    }

    #onboarding-container {
        width: 80;
        height: 24;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #step-title {
        text-style: bold;
        color: $primary;
        content-align: center top;
        width: 100%;
        height: 3;
    }

    #step-description {
        color: $text-muted;
        content-align: center top;
        width: 100%;
        height: 3;
    }

    #step-content {
        width: 100%;
        height: 1fr;
        padding: 1 0;
    }

    #progress-bar {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }

    #button-row {
        width: 100%;
        height: 5;
        align: center middle;
    }

    #button-row Button {
        margin: 0 1;
        min-width: 15;
    }

    #api-key-input {
        width: 100%;
        margin: 1 0;
    }

    RadioSet {
        width: 100%;
        margin: 1 0;
    }

    .provider-option {
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "skip_onboarding", "Pular"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_step = 0
        self.selected_provider = "openrouter"
        self.api_key = ""
        self.selected_theme = "dark"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="onboarding-container"):
            yield Label("", id="step-title")
            yield Label("", id="step-description")
            with Container(id="step-content"):
                pass
            yield Label("", id="progress-bar")
            with Horizontal(id="button-row"):
                yield Button("← Anterior", id="btn-previous", variant="default")
                yield Button("Pular", id="btn-skip", variant="default")
                yield Button("Próximo →", id="btn-next", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._update_step()

    def _update_step(self) -> None:
        """Atualiza a tela com o conteúdo do passo atual."""
        step = ONBOARDING_STEPS[self.current_step]

        title = self.query_one("#step-title", Label)
        title.update(step["title"])

        description = self.query_one("#step-description", Label)
        description.update(step["description"])

        content = self.query_one("#step-content", Container)
        content.remove_children()

        if step["id"] == "welcome":
            content.mount(self._welcome_content())
        elif step["id"] == "provider":
            content.mount(self._provider_content())
        elif step["id"] == "api_key":
            content.mount(self._api_key_content())
        elif step["id"] == "theme":
            content.mount(self._theme_content())
        elif step["id"] == "complete":
            content.mount(self._complete_content())

        progress = self.query_one("#progress-bar", Label)
        progress.update(f"Passo {self.current_step + 1} de {len(ONBOARDING_STEPS)}")

        previous_btn = self.query_one("#btn-previous", Button)
        previous_btn.disabled = self.current_step == 0

        next_btn = self.query_one("#btn-next", Button)
        if self.current_step == len(ONBOARDING_STEPS) - 1:
            next_btn.label = "Concluir ✓"
        else:
            next_btn.label = "Próximo →"

    def _welcome_content(self) -> Static:
        return Static(
            "\n".join([
                "DevSynapse AI é um copiloto de operações de repositório que roda localmente no seu terminal.",
                "",
                "✦ Orquestração inteligente de LLMs",
                "✦ Execução segura de comandos locais",
                "✦ Memória persistente em SQLite",
                "✦ Interface TUI rica e responsiva",
                "",
                "Vamos configurar seu assistente em poucos passos!",
            ])
        )

    def _provider_content(self) -> RadioSet:
        radio_set = RadioSet()
        radio_set.mount(
            RadioButton("OpenRouter (recomendado - modelo gratuito)", id="provider-openrouter", value=True),
            RadioButton("DeepSeek", id="provider-deepseek"),
            RadioButton("OpenCode Zen", id="provider-opencode-zen"),
            RadioButton("OpenCode Go", id="provider-opencode-go"),
        )
        return radio_set

    def _api_key_content(self) -> Vertical:
        vertical = Vertical()
        provider_label = self.selected_provider.replace("-", " ").title()
        vertical.mount(
            Label(f"API Key para {provider_label}:")
        )
        vertical.mount(
            Input(placeholder="Cole sua API key aqui...", id="api-key-input", password=True)
        )
        vertical.mount(
            Label(
                "\n[dim]Você também pode configurar depois com /connect dentro do TUI.[/]",
                markup=True,
            )
        )
        return vertical

    def _theme_content(self) -> RadioSet:
        radio_set = RadioSet()
        radio_set.mount(
            RadioButton("Dark (padrão)", id="theme-dark", value=True),
            RadioButton("Light", id="theme-light"),
            RadioButton("Dracula", id="theme-dracula"),
        )
        return radio_set

    def _complete_content(self) -> Static:
        return Static(
            "\n".join([
                "🎉 Configuração concluída!",
                "",
                f"Provedor: {self.selected_provider}",
                f"Tema: {self.selected_theme}",
                "",
                "Dicas rápidas:",
                "✦ /connect - Configurar provedores",
                "✦ /model - Selecionar modelo",
                "✦ /budget - Definir limites de gasto",
                "✦ /help - Ver todos os comandos",
                "",
                "Pressione 'Concluir' para começar a usar!",
            ])
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-next":
            self._handle_next()
        elif button_id == "btn-previous":
            self._handle_previous()
        elif button_id == "btn-skip":
            self._handle_skip()

    def _handle_next(self) -> None:
        """Avança para o próximo passo ou conclui o onboarding."""
        if self.current_step == len(ONBOARDING_STEPS) - 1:
            self._complete_onboarding()
            return

        self._save_current_step_data()
        self.current_step += 1
        self._update_step()

    def _handle_previous(self) -> None:
        """Volta para o passo anterior."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step()

    def _handle_skip(self) -> None:
        """Pula o onboarding e vai direto para o TUI."""
        self._complete_onboarding()

    def _save_current_step_data(self) -> None:
        """Salva os dados do passo atual."""
        step = ONBOARDING_STEPS[self.current_step]

        if step["id"] == "provider":
            radio_set = self.query_one(RadioSet)
            if radio_set.pressed_button:
                button_id = radio_set.pressed_button.id
                if button_id == "provider-openrouter":
                    self.selected_provider = "openrouter"
                elif button_id == "provider-deepseek":
                    self.selected_provider = "deepseek"
                elif button_id == "provider-opencode-zen":
                    self.selected_provider = "opencode-zen"
                elif button_id == "provider-opencode-go":
                    self.selected_provider = "opencode-go"

        elif step["id"] == "api_key":
            try:
                api_key_input = self.query_one("#api-key-input", Input)
                self.api_key = api_key_input.value.strip()
            except Exception:
                pass

        elif step["id"] == "theme":
            radio_set = self.query_one(RadioSet)
            if radio_set.pressed_button:
                button_id = radio_set.pressed_button.id
                if button_id == "theme-dark":
                    self.selected_theme = "dark"
                elif button_id == "theme-light":
                    self.selected_theme = "light"
                elif button_id == "theme-dracula":
                    self.selected_theme = "dracula"

    def _complete_onboarding(self) -> None:
        """Finaliza o onboarding e salva configurações."""
        self._save_current_step_data()

        app = self.app
        if hasattr(app, "apply_tui_preferences"):
            app.apply_tui_preferences(theme=self.selected_theme)

        from devsynapse.tui_preferences import save_tui_preferences
        config_file = getattr(getattr(app, "ui_preferences", None), "config_file", None)
        preferences = save_tui_preferences(
            onboarding_completed=True,
            config_file=config_file,
        )
        if hasattr(app, "ui_preferences"):
            app.ui_preferences = preferences

        if self.api_key:
            provider = self.selected_provider
            logger.info("Onboarding: configurando provider %s", provider)
            save_credentials = getattr(app, "_save_provider_credentials", None)
            if callable(save_credentials):
                task_factory = getattr(app, "_create_task", None)
                coro = save_credentials(provider, self.api_key)
                if callable(task_factory):
                    task_factory(coro)
                else:
                    asyncio.create_task(coro)

        self.dismiss(True)

    def action_skip_onboarding(self) -> None:
        self._complete_onboarding()
