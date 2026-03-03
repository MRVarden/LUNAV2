"""Fractal Memory V2 — thin async adapter over filesystem JSON.

No dependency on mcp-server. Reads legacy (Format B) and canonical (Format A)
JSON files. All I/O is async via asyncio.to_thread.
"""

from luna.memory.memory_manager import MemoryEntry, MemoryManager

__all__ = ["MemoryEntry", "MemoryManager"]
