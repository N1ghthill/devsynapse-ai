"""
Sistema de plugins/extensões do DevSynapse
"""
import asyncio
import importlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str
    entry_point: str
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    min_api_version: str = "0.1.0"
    hooks: List[str] = field(default_factory=list)


@dataclass
class PluginEvent:
    name: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    cancelled: bool = False


HookHandler = Callable[..., Awaitable[Optional[Dict[str, Any]]]]


class PluginContext:
    def __init__(self, plugin_name: str, plugin_dir: Path):
        self.plugin_name = plugin_name
        self.plugin_dir = plugin_dir
        self.logger = logging.getLogger(f"plugin.{plugin_name}")
        self._storage: Dict[str, Any] = {}

    async def get_storage(self, key: str, default: Any = None) -> Any:
        return self._storage.get(key, default)

    async def set_storage(self, key: str, value: Any):
        self._storage[key] = value

    async def log(self, level: str, message: str):
        getattr(self.logger, level, self.logger.info)(message)


class BasePlugin:
    manifest: PluginManifest

    def __init__(self, context: PluginContext):
        self.context = context

    async def on_load(self):
        pass

    async def on_unload(self):
        pass

    async def on_activate(self):
        pass

    async def on_deactivate(self):
        pass


PLUGIN_EVENTS = {
    "brain:before_process": "Antes de processar mensagem",
    "brain:after_process": "Após processar mensagem",
    "brain:before_llm_call": "Antes de chamar LLM",
    "brain:after_llm_call": "Após chamar LLM",
    "command:before_execute": "Antes de executar comando",
    "command:after_execute": "Após executar comando",
    "memory:before_save": "Antes de salvar na memória",
    "memory:after_save": "Após salvar na memória",
    "server:startup": "Inicialização do servidor",
    "server:shutdown": "Desligamento do servidor",
}

BUILTIN_HOOKS: Dict[str, str] = {
    "pre_process_message": "brain:before_process",
    "post_process_message": "brain:after_process",
    "pre_llm_call": "brain:before_llm_call",
    "post_llm_call": "brain:after_llm_call",
    "pre_command_execute": "command:before_execute",
    "post_command_execute": "command:after_execute",
    "pre_memory_save": "memory:before_save",
    "post_memory_save": "memory:after_save",
    "on_server_startup": "server:startup",
    "on_server_shutdown": "server:shutdown",
}


class PluginManager:
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._manifests: Dict[str, PluginManifest] = {}
        self._hook_handlers: Dict[str, List[HookHandler]] = {
            event: [] for event in PLUGIN_EVENTS
        }
        self._loaded = False

    async def discover_plugins(self) -> List[PluginManifest]:
        manifests = []
        plugins_dir = PLUGINS_DIR
        plugins_dir.mkdir(exist_ok=True)

        for entry in plugins_dir.iterdir():
            if entry.is_dir():
                manifest_file = entry / "manifest.json"
                if manifest_file.exists():
                    try:
                        data = json.loads(manifest_file.read_text())
                        manifest = PluginManifest(**data)
                        manifests.append(manifest)
                        logger.info(f"Plugin descoberto: {manifest.name} v{manifest.version}")
                    except Exception as e:
                        logger.warning(f"Erro lendo manifest de {entry.name}: {e}")

        return manifests

    async def load_plugin(self, manifest: PluginManifest) -> bool:
        try:
            plugin_dir = PLUGINS_DIR / manifest.name
            if not plugin_dir.exists():
                logger.error(f"Diretório do plugin não encontrado: {plugin_dir}")
                return False

            sys_path = str(plugin_dir)
            if sys_path not in importlib.sys.path:
                importlib.sys.path.insert(0, sys_path)

            module_path = manifest.entry_point.replace("/", ".").replace(".py", "")
            module = importlib.import_module(module_path)

            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj != BasePlugin):
                    plugin_class = obj
                    break

            if not plugin_class:
                logger.error(f"Plugin {manifest.name}: classe BasePlugin não encontrada em {manifest.entry_point}")
                return False

            context = PluginContext(manifest.name, plugin_dir)
            plugin_instance = plugin_class(context)
            plugin_instance.manifest = manifest

            for hook_name in manifest.hooks:
                if hook_name in BUILTIN_HOOKS:
                    event_name = BUILTIN_HOOKS[hook_name]
                    method = getattr(plugin_instance, hook_name, None)
                    if method and callable(method):
                        self._hook_handlers[event_name].append(method)
                        logger.debug(f"Plugin {manifest.name}: hook '{hook_name}' registrado para evento '{event_name}'")

            await plugin_instance.on_load()
            self._plugins[manifest.name] = plugin_instance
            self._manifests[manifest.name] = manifest

            logger.info(f"Plugin carregado: {manifest.name} v{manifest.version}")
            return True

        except Exception as e:
            logger.error(f"Erro carregando plugin {manifest.name}: {e}", exc_info=True)
            return False

    async def unload_plugin(self, name: str) -> bool:
        if name not in self._plugins:
            return False

        try:
            plugin = self._plugins[name]
            await plugin.on_unload()

            for event_name in self._hook_handlers:
                self._hook_handlers[event_name] = [
                    h for h in self._hook_handlers[event_name]
                    if getattr(h, '__self__', None) is not plugin
                ]

            del self._plugins[name]
            del self._manifests[name]
            logger.info(f"Plugin removido: {name}")
            return True

        except Exception as e:
            logger.error(f"Erro removendo plugin {name}: {e}")
            return False

    async def load_all(self):
        manifests = await self.discover_plugins()
        for manifest in manifests:
            await self.load_plugin(manifest)
        self._loaded = True
        logger.info(f"PluginManager: {len(self._plugins)} plugins carregados")

    async def unload_all(self):
        for name in list(self._plugins.keys()):
            await self.unload_plugin(name)
        self._loaded = False
        logger.info("PluginManager: todos os plugins descarregados")

    async def emit_event(self, event_name: str, data: Dict[str, Any]) -> PluginEvent:
        event = PluginEvent(name=event_name, data=data)

        if event_name not in self._hook_handlers:
            return event

        for handler in self._hook_handlers[event_name]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)

                if result is not None:
                    event.data.update(result)

                if event.cancelled:
                    logger.debug(f"Evento {event_name} cancelado por handler")
                    break

            except Exception as e:
                logger.error(f"Erro em handler de {event_name}: {e}")

        return event

    @property
    def loaded_plugins(self) -> Dict[str, BasePlugin]:
        return dict(self._plugins)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        return self._manifests.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "version": m.version,
                "description": m.description,
                "author": m.author,
                "hooks": m.hooks,
                "permissions": m.permissions,
            }
            for name, m in self._manifests.items()
        ]


plugin_manager = PluginManager()
