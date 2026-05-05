from core.autoexec_policy import (
    can_autoexecute_command,
    max_autoexec_rounds,
    should_replay_command_result,
    should_retry_missing_tool,
)


def test_max_autoexec_rounds_allows_more_admin_turns():
    assert max_autoexec_rounds(True, "admin") == 20
    assert max_autoexec_rounds(True, "user") == 8
    assert max_autoexec_rounds(False, "admin") == 5


def test_user_autoexec_allows_read_only_bash_only():
    assert can_autoexecute_command('bash "ls -la"', "user") is True
    assert can_autoexecute_command('bash "git status"', "user") is True
    assert can_autoexecute_command('bash "git checkout main"', "user") is False
    assert can_autoexecute_command('write "x.py" --content="print(1)"', "user") is False


def test_admin_autoexec_still_rejects_blacklisted_patterns():
    assert can_autoexecute_command('write "x.py" --content="print(1)"', "admin") is True
    assert can_autoexecute_command('bash "sudo apt-get update"', "admin") is False


def test_should_replay_failed_command_unless_interactive_sudo():
    assert should_replay_command_result(True, "admin", "failed", "execution_failed") is True
    assert (
        should_replay_command_result(
            True,
            "admin",
            "failed",
            "execution_failed",
            "sudo: a terminal is required",
        )
        is False
    )


def test_should_retry_missing_tool_when_response_promises_action():
    assert should_retry_missing_tool(True, "crie app.py", "Vou criar o arquivo agora.", None) is True
    assert should_retry_missing_tool(False, "crie app.py", "Vou criar o arquivo agora.", None) is False

