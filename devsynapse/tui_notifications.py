"""Toast notification system for DevSynapse AI TUI."""
from __future__ import annotations

import asyncio
from typing import Literal

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

NotificationType = Literal["success", "error", "info", "warning"]

NOTIFICATION_ICONS = {
    "success": "OK",
    "error": "ERR",
    "info": "INFO",
    "warning": "WARN",
}


class ToastNotification(Static):
    """A single toast notification widget."""

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
        self.add_class(f"toast-{notification_type}")

    def compose(self) -> ComposeResult:
        icon = NOTIFICATION_ICONS[self.notification_type]
        yield Static(f"[bold]{icon}[/] {self.message}", classes="toast-message")

    async def on_mount(self) -> None:
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
