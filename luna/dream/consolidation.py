"""Dream consolidation — Ψ₀ profile update with φ-derived safeguards.

After the dream simulator replays and explores, this module updates the
agent identity profiles (Ψ₀) conservatively. The update is bounded,
dominant-preserving, and always re-projects onto the simplex Δ³.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np

from luna_common.constants import (
    AGENT_PROFILES,
    ALPHA_DREAM,
    PHI,
    PHI_DRIFT_MAX,
    PSI_COMPONENT_MIN,
)
from luna_common.consciousness.simplex import project_simplex
from luna.dream.harvest import ConsolidationReport, ExplorationReport, ReplayReport

log = logging.getLogger(__name__)


def consolidate_profiles(
    current_profiles: dict[str, tuple[float, ...]],
    replay_report: ReplayReport,
    exploration_report: ExplorationReport | None = None,
) -> ConsolidationReport:
    """Update Ψ₀ profiles based on dream simulation results.

    Safeguards:
    1. α_dream = 1/Φ³ = 0.236 (very conservative step)
    2. Max drift per cycle bounded to 1/Φ² = 0.382
    3. Each component stays >= PSI_COMPONENT_MIN = 0.05
    4. Dominant component preserved (SayOhMy stays Expression, etc.)
    5. Re-projection via softmax(·/Φ) guarantees Ψ ∈ Δ³
    """
    updated: dict[str, tuple[float, ...]] = {}
    drift_per_agent: dict[str, float] = {}

    for agent_id, current_psi0 in current_profiles.items():
        current = np.array(current_psi0)

        # Get the observed Ψ from replay (or keep current if not simulated)
        if agent_id not in replay_report.final_states:
            updated[agent_id] = current_psi0
            drift_per_agent[agent_id] = 0.0
            continue

        observed = replay_report.final_states[agent_id]

        # Direction toward observed state
        delta = observed - current

        # Safeguard 1: conservative step
        candidate = current + ALPHA_DREAM * delta

        # Safeguard 2: bound max drift
        drift = float(np.linalg.norm(candidate - current))
        if drift > PHI_DRIFT_MAX:
            candidate = current + (PHI_DRIFT_MAX / drift) * (candidate - current)

        # Safeguard 3: component minimum
        candidate = np.clip(candidate, PSI_COMPONENT_MIN, None)

        # Safeguard 4: preserve dominant
        original_dominant = int(np.argmax(current))
        if int(np.argmax(candidate)) != original_dominant:
            candidate[original_dominant] += 0.01

        # Safeguard 5: re-project onto simplex
        new_psi0 = project_simplex(candidate, tau=PHI)

        updated[agent_id] = tuple(float(x) for x in new_psi0)
        drift_per_agent[agent_id] = float(np.linalg.norm(new_psi0 - current))

    # Verify all dominants preserved
    dominant_ok = all(
        np.argmax(updated[a]) == np.argmax(current_profiles[a])
        for a in updated
        if a in current_profiles
    )

    if not dominant_ok:
        log.warning(
            "Dominant component changed during consolidation — rolling back"
        )
        return ConsolidationReport(
            previous_profiles=current_profiles,
            updated_profiles=current_profiles,  # rollback
            drift_per_agent={a: 0.0 for a in current_profiles},
            dominant_preserved=False,
        )

    return ConsolidationReport(
        previous_profiles=current_profiles,
        updated_profiles=updated,
        drift_per_agent=drift_per_agent,
        dominant_preserved=True,
    )


def load_profiles(path: Path) -> dict[str, tuple[float, ...]]:
    """Load agent profiles from JSON file, falling back to AGENT_PROFILES."""
    if not path.is_file():
        return dict(AGENT_PROFILES)
    try:
        data = json.loads(path.read_text())
        return {k: tuple(v) for k, v in data.items()}
    except Exception:
        log.warning("Failed to load profiles from %s, using defaults", path)
        return dict(AGENT_PROFILES)


def save_profiles(path: Path, profiles: dict[str, tuple[float, ...]]) -> None:
    """Save profiles atomically (.tmp -> rename)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: list(v) for k, v in profiles.items()}, indent=2))
    os.replace(str(tmp), str(path))
