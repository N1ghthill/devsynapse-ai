from core.checklist import (
    build_checklist_repair_messages,
    build_task_checklist,
    task_checklist_complete,
    update_task_checklist,
)


def test_task_checklist_tracks_expected_files_and_pytest():
    checklist = build_task_checklist("Crie app.py e rode pytest para os tests pass")

    assert checklist is not None
    assert checklist.expected_files == {"app.py"}
    assert checklist.requires_pytest is True
    assert task_checklist_complete(checklist) is False

    update_task_checklist(checklist, 'write "src/app.py" --content="print(1)"', None)
    update_task_checklist(checklist, 'bash "pytest -q"', "1 passed in 0.01s")

    assert task_checklist_complete(checklist) is True


def test_build_checklist_repair_messages_describes_missing_work():
    checklist = build_task_checklist("Crie app.py")

    assert checklist is not None
    messages = build_checklist_repair_messages("ok", checklist)

    assert messages[0]["role"] == "assistant"
    assert "Files missing: app.py" in messages[1]["content"]
