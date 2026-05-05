"""
Command execution engine for DevSynapse.

Extracted from OpenCodeBridge to separate execution from orchestration.
"""
import glob as glob_module
import json
import logging
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.settings import get_settings

logger = logging.getLogger(__name__)

COMMAND_TIMEOUTS: Dict[str, int] = {
    "bash": 30,
    "grep": 60,
    "read": 5,
    "glob": 5,
    "edit": 10,
    "write": 10,
}


class CommandExecutor:
    """Executes OpenCode commands (bash, read, glob, grep, edit, write)."""

    def __init__(
        self,
        validate_file_path: Callable[[str, bool], bool],
        validate_file_size: Callable[[Path, int], bool],
        decode_quoted_arg: Callable[[str], str],
        backup_enabled: bool,
        backup_suffix: str,
        dry_run: bool = False,
    ) -> None:
        self._validate_file_path = validate_file_path
        self._validate_file_size = validate_file_size
        self._decode_quoted_arg = decode_quoted_arg
        self.backup_enabled = backup_enabled
        self.backup_suffix = backup_suffix
        self.dry_run = dry_run

    async def execute_bash(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        trusted_shell: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """Execute bash command.

        Security: Even for admin users, commands are parsed with shlex.split()
        and executed as argument lists (shell=False) to prevent command injection.
        The trusted_shell flag is kept for backward compatibility but does not
        enable shell=True anymore.
        """
        command = args[0]

        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command", None

            if parts[0] == "cd":
                return False, "Bash command not allowed for direct execution: cd", None

            if self.dry_run:
                return True, f"[DRY RUN] Would execute: {command}", None

            exec_cwd = cwd or str(get_settings().default_execution_cwd)
            settings = get_settings()
            timeout = COMMAND_TIMEOUTS.get("bash", settings.opencode_timeout)
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=exec_cwd,
                shell=False,
            )

            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            if len(output) > settings.opencode_max_output:
                output = output[:settings.opencode_max_output] + f"\n... (truncated, total: {len(output)} chars)"

            if result.returncode == 0:
                return True, f"Command executed successfully (exit code: {result.returncode})", output
            else:
                return False, f"Command failed (exit code: {result.returncode})", output

        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds", None
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"Error executing command: {str(e)}", None

    async def execute_read(self, args: List[str]) -> Tuple[bool, str, Optional[str]]:
        """Simulate OpenCode read command."""
        filepath = args[0]

        try:
            path = Path(filepath)
            if not path.exists():
                return False, f"File not found: {filepath}", None

            if not path.is_file():
                return False, f"Path is not a file: {filepath}", None

            content = path.read_text(encoding="utf-8", errors="ignore")

            if len(content) > get_settings().opencode_max_output:
                content = content[:get_settings().opencode_max_output] + f"\n... (truncated, total: {len(content)} chars)"

            return True, f"File read: {filepath} ({len(content)} chars)", content

        except OSError as e:
            return False, f"Error reading file: {str(e)}", None

    async def execute_glob(
        self,
        args: List[str],
        trusted_paths: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """Simulate OpenCode glob command."""
        pattern = args[0]

        try:
            files = glob_module.glob(pattern, recursive=True)

            allowed_files = []
            for file in files:
                if trusted_paths or self._validate_file_path(file):
                    allowed_files.append(file)

            if not allowed_files:
                return True, f"No files found for pattern: {pattern}", "[]"

            output = json.dumps(allowed_files[:50], indent=2)
            if len(allowed_files) > 50:
                output += f"\n... and {len(allowed_files) - 50} more files"

            return True, f"Found {len(allowed_files)} files for pattern: {pattern}", output

        except OSError as e:
            return False, f"Error searching files: {str(e)}", None

    async def execute_grep(
        self, args: List[str], cwd: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Simulate OpenCode grep command."""
        pattern = args[0]
        extra_args = args[1]

        try:
            include_pattern = None
            if extra_args and "--include=" in extra_args:
                include_match = re.search(r'--include="([^"]+)"', extra_args)
                if include_match:
                    include_pattern = include_match.group(1)

            cmd = ["grep", "-r", "-n", "--color=never", pattern]

            if include_pattern:
                cmd.extend(["--include", include_pattern])

            base_dir = cwd or str(get_settings().dev_repos_root.resolve())
            cmd.append(base_dir)
            settings = get_settings()
            timeout = COMMAND_TIMEOUTS.get("grep", settings.opencode_timeout)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            if len(output) > settings.opencode_max_output:
                output = output[:settings.opencode_max_output] + f"\n... (truncated, total: {len(output)} chars)"

            if result.returncode in [0, 1]:
                msg = "Search completed" if result.returncode == 0 else "Pattern not found"
                return True, msg, output
            else:
                return False, f"grep failed (exit code: {result.returncode})", output

        except subprocess.TimeoutExpired:
            return False, f"Search timed out after {timeout} seconds", None
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"Error in search: {str(e)}", None

    async def execute_edit(self, args: List[str]) -> Tuple[bool, str, Optional[str]]:
        """Execute OpenCode edit command with safety checks."""
        filepath = args[0]
        extra_args = args[1]

        old_new_match = re.search(
            r'--old="((?:[^"\\]|\\.)*)"\s+--new="((?:[^"\\]|\\.)*)"', extra_args
        )
        if not old_new_match:
            return False, "Invalid edit format. Use: edit \"file\" --old=\"text\" --new=\"text\"", None

        old_text = self._decode_quoted_arg(old_new_match.group(1))
        new_text = self._decode_quoted_arg(old_new_match.group(2))

        try:
            path = Path(filepath)

            if not path.exists():
                return False, f"File not found: {filepath}", None

            if not path.is_file():
                return False, f"Path is not a file: {filepath}", None

            max_edit = get_settings().max_edit_size
            if not self._validate_file_size(path, max_edit):
                return False, f"File too large for editing (limit: {max_edit/1024/1024:.1f}MB)", None

            current_content = path.read_text(encoding="utf-8", errors="ignore")

            if old_text not in current_content:
                try:
                    current_content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        current_content = path.read_text(encoding="latin-1")
                    except UnicodeDecodeError:
                        current_content = path.read_text(errors="ignore")

                if old_text not in current_content:
                    return False, f"Text not found in file: '{old_text[:50]}...'", None

            new_content = current_content.replace(old_text, new_text)

            if new_content == current_content:
                return False, "No changes applied (identical text)", None

            if self.dry_run:
                occurrences = current_content.count(old_text)
                preview = f"--- {filepath}\n+++ {filepath}\n@@\n-{old_text[:200]}\n+{new_text[:200]}"
                return True, f"[DRY RUN] Would edit {occurrences} occurrence(s) in {filepath}", preview

            backup_path = None
            backup_label = "disabled"
            if self.backup_enabled:
                backup_path = path.with_suffix(path.suffix + self.backup_suffix)
                shutil.copy2(path, backup_path)
                backup_label = backup_path.name
                logger.info("Backup created: %s", backup_path)

            path.write_text(new_content, encoding="utf-8")

            occurrences = current_content.count(old_text)

            if backup_path:
                backup_path.unlink(missing_ok=True)

            return True, f"Edited: {occurrences} occurrence(s) substituted in {filepath}", f"Backup: {backup_label}\nReplaced: '{old_text[:100]}...'\nWith: '{new_text[:100]}...'"

        except OSError as e:
            logger.error("Error editing file %s: %s", filepath, e)
            return False, f"Error editing file: {str(e)}", None

    async def execute_write(self, args: List[str]) -> Tuple[bool, str, Optional[str]]:
        """Execute OpenCode write command with safety checks."""
        filepath = args[0]
        extra_args = args[1]

        content_match = re.search(r'--content="((?:[^"\\]|\\.)*)"', extra_args)
        if not content_match:
            return False, "Invalid write format. Use: write \"file\" --content=\"text\"", None

        content = self._decode_quoted_arg(content_match.group(1))

        try:
            path = Path(filepath)

            parent_dir = path.parent
            if not parent_dir.exists():
                if self.dry_run:
                    return True, f"[DRY RUN] Would create directory: {parent_dir}", None
                parent_dir.mkdir(parents=True, exist_ok=True)
                parent_dir.chmod(0o755)

            file_exists = path.exists()

            if self.dry_run:
                action = "overwrite" if file_exists else "create"
                preview = content[:300] + ("..." if len(content) > 300 else "")
                return True, f"[DRY RUN] Would {action} {filepath} ({len(content)} chars)", preview

            if file_exists:
                backup_path = path.with_suffix(path.suffix + ".devsynapse_backup")
                shutil.copy2(path, backup_path)

            path.write_text(content, encoding="utf-8")

            path.chmod(0o644)

            if file_exists:
                old_content = backup_path.read_text(encoding="utf-8", errors="ignore") if backup_path else ""
                old_size = len(old_content)
                new_size = len(content)

                if backup_path and backup_path.exists():
                    backup_path.unlink()

                return True, f"File overwritten: {filepath} ({old_size} -> {new_size} chars)", f"Backup: {backup_path.name if backup_path else 'N/A'}\nPrevious size: {old_size} chars\nNew size: {new_size} chars"
            else:
                return True, f"File created: {filepath} ({len(content)} chars)", f"New file created\nSize: {len(content)} chars"

        except OSError as e:
            logger.error("Error writing file %s: %s", filepath, e)
            return False, f"Error writing file: {str(e)}", None
