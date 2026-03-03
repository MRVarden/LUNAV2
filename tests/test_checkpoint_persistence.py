"""Tests for ConsciousnessState checkpoint persistence with phi_metrics (v2.4.0).

Validates that save_checkpoint/load_checkpoint correctly handle the new
phi_metrics field introduced in v2.4.0, while maintaining backward
compatibility with v2.2.0 and legacy v2.0.0 checkpoint formats.

CRITICAL INVARIANTS:
  - v2.4.0 checkpoints include "phi_metrics" when provided
  - v2.4.0 checkpoints have version "2.4.0"
  - Loading v2.4 with phi_metrics populates phi_metrics_snapshot
  - Loading v2.2 or v2.0 sets phi_metrics_snapshot to None
  - Round-trip save/load preserves phi_metrics faithfully
  - Fresh ConsciousnessState has phi_metrics_snapshot = None
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from luna_common.constants import METRIC_NAMES

from luna.consciousness.state import ConsciousnessState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(agent: str = "LUNA") -> ConsciousnessState:
    """Create a minimal ConsciousnessState for testing."""
    return ConsciousnessState(agent_name=agent)


def _sample_phi_metrics() -> dict[str, dict]:
    """Build a realistic phi_metrics dict with all 7 canonical metrics."""
    values = [0.95, 0.72, 0.60, 0.45, 0.38, 0.25, 0.10]
    return {name: {"value": v} for name, v in zip(METRIC_NAMES, values)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckpointSaveFormat:
    """Validate the JSON structure written by save_checkpoint."""

    def test_save_without_phi_metrics_omits_key(self, tmp_path: Path):
        """When phi_metrics is None, the key should not appear in JSON."""
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt, phi_metrics=None)

        data = json.loads(ckpt.read_text())
        assert "phi_metrics" not in data, (
            "phi_metrics key should be absent when not provided"
        )

    def test_save_with_phi_metrics_includes_key(self, tmp_path: Path):
        """When phi_metrics is provided, it must appear in saved JSON."""
        state = _make_state()
        metrics = _sample_phi_metrics()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        data = json.loads(ckpt.read_text())
        assert "phi_metrics" in data, "phi_metrics key missing from checkpoint"
        assert data["phi_metrics"] == metrics

    def test_version_bumped_to_24(self, tmp_path: Path):
        """Saved checkpoint must have version '2.4.0'."""
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt)

        data = json.loads(ckpt.read_text())
        assert data["version"] == "2.4.0", (
            f"Expected version '2.4.0', got {data['version']!r}"
        )

    def test_save_creates_backup_when_file_exists(self, tmp_path: Path):
        """If checkpoint file already exists, a backup is created."""
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt)  # first save
        state.save_checkpoint(ckpt)  # second save => backup

        backups = list(tmp_path.glob("ckpt.backup_*.json"))
        assert len(backups) >= 1, "Expected at least one backup file"


class TestCheckpointLoadFormats:
    """Validate loading from different checkpoint format versions."""

    def test_load_v24_with_phi_metrics(self, tmp_path: Path):
        """Loading a v2.4 checkpoint with phi_metrics populates the snapshot."""
        metrics = _sample_phi_metrics()
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.phi_metrics_snapshot is not None, (
            "phi_metrics_snapshot should not be None for v2.4 checkpoint"
        )
        assert loaded.phi_metrics_snapshot == metrics

    def test_load_v24_without_phi_metrics(self, tmp_path: Path):
        """A v2.4 checkpoint without phi_metrics yields None snapshot."""
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt, phi_metrics=None)

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.phi_metrics_snapshot is None

    def test_load_v22_format_has_none_snapshot(self, tmp_path: Path):
        """A v2.2.0 checkpoint (no phi_metrics key) yields None snapshot."""
        # Manually write a v2.2 checkpoint
        psi = [0.25, 0.35, 0.25, 0.15]
        data = {
            "version": "2.2.0",
            "type": "consciousness_state",
            "agent_name": "LUNA",
            "psi": psi,
            "psi0": psi,
            "mass_m": np.diag(psi).tolist(),
            "step_count": 10,
            "phase": "BROKEN",
            "phi_iit": 0.0,
            "history_tail": [],
        }
        ckpt = tmp_path / "v22.json"
        ckpt.write_text(json.dumps(data))

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.phi_metrics_snapshot is None, (
            "v2.2 checkpoint should not have phi_metrics_snapshot"
        )

    def test_load_v20_legacy_has_none_snapshot(self, tmp_path: Path):
        """A v2.0.0 legacy checkpoint (no psi vector) yields None snapshot."""
        data = {
            "version": "2.0.0",
            "type": "consciousness_state",
            "agent_name": "LUNA",
        }
        ckpt = tmp_path / "v20.json"
        ckpt.write_text(json.dumps(data))

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.phi_metrics_snapshot is None, (
            "v2.0 legacy checkpoint should not have phi_metrics_snapshot"
        )

    def test_load_file_not_found_raises(self, tmp_path: Path):
        """Loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ConsciousnessState.load_checkpoint(tmp_path / "missing.json", "LUNA")


class TestCheckpointRoundTrip:
    """Full save -> load round-trip validation."""

    def test_roundtrip_preserves_phi_metrics(self, tmp_path: Path):
        """Save with phi_metrics, load, verify snapshot matches exactly."""
        metrics = _sample_phi_metrics()
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.phi_metrics_snapshot == metrics, (
            f"Round-trip mismatch:\n"
            f"  saved:  {metrics}\n"
            f"  loaded: {loaded.phi_metrics_snapshot}"
        )

    def test_roundtrip_preserves_psi_vector(self, tmp_path: Path):
        """Save/load preserves the Psi vector within numerical tolerance."""
        state = _make_state()
        ckpt = tmp_path / "ckpt.json"
        original_psi = state.psi.copy()
        state.save_checkpoint(ckpt)

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        np.testing.assert_allclose(
            loaded.psi, original_psi, atol=1e-10,
            err_msg="Psi vector not preserved through save/load"
        )

    def test_roundtrip_preserves_step_count(self, tmp_path: Path):
        """Step count survives the round-trip."""
        state = _make_state()
        state.step_count = 42
        ckpt = tmp_path / "ckpt.json"
        state.save_checkpoint(ckpt)

        loaded = ConsciousnessState.load_checkpoint(ckpt, "LUNA")
        assert loaded.step_count == 42


class TestPhiMetricsSnapshotFallback:
    """Phase 2A fix: save_checkpoint WITHOUT explicit phi_metrics
    must still persist the cached phi_metrics_snapshot."""

    def test_save_without_param_uses_cached_snapshot(self, tmp_path: Path):
        """If phi_metrics_snapshot was set by a prior save, subsequent saves
        without the phi_metrics= param still include it in the JSON."""
        state = _make_state()
        metrics = _sample_phi_metrics()
        ckpt = tmp_path / "ckpt.json"

        # First save: explicitly provide phi_metrics (e.g., from LunaEngine.stop).
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        # Second save: NO phi_metrics param (e.g., from heartbeat or CLI evolve).
        ckpt2 = tmp_path / "ckpt2.json"
        state.save_checkpoint(ckpt2)  # <-- the critical call

        data = json.loads(ckpt2.read_text())
        assert "phi_metrics" in data, (
            "save_checkpoint() without phi_metrics= must still persist "
            "the cached phi_metrics_snapshot"
        )
        assert data["phi_metrics"] == metrics

    def test_cached_snapshot_survives_multiple_saves(self, tmp_path: Path):
        """Multiple consecutive saves without phi_metrics= all preserve the snapshot."""
        state = _make_state()
        metrics = _sample_phi_metrics()
        ckpt = tmp_path / "ckpt.json"

        # Seed the cache.
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        # 3 more saves without phi_metrics= (simulating heartbeat ticks).
        for i in range(3):
            path = tmp_path / f"heartbeat_{i}.json"
            state.save_checkpoint(path)
            data = json.loads(path.read_text())
            assert "phi_metrics" in data, f"Heartbeat save {i} lost phi_metrics"
            assert data["phi_metrics"] == metrics

    def test_explicit_none_does_not_erase_cached(self, tmp_path: Path):
        """Passing phi_metrics=None does NOT erase the cached snapshot."""
        state = _make_state()
        metrics = _sample_phi_metrics()
        ckpt = tmp_path / "ckpt.json"

        # Seed cache.
        state.save_checkpoint(ckpt, phi_metrics=metrics)

        # Save with explicit None (should still use cache via `or` fallback).
        ckpt2 = tmp_path / "ckpt2.json"
        state.save_checkpoint(ckpt2, phi_metrics=None)

        data = json.loads(ckpt2.read_text())
        assert "phi_metrics" in data, (
            "phi_metrics=None should not erase the cached snapshot"
        )

    def test_no_cache_no_phi_metrics_in_output(self, tmp_path: Path):
        """Fresh state (no cache) + no phi_metrics param => no key in JSON."""
        state = _make_state()
        assert state.phi_metrics_snapshot is None
        ckpt = tmp_path / "fresh.json"
        state.save_checkpoint(ckpt)

        data = json.loads(ckpt.read_text())
        assert "phi_metrics" not in data


class TestBackupRotation:
    """Phase 5B: old backups are pruned to keep only N most recent."""

    def test_rotation_keeps_only_5(self, tmp_path: Path):
        """Creating 8 backups leaves only the 5 newest."""
        state = _make_state()
        ckpt = tmp_path / "cs.json"
        # First save (no backup yet).
        state.save_checkpoint(ckpt, backup=True)
        # 8 more saves -> 8 backups created.
        import time as _time
        for _ in range(8):
            _time.sleep(0.01)  # ensure distinct timestamps
            state.save_checkpoint(ckpt, backup=True)
        backups = sorted(tmp_path.glob("cs.backup_*.json"))
        assert len(backups) <= 5, (
            f"Expected at most 5 backups after rotation, got {len(backups)}"
        )

    def test_rotation_preserves_newest(self, tmp_path: Path):
        """When fewer backups than keep limit, none are deleted."""
        from luna.consciousness.state import _rotate_backups

        ckpt = tmp_path / "cs.json"
        ckpt.write_text("{}")
        # Manually create 3 distinctly-named backups.
        for i in range(3):
            (tmp_path / f"cs.backup_20260101_00000{i}.json").write_text("{}")
        _rotate_backups(ckpt, keep=5)
        backups = sorted(tmp_path.glob("cs.backup_*.json"))
        assert len(backups) == 3, "All 3 should survive (under keep=5)"


class TestConsciousnessStateInit:
    """Validate initial state defaults."""

    def test_phi_metrics_snapshot_default_none(self):
        """Fresh ConsciousnessState has phi_metrics_snapshot = None."""
        state = _make_state()
        assert state.phi_metrics_snapshot is None, (
            "Fresh state should have phi_metrics_snapshot = None"
        )
