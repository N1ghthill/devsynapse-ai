"""DevSynapse AI terminal UI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devsynapse",
        description="DevSynapse AI terminal UI",
        epilog=(
            "Run `devsynapse` to open the TUI. Inside it, use slash commands "
            "such as /connect, /providers, /status, /usage, /budget and /router."
        ),
    )
    parser.add_argument(
        "unsupported_command",
        nargs="?",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if args.unsupported_command:
        parser.error(
            "DevSynapse now opens the TUI directly. Run `devsynapse` and use "
            "slash commands inside the TUI, for example `/connect deepseek <api-key>`."
        )

    from devsynapse.tui import run_tui

    run_tui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
