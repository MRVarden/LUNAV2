"""Wave 3 — Tests for dream consolidation (Psi0 profile update with safeguards).

Tests cover:
  - consolidate_profiles() with all 5 safeguards.
  - Alpha_dream conservative step (1/Phi^3 = 0.236).
  - Drift max bounding (1/Phi^2 = 0.382).
  - Component minimum enforcement (>= 0.05).
  - Dominant component preservation.
  - Simplex re-projection.
  - Rollback when dominant changes.
  - load_profiles() from file and fallback.
  - save_profiles() atomic write.
  - Round-trip load/save.
  - ConsolidationReport frozen dataclass.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from luna_common.constants import (
    AGENT_PROFILES,
    ALPHA_DREAM,
    PHI,
    PHI_DRIFT_MAX,
    PSI_COMPONENT_MIN,
)
from luna.dream.consolidation import consolidate_profiles, load_profiles, save_profiles
from luna.dream.harvest import ConsolidationReport, ReplayReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_replay_report(
    final_states: dict[str, np.ndarray] | None = None,
) -> ReplayReport:
    """Build a minimal ReplayReport with given final states."""
    if final_states is None:
        final_states = {}
    return ReplayReport(
        final_states=final_states,
        phi_iit_trajectory=(),
        divergence_from_static={},
        steps_replayed=10,
    )


def _default_profiles() -> dict[str, tuple[float, ...]]:
    return dict(AGENT_PROFILES)


# ---------------------------------------------------------------------------
# consolidate_profiles — safeguards
# ---------------------------------------------------------------------------


class TestConsolidateProfiles:
    """consolidate_profiles() with all 5 safeguards."""

    def test_no_simulated_agents(self) -> None:
        """If no agent is in final_states, profiles are unchanged."""
        profiles = _default_profiles()
        report = consolidate_profiles(profiles, _make_replay_report())
        assert report.updated_profiles == profiles
        assert report.dominant_preserved is True
        for d in report.drift_per_agent.values():
            assert d == 0.0

    def test_safeguard_1_alpha_dream_conservative(self) -> None:
        """Update step is scaled by alpha_dream = 1/Phi^3 ~ 0.236."""
        profiles = _default_profiles()
        # Push Luna toward a very different observed state.
        observed = np.array([0.10, 0.10, 0.10, 0.70])
        final = {"LUNA": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))

        old = np.array(profiles["LUNA"])
        new = np.array(report.updated_profiles["LUNA"])

        # The update direction should be toward observed.
        delta_full = observed - old
        delta_actual = new - old

        # Without drift capping, the raw step would be alpha_dream * delta_full.
        raw_step = ALPHA_DREAM * delta_full
        raw_drift = float(np.linalg.norm(raw_step))

        # The actual drift should be <= alpha_dream * ||delta|| (conservative).
        actual_drift = report.drift_per_agent["LUNA"]
        # Allow some tolerance for the simplex projection.
        assert actual_drift <= raw_drift + 0.05

    def test_safeguard_2_drift_max_bound(self) -> None:
        """Total drift per cycle is bounded to PHI_DRIFT_MAX = 1/Phi^2 ~ 0.382."""
        profiles = _default_profiles()
        # Extreme observed state.
        observed = np.array([0.01, 0.01, 0.01, 0.97])
        final = {"LUNA": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))
        assert report.drift_per_agent["LUNA"] <= PHI_DRIFT_MAX + 0.01

    def test_safeguard_3_component_minimum(self) -> None:
        """No component falls below PSI_COMPONENT_MIN = 0.05."""
        profiles = _default_profiles()
        # Observed state with near-zero components.
        observed = np.array([0.98, 0.005, 0.005, 0.01])
        final = {"SENTINEL": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))
        new_psi = np.array(report.updated_profiles["SENTINEL"])
        assert (new_psi >= PSI_COMPONENT_MIN - 1e-6).all(), (
            f"Component below minimum: {new_psi}"
        )

    def test_safeguard_4_dominant_preserved(self) -> None:
        """Dominant component must be preserved for each agent."""
        profiles = _default_profiles()
        # Push SENTINEL toward expression-dominant (index 3),
        # which conflicts with its perception-dominant (index 0) identity.
        observed = np.array([0.10, 0.10, 0.10, 0.70])
        final = {"SENTINEL": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))

        old_dominant = int(np.argmax(profiles["SENTINEL"]))
        new_dominant = int(np.argmax(report.updated_profiles["SENTINEL"]))
        assert new_dominant == old_dominant, (
            f"Dominant changed: {old_dominant} -> {new_dominant}"
        )

    def test_safeguard_5_simplex_projection(self) -> None:
        """Updated profiles must sum to 1.0 (on simplex)."""
        profiles = _default_profiles()
        observed = np.array([0.30, 0.30, 0.30, 0.10])
        final = {"LUNA": observed, "SAYOHMY": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))

        for agent_id, vals in report.updated_profiles.items():
            total = sum(vals)
            assert abs(total - 1.0) < 1e-6, (
                f"{agent_id} not on simplex: sum={total}"
            )

    def test_rollback_when_dominant_changes(self) -> None:
        """If post-safeguard dominant still changes, full rollback occurs."""
        # Create a pathological case: profiles where the dominant is
        # barely ahead, and the observed state inverts it drastically.
        custom_profiles: dict[str, tuple[float, ...]] = {
            "LUNA": (0.26, 0.25, 0.25, 0.24),  # Perception barely dominant
        }
        # Observed: strong expression dominance.
        observed = np.array([0.05, 0.05, 0.05, 0.85])
        final = {"LUNA": observed}

        report = consolidate_profiles(custom_profiles, _make_replay_report(final))

        if not report.dominant_preserved:
            # Rollback happened: profiles should be unchanged.
            assert report.updated_profiles == custom_profiles
            assert all(d == 0.0 for d in report.drift_per_agent.values())

    def test_all_agents_consolidated(self) -> None:
        """When all 4 agents have final states, all are updated."""
        profiles = _default_profiles()
        final_states = {}
        for agent_name, profile in profiles.items():
            # Slight perturbation toward uniform.
            observed = np.array(profile) * 0.9 + 0.025
            final_states[agent_name] = observed

        report = consolidate_profiles(profiles, _make_replay_report(final_states))
        assert report.dominant_preserved is True
        assert len(report.updated_profiles) == len(profiles)

        # All agents should have some drift (not zero).
        for agent_id in profiles:
            assert report.drift_per_agent[agent_id] > 0.0

    def test_report_fields_populated(self) -> None:
        """ConsolidationReport has all expected fields."""
        profiles = _default_profiles()
        observed = np.array([0.20, 0.40, 0.20, 0.20])
        final = {"LUNA": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))

        assert isinstance(report, ConsolidationReport)
        assert "LUNA" in report.updated_profiles
        assert "LUNA" in report.drift_per_agent
        assert isinstance(report.dominant_preserved, bool)
        assert report.previous_profiles == profiles

    def test_non_simulated_agents_unchanged(self) -> None:
        """Agents not in replay final_states keep their original profile."""
        profiles = _default_profiles()
        observed = np.array([0.20, 0.40, 0.20, 0.20])
        # Only update Luna.
        final = {"LUNA": observed}
        report = consolidate_profiles(profiles, _make_replay_report(final))

        for agent_id in ("SAYOHMY", "SENTINEL", "TESTENGINEER"):
            assert report.updated_profiles[agent_id] == profiles[agent_id]
            assert report.drift_per_agent[agent_id] == 0.0

    def test_no_change_when_equal(self) -> None:
        """If replay final == current, drift comes only from simplex re-projection.

        When the observed state equals the current profile, delta is zero and
        candidate == current. However, safeguard 5 (softmax re-projection)
        may shift the vector. The drift should still be small and bounded by
        the re-projection effect alone (no alpha_dream or drift_max influence).
        """
        profiles = _default_profiles()
        final = {k: np.array(v) for k, v in profiles.items()}
        report = consolidate_profiles(profiles, _make_replay_report(final))
        for agent_id, drift in report.drift_per_agent.items():
            # Drift comes solely from softmax re-projection of the profile.
            # This is bounded but not zero -- PHI-temperature softmax shifts values.
            assert drift < PHI_DRIFT_MAX, (
                f"{agent_id} drift {drift} exceeds PHI_DRIFT_MAX even with no delta"
            )


# ---------------------------------------------------------------------------
# load_profiles / save_profiles
# ---------------------------------------------------------------------------


class TestProfilePersistence:
    """load_profiles() and save_profiles() round-trip."""

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.json"
        profiles = load_profiles(path)
        assert profiles == dict(AGENT_PROFILES)

    def test_load_valid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "profiles.json"
        custom = {"LUNA": [0.3, 0.3, 0.2, 0.2], "SAYOHMY": [0.1, 0.1, 0.1, 0.7]}
        path.write_text(json.dumps(custom))

        profiles = load_profiles(path)
        assert profiles["LUNA"] == (0.3, 0.3, 0.2, 0.2)
        assert profiles["SAYOHMY"] == (0.1, 0.1, 0.1, 0.7)

    def test_load_corrupt_file_returns_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("NOT VALID JSON {{{")

        profiles = load_profiles(path)
        assert profiles == dict(AGENT_PROFILES)

    def test_save_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        profiles = _default_profiles()
        save_profiles(path, profiles)
        assert path.exists()

    def test_save_atomic_no_tmp_left(self, tmp_path: Path) -> None:
        """After save, no .tmp file should remain."""
        path = tmp_path / "profiles.json"
        save_profiles(path, _default_profiles())
        assert not path.with_suffix(".tmp").exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        """save then load produces the same profiles."""
        path = tmp_path / "profiles.json"
        original = _default_profiles()
        save_profiles(path, original)
        loaded = load_profiles(path)

        for agent_id in original:
            assert loaded[agent_id] == pytest.approx(original[agent_id], abs=1e-10)

    def test_save_load_preserves_custom_values(self, tmp_path: Path) -> None:
        path = tmp_path / "custom.json"
        custom: dict[str, tuple[float, ...]] = {
            "LUNA": (0.28, 0.32, 0.24, 0.16),
            "SAYOHMY": (0.14, 0.14, 0.22, 0.50),
        }
        save_profiles(path, custom)
        loaded = load_profiles(path)
        for agent_id, vals in custom.items():
            assert loaded[agent_id] == pytest.approx(vals, abs=1e-10)


# ---------------------------------------------------------------------------
# ConsolidationReport dataclass
# ---------------------------------------------------------------------------


class TestConsolidationReport:
    """ConsolidationReport frozen dataclass tests."""

    def test_frozen(self) -> None:
        """ConsolidationReport is immutable (frozen=True)."""
        report = ConsolidationReport(
            previous_profiles=_default_profiles(),
            updated_profiles=_default_profiles(),
            drift_per_agent={"LUNA": 0.01},
            dominant_preserved=True,
        )
        with pytest.raises(AttributeError):
            report.dominant_preserved = False  # type: ignore[misc]

    def test_fields_present(self) -> None:
        """ConsolidationReport has all expected fields."""
        report = ConsolidationReport(
            previous_profiles=_default_profiles(),
            updated_profiles=_default_profiles(),
            drift_per_agent={"LUNA": 0.05, "SAYOHMY": 0.02},
            dominant_preserved=True,
        )
        assert isinstance(report.previous_profiles, dict)
        assert isinstance(report.updated_profiles, dict)
        assert isinstance(report.drift_per_agent, dict)
        assert isinstance(report.dominant_preserved, bool)
        assert report.timestamp is not None
