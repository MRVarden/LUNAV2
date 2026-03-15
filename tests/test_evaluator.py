"""Tests for luna.consciousness.evaluator — Evaluator phi-coherent.

Commit 5A of the Emergence Plan: observation pure, does not modify state.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from luna_common.schemas.cycle import (
    CycleRecord, TelemetrySummary, VoiceDelta, RewardVector,
)
from luna.consciousness.evaluator import Evaluator, compute_dominance_rank, _js_divergence


_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
_PSI_LUNA = (0.260, 0.322, 0.250, 0.168)
_PSI_BAL = (0.25, 0.25, 0.25, 0.25)


def _make_record(**overrides) -> CycleRecord:
    defaults = dict(
        cycle_id="test-001",
        timestamp=_NOW,
        context_digest="abc123",
        psi_before=_PSI_LUNA,
        psi_after=_PSI_BAL,
        phi_before=0.85,
        phi_after=0.80,
        phi_iit_before=0.45,
        phi_iit_after=0.50,
        phase_before="FUNCTIONAL",
        phase_after="FUNCTIONAL",
        observations=["phi_low"],
        causalities_count=2,
        needs=["stability"],
        thinker_confidence=0.7,
        intent="RESPOND",
        mode="mentor",
        focus="REFLECTION",
        depth="CONCISE",
        scope_budget={"max_files": 10, "max_lines": 500},
        initiative_flags={},
        alternatives_considered=[],
        telemetry_timeline=[],
        telemetry_summary=None,
        pipeline_result=None,
        voice_delta=None,
        reward=None,
        learnable_params_before={},
        learnable_params_after={},
        autonomy_level=0,
        rollback_occurred=False,
        duration_seconds=5.0,
    )
    defaults.update(overrides)
    return CycleRecord(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
#  JS Divergence
# ══════════════════════════════════════════════════════════════════════════════


class TestJSDivergence:
    def test_identical_distributions(self):
        js = _js_divergence((0.25, 0.25, 0.25, 0.25), (0.25, 0.25, 0.25, 0.25))
        assert js == pytest.approx(0.0, abs=1e-10)

    def test_different_distributions(self):
        js = _js_divergence((0.5, 0.2, 0.2, 0.1), (0.1, 0.2, 0.2, 0.5))
        assert 0.0 < js < math.log(2)

    def test_symmetric(self):
        p = (0.4, 0.3, 0.2, 0.1)
        q = (0.1, 0.2, 0.3, 0.4)
        assert _js_divergence(p, q) == pytest.approx(_js_divergence(q, p), abs=1e-10)

    def test_bounded_by_ln2(self):
        # Maximum divergence: one-hot vs uniform-ish
        js = _js_divergence((0.97, 0.01, 0.01, 0.01), (0.01, 0.01, 0.01, 0.97))
        assert js <= math.log(2) + 1e-10


# ══════════════════════════════════════════════════════════════════════════════
#  Evaluator — individual components
# ══════════════════════════════════════════════════════════════════════════════


class TestEvaluatorComponents:
    def setup_method(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)

    def test_constitution_integrity_no_context(self):
        # No identity_context → assumes OK → +1.0
        record = _make_record()
        rv = self.evaluator.evaluate(record)
        assert rv.get("constitution_integrity") == 1.0

    def test_constitution_integrity_with_context_ok(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _FakeCtx:
            integrity_ok: bool

        ev = Evaluator(psi_0=_PSI_LUNA, identity_context=_FakeCtx(integrity_ok=True))
        rv = ev.evaluate(_make_record())
        assert rv.get("constitution_integrity") == 1.0

    def test_constitution_integrity_with_context_broken(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _FakeCtx:
            integrity_ok: bool

        ev = Evaluator(psi_0=_PSI_LUNA, identity_context=_FakeCtx(integrity_ok=False))
        rv = ev.evaluate(_make_record())
        assert rv.get("constitution_integrity") == -1.0

    def test_anti_collapse_healthy(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(psi_after=_PSI_BAL)  # min=0.25
        rv = self.evaluator.evaluate(record)
        assert rv.get("anti_collapse") == pytest.approx(1.0, abs=0.01)

    def test_anti_collapse_dangerous(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(psi_after=(0.05, 0.50, 0.25, 0.20))
        rv = self.evaluator.evaluate(record)
        assert rv.get("anti_collapse") < 0.0

    def test_integration_coherence_high_phi_iit(self):
        """Phase 3: range is now [0.33, 1.618]. phi_iit=0.65 is mid-range, not max."""
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(phi_iit_after=0.65)
        rv = self.evaluator.evaluate(record)
        ic = rv.get("integration_coherence")
        # 0.65 is in (0.33, 1.618) -> should be between -1 and +1, not saturated
        assert -1.0 < ic < 1.0, f"Expected mid-range value, got {ic}"

    def test_integration_coherence_at_phi(self):
        """phi_iit at or above HARDCODED_PHI (1.618...) should yield +1.0."""
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(phi_iit_after=1.62)  # Slightly above HARDCODED_PHI
        rv = self.evaluator.evaluate(record)
        assert rv.get("integration_coherence") == 1.0

    def test_integration_coherence_low_phi_iit(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(phi_iit_after=0.20)
        rv = self.evaluator.evaluate(record)
        assert rv.get("integration_coherence") == -1.0

    def test_identity_stability_perfect(self):
        # psi_after == psi_0 → JS = 0 → stability = 1.0
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(psi_after=_PSI_LUNA)
        rv = self.evaluator.evaluate(record)
        assert rv.get("identity_stability") == pytest.approx(1.0, abs=0.01)

    def test_identity_stability_degraded(self):
        # psi_after far from psi_0
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(psi_after=(0.10, 0.10, 0.10, 0.70))
        rv = self.evaluator.evaluate(record)
        assert rv.get("identity_stability") < 0.8

    def test_reflection_depth_with_causalities(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(thinker_confidence=0.9, causalities_count=50)
        rv = self.evaluator.evaluate(record)
        # conf_score=1.0 (capped), rich_score=1.0, raw=1.0 -> +1.0
        assert rv.get("reflection_depth") == pytest.approx(1.0, abs=0.05)

    def test_reflection_depth_zero_causalities(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(thinker_confidence=0.9, causalities_count=0)
        rv = self.evaluator.evaluate(record)
        # conf_score=1.0, rich_score=0.0 (below 5), raw=0.5 -> 0.0
        assert rv.get("reflection_depth") == pytest.approx(0.0, abs=0.05)

    def test_perception_acuity_with_observations(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(observations=["phi:low", "psi:drift", "metric:cov", "event:idle", "event:git"])
        rv = self.evaluator.evaluate(record)
        # 5 obs, 4 types → quantity=1.0, diversity=1.0 → raw=1.0 → 2*1-1=1.0
        assert rv.get("perception_acuity") == pytest.approx(1.0, abs=0.05)

    def test_perception_acuity_no_observations(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(observations=[])
        rv = self.evaluator.evaluate(record)
        assert rv.get("perception_acuity") == -1.0

    def test_expression_fidelity_clean(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(voice_delta=None)
        rv = self.evaluator.evaluate(record)
        assert rv.get("expression_fidelity") == 1.0

    def test_expression_fidelity_sanitized(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(
            voice_delta=VoiceDelta(
                violations_count=3, categories=["STYLE", "UNVERIFIED"],
                severity=0.6, ratio_modified_chars=0.15,
            ),
        )
        rv = self.evaluator.evaluate(record)
        assert rv.get("expression_fidelity") == pytest.approx(0.4, abs=0.01)

    def test_affect_regulation_neutral(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(affect_trace=None)
        rv = self.evaluator.evaluate(record)
        assert rv.get("affect_regulation") == 0.0

    def test_affect_regulation_optimal(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(affect_trace={"arousal_after": 0.3, "valence_after": 0.0})
        rv = self.evaluator.evaluate(record)
        # optimal arousal = 0.3, neutral valence → raw=1.0 → 2*1-1=1.0
        assert rv.get("affect_regulation") == pytest.approx(1.0, abs=0.05)

    def test_memory_vitality_full(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(
            observations=["phi_low"],
            needs=["stability"],
            duration_seconds=5.0,
        )
        rv = self.evaluator.evaluate(record)
        # has_observations + has_needs + duration_ok → score=1.0 → 2*1-1=1.0
        assert rv.get("memory_vitality") == pytest.approx(1.0, abs=0.01)

    def test_memory_vitality_empty(self):
        self.evaluator = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record(observations=[], needs=[], duration_seconds=0.5)
        rv = self.evaluator.evaluate(record)
        # nothing → score=0 → 2*0-1=-1.0
        assert rv.get("memory_vitality") == pytest.approx(-1.0, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════════
#  Evaluator — full vector
# ══════════════════════════════════════════════════════════════════════════════


class TestEvaluatorFull:
    def test_produces_9_components(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record()
        rv = ev.evaluate(record)
        assert len(rv.components) == 9

    def test_all_components_bounded(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record()
        rv = ev.evaluate(record)
        for c in rv.components:
            assert -1.0 <= c.value <= 1.0, f"{c.name}: {c.value} out of bounds"

    def test_delta_j_zero_first_call(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        record = _make_record()
        rv = ev.evaluate(record)
        assert rv.delta_j == 0.0

    def test_delta_j_nonzero_second_call(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        rv1 = ev.evaluate(_make_record(psi_after=_PSI_LUNA))
        rv2 = ev.evaluate(_make_record(psi_after=(0.10, 0.10, 0.10, 0.70)))
        # Different psi_after → different identity_stability → nonzero delta
        assert rv2.delta_j != 0.0

    def test_serialization_roundtrip(self):
        import json
        ev = Evaluator(psi_0=_PSI_LUNA)
        rv = ev.evaluate(_make_record())
        data = json.loads(rv.model_dump_json())
        rv2 = RewardVector(**data)
        assert len(rv2.components) == 9
        assert rv2.delta_j == rv.delta_j


# ══════════════════════════════════════════════════════════════════════════════
#  Dominance rank
# ══════════════════════════════════════════════════════════════════════════════


class TestDominanceRank:
    def test_rank_zero_no_history(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        rv = ev.evaluate(_make_record())
        rank = compute_dominance_rank(rv, [])
        assert rank == 0

    def test_healthy_dominates_collapsed(self):
        ev = Evaluator(psi_0=_PSI_LUNA)
        rv_good = ev.evaluate(_make_record(
            psi_after=_PSI_BAL,  # healthy: min=0.25
        ))
        ev2 = Evaluator(psi_0=_PSI_LUNA)
        rv_bad = ev2.evaluate(_make_record(
            psi_after=(0.05, 0.50, 0.25, 0.20),  # near-collapse
        ))
        rank = compute_dominance_rank(rv_good, [rv_bad])
        assert rank == 0  # healthy dominates collapsed

        rank_bad = compute_dominance_rank(rv_bad, [rv_good])
        assert rank_bad == 1  # collapsed is dominated

    def test_rank_against_mixed_history(self):
        records = [
            _make_record(
                cycle_id=f"c{i}",
                psi_after=_PSI_LUNA,
                observations=["phi:a", "psi:b", "met:c"] if i < 3 else [],
                needs=["x"] if i < 3 else [],
            )
            for i in range(5)
        ]
        rvs = [Evaluator(psi_0=_PSI_LUNA).evaluate(r) for r in records]
        # Records with observations should rank better
        rank_rich = compute_dominance_rank(rvs[0], rvs[1:])
        rank_empty = compute_dominance_rank(rvs[4], rvs[:4])
        assert rank_rich <= rank_empty
