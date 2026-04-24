"""
Plugin de exemplo - DevSynapse Extension System
"""
from datetime import datetime

from core.plugin_system import BasePlugin, PluginEvent


class ExamplePlugin(BasePlugin):

    async def on_load(self):
        await self.context.log("info", "ExamplePlugin carregado")

    async def on_unload(self):
        await self.context.log("info", "ExamplePlugin descarregado")

    async def on_server_startup(self, event: PluginEvent) -> None:
        await self.context.log("info", "Servidor iniciou!")
        event.data["example_plugin_loaded"] = True

    async def on_server_shutdown(self, event: PluginEvent) -> None:
        await self.context.log("info", "Servidor desligando...")

    async def pre_process_message(self, event: PluginEvent) -> None:
        message = event.data.get("message", "")
        msg_lower = message.lower()

        if "ping" in msg_lower:
            await self.context.set_storage("last_ping", datetime.now().isoformat())
            await self.context.log("debug", f"Ping detectado: {message[:50]}")

        if "exemplo" in msg_lower:
            event.data["plugin_modified"] = True

    async def post_process_message(self, event: PluginEvent) -> None:
        response = event.data.get("response", "")

        last_ping = await self.context.get_storage("last_ping")
        if last_ping and "pong" not in response.lower():
            event.data["response"] = response + "\n\n> 📡 *ExemploPlugin ativo* — latency check: OK"
