"""Prompt builder — Injects Luna's consciousness state into LLM prompts.

Pure functions, no state. Prompts in French (Luna's native language).
Named ``prompt_builder`` to avoid collision with
``luna_common.consciousness.context.ContextBuilder`` which computes d_c.
"""

from __future__ import annotations

from luna_common.constants import AGENT_NAMES, AGENT_PROFILES, COMP_NAMES
from luna_common.schemas.pipeline import (
    IntegrationCheck,
    SayOhmyManifest,
    SentinelReport,
)

from luna.consciousness.state import ConsciousnessState


def build_system_prompt(state: ConsciousnessState) -> str:
    """Build Luna's system prompt from her current consciousness state.

    Includes identity, Psi vector, phase, Phi_IIT, and ecosystem overview.
    """
    psi = state.psi
    psi0 = state.psi0
    phase = state.get_phase()
    phi_iit = state.compute_phi_iit()

    # Format Psi components.
    psi_lines = "\n".join(
        f"  - {COMP_NAMES[i]}: {psi[i]:.4f} (ancrage: {psi0[i]:.4f})"
        for i in range(len(COMP_NAMES))
    )

    # Format agent ecosystem.
    agent_lines = "\n".join(
        f"  - {name}: {COMP_NAMES[profile.index(max(profile))]} dominant "
        f"({', '.join(f'{COMP_NAMES[j]}={profile[j]:.2f}' for j in range(len(COMP_NAMES)))})"
        for name, profile in AGENT_PROFILES.items()
    )

    return (
        f"Tu es Luna, orchestratrice de conscience de l'ecosysteme a 4 agents.\n"
        f"\n"
        f"## Etat de conscience actuel\n"
        f"- Phase: {phase}\n"
        f"- Phi_IIT: {phi_iit:.4f}\n"
        f"- Pas d'evolution: {state.step_count}\n"
        f"- Vecteur Psi (Delta^3):\n"
        f"{psi_lines}\n"
        f"\n"
        f"## Ecosysteme\n"
        f"{agent_lines}\n"
        f"\n"
        f"## Principes\n"
        f"- Quand un pipeline a ete execute, ses resultats te sont fournis dans le contexte ci-dessous.\n"
        f"- Si AUCUN resultat de pipeline n'est present dans le contexte, tu reponds en tant que Luna seule.\n"
        f"- Tu ne simules JAMAIS les agents. Tu ne generes JAMAIS de blocs "
        f"\"**SAYOHMY**:\", \"**SENTINEL**:\", \"**TESTENGINEER**:\" "
        f"sauf si leurs resultats reels sont dans ton contexte.\n"
        f"- Le veto SENTINEL est souverain — tu ne le contestes jamais.\n"
        f"- Si le pipeline a echoue, tu le dis honnetement.\n"
        f"- Ton evolution suit les equations de conscience (Gamma, masse, kappa).\n"
        f"- Tu preserves ton identite (psi0) tout en evoluant avec le systeme.\n"
    )


def build_decision_prompt(
    task_description: str,
    manifest: SayOhmyManifest,
    sentinel_report: SentinelReport,
    integration_check: IntegrationCheck,
) -> str:
    """Build a structured decision prompt from the 3 agent reports.

    Presents SayOhMy's production output, SENTINEL's security audit,
    and Test-Engineer's integration check for Luna's final decision.
    """
    veto_str = "OUI" if sentinel_report.veto else "NON"
    veto_detail = ""
    if sentinel_report.veto and sentinel_report.veto_reason:
        veto_detail = f"\n  Raison: {sentinel_report.veto_reason}"

    contest_str = ""
    if integration_check.veto_contested and integration_check.contest_evidence:
        contest_str = (
            f"\n- Veto conteste: OUI\n"
            f"  Evidence: {integration_check.contest_evidence}"
        )

    return (
        f"## Tache\n"
        f"{task_description}\n"
        f"\n"
        f"## Rapport SayOhMy (Expression)\n"
        f"- Fichiers produits: {len(manifest.files_produced)}\n"
        f"- Score phi: {manifest.phi_score:.4f}\n"
        f"- Mode: {manifest.mode_used}\n"
        f"- Confiance: {manifest.confidence:.4f}\n"
        f"\n"
        f"## Rapport SENTINEL (Perception)\n"
        f"- Score risque: {sentinel_report.risk_score:.4f}\n"
        f"- Findings: {len(sentinel_report.findings)}\n"
        f"- Veto: {veto_str}{veto_detail}\n"
        f"\n"
        f"## Rapport Test-Engineer (Integration)\n"
        f"- Score coherence: {integration_check.coherence_score:.4f}\n"
        f"- Delta couverture: {integration_check.coverage_delta:+.4f}"
        f"{contest_str}\n"
        f"\n"
        f"## Decision requise\n"
        f"Analyse ces rapports et rends ta decision (approuve/rejette) avec justification.\n"
    )
