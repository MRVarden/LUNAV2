"""Luna orchestrator — the main entry point.

Coordinates cognitive evolution.
Deterministic: no HTTP, no LLM calls, no Docker.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from luna_common.constants import COMP_NAMES, DIM, INV_PHI3
from luna_common.consciousness import detect_self_illusion
from luna_common.consciousness.context import ContextBuilder
from luna_common.phi_engine import (
    ConvergenceDetector,
    PhiScorer,
    build_veto_event,
    resolve_veto,
)
from luna_common.schemas import (
    Decision,
    InfoGradient,
    IntegrationCheck,
    PsiState,
)

from luna.consciousness.state import ConsciousnessState
from luna.core.config import LunaConfig
from luna.identity.bundle import compute_bundle
from luna.identity.context import IdentityContext
from luna.identity.ledger import IdentityLedger
from luna.identity.recovery import IdentityError, RecoveryShell

log = logging.getLogger(__name__)

# Paths to founding documents (relative to repo root)
_DOC_NAMES_TO_FILES: dict[str, str] = {
    "FOUNDERS_MEMO": "docs/FOUNDERS_MEMO.md",
    "LUNA_CONSTITUTION": "docs/LUNA_CONSTITUTION.md",
    "FOUNDING_EPISODES": "docs/FOUNDING_EPISODES.md",
}


class LunaEngine:
    """The main orchestrator that drives Luna's cognitive loop.

    Responsibilities:
        - Load configuration and cognitive checkpoint.
        - Evolve Psi in response to cognitive signals.
        - Produce a Decision with full traceability (psi_before, psi_after, d_c).
    """

    def __init__(self, config: LunaConfig) -> None:
        self.config = config
        self.agent_name: str = config.luna.agent_name
        self.consciousness: ConsciousnessState | None = None

        # Phase 1.7 — Context builder for true delta computation
        self.context_builder = ContextBuilder()

        # Phase 2 — Phi Engine integration
        # ConsciousnessState._phase (driven by phi_iit) is the sole phase system.
        # PhiScorer tracks code quality metrics but does not drive a separate phase.
        self.phi_scorer = PhiScorer()
        self.convergence_health = ConvergenceDetector()  # window=5, tol_relative=0.01
        self.convergence_psi = ConvergenceDetector()
        self._last_health_conv = None
        self._last_psi_conv = None

        # Phase 3 — Illusion detection buffers
        self._phi_iit_buffer: list[float] = []
        self._health_buffer: list[float] = []

        # Phase 5 — Heartbeat idle step support
        self._idle_steps: int = 0

        # Validation — phi_iit samples collected during cognitive_step()
        self.phi_iit_samples: list[float] = []

        # Identity anchoring (PlanManifest Phase 6)
        self.identity_context: IdentityContext | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load the cognitive state from the last checkpoint.

        If no checkpoint exists, starts fresh from the identity profile.
        After loading, applies dream-consolidated Psi0 profile if available.
        """
        ckpt_path = self.config.resolve(self.config.consciousness.checkpoint_file)

        if ckpt_path.exists():
            log.info("Loading cognitive checkpoint from %s", ckpt_path)
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

        # PlanManifest — Identity hard gate.
        self._load_identity()

    # ------------------------------------------------------------------
    # Pipeline processing
    # ------------------------------------------------------------------

    def process_pipeline_result(
        self,
        manifest: dict,
        sentinel_report: dict,
        integration_check: IntegrationCheck,
        metrics: object | None = None,
    ) -> Decision:
        """Process one complete pipeline cycle and evolve cognitive state.

        .. deprecated::
            Legacy pipeline method. Only called when runner_enabled=true.
            See PLAN_PIPELINE_DISSOCIATION.md.

        Args:
            manifest: External code generation result.
            sentinel_report: External security audit (risk_score, psi).
            integration_check: External coherence report (psi).

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
            output_quality=1.0 - sentinel_report["risk_score"],
        )

        # Evolve — v5.1 single-agent: spatial gradient is internal.
        cs.evolve(info_deltas=info_grad.as_list())

        # Capture psi after evolution.
        psi_after = cs.to_psi_state()

        # --- Phase 2: Phi Engine scoring ---
        # Feed raw metrics from the pipeline reports.
        # integration_coherence: inverse of risk (0 risk = 1.0 score)
        self.phi_scorer.update("integration_coherence", 1.0 - sentinel_report["risk_score"])
        # memory_vitality: use SayOhMy confidence as proxy
        self.phi_scorer.update("memory_vitality", manifest["confidence"])

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
            task_id=manifest["task_id"],
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
            manifest["task_id"],
            approved,
            phase,
            cs.compute_phi_iit(),
        )

        return decision

    # ------------------------------------------------------------------
    # Idle step (heartbeat)
    # ------------------------------------------------------------------

    def idle_step(self) -> None:
        """Evolve Psi with zero info_deltas (or micro-perturbation if stagnant).

        v5.1 single-agent: spatial gradient from internal history.
        kappa*(psi0-psi) pulls toward identity.

        Anti-stagnation (v5.3.1): when the last N history entries are identical,
        inject a tiny perturbation (INV_PHI3 * 0.01 ≈ 0.0024) to break the
        fixed point.  This prevents the phi_iit correlator from seeing zero
        variance, which would collapse the phase to BROKEN.
        """
        if self.consciousness is None:
            raise RuntimeError("initialize() first")

        deltas = [0.0, 0.0, 0.0, 0.0]

        # Detect stagnation: last 10 history entries identical.
        h = self.consciousness.history
        if len(h) >= 10:
            import numpy as _np
            tail = _np.array(h[-10:])
            if _np.std(tail, axis=0).max() < 1e-10:
                # Micro-perturbation toward psi0 — breaks fixed point
                # without distorting identity (direction = psi0 - psi).
                diff = self.consciousness.psi0 - self.consciousness.psi
                scale = INV_PHI3 * 0.01  # ~0.0024 per component max
                deltas = (diff * scale).tolist()

        self.consciousness.evolve(deltas)
        self._idle_steps += 1

    # ------------------------------------------------------------------
    # Cognitive step (full pipeline for benchmarks)
    # ------------------------------------------------------------------

    def cognitive_step(self) -> None:
        """Evolve Psi with real cognitive input: Thinker -> Reactor -> evolve.

        Unlike idle_step() which feeds [0,0,0,0], this builds a Stimulus
        from the current state, runs the Thinker to generate observations,
        converts them to info_deltas via the Reactor, and evolves.
        """
        from luna.consciousness.thinker import Stimulus, Thinker, ThinkMode
        from luna.consciousness.reactor import ConsciousnessReactor

        if self.consciousness is None:
            raise RuntimeError("initialize() first")

        cs = self.consciousness

        # Lazy-init Thinker (persists across steps for causal graph accumulation)
        if not hasattr(self, "_benchmark_thinker"):
            self._benchmark_thinker = Thinker(state=cs)

        # Build stimulus from current state
        stimulus = Stimulus(
            psi=cs.psi.copy(),
            phi_iit=cs.compute_phi_iit(),
            phase=cs.get_phase(),
            psi_trajectory=[h.copy() for h in cs.history[-5:]],
        )

        # Think -> structured observations
        thought = self._benchmark_thinker.think(stimulus, mode=ThinkMode.RESPONSIVE)

        # React -> info_deltas
        reaction = ConsciousnessReactor.react(thought, cs.psi)

        # Evolve with real cognitive input
        cs.evolve(reaction.deltas)

        # Collect phi_iit for validation coherence criterion
        self.phi_iit_samples.append(cs.compute_phi_iit())

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
            "phi_metrics": self.phi_scorer.get_all_metrics(),
            # EmergentPhi — self-discovered golden ratio
            "emergent_phi": cs.get_emergent_phi(),
            "emergent_phi_precision": cs.emergent_phi.precision(),
            "emergent_phi_bootstrapping": cs.emergent_phi.is_bootstrapping(),
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
        """Restore PhiScorer EMA values from the cognitive checkpoint.

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
    # Identity anchoring (PlanManifest)
    # ------------------------------------------------------------------

    def _load_identity(self) -> None:
        """Load and verify identity bundle, with recovery on failure.

        Sets self.identity_context. On unrecoverable failure, logs a
        critical warning but does NOT halt — Luna degrades gracefully
        with identity_context=None (backward compat).
        """
        repo_root = self.config.resolve(Path("."))
        ledger_path = self.config.resolve(self.config.identity.ledger_file)
        ledger = IdentityLedger(ledger_path)

        doc_paths = {
            name: repo_root / filename
            for name, filename in _DOC_NAMES_TO_FILES.items()
        }

        # Check if all docs exist before computing
        docs_present = all(p.exists() for p in doc_paths.values())

        if docs_present:
            try:
                bundle = compute_bundle(doc_paths)
            except (FileNotFoundError, UnicodeDecodeError) as e:
                log.warning("Identity bundle computation failed: %s", e)
                bundle = None
        else:
            bundle = None

        # Verify against ledger
        if bundle is not None and ledger.verify(bundle):
            self.identity_context = IdentityContext.from_bundle(bundle, ledger)
            log.info(
                "Identity anchored: v%s hash=%s",
                self.identity_context.bundle_version,
                self.identity_context.bundle_hash[:20] + "...",
            )
            return

        # Recovery needed
        log.warning("Identity missing or corrupted — entering RecoveryShell")
        shell = RecoveryShell(
            ledger=ledger,
            doc_paths=doc_paths if docs_present else None,
            search_roots=[repo_root],
        )
        result = shell.attempt_recovery()

        if result.success and result.bundle is not None:
            self.identity_context = IdentityContext.from_bundle(
                result.bundle, ledger,
            )
            log.info("Identity recovered via %s", result.method)
        else:
            log.critical(
                "IDENTITY UNRECOVERABLE: %s — running without identity context",
                result.reason,
            )
            self.identity_context = None

    # ------------------------------------------------------------------
    # Dream consolidation (v2.3)
    # ------------------------------------------------------------------

    def _apply_consolidated_profiles(self) -> None:
        """v5.3: Validate psi0_core matches AGENT_PROFILES.

        psi0_core is the immutable identity anchor. psi0 (effective) may
        differ due to the adaptive layer from dream consolidation.
        This method restores psi0_core if it was corrupted.
        """
        from luna_common.constants import AGENT_PROFILES
        from luna_common.consciousness.evolution import MassMatrix

        correct_psi0 = np.array(
            AGENT_PROFILES.get(self.agent_name, (0.260, 0.322, 0.250, 0.168)),
            dtype=np.float64,
        )

        if not np.allclose(self.consciousness.psi0_core, correct_psi0, atol=1e-6):
            log.warning(
                "Psi0 core changed: %s → %s — resetting adaptive layer",
                np.array2string(self.consciousness.psi0_core, precision=4),
                np.array2string(correct_psi0, precision=4),
            )
            self.consciousness.psi0_core = correct_psi0.copy()
            # Reset adaptive layer — old drift was relative to old core.
            self.consciousness._psi0_adaptive = np.zeros(DIM, dtype=np.float64)
            self.consciousness.psi0 = self.consciousness._recompute_psi0()
            self.consciousness.mass = MassMatrix(self.consciousness.psi0)
            log.info("Psi0 core updated, adaptive layer reset")
