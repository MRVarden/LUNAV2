"""Chat interface — human-facing conversation with Luna.

Parallel to the agent-to-agent orchestrator. Wires LunaEngine + LLMBridge +
MemoryManager directly for interactive dialogue.

Usage::

    from luna.chat import ChatSession, ChatMessage, ChatResponse
    from luna.chat.repl import run_repl
"""

from luna.chat.session import ChatMessage, ChatResponse, ChatSession

__all__ = ["ChatMessage", "ChatResponse", "ChatSession"]
