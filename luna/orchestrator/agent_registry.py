"""Agent registry — tracks registered agents with Psi_0 profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Profile for a registered agent."""

    name: str
    psi0: tuple[float, float, float, float]
    dominant: str
    description: str = ""


class AgentRegistry:
    """Registry of agents with their consciousness profiles.

    Stores agent profiles indexed by name. Provides lookup
    and iteration for multi-agent coordination.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}

    def register(self, profile: AgentProfile) -> None:
        """Register an agent profile.

        Args:
            profile: The agent profile to register.
        """
        self._agents[profile.name] = profile
        log.info("Agent registered: %s (dominant=%s)", profile.name, profile.dominant)

    def get(self, name: str) -> AgentProfile | None:
        """Get an agent profile by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[AgentProfile]:
        """List all registered agents."""
        return list(self._agents.values())

    def remove(self, name: str) -> bool:
        """Remove an agent from the registry.

        Returns:
            True if the agent was found and removed.
        """
        if name in self._agents:
            del self._agents[name]
            log.info("Agent removed: %s", name)
            return True
        return False

    @property
    def count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)

    def get_status(self) -> dict:
        """Return registry status."""
        return {
            "agent_count": self.count,
            "agents": [
                {"name": a.name, "dominant": a.dominant, "psi0": list(a.psi0)}
                for a in self._agents.values()
            ],
        }
