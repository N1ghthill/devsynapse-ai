import os
import stat
from pathlib import Path

from core.runtime_config import set_runtime_config_values


def test_runtime_config_file_is_private_on_posix(tmp_path: Path):
    config_file = tmp_path / "config" / ".env"

    set_runtime_config_values({"OPENROUTER_API_KEY": "sk-test"}, config_file)

    assert config_file.read_text(encoding="utf-8") == "OPENROUTER_API_KEY=sk-test\n"
    if os.name != "nt":
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600
