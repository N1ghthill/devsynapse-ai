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
SIDEBAR_PANELS = ("model", "telemetry")

DEFAULT_UI_CONFIG: dict[str, Any] = {
    "chat": {
        "max_lines": 2000,
    },
    "theme": "dark",
    "layout": "default",
    "sidebar": {
        "collapsed_panels": {
            "model": False,
            "telemetry": False,
        },
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
    chat_max_lines: int
    sidebar_collapsed: dict[str, bool]

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
        chat_max_lines=_normalized_int(
            os.getenv("DEVSYNAPSE_TUI_MAX_LINES")
            or _nested_value(data, "chat", "max_lines"),
            default=2000,
            minimum=200,
            maximum=20000,
        ),
        sidebar_collapsed=_normalized_sidebar_collapsed(data.get("sidebar")),
    )


def save_tui_preferences(
    *,
    theme: str | None = None,
    layout: str | None = None,
    sidebar_collapsed: dict[str, bool] | None = None,
    config_file: Path | None = None,
) -> TUIPreferences:
    """Persist TUI appearance preferences and return the resolved values."""
    config_file = config_file or _default_config_file()
    data = _read_or_create_config(config_file)
    if theme is not None:
        data["theme"] = _normalized_choice(theme, allowed=ALLOWED_THEMES, default="dark")
    if layout is not None:
        data["layout"] = _normalized_choice(layout, allowed=ALLOWED_LAYOUTS, default="default")
    chat = data.get("chat") if isinstance(data.get("chat"), dict) else {}
    data["chat"] = {**DEFAULT_UI_CONFIG["chat"], **chat}
    sidebar = data.get("sidebar") if isinstance(data.get("sidebar"), dict) else {}
    if sidebar_collapsed is not None:
        sidebar["collapsed_panels"] = _normalized_sidebar_collapsed(
            {"collapsed_panels": sidebar_collapsed}
        )
    data["sidebar"] = {**DEFAULT_UI_CONFIG["sidebar"], **sidebar}
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
        return _default_ui_config()

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_ui_config()
    if not isinstance(parsed, dict):
        return _default_ui_config()
    return parsed


def _normalized_choice(value: object, *, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _normalized_int(
    value: object,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _nested_value(data: dict[str, Any], section: str, key: str) -> object:
    section_data = data.get(section)
    if not isinstance(section_data, dict):
        return None
    return section_data.get(key)


def _default_ui_config() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_UI_CONFIG))


def _normalized_sidebar_collapsed(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        value = {}
    collapsed = value.get("collapsed_panels")
    if not isinstance(collapsed, dict):
        collapsed = {}
    return {
        panel: bool(collapsed.get(panel, False))
        for panel in SIDEBAR_PANELS
    }
