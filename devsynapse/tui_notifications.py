"""Toast notification system for DevSynapse AI TUI."""
from __future__ import annotations

import asyncio
from typing import Literal

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

NotificationType = Literal["success", "error", "info", "warning"]

NOTIFICATION_STYLES = {
    "success": {"border": "#3fb950", "bg": "#0d1f0d", "fg": "#3fb950"},
    "error": {"border": "#f85149", "bg": "#1f0d0d", "fg": "#f85149"},
    "info": {"border": "#58a6ff", "bg": "#0d1520", "fg": "#58a6ff"},
    "warning": {"border": "#d29922", "bg": "#1f1a0d", "fg": "#d29922"},
}

NOTIFICATION_ICONS = {
    "success": "OK",
    "error": "ERR",
    "info": "INFO",
    "warning": "WARN",
}


class ToastNotification(Static):
    """A single toast notification widget."""

    DEFAULT_CSS = """
    ToastNotification {
        width: auto;
        max-width: 60;
        height: auto;
        padding: 1 2;
        border: round #58a6ff;
        background: #161b22;
        dock: top;
    }
    """

    def __init__(
        self,
        message: str,
        notification_type: NotificationType = "info",
        duration: float = 3.0,
    ) -> None:
        super().__init__()
        self.notification_type = notification_type
        self.duration = duration
        self.message = message

    def compose(self) -> ComposeResult:
        style = NOTIFICATION_STYLES[self.notification_type]
        icon = NOTIFICATION_ICONS[self.notification_type]
        yield Static(f"[bold {style['fg']}]{icon}[/] {self.message}")

    async def on_mount(self) -> None:
        style = NOTIFICATION_STYLES[self.notification_type]
        self.styles.border = ("round", style["border"])
        self.styles.background = style["bg"]
        if self.duration > 0:
            await asyncio.sleep(self.duration)
            await self.fade_out()

    async def fade_out(self) -> None:
        """Animate the notification out."""
        try:
            await self.remove()
        except Exception:
            pass


class NotificationManager(Vertical):
    """Manages a queue of toast notifications."""

    DEFAULT_CSS = """
    NotificationManager {
        dock: top;
        width: 100%;
        height: auto;
        layers: above;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._active_toasts: list[ToastNotification] = []

    def show(
        self,
        message: str,
        notification_type: NotificationType = "info",
        duration: float = 3.0,
    ) -> None:
        """Show a new toast notification."""
        toast = ToastNotification(message, notification_type, duration)
        self._active_toasts.append(toast)
        self.mount(toast)
        self._cleanup_old()

    def _cleanup_old(self) -> None:
        """Remove old notifications if we have too many."""
        max_toasts = 5
        if len(self._active_toasts) > max_toasts:
            old = self._active_toasts[:-max_toasts]
            for toast in old:
                try:
                    toast.remove()
                except Exception:
                    pass
            self._active_toasts = self._active_toasts[-max_toasts:]
