"""User-facing TUI appearance preferences."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import CONFIG_DIR

STYLE_DIR = Path(__file__).resolve().parent / "styles"
THEME_DIR = STYLE_DIR / "themes"
LAYOUT_DIR = STYLE_DIR / "layouts"

ALLOWED_THEMES = {"dark", "light", "dracula"}
ALLOWED_LAYOUTS = {"default", "dense"}

DEFAULT_UI_CONFIG: dict[str, Any] = {
    "theme": "dark",
    "layout": "default",
    "sidebar": {
        "visible": True,
    },
}

THEME_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "thinking": "#58a6ff",
        "streaming": "#79c0ff",
        "executing": "#d29922",
        "success": "#3fb950",
        "error": "#f85149",
        "warning": "#d29922",
        "user": "#58a6ff",
        "assistant": "#3fb950",
        "muted": "#8b949e",
        "title": "#58a6ff",
        "metric": "#79c0ff",
    },
    "light": {
        "thinking": "#0969da",
        "streaming": "#218bff",
        "executing": "#9a6700",
        "success": "#1a7f37",
        "error": "#cf222e",
        "warning": "#9a6700",
        "user": "#0969da",
        "assistant": "#1a7f37",
        "muted": "#57606a",
        "title": "#0969da",
        "metric": "#218bff",
    },
    "dracula": {
        "thinking": "#8be9fd",
        "streaming": "#bd93f9",
        "executing": "#f1fa8c",
        "success": "#50fa7b",
        "error": "#ff5555",
        "warning": "#ffb86c",
        "user": "#8be9fd",
        "assistant": "#50fa7b",
        "muted": "#bfbfd8",
        "title": "#ff79c6",
        "metric": "#8be9fd",
    },
}


@dataclass(frozen=True)
class TUIPreferences:
    """Resolved TUI preferences and style assets."""

    theme: str
    layout: str
    config_file: Path
    palette: dict[str, str]

    @property
    def css_paths(self) -> list[Path]:
        return [
            STYLE_DIR / "base.tcss",
            THEME_DIR / f"{self.theme}.tcss",
            LAYOUT_DIR / f"{self.layout}.tcss",
        ]


def load_tui_preferences(config_file: Path | None = None) -> TUIPreferences:
    """Load TUI preferences from JSON, creating a default file when needed."""
    config_file = config_file or _default_config_file()
    data = _read_or_create_config(config_file)

    theme = _normalized_choice(
        os.getenv("DEVSYNAPSE_TUI_THEME") or data.get("theme"),
        allowed=ALLOWED_THEMES,
        default="dark",
    )
    layout = _normalized_choice(
        os.getenv("DEVSYNAPSE_TUI_LAYOUT") or data.get("layout"),
        allowed=ALLOWED_LAYOUTS,
        default="default",
    )
    return TUIPreferences(
        theme=theme,
        layout=layout,
        config_file=config_file,
        palette=THEME_PALETTES[theme],
    )


def save_tui_preferences(
    *,
    theme: str | None = None,
    layout: str | None = None,
    config_file: Path | None = None,
) -> TUIPreferences:
    """Persist TUI appearance preferences and return the resolved values."""
    config_file = config_file or _default_config_file()
    data = _read_or_create_config(config_file)
    if theme is not None:
        data["theme"] = _normalized_choice(theme, allowed=ALLOWED_THEMES, default="dark")
    if layout is not None:
        data["layout"] = _normalized_choice(layout, allowed=ALLOWED_LAYOUTS, default="default")
    data.setdefault("sidebar", DEFAULT_UI_CONFIG["sidebar"])
    config_file.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return load_tui_preferences(config_file)


def _default_config_file() -> Path:
    configured = os.getenv("DEVSYNAPSE_TUI_CONFIG_FILE")
    return Path(configured).expanduser().resolve() if configured else CONFIG_DIR / "ui.json"


def _read_or_create_config(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            json.dumps(DEFAULT_UI_CONFIG, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return dict(DEFAULT_UI_CONFIG)

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_UI_CONFIG)
    if not isinstance(parsed, dict):
        return dict(DEFAULT_UI_CONFIG)
    return parsed


def _normalized_choice(value: object, *, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default
