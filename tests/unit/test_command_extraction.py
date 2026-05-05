from core.command_extraction import (
    extract_opencode_command,
    normalize_bare_shell_line,
    tool_calls_to_opencode_command,
)


def test_tool_calls_to_opencode_command_escapes_write_content():
    command = tool_calls_to_opencode_command(
        [
            {
                "function": {
                    "name": "write",
                    "arguments": {
                        "path": "README.md",
                        "content": 'line 1\n"quoted"',
                    },
                }
            }
        ]
    )

    assert command == 'write "README.md" --content="line 1\\n\\"quoted\\""'


def test_extract_opencode_command_prefers_last_command():
    response = 'First read "a.py"\nThen bash "pytest -q"'

    assert extract_opencode_command(response) == 'bash "pytest -q"'


def test_extract_flexible_bare_shell_command():
    assert extract_opencode_command("```bash\nls -la\n```") == 'bash "ls -la"'


def test_normalize_bare_shell_rejects_shell_operators():
    assert normalize_bare_shell_line("ls -la && rm -rf build") is None

