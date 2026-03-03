"""REPL — Thin async read-eval-print loop for talking to Luna.

Usage::

    from luna.chat.repl import run_repl
    asyncio.run(run_repl(config))
"""

from __future__ import annotations

import asyncio
import logging

from luna.core.config import LunaConfig
from luna.chat.session import ChatSession, _COMMANDS

log = logging.getLogger(__name__)


def _banner(session: ChatSession) -> str:
    """Build the startup banner."""
    mode = "LLM" if session.has_llm else "sans LLM (status only)"
    mem = "active" if session.has_memory else "absente"
    pipeline = "actif" if session.has_pipeline else "inactif"
    return (
        f"\n{'=' * 50}\n"
        f"  Luna v{session.engine.config.luna.version} — Chat\n"
        f"  Mode: {mode}\n"
        f"  Memoire: {mem}\n"
        f"  Pipeline: {pipeline}\n"
        f"  Tapez /help pour les commandes, /quit pour sortir\n"
        f"{'=' * 50}\n"
    )


async def run_repl(config: LunaConfig) -> None:
    """Run the interactive REPL. Blocks until /quit, EOF, or Ctrl+C."""
    session = ChatSession(config)
    await session.start()

    print(_banner(session))

    prefix = config.chat.prompt_prefix

    try:
        while True:
            try:
                user_input = await asyncio.to_thread(input, prefix)
            except EOFError:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Quit command.
            if user_input.lower() == "/quit":
                break

            # Slash commands.
            if user_input.startswith("/"):
                result = await session.handle_command(user_input)
                print(result)
                continue

            # Regular chat message.
            response = await session.send(user_input)
            print(f"\n{response.content}")
            print(
                f"[{response.phase} | Phi={response.phi_iit:.4f}"
                f" | {response.input_tokens}+{response.output_tokens} tokens]"
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Ctrl+C arrives as KeyboardInterrupt or CancelledError depending
        # on whether asyncio.run() intercepts the signal first.
        print("\nInterrupted.")
    finally:
        # Always save checkpoint on exit — even if interrupted.
        try:
            await session.stop()
        except asyncio.CancelledError:
            # If the event loop is shutting down, stop() may be cancelled.
            # Force a synchronous checkpoint save as last resort.
            session._save_checkpoint()
        print("Au revoir.")
