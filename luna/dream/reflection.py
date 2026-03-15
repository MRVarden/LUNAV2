"""Dream Reflection — Mode 2 (Reflexion psi_2).

The Thinker in REFLECTIVE mode — 100 iterations without LLM.
Explores causalities, correlations, counterfactuals in depth.
Updates the causal graph with new discoveries.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from luna.consciousness.causal_graph import CausalGraph
from luna.consciousness.thinker import Stimulus, ThinkMode, Thinker, Thought


# ═══════════════════════════════════════════════════════════════════════════════
#  DREAM REFLECTION
# ═══════════════════════════════════════════════════════════════════════════════

class DreamReflection:
    """Deep reflection — Thinker in REFLECTIVE mode, 100 iterations.

    1. Thinker.think(stimulus, max_iter=100, REFLECTIVE)
    2. New causalities -> graph (observe_pair)
    3. Prune the graph (clean dead edges)
    4. Persist discovered insights
    """

    def __init__(
        self,
        thinker: Thinker,
        causal_graph: CausalGraph,
    ) -> None:
        self._thinker = thinker
        self._graph = causal_graph

    def reflect(
        self,
        max_iterations: int = 100,
        journal_context: str = "",
    ) -> Thought:
        """Run deep reflection.

        Creates a minimal stimulus (no user message — Luna is dreaming)
        and lets the Thinker process for up to max_iterations.
        Updates the causal graph with discovered causalities.

        Args:
            max_iterations: Maximum thinking iterations.
            journal_context: Optional context from previous dream journal
                entries. Injected as a weak signal via Stimulus.
        """
        state = self._thinker._state

        # Build dream stimulus — no user message (sleeping)
        stimulus = Stimulus(
            user_message="",
            metrics={},
            phi_iit=state.compute_phi_iit(),
            phase=state.get_phase(),
            psi=state.psi,
            psi_trajectory=list(state.history[-10:]) if state.history else [],
            dream_journal_context=journal_context,
        )

        thought = self._thinker.think(
            stimulus=stimulus,
            max_iterations=max_iterations,
            mode=ThinkMode.REFLECTIVE,
        )

        # Update causal graph with discovered causalities
        step = state.step_count
        for causality in thought.causalities:
            self._graph.observe_pair(
                causality.cause,
                causality.effect,
                step=step,
            )

        # Prune dead edges
        self._graph.prune()

        return thought

    def persist_insights(
        self,
        thought: Thought,
        insights_dir: Path,
    ) -> Path | None:
        """Persist insights to memory_fractal/insights/.

        Format: dream_insight_{timestamp}.json
        Contains: observations, causalities, proposals, depth, confidence.

        Returns the path of the created file, or None if no insights.
        """
        if not thought.insights:
            return None

        insights_dir = Path(insights_dir)
        insights_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        filename = f"dream_insight_{ts}.json"
        path = insights_dir / filename

        data = {
            "timestamp": ts,
            "depth_reached": thought.depth_reached,
            "confidence": thought.confidence,
            "observation_count": len(thought.observations),
            "causality_count": len(thought.causalities),
            "insight_count": len(thought.insights),
            "proposal_count": len(thought.proposals),
            "insights": [
                {
                    "type": i.type,
                    "content": i.content,
                    "confidence": i.confidence,
                    "iteration": i.iteration,
                }
                for i in thought.insights
            ],
            "uncertainties": thought.uncertainties,
        }

        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)

        return path
