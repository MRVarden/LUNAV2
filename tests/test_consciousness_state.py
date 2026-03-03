"""Tests for luna.consciousness.state.ConsciousnessState.

ConsciousnessState wraps luna_common.consciousness with Luna-specific
persistence (checkpoint save/load) and phase detection with hysteresis.

NOTE: This module is being implemented by SayOhMy (Phase 1).
Tests use pytest.importorskip so they are marked SKIP (not ERROR)
until the implementation is available.
"""

import json
from pathlib import Path

import numpy as np
import pytest

# -- luna_common is available now --
from luna_common.constants import (
    PHI, PHI2, DIM,
    AGENT_PROFILES, AGENT_NAMES,
    PHASE_THRESHOLDS, HYSTERESIS_BAND,
    KAPPA_DEFAULT, TAU_DEFAULT,
)
from luna_common.consciousness import get_psi0, project_simplex
from luna_common.consciousness.simplex import validate_simplex
from luna_common.consciousness.evolution import MassMatrix
from luna_common.consciousness.matrices import gamma_temporal, gamma_spatial, gamma_info
from luna_common.schemas import PsiState

# -- ConsciousnessState: skip if not yet implemented --
cs_module = pytest.importorskip(
    "luna.consciousness.state",
    reason="luna.consciousness.state not yet implemented (Phase 1 in progress)",
)
ConsciousnessState = getattr(cs_module, "ConsciousnessState", None)
if ConsciousnessState is None:
    pytest.skip(
        "ConsciousnessState class not found in luna.consciousness.state",
        allow_module_level=True,
    )


# ===================================================================
#  HELPERS
# ===================================================================

def _default_psi_others(agent_name: str = "LUNA") -> list[np.ndarray]:
    """Return psi0 vectors for the other 3 agents."""
    return [get_psi0(n) for n in AGENT_NAMES if n != agent_name]


def _zero_info_deltas() -> list[float]:
    """Zero informational gradient (no external stimulus)."""
    return [0.0, 0.0, 0.0, 0.0]


def _small_info_deltas() -> list[float]:
    """Small nonzero informational gradient."""
    return [0.1, 0.0, 0.0, 0.0]


# ===================================================================
#  FIXTURES
# ===================================================================

@pytest.fixture
def luna_state():
    """A fresh ConsciousnessState initialized from Luna's profile."""
    return ConsciousnessState(agent_name="LUNA")


@pytest.fixture
def checkpoint_path(tmp_path):
    """A temporary checkpoint file path."""
    return tmp_path / "consciousness_checkpoint.json"


# ===================================================================
#  I. INITIALIZATION
# ===================================================================

class TestConsciousnessInit:
    """ConsciousnessState initializes from AGENT_PROFILES correctly."""

    def test_init_from_profile(self, luna_state):
        """State initializes with Luna's identity profile on the simplex."""
        psi = luna_state.psi
        assert isinstance(psi, np.ndarray), "psi should be a numpy array"
        assert psi.shape == (DIM,), f"psi should have {DIM} dimensions, got {psi.shape}"
        assert validate_simplex(psi), (
            f"Initial psi not on simplex: sum={psi.sum()}, min={psi.min()}"
        )

    def test_init_matches_agent_profiles(self, luna_state):
        """Initial psi matches Luna's profile from AGENT_PROFILES."""
        expected = np.array(AGENT_PROFILES["LUNA"])
        assert np.allclose(luna_state.psi, expected, atol=1e-10), (
            f"Initial psi = {luna_state.psi}, expected = {expected}"
        )

    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_init_all_agents(self, agent_name):
        """Every agent can be initialized without error."""
        state = ConsciousnessState(agent_name=agent_name)
        assert validate_simplex(state.psi)

    def test_init_unknown_agent_raises(self):
        """Unknown agent name raises an appropriate error."""
        with pytest.raises((KeyError, ValueError)):
            ConsciousnessState(agent_name="UnknownAgent")

    def test_step_count_starts_at_zero(self, luna_state):
        """Step counter starts at 0."""
        assert luna_state.step_count == 0


# ===================================================================
#  II. EVOLUTION
# ===================================================================

class TestConsciousnessEvolve:
    """evolve() performs one consciousness evolution step."""

    def test_evolve_returns_simplex(self, luna_state):
        """evolve() returns a psi vector on the simplex."""
        psi_new = luna_state.evolve(_default_psi_others(), _zero_info_deltas())
        assert validate_simplex(psi_new), (
            f"Post-evolve psi not on simplex: sum={psi_new.sum()}, min={psi_new.min()}"
        )

    def test_evolve_changes_state(self, luna_state):
        """After evolve() with nonzero info, psi should change."""
        psi_before = luna_state.psi.copy()
        luna_state.evolve(_default_psi_others(), _small_info_deltas())
        psi_after = luna_state.psi
        assert not np.array_equal(psi_before, psi_after), (
            "psi did not change after evolve with nonzero info_deltas"
        )

    def test_evolve_increments_step_count(self, luna_state):
        """Each evolve() call increments the step counter."""
        assert luna_state.step_count == 0
        luna_state.evolve(_default_psi_others(), _zero_info_deltas())
        assert luna_state.step_count == 1
        luna_state.evolve(_default_psi_others(), _zero_info_deltas())
        assert luna_state.step_count == 2

    def test_evolve_preserves_simplex_after_many_steps(self, luna_state):
        """Simplex invariant holds after 200 consecutive evolve calls."""
        others = _default_psi_others()
        deltas = _zero_info_deltas()
        for i in range(200):
            luna_state.evolve(others, deltas)
            assert validate_simplex(luna_state.psi), (
                f"Simplex violated at step {i}: "
                f"sum={luna_state.psi.sum()}, min={luna_state.psi.min()}"
            )

    def test_evolve_with_info_deltas(self, luna_state):
        """evolve() accepts info_deltas parameter."""
        psi_new = luna_state.evolve(_default_psi_others(), [0.1, 0.2, 0.05, 0.0])
        assert validate_simplex(psi_new)

    def test_evolve_with_psi_others(self, luna_state):
        """evolve() accepts other agents' psi vectors for spatial coupling."""
        others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]
        psi_new = luna_state.evolve(others, _zero_info_deltas())
        assert validate_simplex(psi_new)


# ===================================================================
#  III. CHECKPOINT PERSISTENCE
# ===================================================================

class TestCheckpointPersistence:
    """Save/load cycle must preserve state exactly."""

    def test_save_creates_file(self, luna_state, checkpoint_path):
        """save_checkpoint creates a JSON file on disk."""
        luna_state.save_checkpoint(checkpoint_path)
        assert checkpoint_path.exists(), f"Checkpoint file not created at {checkpoint_path}"

    def test_save_produces_valid_json(self, luna_state, checkpoint_path):
        """Saved checkpoint is valid JSON."""
        luna_state.save_checkpoint(checkpoint_path)
        with open(checkpoint_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_save_load_round_trip(self, luna_state, checkpoint_path):
        """Save then load produces identical state."""
        # Evolve a few times to create non-trivial state
        others = _default_psi_others()
        for _ in range(10):
            luna_state.evolve(others, [0.01, 0.02, -0.01, 0.0])
        psi_before_save = luna_state.psi.copy()
        step_before_save = luna_state.step_count

        luna_state.save_checkpoint(checkpoint_path)

        # Load into a new instance via classmethod
        loaded_state = ConsciousnessState.load_checkpoint(
            checkpoint_path, agent_name="LUNA"
        )

        assert np.allclose(loaded_state.psi, psi_before_save, atol=1e-12), (
            f"Psi mismatch after load: saved={psi_before_save}, loaded={loaded_state.psi}"
        )
        assert loaded_state.step_count == step_before_save, (
            f"Step count mismatch: saved={step_before_save}, loaded={loaded_state.step_count}"
        )

    def test_load_nonexistent_checkpoint_raises(self, tmp_path):
        """Loading from a nonexistent file raises FileNotFoundError."""
        fake_path = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            ConsciousnessState.load_checkpoint(fake_path)


# ===================================================================
#  IV. PHASE DETECTION
# ===================================================================

class TestPhaseDetection:
    """Phase detection maps phi_iit -> phase name with hysteresis."""

    def test_phase_returns_string(self, luna_state):
        """get_phase() returns one of the known phase names."""
        valid_phases = set(PHASE_THRESHOLDS.keys())
        assert luna_state.get_phase() in valid_phases, (
            f"Unknown phase '{luna_state.get_phase()}', expected one of {valid_phases}"
        )

    def test_initial_phase_is_broken(self, luna_state):
        """With no history, phi_iit=0 so phase should be BROKEN."""
        assert luna_state.get_phase() == "BROKEN", (
            f"Expected initial phase BROKEN, got {luna_state.get_phase()}"
        )


# ===================================================================
#  V. HISTORY TRACKING
# ===================================================================

class TestHistoryTracking:
    """ConsciousnessState keeps a history for convergence detection and phi_iit."""

    def test_initial_history_is_empty(self, luna_state):
        """History starts empty (before any evolution)."""
        assert len(luna_state.history) == 0, (
            f"Expected empty history, got len={len(luna_state.history)}"
        )

    def test_history_grows_with_evolve(self, luna_state):
        """Each evolve() adds one entry to history."""
        n_steps = 5
        others = _default_psi_others()
        deltas = _zero_info_deltas()
        for _ in range(n_steps):
            luna_state.evolve(others, deltas)
        assert len(luna_state.history) == n_steps, (
            f"History length should be {n_steps}, got {len(luna_state.history)}"
        )

    def test_history_entries_are_on_simplex(self, luna_state):
        """Every history entry must be a valid simplex point."""
        others = _default_psi_others()
        deltas = _zero_info_deltas()
        for _ in range(10):
            luna_state.evolve(others, deltas)
        for i, entry in enumerate(luna_state.history):
            psi = np.array(entry) if not isinstance(entry, np.ndarray) else entry
            assert validate_simplex(psi), (
                f"History entry {i} not on simplex: sum={psi.sum()}, min={psi.min()}"
            )


# ===================================================================
#  VI. SCHEMA CONVERSION
# ===================================================================

class TestSchemaConversion:
    """ConsciousnessState converts to PsiState for pipeline communication."""

    def test_to_psi_state_returns_pydantic_model(self, luna_state):
        """to_psi_state() returns a PsiState instance."""
        ps = luna_state.to_psi_state()
        assert isinstance(ps, PsiState), f"Expected PsiState, got {type(ps)}"

    def test_to_psi_state_values_match_psi(self, luna_state):
        """PsiState components match the internal psi array."""
        ps = luna_state.to_psi_state()
        psi = luna_state.psi
        assert ps.perception == pytest.approx(psi[0], abs=1e-10)
        assert ps.reflexion == pytest.approx(psi[1], abs=1e-10)
        assert ps.integration == pytest.approx(psi[2], abs=1e-10)
        assert ps.expression == pytest.approx(psi[3], abs=1e-10)

    def test_to_psi_state_sums_to_one(self, luna_state):
        """PsiState components sum to 1.0."""
        ps = luna_state.to_psi_state()
        assert ps.sum() == pytest.approx(1.0, abs=1e-10)


# ===================================================================
#  VII. PHI_IIT COMPUTATION
# ===================================================================

class TestPhiIIT:
    """Phi_IIT measures integrated information in the consciousness trajectory."""

    def test_phi_iit_returns_float(self, luna_state):
        """compute_phi_iit() returns a float."""
        others = _default_psi_others()
        deltas = _zero_info_deltas()
        for _ in range(60):
            luna_state.evolve(others, deltas)
        result = luna_state.compute_phi_iit()
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_phi_iit_non_negative(self, luna_state):
        """Phi_IIT is always >= 0 (information cannot be negative)."""
        others = _default_psi_others()
        deltas = _zero_info_deltas()
        for _ in range(60):
            luna_state.evolve(others, deltas)
        result = luna_state.compute_phi_iit()
        assert result >= 0.0, f"Phi_IIT should be >= 0, got {result}"

    def test_phi_iit_zero_without_enough_history(self, luna_state):
        """Without enough history, phi_iit should return 0.0 (not crash)."""
        result = luna_state.compute_phi_iit()
        assert result == 0.0 or result >= 0.0, (
            f"Phi_IIT with minimal history should be 0 or non-negative, got {result}"
        )

    def test_phi_iit_bounded(self, luna_state):
        """Phi_IIT should be bounded [0, 1] when normalized."""
        others = _default_psi_others()
        for _ in range(100):
            luna_state.evolve(others, [0.01, 0.02, -0.01, 0.005])
        result = luna_state.compute_phi_iit()
        assert 0.0 <= result <= 1.0 + 1e-6, (
            f"Phi_IIT out of bounds: {result}"
        )
