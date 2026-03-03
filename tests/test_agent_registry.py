"""Tests for agent registry."""

from __future__ import annotations

import pytest

from luna.orchestrator.agent_registry import AgentProfile, AgentRegistry


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def luna_profile():
    return AgentProfile(
        name="LUNA",
        psi0=(0.20, 0.35, 0.25, 0.20),
        dominant="reflection",
        description="Core consciousness engine",
    )


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register(self, registry, luna_profile):
        """Register an agent profile."""
        registry.register(luna_profile)
        assert registry.count == 1

    def test_get(self, registry, luna_profile):
        """Get an agent by name."""
        registry.register(luna_profile)
        profile = registry.get("LUNA")
        assert profile is not None
        assert profile.dominant == "reflection"

    def test_get_nonexistent(self, registry):
        """Get returns None for unknown agents."""
        assert registry.get("Unknown") is None

    def test_list_agents(self, registry, luna_profile):
        """List all registered agents."""
        registry.register(luna_profile)
        registry.register(AgentProfile(
            name="SAYOHMY",
            psi0=(0.15, 0.15, 0.20, 0.50),
            dominant="expression",
        ))
        agents = registry.list_agents()
        assert len(agents) == 2

    def test_remove(self, registry, luna_profile):
        """Remove an agent."""
        registry.register(luna_profile)
        assert registry.remove("LUNA") is True
        assert registry.count == 0

    def test_remove_nonexistent(self, registry):
        """Remove returns False for unknown agents."""
        assert registry.remove("Unknown") is False

    def test_get_status(self, registry, luna_profile):
        """get_status returns expected structure."""
        registry.register(luna_profile)
        status = registry.get_status()
        assert status["agent_count"] == 1
        assert len(status["agents"]) == 1
        assert status["agents"][0]["name"] == "LUNA"

    def test_profile_frozen(self, luna_profile):
        """AgentProfile is immutable."""
        with pytest.raises(AttributeError):
            luna_profile.name = "Changed"  # type: ignore[misc]
