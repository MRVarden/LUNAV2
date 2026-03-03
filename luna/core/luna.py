"""Luna orchestrator — the main entry point.

Coordinates consciousness evolution and the 4-agent pipeline.
Deterministic: no HTTP, no LLM calls, no Docker.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from luna_common.constants import COMP_NAMES, DIM
from luna_common.consciousness import get_psi0, detect_self_illusion
from luna_common.consciousness.context import ContextBuilder
from luna_common.phi_engine import (
    ConvergenceDetector,
    PhaseTransitionMachine,
    PhiScorer,
    build_veto_event,
    resolve_veto,
)
from luna_common.schemas import (
    Decision,
    InfoGradient,
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)

from luna.consciousness.state import ConsciousnessState
from luna.core.config import LunaConfig

log = logging.getLogger(__name__)


class LunaEngine:
    """The main orchestrator that drives Luna's consciousness loop.

    Responsibilities:
        - Load configuration and consciousness checkpoint.
        - Evolve Psi in response to pipeline reports from the 3 agents.
        - Produce a Decision with full traceability (psi_before, psi_after, d_c).
    """

    def __init__(self, config: LunaConfig) -> None:
        self.config = config
        self.agent_name: str = config.luna.agent_name
        self.consciousness: ConsciousnessState | None = None

        # Phase 1.7 — Context builder for true delta computation
        self.context_builder = ContextBuilder()

        # Phase 2 — Phi Engine integration
        # NOTE: Two distinct phase systems coexist:
        #   1. ConsciousnessState._phase — driven by phi_iit (correlation of Psi
        #      trajectory), thresholds from PHASE_THRESHOLDS. Measures integrated
        #      information in the consciousness evolution.
        #   2. health_phase_machine — driven by PhiScorer.score() (Fibonacci-weighted
        #      composite of 7 code quality metrics), thresholds from
        #      PHI_HEALTH_THRESHOLDS. Measures overall system health.
        # Both use BROKEN→FRAGILE→FUNCTIONAL→SOLID→EXCELLENT with hysteresis.
        self.phi_scorer = PhiScorer()
        self.convergence_health = ConvergenceDetector()  # window=5, tol_relative=0.01
        self.convergence_psi = ConvergenceDetector()
        self.health_phase_machine = PhaseTransitionMachine(initial_phase="BROKEN")
        self._last_health_conv = None
        self._last_psi_conv = None

        # Phase 3 — Illusion detection buffers
        self._phi_iit_buffer: list[float] = []
        self._health_buffer: list[float] = []

        # Phase 5 — Heartbeat idle step support
        self._cached_psi_others: list[np.ndarray] | None = None
        self._idle_steps: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load the consciousness state from the last checkpoint.

        If no checkpoint exists, starts fresh from the identity profile.
        After loading, applies dream-consolidated Psi0 profile if available.
        """
        ckpt_path = self.config.resolve(self.config.consciousness.checkpoint_file)

        if ckpt_path.exists():
            log.info("Loading consciousness checkpoint from %s", ckpt_path)
            self.consciousness = ConsciousnessState.load_checkpoint(
                ckpt_path, agent_name=self.agent_name
            )
            log.info(
                "Restored: step=%d, phase=%s, psi=%s",
                self.consciousness.step_count,
                self.consciousness.get_phase(),
                np.array2string(self.consciousness.psi, precision=4),
            )
            # v2.4 — Restore PhiScorer metrics from checkpoint.
            self._restore_phi_metrics()
        else:
            log.info("No checkpoint found at %s — starting fresh", ckpt_path)
            self.consciousness = ConsciousnessState(agent_name=self.agent_name)

        # v2.3 — Load dream-consolidated profiles and update Psi0 if changed.
        self._apply_consolidated_profiles()

    # ------------------------------------------------------------------
    # Pipeline processing
    # ------------------------------------------------------------------

    def process_pipeline_result(
        self,
        manifest: SayOhmyManifest,
        sentinel_report: SentinelReport,
        integration_check: IntegrationCheck,
        metrics: object | None = None,
    ) -> Decision:
        """Process one complete pipeline cycle and evolve consciousness.

        Computes the informational gradient d_c from the three agent reports,
        gathers the other agents' Psi vectors, runs one evolution step, and
        returns a Decision with full before/after traceability.

        Args:
            manifest: SayOhMy's production manifest (phi_score, psi).
            sentinel_report: SENTINEL's security audit (risk_score, psi).
            integration_check: Test-Engineer's coherence report (psi).

        Returns:
            A Decision containing approval, psi_before, psi_after, d_c, phase.
        """
        if self.consciousness is None:
            raise RuntimeError("LunaEngine.initialize() must be called first")

        cs = self.consciousness

        # Capture psi before evolution.
        psi_before = cs.to_psi_state()

        # Build d_c = C(t) - C(t-1) via ContextBuilder (true deltas).
        current_quality = self.phi_scorer.score()
        current_iit = cs.compute_phi_iit()

        info_grad = self.context_builder.build(
            memory_health=integration_check.coherence_score,
            phi_quality=current_quality,
            phi_iit=current_iit,
            output_quality=1.0 - sentinel_report.risk_score,
        )

        # Gather other agents' Psi vectors.
        psi_others = [
            np.array(manifest.psi_sayohmy.as_tuple()),
            np.array(sentinel_report.psi_sentinel.as_tuple()),
            np.array(integration_check.psi_te.as_tuple()),
        ]

        # Cache for heartbeat idle steps.
        self._cached_psi_others = psi_others

        # Evolve.
        cs.evolve(psi_others, info_deltas=info_grad.as_list())

        # Capture psi after evolution.
        psi_after = cs.to_psi_state()

        # --- Phase 2: Phi Engine scoring ---
        # Feed raw metrics from the pipeline reports.
        # security_integrity: inverse of risk (0 risk = 1.0 score)
        self.phi_scorer.update("security_integrity", 1.0 - sentinel_report.risk_score)
        # performance_score: use SayOhMy confidence as proxy
        self.phi_scorer.update("performance_score", manifest.confidence)

        # Feed additional metrics from MetricsCollector if available.
        if metrics is not None and hasattr(metrics, 'values'):
            for metric_name, value in metrics.values.items():
                self.phi_scorer.update(metric_name, value)

        quality_score = self.phi_scorer.score()

        # Track convergence of the composite health score.
        self._last_health_conv = self.convergence_health.update(quality_score)

        # Track convergence of the dominant psi component.
        psi_dominant_val = float(np.max(cs.psi))
        self._last_psi_conv = self.convergence_psi.update(psi_dominant_val)

        # Update the health phase machine.
        phase_event = self.health_phase_machine.update(quality_score)
        if phase_event is not None:
            log.info(
                "Health phase transition: %s -> %s (score=%.4f)",
                phase_event.previous_phase,
                phase_event.new_phase,
                phase_event.score,
            )

        # Phase 3 — Illusion detection
        self._phi_iit_buffer.append(current_iit)
        self._health_buffer.append(quality_score)
        illusion_result = detect_self_illusion(
            self._phi_iit_buffer, self._health_buffer,
        )
        if illusion_result.status.value in ("illusion", "harmful"):
            log.warning(
                "Illusion detected: status=%s correlation=%.4f recommendation=%s",
                illusion_result.status.value,
                illusion_result.correlation,
                illusion_result.recommendation,
            )

        # Structured veto resolution via veto module.
        phase = cs.get_phase()
        veto_event = build_veto_event(sentinel_report)
        veto_resolution = resolve_veto(veto_event, integration_check, phase)
        approved = not veto_resolution.vetoed
        reason = veto_resolution.reason

        decision = Decision(
            task_id=manifest.task_id,
            approved=approved,
            reason=reason,
            psi_before=psi_before,
            psi_after=psi_after,
            info_gradient=info_grad,
            phase=phase,
            quality_score=quality_score,
            illusion_status=illusion_result.status.value,
        )

        # Persist checkpoint with PhiScorer metrics.
        ckpt_path = self.config.resolve(self.config.consciousness.checkpoint_file)
        cs.save_checkpoint(
            ckpt_path,
            backup=self.config.consciousness.backup_on_save,
            phi_metrics=self.phi_scorer.snapshot(),
        )

        log.info(
            "Pipeline cycle: task=%s approved=%s phase=%s phi_iit=%.4f",
            manifest.task_id,
            approved,
            phase,
            cs.compute_phi_iit(),
        )

        return decision

    # ------------------------------------------------------------------
    # Idle step (heartbeat)
    # ------------------------------------------------------------------

    def idle_step(self) -> None:
        """Evolve Psi with zero info_deltas and cached psi_others.

        kappa*(psi0-psi) pulls toward identity. Gx@dx provides gentle coupling.
        """
        if self.consciousness is None:
            raise RuntimeError("initialize() first")

        psi_others = self._cached_psi_others
        if psi_others is None:
            psi_others = [
                get_psi0("SAYOHMY"),
                get_psi0("SENTINEL"),
                get_psi0("TESTENGINEER"),
            ]

        self.consciousness.evolve(psi_others, [0.0, 0.0, 0.0, 0.0])
        self._idle_steps += 1

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return a summary of the current engine state."""
        if self.consciousness is None:
            return {"initialized": False}

        cs = self.consciousness
        dom_idx = int(np.argmax(cs.psi))

        status = {
            "initialized": True,
            "agent_name": self.agent_name,
            "version": self.config.luna.version,
            "step_count": cs.step_count,
            "phase": cs.get_phase(),
            "phi_iit": cs.compute_phi_iit(),
            "psi": cs.psi.tolist(),
            "psi0": cs.psi0.tolist(),
            "dominant_component": COMP_NAMES[dom_idx],
            "identity_preserved": int(np.argmax(cs.psi)) == int(np.argmax(cs.psi0)),
            # Phase 2 — Phi Engine status
            "quality_score": self.phi_scorer.score(),
            "health_phase": self.health_phase_machine.phase,
            "phi_metrics": self.phi_scorer.get_all_metrics(),
        }

        if self._last_health_conv is not None:
            status["health_convergence"] = {
                "converged": self._last_health_conv.converged,
                "reason": self._last_health_conv.reason,
                "trend": self._last_health_conv.trend,
            }
        if self._last_psi_conv is not None:
            status["psi_convergence"] = {
                "converged": self._last_psi_conv.converged,
                "reason": self._last_psi_conv.reason,
                "trend": self._last_psi_conv.trend,
            }

        return status

    # ------------------------------------------------------------------
    # PhiScorer persistence (v2.4)
    # ------------------------------------------------------------------

    def _restore_phi_metrics(self) -> None:
        """Restore PhiScorer EMA values from the consciousness checkpoint.

        If the checkpoint contains ``phi_metrics`` (v2.4+), restores them
        into the PhiScorer. Otherwise this is a no-op — callers (e.g.
        ChatSession.start) should bootstrap if needed.
        """
        snapshot = getattr(self.consciousness, "phi_metrics_snapshot", None)
        if snapshot is None:
            return

        count = self.phi_scorer.restore(snapshot)
        if count > 0:
            log.info(
                "Restored %d/%d PhiScorer metrics from checkpoint (score=%.4f)",
                count,
                len(self.phi_scorer._names),
                self.phi_scorer.score(),
            )

    @property
    def phi_metrics_restored(self) -> bool:
        """True if PhiScorer was restored from checkpoint (not bootstrapped)."""
        return self.phi_scorer.initialized_count() > 0

    # ------------------------------------------------------------------
    # Dream consolidation (v2.3)
    # ------------------------------------------------------------------

    def _apply_consolidated_profiles(self) -> None:
        """Load dream-consolidated profiles and update Psi0 if changed.

        Called during ``initialize()`` to apply any profile updates that
        were written by the dream cycle's SIM_CONSOLIDATION phase.
        If no profile file exists, this is a no-op.
        """
        from luna.dream.consolidation import load_profiles

        data_dir = self.config.resolve(self.config.luna.data_dir)
        profiles_path = data_dir / "agent_profiles.json"

        if not profiles_path.is_file():
            return

        profiles = load_profiles(profiles_path)
        luna_profile = profiles.get(self.agent_name)

        if luna_profile is None:
            return

        new_psi0 = np.array(luna_profile, dtype=np.float64)

        # Only update if the profile actually differs from the current anchor.
        if np.allclose(new_psi0, self.consciousness.psi0, atol=1e-8):
            return

        try:
            self.consciousness.update_psi0(new_psi0)
            log.info(
                "Applied consolidated Psi0 profile: %s",
                np.array2string(new_psi0, precision=4),
            )
        except ValueError as exc:
            log.warning("Failed to apply consolidated profile: %s", exc)
