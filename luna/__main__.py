"""Entry point for ``python -m luna chat``.

Usage::

    python -m luna chat                     # defaults
    python -m luna chat --config luna.toml   # explicit config
    python -m luna chat --log-level DEBUG    # verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from luna.core.config import LunaConfig


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m luna", description="Luna CLI")
    sub = parser.add_subparsers(dest="command")

    chat_parser = sub.add_parser("chat", help="Start interactive chat with Luna")
    chat_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")
    chat_parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "chat":
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper(), logging.INFO),
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )

        config = LunaConfig.load(args.config)

        from luna.chat.repl import run_repl

        try:
            asyncio.run(run_repl(config))
        except KeyboardInterrupt:
            pass  # Already handled inside run_repl.


if __name__ == "__main__":
    main()
