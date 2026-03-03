"""DreamCycle — four-phase nocturnal consolidation of Psi history.

Runs after prolonged inactivity (triggered by Heartbeat). Purely deterministic
math over the history buffer. Does not call LLM or network.

Phases:
  1. Consolidation: mean, variance, drift from psi0
  2. Reinterpretation: cross-component correlations (significant if |r| > INV_PHI)
  3. Defragmentation: remove near-duplicates (L2 < 1e-6), cap history buffer
  4. Creative connections: non-adjacent pipeline correlations
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import numpy as np

from luna_common.constants import COMP_NAMES, DIM, INV_PHI
from luna.core.config import LunaConfig
from luna.dream.consolidation import consolidate_profiles, save_profiles
from luna.dream.harvest import (
    ConsolidationReport,
    DreamHarvest,
    ExplorationReport,
    ReplayReport,
)
from luna.dream.scenarios import explore_all
from luna.dream.simulator import DreamSimulator

log = logging.getLogger(__name__)

# Pipeline circuit order: Expression(3) → Perception(0) → Integration(2) → Reflexion(1)
_PIPELINE_ORDER = [3, 0, 2, 1]


class DreamPhase(str, Enum):
    # Legacy phases (v2.2) — kept for backward compatibility.
    CONSOLIDATION = "consolidation"
    REINTERPRETATION = "reinterpretation"
    DEFRAGMENTATION = "defragmentation"
    CREATIVE = "creative_connections"
    # New simulation phases (v2.3).
    HARVEST = "harvest"
    REPLAY = "replay"
    EXPLORATION = "exploration"
    SIM_CONSOLIDATION = "sim_consolidation"


@dataclass(slots=True)
class PhaseResult:
    """Result from a single dream phase."""

    phase: DreamPhase
    data: dict = field(default_factory=dict)
    duration_seconds: float = 0.0


@dataclass(slots=True)
class DreamReport:
    """Full report from a complete dream cycle."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    phases: list[PhaseResult] = field(default_factory=list)
    total_duration: float = 0.0
    history_before: int = 0
    history_after: int = 0
    consolidation_report: ConsolidationReport | None = None

    def to_dict(self) -> dict:
        """Serialize the report to a plain dict (JSON-compatible)."""
        d = {
            "timestamp": self.timestamp.isoformat(),
            "total_duration": self.total_duration,
            "history_before": self.history_before,
            "history_after": self.history_after,
            "phases": [
                {
                    "phase": pr.phase.value,
                    "duration_seconds": pr.duration_seconds,
                    "data": pr.data,
                }
                for pr in self.phases
            ],
        }
        if self.consolidation_report is not None:
            cr = self.consolidation_report
            d["consolidation_report"] = {
                "previous_profiles": cr.previous_profiles,
                "updated_profiles": cr.updated_profiles,
                "drift_per_agent": cr.drift_per_agent,
                "dominant_preserved": cr.dominant_preserved,
            }
        return d


class DreamCycle:
    """Four-phase dream consolidation over consciousness history."""

    def __init__(
        self,
        engine: object,
        config: LunaConfig,
        memory: object | None = None,
    ) -> None:
        self._engine = engine
        self._config = config
        self._memory = memory
        self._last_activity: float = time.monotonic()

    # ------------------------------------------------------------------
    # Activity tracking
    # ------------------------------------------------------------------

    def record_activity(self) -> None:
        """Reset the inactivity timer (called after each pipeline cycle)."""
        self._last_activity = time.monotonic()

    def should_dream(self) -> bool:
        """True if conditions for dreaming are met."""
        if not self._config.dream.enabled:
            return False

        cs = self._engine.consciousness
        if cs is None:
            return False

        # Need enough history for meaningful analysis.
        if len(cs.history) < 10:
            return False

        elapsed = time.monotonic() - self._last_activity
        return elapsed >= self._config.dream.inactivity_threshold

    # ------------------------------------------------------------------
    # Dream execution
    # ------------------------------------------------------------------

    async def run(self, harvest: DreamHarvest | None = None) -> DreamReport:
        """Execute dream phases sequentially.

        When *harvest* is ``None`` (legacy path), runs the original 4 statistical
        phases over the consciousness history buffer.  When a ``DreamHarvest`` is
        provided (v2.3 simulation path), runs the 4-phase dream simulation:
        harvest -> replay -> exploration -> consolidation.
        """
        if harvest is not None:
            return await self._run_simulation(harvest)
        return await self._run_legacy()

    # ------------------------------------------------------------------
    # Legacy dream path (v2.2)
    # ------------------------------------------------------------------

    async def _run_legacy(self) -> DreamReport:
        """Execute the original four statistical dream phases."""
        t0 = time.monotonic()
        cs = self._engine.consciousness
        report = DreamReport(history_before=len(cs.history))

        # Build history array from the consolidation window.
        window = self._config.dream.consolidation_window
        history_slice = cs.history[-window:] if len(cs.history) > window else cs.history
        history_arr = np.array(history_slice)
        psi0 = cs.psi0

        # Phase 1: Consolidation (CPU-bound).
        t1 = time.monotonic()
        consolidation = await asyncio.to_thread(self._consolidate, history_arr, psi0)
        report.phases.append(PhaseResult(
            phase=DreamPhase.CONSOLIDATION,
            data=consolidation,
            duration_seconds=time.monotonic() - t1,
        ))

        # Phase 2: Reinterpretation (CPU-bound).
        t2 = time.monotonic()
        reinterpretation = await asyncio.to_thread(self._reinterpret, history_arr)
        report.phases.append(PhaseResult(
            phase=DreamPhase.REINTERPRETATION,
            data=reinterpretation,
            duration_seconds=time.monotonic() - t2,
        ))

        # Phase 3: Defragmentation (mutates cs.history, CPU-bound).
        t3 = time.monotonic()
        defrag = await asyncio.to_thread(self._defragment, cs)
        report.phases.append(PhaseResult(
            phase=DreamPhase.DEFRAGMENTATION,
            data=defrag,
            duration_seconds=time.monotonic() - t3,
        ))

        # Phase 4: Creative connections (CPU-bound).
        t4 = time.monotonic()
        creative = await asyncio.to_thread(self._creative_connect, history_arr)
        report.phases.append(PhaseResult(
            phase=DreamPhase.CREATIVE,
            data=creative,
            duration_seconds=time.monotonic() - t4,
        ))

        report.history_after = len(cs.history)
        report.total_duration = time.monotonic() - t0

        self._save_report(report)

        # Dream -> Memory feedback: persist insights as branch memories.
        if self._memory is not None:
            await self._persist_insights(report)

        self._last_activity = time.monotonic()

        log.info(
            "Dream cycle complete (legacy): %.3fs, history %d -> %d",
            report.total_duration,
            report.history_before,
            report.history_after,
        )
        return report

    # ------------------------------------------------------------------
    # Simulation dream path (v2.3)
    # ------------------------------------------------------------------

    async def _run_simulation(self, harvest: DreamHarvest) -> DreamReport:
        """Execute the 4-phase dream simulation using wake-cycle data."""
        t0 = time.monotonic()
        cs = self._engine.consciousness
        report = DreamReport(history_before=len(cs.history))

        # Phase 1: Harvest (record the collected data).
        t1 = time.monotonic()
        harvest_data = {
            "pipeline_events": len(harvest.pipeline_events),
            "psi_snapshots": len(harvest.luna_psi_snapshots),
            "metrics_entries": len(harvest.metrics_history),
            "phi_iit_entries": len(harvest.phi_iit_history),
            "agents": list(harvest.current_profiles.keys()),
        }
        report.phases.append(PhaseResult(
            phase=DreamPhase.HARVEST,
            data=harvest_data,
            duration_seconds=time.monotonic() - t1,
        ))

        # Phase 2: Replay -- create simulator and replay wake events.
        t2 = time.monotonic()
        profiles = harvest.current_profiles or None
        sim = DreamSimulator(profiles=profiles)

        # Build info_deltas sequence from metrics history if available.
        info_deltas_seq: list[dict[str, list[float]]] | None = None
        if harvest.phi_iit_history:
            # Use phi_iit values as a uniform positive signal for all agents.
            info_deltas_seq = []
            for phi_val in harvest.phi_iit_history:
                step_deltas = {
                    agent_id: [0.0, phi_val * 0.1, phi_val * 0.1, 0.0]
                    for agent_id in sim.agent_ids
                }
                info_deltas_seq.append(step_deltas)

        await asyncio.to_thread(
            sim.replay,
            harvest_events=len(harvest.pipeline_events),
            info_deltas_sequence=info_deltas_seq,
        )

        # Build replay report.
        # Translate simulator lowercase keys -> canonical profile keys
        # so consolidation can match against harvest.current_profiles.
        from luna.dream.simulator import _AGENT_KEYS

        raw_final = sim.get_all_psi()
        final_states = {_AGENT_KEYS[k]: v for k, v in raw_final.items()}

        phi_trajectory = tuple(
            sim.compute_mean_phi_iit(window=min(20, len(sim.get_history(a))))
            for a in sim.agent_ids
        )
        raw_divs = sim.measure_divergence()
        divergences = {_AGENT_KEYS[k]: v for k, v in raw_divs.items()}
        replay_report = ReplayReport(
            final_states=final_states,
            phi_iit_trajectory=phi_trajectory,
            divergence_from_static=divergences,
            steps_replayed=max(len(harvest.pipeline_events), 10),
        )
        report.phases.append(PhaseResult(
            phase=DreamPhase.REPLAY,
            data={
                "steps_replayed": replay_report.steps_replayed,
                "divergences": {k: round(v, 4) for k, v in divergences.items()},
                "phi_iit_trajectory": [round(p, 4) for p in phi_trajectory],
            },
            duration_seconds=time.monotonic() - t2,
        ))

        # Phase 3: Exploration -- run hypothetical scenarios.
        t3 = time.monotonic()
        scenario_results = await asyncio.to_thread(explore_all, sim)
        exploration_report = ExplorationReport(
            scenarios_run=len(scenario_results),
            results=tuple(scenario_results),
            most_stable_scenario=(
                max(scenario_results, key=lambda r: r.stability_score).scenario_id
                if scenario_results else ""
            ),
            most_fragile_scenario=(
                min(scenario_results, key=lambda r: r.stability_score).scenario_id
                if scenario_results else ""
            ),
        )
        report.phases.append(PhaseResult(
            phase=DreamPhase.EXPLORATION,
            data={
                "scenarios_run": exploration_report.scenarios_run,
                "most_stable": exploration_report.most_stable_scenario,
                "most_fragile": exploration_report.most_fragile_scenario,
                "results": [
                    {
                        "scenario_id": r.scenario_id,
                        "stability": r.stability_score,
                        "phi_iit": r.phi_iit_mean,
                        "preserved": r.identities_preserved,
                        "insight": r.insight,
                    }
                    for r in scenario_results
                ],
            },
            duration_seconds=time.monotonic() - t3,
        ))

        # Phase 4: Consolidation -- update Psi0 profiles.
        t4 = time.monotonic()
        consolidation_rpt = await asyncio.to_thread(
            consolidate_profiles,
            harvest.current_profiles,
            replay_report,
            exploration_report,
        )
        report.consolidation_report = consolidation_rpt
        report.phases.append(PhaseResult(
            phase=DreamPhase.SIM_CONSOLIDATION,
            data={
                "dominant_preserved": consolidation_rpt.dominant_preserved,
                "drift_per_agent": consolidation_rpt.drift_per_agent,
                "profiles_updated": consolidation_rpt.dominant_preserved,
            },
            duration_seconds=time.monotonic() - t4,
        ))

        # Gap 2 — Persist consolidated profiles + apply to current engine.
        if consolidation_rpt.dominant_preserved:
            data_dir = self._config.resolve(self._config.luna.data_dir)
            profiles_path = data_dir / "agent_profiles.json"
            try:
                save_profiles(profiles_path, consolidation_rpt.updated_profiles)
                log.info("Consolidated profiles saved to %s", profiles_path)
            except Exception:
                log.warning("Failed to save consolidated profiles", exc_info=True)

            # Apply Luna's updated Psi0 to the live engine.
            luna_profile = consolidation_rpt.updated_profiles.get(
                self._engine.agent_name,
            )
            if luna_profile is not None:
                new_psi0 = np.array(luna_profile, dtype=np.float64)
                if not np.allclose(new_psi0, cs.psi0, atol=1e-8):
                    try:
                        cs.update_psi0(new_psi0)
                        log.info(
                            "Dream applied consolidated Psi0: %s",
                            np.array2string(new_psi0, precision=4),
                        )
                    except ValueError as exc:
                        log.warning("Failed to apply consolidated Psi0: %s", exc)

        report.history_after = len(cs.history)
        report.total_duration = time.monotonic() - t0

        self._save_report(report)

        # Dream -> Memory feedback.
        if self._memory is not None:
            await self._persist_insights(report)

        self._last_activity = time.monotonic()

        log.info(
            "Dream cycle complete (simulation): %.3fs, %d scenarios, "
            "profiles_updated=%s",
            report.total_duration,
            len(scenario_results),
            consolidation_rpt.dominant_preserved,
        )
        return report

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _consolidate(history_arr: np.ndarray, psi0: np.ndarray) -> dict:
        """Phase 1: Statistics on recent Psi history."""
        if len(history_arr) == 0:
            return {"mean_psi": [], "variance": [], "drift_from_psi0": 0.0}

        mean_psi = history_arr.mean(axis=0)
        variance = history_arr.var(axis=0)
        drift = float(np.linalg.norm(mean_psi - psi0))

        return {
            "mean_psi": mean_psi.tolist(),
            "variance": variance.tolist(),
            "drift_from_psi0": drift,
            "num_entries": len(history_arr),
        }

    @staticmethod
    def _reinterpret(history_arr: np.ndarray) -> dict:
        """Phase 2: Cross-component correlations.

        Significant if |r| > INV_PHI (0.618).
        """
        if len(history_arr) < 3:
            return {"correlations": [], "significant": []}

        # Check if any component has zero variance.
        stds = np.std(history_arr, axis=0)
        if np.any(stds < 1e-12):
            return {"correlations": [], "significant": []}

        corr = np.corrcoef(history_arr.T)

        correlations: list[dict] = []
        significant: list[dict] = []

        for i in range(DIM):
            for j in range(i + 1, DIM):
                r = float(corr[i, j])
                pair = {
                    "components": [COMP_NAMES[i], COMP_NAMES[j]],
                    "correlation": r,
                }
                correlations.append(pair)
                if abs(r) > INV_PHI:
                    significant.append(pair)

        return {"correlations": correlations, "significant": significant}

    @staticmethod
    def _defragment(cs: object) -> dict:
        """Phase 3: Remove near-duplicate states, cap history buffer.

        MUTATES cs.history intentionally.
        """
        if len(cs.history) < 2:
            return {"removed": 0, "capped": False}

        original_len = len(cs.history)

        # Remove near-duplicates (L2 < 1e-6).
        unique: list[np.ndarray] = [cs.history[0]]
        for h in cs.history[1:]:
            if np.linalg.norm(h - unique[-1]) >= 1e-6:
                unique.append(h)

        removed = original_len - len(unique)
        cs.history = unique

        # Cap buffer at 2× consolidation window (defensive).
        capped = False
        max_size = 200  # 2 × default window
        if len(cs.history) > max_size:
            cs.history = cs.history[-max_size:]
            capped = True

        return {"removed": removed, "capped": capped, "final_size": len(cs.history)}

    @staticmethod
    def _creative_connect(history_arr: np.ndarray) -> dict:
        """Phase 4: Correlations between non-adjacent pipeline components.

        Pipeline: ψ₄(Expr) → ψ₁(Perc) → ψ₃(Integ) → ψ₂(Refl)
        Non-adjacent pairs: (ψ₄, ψ₃) and (ψ₁, ψ₂) — i.e., pairs that don't
        directly feed each other in the pipeline circuit.
        """
        if len(history_arr) < 3:
            return {"unexpected_couplings": []}

        stds = np.std(history_arr, axis=0)
        if np.any(stds < 1e-12):
            return {"unexpected_couplings": []}

        corr = np.corrcoef(history_arr.T)

        # Non-adjacent pairs in the pipeline circuit.
        # Pipeline order: 3→0→2→1. Adjacent: (3,0), (0,2), (2,1), (1,3).
        adjacent = {(3, 0), (0, 3), (0, 2), (2, 0), (2, 1), (1, 2), (1, 3), (3, 1)}

        unexpected: list[dict] = []
        for i in range(DIM):
            for j in range(i + 1, DIM):
                if (i, j) not in adjacent and (j, i) not in adjacent:
                    r = float(corr[i, j])
                    if abs(r) > INV_PHI:
                        unexpected.append({
                            "components": [COMP_NAMES[i], COMP_NAMES[j]],
                            "correlation": r,
                        })

        return {"unexpected_couplings": unexpected}

    # ------------------------------------------------------------------
    # Dream → Memory feedback
    # ------------------------------------------------------------------

    async def _persist_insights(self, report: DreamReport) -> None:
        """Extract insights from the dream report and write as branch memories."""
        from luna.memory.memory_manager import MemoryEntry

        insights: list[MemoryEntry] = []

        # Extract consolidation insight.
        for pr in report.phases:
            if pr.phase == DreamPhase.CONSOLIDATION and pr.data.get("drift_from_psi0", 0) > 0:
                drift = pr.data["drift_from_psi0"]
                mean_psi = pr.data.get("mean_psi", [])
                insights.append(MemoryEntry(
                    id=f"dream_{uuid.uuid4().hex[:12]}",
                    content=(
                        f"Dream consolidation: mean drift from identity = {drift:.4f}. "
                        f"Mean Psi = {mean_psi}."
                    ),
                    memory_type="branch",
                    keywords=["dream", "consolidation", "drift"],
                    phi_resonance=max(0.0, 1.0 - drift),  # High resonance if low drift.
                ))

            # Extract creative connections insight.
            if pr.phase == DreamPhase.CREATIVE:
                couplings = pr.data.get("unexpected_couplings", [])
                if couplings:
                    coupling_desc = "; ".join(
                        f"{c['components'][0]}-{c['components'][1]} (r={c['correlation']:.3f})"
                        for c in couplings
                    )
                    insights.append(MemoryEntry(
                        id=f"dream_{uuid.uuid4().hex[:12]}",
                        content=f"Dream creative connections: {coupling_desc}",
                        memory_type="branch",
                        keywords=["dream", "creative", "coupling"],
                        phi_resonance=INV_PHI,  # Creative insight = golden resonance.
                    ))

        for entry in insights:
            try:
                await self._memory.write_memory(entry, "branches")
                log.info("Dream insight persisted: %s", entry.id)
            except Exception:
                log.warning("Failed to persist dream insight %s", entry.id, exc_info=True)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Dream subsystem status for aggregation."""
        elapsed = time.monotonic() - self._last_activity
        cs = self._engine.consciousness
        history_len = len(cs.history) if cs is not None else 0
        return {
            "enabled": self._config.dream.enabled,
            "seconds_since_activity": round(elapsed, 1),
            "inactivity_threshold": self._config.dream.inactivity_threshold,
            "should_dream": self.should_dream(),
            "history_size": history_len,
            "has_memory": self._memory is not None,
        }

    # ------------------------------------------------------------------
    # Report persistence
    # ------------------------------------------------------------------

    def _save_report(self, report: DreamReport) -> None:
        """Save dream report as JSON."""
        report_dir = self._config.resolve(self._config.dream.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        ts = report.timestamp.strftime("%Y%m%d_%H%M%S")
        path = report_dir / f"dream_{ts}.json"

        # Serialize numpy arrays in data dicts.
        data = report.to_dict()
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
        log.debug("Dream report saved: %s", path)
