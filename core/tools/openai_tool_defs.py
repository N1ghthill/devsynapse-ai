"""
OpenCode tool definitions for LLM function calling.

Extracted from brain.py to keep the orchestrator focused on control flow.
"""

OPENCODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "strict": True,
            "description": (
                "Execute a shell command on the system. "
                "Use to list files, check git status, run tests, install project dependencies, etc. "
                "Do not use sudo or privileged OS package installation from chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The full shell command to execute (e.g. 'ls -la', 'git status')",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "strict": True,
            "description": "Read the contents of a file from the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "strict": True,
            "description": "Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to search for files",
                    }
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "strict": True,
            "description": "Search for a regex pattern in file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression to search for",
                    },
                    "include": {
                        "type": "string",
                        "description": "File extension filter (e.g. '*.js', '*.py'). Use empty string to search all files.",
                    },
                },
                "required": ["pattern", "include"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "strict": True,
            "description": "Edit a file by replacing one piece of text with another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to edit",
                    },
                    "old": {
                        "type": "string",
                        "description": "Exact text to replace (must match precisely)",
                    },
                    "new": {
                        "type": "string",
                        "description": "New text that will replace the old text",
                    },
                },
                "required": ["path", "old", "new"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "strict": True,
            "description": (
                "Write content to a file (overwrites if it exists). "
                "Parent directories are created automatically; use this as the first action "
                "when creating a small new project instead of running mkdir separately."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
]
