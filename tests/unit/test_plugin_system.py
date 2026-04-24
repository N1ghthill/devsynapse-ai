"""
Unit tests for plugin system
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from core.plugin_system import (
    PluginManager, PluginContext, PluginEvent, BasePlugin,
    PluginManifest, PLUGIN_EVENTS, BUILTIN_HOOKS, plugin_manager
)


@pytest.fixture(autouse=True)
def reset_plugin_manager():
    plugin_manager._plugins.clear()
    plugin_manager._manifests.clear()
    for event in plugin_manager._hook_handlers:
        plugin_manager._hook_handlers[event].clear()
    plugin_manager._loaded = False


class TestPluginManifest:
    def test_minimal_manifest(self):
        m = PluginManifest(name="test", version="1.0", description="desc", author="me", entry_point="main.py")
        assert m.name == "test"
        assert m.dependencies == []
        assert m.permissions == []
        assert m.min_api_version == "0.1.0"

    def test_full_manifest(self):
        m = PluginManifest(
            name="full", version="2.0", description="full desc", author="dev",
            entry_point="plugin.py", dependencies=["requests"],
            permissions=["read_memory"], hooks=["pre_process_message"],
            min_api_version="0.2.0"
        )
        assert m.dependencies == ["requests"]
        assert m.permissions == ["read_memory"]
        assert m.hooks == ["pre_process_message"]


class TestPluginEvent:
    def test_event_creation(self):
        event = PluginEvent(name="test:event", data={"key": "value"})
        assert event.name == "test:event"
        assert event.data == {"key": "value"}
        assert event.cancelled is False

    def test_event_cancel(self):
        event = PluginEvent(name="test:event", data={})
        event.cancelled = True
        assert event.cancelled is True


class TestPluginContext:
    @pytest.fixture
    def ctx(self, tmp_path):
        return PluginContext("test-plugin", tmp_path)

    @pytest.mark.asyncio
    async def test_storage(self, ctx):
        await ctx.set_storage("key1", "value1")
        assert await ctx.get_storage("key1") == "value1"
        assert await ctx.get_storage("nonexistent") is None
        assert await ctx.get_storage("nonexistent", "default") == "default"


class TestPluginManager:
    @pytest.mark.asyncio
    async def test_initial_state(self):
        pm = PluginManager()
        assert pm.loaded_plugins == {}
        assert pm._loaded is False

    @pytest.mark.asyncio
    async def test_discover_no_plugins_dir(self, tmp_path):
        with patch("core.plugin_system.PLUGINS_DIR", tmp_path / "nonexistent"):
            pm = PluginManager()
            manifests = await pm.discover_plugins()
            assert manifests == []

    @pytest.mark.asyncio
    async def test_discover_empty_plugins_dir(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        with patch("core.plugin_system.PLUGINS_DIR", plugins_dir):
            pm = PluginManager()
            manifests = await pm.discover_plugins()
            assert manifests == []

    @pytest.mark.asyncio
    async def test_discover_with_plugin(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test-plugin"
        plugin_dir.mkdir(parents=True)
        manifest = {
            "name": "test-plugin", "version": "1.0", "description": "desc",
            "author": "me", "entry_point": "main.py"
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))

        with patch("core.plugin_system.PLUGINS_DIR", plugins_dir):
            pm = PluginManager()
            manifests = await pm.discover_plugins()
            assert len(manifests) == 1
            assert manifests[0].name == "test-plugin"

    @pytest.mark.asyncio
    async def test_load_plugin_module_not_found(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "missing-mod"
        plugin_dir.mkdir(parents=True)
        manifest_data = {
            "name": "missing-mod", "version": "1.0", "description": "desc",
            "author": "me", "entry_point": "nonexistent.py"
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = PluginManifest(**manifest_data)

        with patch("core.plugin_system.PLUGINS_DIR", plugins_dir):
            pm = PluginManager()
            result = await pm.load_plugin(manifest)
            assert result is False

    @pytest.mark.asyncio
    async def test_load_and_unload_plugin(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "testable"
        plugin_dir.mkdir(parents=True)

        plugin_code = '''
from core.plugin_system import BasePlugin, PluginContext

class TestablePlugin(BasePlugin):
    loaded = False
    unloaded = False

    async def on_load(self):
        TestablePlugin.loaded = True

    async def on_unload(self):
        TestablePlugin.unloaded = True
'''
        (plugin_dir / "main.py").write_text(plugin_code)
        manifest_data = {
            "name": "testable", "version": "1.0", "description": "desc",
            "author": "me", "entry_point": "main.py"
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = PluginManifest(**manifest_data)

        with patch("core.plugin_system.PLUGINS_DIR", plugins_dir):
            pm = PluginManager()
            result = await pm.load_plugin(manifest)
            assert result is True
            assert "testable" in pm.loaded_plugins
            plugin = pm.get_plugin("testable")
            assert plugin is not None

            result2 = await pm.unload_plugin("testable")
            assert result2 is True
            assert "testable" not in pm.loaded_plugins

    @pytest.mark.asyncio
    async def test_unload_nonexistent(self):
        pm = PluginManager()
        result = await pm.unload_plugin("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_plugins(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "listed"
        plugin_dir.mkdir(parents=True)

        plugin_code = "from core.plugin_system import BasePlugin\nclass ListedPlugin(BasePlugin): pass\n"
        (plugin_dir / "main.py").write_text(plugin_code)
        manifest_data = {
            "name": "listed", "version": "2.0", "description": "a listed plugin",
            "author": "dev", "entry_point": "main.py"
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = PluginManifest(**manifest_data)

        with patch("core.plugin_system.PLUGINS_DIR", plugins_dir):
            pm = PluginManager()
            await pm.load_plugin(manifest)
            plugins_list = pm.list_plugins()
            assert len(plugins_list) == 1
            entry = plugins_list[0]
            assert entry["name"] == "listed"
            assert entry["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_emit_event_no_handlers(self):
        pm = PluginManager()
        event = await pm.emit_event("brain:before_process", {"msg": "hello"})
        assert event.name == "brain:before_process"
        assert event.cancelled is False

    @pytest.mark.asyncio
    async def test_emit_event_with_handler(self):
        pm = PluginManager()
        received = []

        async def handler(event):
            received.append(event.data)
            event.data["modified"] = True

        pm._hook_handlers["brain:before_process"].append(handler)
        event = await pm.emit_event("brain:before_process", {"msg": "hello"})
        assert len(received) == 1
        assert event.data.get("modified") is True

    @pytest.mark.asyncio
    async def test_emit_event_cancelled(self):
        pm = PluginManager()
        async def cancel_handler(event):
            event.cancelled = True

        async def should_not_run(event):
            pytest.fail("This handler should not run after cancel")

        pm._hook_handlers["brain:before_process"].append(cancel_handler)
        pm._hook_handlers["brain:before_process"].append(should_not_run)
        event = await pm.emit_event("brain:before_process", {"msg": "hi"})
        assert event.cancelled is True

    @pytest.mark.asyncio
    async def test_emit_event_handler_error_does_not_block(self):
        pm = PluginManager()
        async def broken_handler(event):
            raise RuntimeError("handler error")

        async def good_handler(event):
            event.data["ok"] = True

        pm._hook_handlers["brain:before_process"].append(broken_handler)
        pm._hook_handlers["brain:before_process"].append(good_handler)
        event = await pm.emit_event("brain:before_process", {"msg": "hi"})
        assert event.data.get("ok") is True

    @pytest.mark.asyncio
    async def test_get_plugin_nonexistent(self):
        pm = PluginManager()
        assert pm.get_plugin("ghost") is None
        assert pm.get_manifest("ghost") is None

    @pytest.mark.asyncio
    async def test_load_all_empty(self):
        with patch.object(PluginManager, "discover_plugins", return_value=[]):
            pm = PluginManager()
            await pm.load_all()
            assert pm._loaded is True
            assert pm.loaded_plugins == {}

    @pytest.mark.asyncio
    async def test_unload_all(self):
        pm = PluginManager()
        p = AsyncMock()
        m = MagicMock()
        pm._plugins["p1"] = p
        pm._manifests["p1"] = m
        await pm.unload_all()
        assert pm._loaded is False
        assert pm.loaded_plugins == {}

    def test_builtin_hooks_map_to_events(self):
        for hook, event in BUILTIN_HOOKS.items():
            assert event in PLUGIN_EVENTS, f"Hook {hook} -> {event} not in PLUGIN_EVENTS"

    def test_plugin_events_defined(self):
        expected = [
            "brain:before_process", "brain:after_process",
            "brain:before_llm_call", "brain:after_llm_call",
            "command:before_execute", "command:after_execute",
            "memory:before_save", "memory:after_save",
            "server:startup", "server:shutdown",
        ]
        for event in expected:
            assert event in PLUGIN_EVENTS, f"Missing event: {event}"
