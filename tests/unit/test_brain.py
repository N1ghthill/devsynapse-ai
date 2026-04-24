"""
Unit tests for brain system
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

from core.brain import DevSynapseBrain


@pytest.fixture
def mock_memory():
    memory = Mock()
    memory.get_user_preferences.return_value = "Usuário prefere Python e VS Code"
    memory.get_projects_context.return_value = "Projeto: DevSynapse AI"
    memory.get_conversation_context = AsyncMock(return_value={
        "conversation_history": [],
        "user_preferences": "Python",
        "projects_context": "DevSynapse",
        "recent_decisions": []
    })
    memory.save_interaction = AsyncMock()
    memory.save_command_execution = AsyncMock()
    return memory


@pytest.fixture
def mock_bridge():
    bridge = Mock()
    bridge.execute_command.return_value = {
        "success": True,
        "output": "Command executed",
        "error": None
    }
    return bridge


class TestDevSynapseBrain:
    """Test DevSynapseBrain class"""

    def test_init(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        assert brain.memory == mock_memory
        assert brain.opencode == mock_bridge

    def test_init_without_api_key(self, mock_memory, mock_bridge):
        import config.settings as settings
        orig = settings.DEEPSEEK_API_KEY
        settings.DEEPSEEK_API_KEY = None
        try:
            brain = DevSynapseBrain(mock_memory, mock_bridge)
            assert brain.api_key is None
        finally:
            settings.DEEPSEEK_API_KEY = orig

    def test_generate_system_prompt(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        prompt = brain.generate_system_prompt({"test": "context"})
        assert "DevSynapse" in prompt
        assert "Irving" in prompt or "N1ghthill" in prompt
        assert "OpenCode" in prompt or "OPENCODE" in prompt

    @pytest.mark.asyncio
    async def test_process_message_calls_api(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Here is a response for you!"

            response, cmd, usage = await brain.process_message("Hello!", "test_session")

            assert response == "Here is a response for you!"
            assert cmd is None
            assert usage is None

        # Verify memory was saved
        mock_memory.save_interaction.assert_called_once()
        args = mock_memory.save_interaction.call_args[1]
        assert args["user_message"] == "Hello!"

    @pytest.mark.asyncio
    async def test_process_message_with_opencode_command(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = 'Here is the file list: bash "ls -la"'

            response, cmd, usage = await brain.process_message("List files", "test_session")

            assert cmd is not None
            assert "bash" in cmd
            assert "ls" in cmd
            assert usage is None

    @pytest.mark.asyncio
    async def test_process_message_sanitizes_unconfirmed_side_effect_claims(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (
                'echo "ok" > /tmp/test.txt\n\n'
                "Feito! Criei o arquivo para você."
            )

            response, cmd, usage = await brain.process_message("Crie um arquivo", "test_session")

            assert cmd is None
            assert "Ainda não executei nenhuma alteração" in response
            assert usage is None

    @pytest.mark.asyncio
    async def test_process_message_repairs_invalid_shell_into_opencode(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                'echo "ok" > /tmp/test.txt\n\nFeito! Criei o arquivo para você.',
                'write "/tmp/test.txt" --content="ok"',
            ]

            response, cmd, usage = await brain.process_message("Crie um arquivo", "test_session")

            assert cmd == 'write "/tmp/test.txt" --content="ok"'
            assert response == 'write "/tmp/test.txt" --content="ok"'
            assert mock_call.await_count == 2
            assert usage is None

    @pytest.mark.asyncio
    async def test_process_message_error_handling(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        # Mock the low-level Deepseek call to fail
        with patch.object(brain, '_call_deepseek_api', new_callable=AsyncMock) as mock_deepseek:
            mock_deepseek.side_effect = Exception("API connection failed")

            # Mock the fallback to test it's called
            with patch.object(brain, '_get_fallback_response') as mock_fallback:
                mock_fallback.return_value = "Fallback response"

                response, cmd, usage = await brain.process_message("Hello", "test_session")

                assert response == "Fallback response"
                assert cmd is None
                assert usage is None
                mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_deepseek_api_success(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.brain.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Hello from Deepseek!", "role": "assistant"}}],
                "model": "deepseek-chat",
                "usage": {
                    "prompt_tokens": 16,
                    "completion_tokens": 10,
                    "total_tokens": 26,
                },
            }
            mock_post.return_value = mock_response

            result = await brain._call_deepseek_api([{"role": "user", "content": "Hi"}])

            assert result.content == "Hello from Deepseek!"
            assert result.provider == "deepseek"
            assert result.usage["total_tokens"] == 26
            assert result.usage["prompt_cache_miss_tokens"] == 16
            assert result.usage["estimated_cost_usd"] == pytest.approx(0.00000504)
            mock_post.assert_called_once_with(
                f"{brain.deepseek_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {brain.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": brain.deepseek_model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "temperature": brain.temperature,
                    "max_tokens": brain.max_tokens,
                    "stream": False,
                },
                timeout=(5, brain.request_timeout),
            )

    def test_merge_usage_adds_prompt_tokens_and_cost(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        merged = brain._merge_usage(
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 40,
                "prompt_cache_miss_tokens": 60,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00002,
            },
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "prompt_cache_hit_tokens": 10,
                "prompt_cache_miss_tokens": 40,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00001,
            },
        )

        assert merged["prompt_tokens"] == 150
        assert merged["completion_tokens"] == 30
        assert merged["total_tokens"] == 180
        assert merged["prompt_cache_hit_tokens"] == 50
        assert merged["prompt_cache_miss_tokens"] == 100
        assert merged["estimated_cost_usd"] == pytest.approx(0.00003)

    @pytest.mark.asyncio
    async def test_call_deepseek_api_error(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.brain.requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            with pytest.raises(Exception):
                await brain._call_deepseek_api([{"role": "user", "content": "Hi"}])

    def test_extract_opencode_command_bash(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command('Vou listar: bash "ls -la"')
        assert command == 'bash "ls -la"'

    def test_extract_opencode_command_read(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command('Deixe-me ler: read "/path/to/file.py"')
        assert command == 'read "/path/to/file.py"'

    def test_extract_opencode_command_write(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = (
            'Vou criar o arquivo: write "/tmp/test.md" '
            '--content="# Teste\\n\\nConteudo de exemplo."'
        )
        command = brain._extract_opencode_command(response)
        assert command == 'write "/tmp/test.md" --content="# Teste\\n\\nConteudo de exemplo."'

    def test_extract_opencode_command_prefers_last_command(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = (
            'Primeiro vou localizar: bash "find /tmp -name test" '
            'depois ler: read "/tmp/test.md" '
            'e por fim criar: write "/tmp/out.md" --content="ok"'
        )
        command = brain._extract_opencode_command(response)
        assert command == 'write "/tmp/out.md" --content="ok"'

    def test_extract_opencode_command_normalizes_unquoted_bash_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "Vou listar a pasta agora.\n`bash ls -la /home/irving/ruas/repos`"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "ls -la /home/irving/ruas/repos"'

    def test_extract_opencode_command_normalizes_bare_shell_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "docker ps"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "docker ps"'

    def test_extract_opencode_command_normalizes_touch_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "touch /home/irving/Documentos/TESTE_ESCRITA.md"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "touch /home/irving/Documentos/TESTE_ESCRITA.md"'

    def test_extract_opencode_command_none(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command("This is just a regular conversation response")
        assert command is None

    def test_prepare_messages_with_history(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        context = {
            "conversation_history": [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"}
            ]
        }

        messages = brain._prepare_messages("New question", context)

        assert len(messages) == 4  # system + 2 history + user
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New question"

    def test_prepare_messages_no_history(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        context = {"conversation_history": []}

        messages = brain._prepare_messages("First question", context)

        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_get_fallback_response(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = brain._get_fallback_response([{"role": "user", "content": "Hello"}])

        assert len(response) > 0
        assert isinstance(response, str)

    def test_init_uses_llm_request_timeout(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        assert brain.request_timeout == 12
