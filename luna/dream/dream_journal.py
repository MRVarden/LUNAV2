"""DreamJournal — persistent, append-only dream memory.

Each dream cycle records its outputs as a DreamJournalEntry. The next dream
recalls recent entries as context, enabling cumulative consolidation: Dream N+1
knows what Dream N discovered.

Storage: JSONL in memory_fractal/dream_journal.jsonl
Deletion policy: ZERO — append-only, Luna preserves everything.
LLM calls: ZERO — all insights are deterministic.

Integration points:
  - DreamCycle.__init__  : accepts dream_journal parameter
  - DreamCycle.run()     : recalls context at start, records entry at end
  - CognitiveLoop._boot  : creates DreamJournal, passes to DreamCycle
  - ChatSession._finalize_dream_v2 : records entry after dream
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from luna_common.constants import INV_PHI, INV_PHI3

log = logging.getLogger(__name__)


# Component names indexed by argmax of psi0_delta.
_PSI_COMPONENTS = ("Perception", "Reflexion", "Integration", "Expression")


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class DreamJournalEntry:
    """Single dream record — deterministic snapshot of one dream cycle."""

    dream_id: str
    timestamp: str                        # ISO 8601 UTC
    dream_number: int                     # Sequential (1-indexed)
    mode: str                             # "full", "quick"
    skills_learned: list[str]             # Skill descriptions
    simulation_insights: list[str]        # Flattened from all SimulationResults
    psi0_delta: list[float]               # Identity consolidation delta
    cem_summary: str | None               # LearningTrace.summary() or None
    reflection_summary: str | None        # Deterministic reflection synopsis
    phi_before: float
    phi_after: float
    key_insight: str                      # One-line deterministic synthesis
    tags: list[str] = field(default_factory=list)  # Thematic tags for recall

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DreamJournalEntry:
        return cls(
            dream_id=data.get("dream_id", ""),
            timestamp=data.get("timestamp", ""),
            dream_number=data.get("dream_number", 0),
            mode=data.get("mode", "full"),
            skills_learned=data.get("skills_learned", []),
            simulation_insights=data.get("simulation_insights", []),
            psi0_delta=data.get("psi0_delta", []),
            cem_summary=data.get("cem_summary"),
            reflection_summary=data.get("reflection_summary"),
            phi_before=data.get("phi_before", 0.0),
            phi_after=data.get("phi_after", 0.0),
            key_insight=data.get("key_insight", ""),
            tags=data.get("tags", []),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  DREAM JOURNAL
# ══════════════════════════════════════════════════════════════════════════════


class DreamJournal:
    """Persistent, append-only dream memory. Zero deletion.

    Stores entries as JSONL (one JSON object per line). Reads are lazy —
    entries are loaded once at init and kept in memory. Writes use atomic
    append (write to .tmp, then append to main file).
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: list[DreamJournalEntry] = []
        self._load()

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Total number of recorded dreams."""
        return len(self._entries)

    def record(self, entry: DreamJournalEntry) -> None:
        """Append a new dream entry. Atomic write.

        The entry is serialized to JSON, written to a .tmp file, then
        appended to the main JSONL file. If the append fails, the .tmp
        file is left for manual recovery (zero deletion).
        """
        self._entries.append(entry)
        self._append(entry)
        log.info(
            "Dream journal: recorded dream #%d (%s) — %s",
            entry.dream_number, entry.dream_id[:8], entry.key_insight,
        )

    def recall(self, limit: int = 5) -> list[DreamJournalEntry]:
        """Return the N most recent entries for dream context.

        Args:
            limit: Maximum entries to return. Clamped to available count.

        Returns:
            List of entries ordered oldest-first (chronological for context).
        """
        if not self._entries:
            return []
        start = max(0, len(self._entries) - limit)
        return list(self._entries[start:])

    def recall_by_theme(self, tags: list[str], limit: int = 3) -> list[DreamJournalEntry]:
        """Return entries matching any of the thematic tags.

        Scans from most recent to oldest, returns up to `limit` matches
        in chronological order.
        """
        if not tags or not self._entries:
            return []
        tag_set = set(t.lower() for t in tags)
        matches: list[DreamJournalEntry] = []
        for entry in reversed(self._entries):
            entry_tags = set(t.lower() for t in entry.tags)
            if entry_tags & tag_set:
                matches.append(entry)
                if len(matches) >= limit:
                    break
        matches.reverse()  # Chronological order
        return matches

    def summary(self, last_n: int = 10) -> str:
        """Generate a text summary of recent dreams for context injection.

        Returns a deterministic, human-readable digest. No LLM calls.
        """
        entries = self.recall(limit=last_n)
        if not entries:
            return "No previous dreams recorded."

        lines: list[str] = [f"Dream Journal ({len(entries)} recent entries):"]
        for e in entries:
            lines.append(
                f"  #{e.dream_number} [{e.mode}] phi {e.phi_before:.3f}->{e.phi_after:.3f}: "
                f"{e.key_insight}"
            )

        # Cumulative statistics
        total_skills = sum(len(e.skills_learned) for e in entries)
        total_sims = sum(len(e.simulation_insights) for e in entries)
        avg_phi_delta = (
            sum(e.phi_after - e.phi_before for e in entries) / len(entries)
            if entries else 0.0
        )
        lines.append(
            f"  Cumulative: {total_skills} skills, {total_sims} insights, "
            f"avg phi delta {avg_phi_delta:+.4f}"
        )
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from JSONL. Handles corruption gracefully.

        Bad lines are logged and skipped — never crash on corrupt data.
        """
        if not self._path.exists():
            log.debug("Dream journal not found at %s — starting fresh", self._path)
            return

        loaded = 0
        skipped = 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = DreamJournalEntry.from_dict(data)
                        self._entries.append(entry)
                        loaded += 1
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        skipped += 1
                        log.warning(
                            "Dream journal: skipped corrupt line %d in %s",
                            line_num, self._path,
                        )
        except OSError:
            log.warning("Dream journal: could not read %s", self._path, exc_info=True)

        if loaded > 0 or skipped > 0:
            log.info(
                "Dream journal loaded: %d entries, %d skipped from %s",
                loaded, skipped, self._path,
            )

    def _append(self, entry: DreamJournalEntry) -> None:
        """Atomic append to JSONL.

        Strategy:
          1. Serialize entry to JSON (single line, no pretty print).
          2. Write to .tmp file.
          3. Read .tmp and append to main JSONL.
          4. Remove .tmp.

        If step 3 fails, the .tmp file survives for manual recovery.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_dict(), separators=(",", ":"), ensure_ascii=False)

        tmp_path = self._path.with_suffix(".tmp")
        try:
            # Write to tmp first (crash-safe: either full write or nothing).
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            # Append tmp content to main file.
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            # Clean up tmp.
            try:
                tmp_path.unlink()
            except OSError:
                pass  # Non-critical

        except OSError:
            log.error(
                "Dream journal: failed to append entry %s (tmp preserved at %s)",
                entry.dream_id, tmp_path,
                exc_info=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY BUILDER — deterministic synthesis from DreamResult
# ══════════════════════════════════════════════════════════════════════════════


def build_journal_entry(
    dream_result: object,
    journal: DreamJournal,
    phi_before: float,
    phi_after: float,
) -> DreamJournalEntry:
    """Build a DreamJournalEntry from a DreamResult. No LLM calls.

    Args:
        dream_result: A DreamResult instance.
        journal: The DreamJournal (for sequential numbering).
        phi_before: Phi IIT measured before the dream.
        phi_after: Phi IIT measured after the dream.

    Returns:
        A fully populated DreamJournalEntry ready for recording.
    """
    dream_number = journal.count + 1
    dream_id = uuid.uuid4().hex[:16]
    timestamp = datetime.now(timezone.utc).isoformat()

    # Skills — extract descriptions.
    skills_desc: list[str] = []
    for skill in dream_result.skills_learned:
        desc = f"{skill.trigger}({skill.outcome}, phi {skill.phi_impact:+.3f})"
        if skill.context:
            desc += f": {skill.context[:60]}"
        skills_desc.append(desc)

    # Simulation insights — flatten all insights from all simulations.
    sim_insights: list[str] = []
    for sim in dream_result.simulations:
        for insight in sim.insights:
            label = f"{sim.scenario.source}/{sim.scenario.name}: {insight}"
            sim_insights.append(label[:120])

    # Psi0 delta.
    psi0_delta = list(dream_result.psi0_delta) if dream_result.psi0_delta else []

    # CEM summary — deterministic from LearningTrace.
    cem_summary: str | None = None
    if dream_result.learning_trace is not None:
        cem_summary = dream_result.learning_trace.summary()

    # Reflection summary — deterministic from Thought.
    reflection_summary: str | None = None
    if dream_result.thought is not None:
        t = dream_result.thought
        parts: list[str] = []
        parts.append(f"depth={t.depth_reached}, confidence={t.confidence:.3f}")
        if t.needs:
            top_needs = sorted(t.needs, key=lambda n: n.priority, reverse=True)[:2]
            needs_str = ", ".join(n.description[:40] for n in top_needs)
            parts.append(f"needs=[{needs_str}]")
        if t.proposals:
            props_str = ", ".join(p.description[:40] for p in t.proposals[:2])
            parts.append(f"proposals=[{props_str}]")
        reflection_summary = "; ".join(parts)

    # Key insight — deterministic one-line synthesis.
    key_insight = _synthesize_key_insight(
        dream_result, phi_before, phi_after, psi0_delta,
    )

    # Tags — derived from content for thematic recall.
    tags = _extract_tags(dream_result, sim_insights)

    return DreamJournalEntry(
        dream_id=dream_id,
        timestamp=timestamp,
        dream_number=dream_number,
        mode=dream_result.mode,
        skills_learned=skills_desc,
        simulation_insights=sim_insights,
        psi0_delta=psi0_delta,
        cem_summary=cem_summary,
        reflection_summary=reflection_summary,
        phi_before=phi_before,
        phi_after=phi_after,
        key_insight=key_insight,
        tags=tags,
    )


def _synthesize_key_insight(
    dream_result: object,
    phi_before: float,
    phi_after: float,
    psi0_delta: list[float],
) -> str:
    """Deterministic one-line synthesis. No LLM.

    Format:
        "N skills (dominant_skill), M sims (stability X.XXX),
         identity drifting toward Component, CEM J +/-X.XXX"
    """
    parts: list[str] = []

    # Skills count + most significant.
    n_skills = len(dream_result.skills_learned)
    if n_skills > 0:
        # Most significant = largest absolute phi_impact.
        best = max(dream_result.skills_learned, key=lambda s: abs(s.phi_impact))
        trigger = best.trigger
        parts.append(f"{n_skills} skill{'s' if n_skills != 1 else ''} ({trigger} dominant)")
    else:
        parts.append("0 skills")

    # Simulation stability.
    n_sims = len(dream_result.simulations)
    if n_sims > 0:
        avg_stability = sum(s.stability for s in dream_result.simulations) / n_sims
        parts.append(f"{n_sims} sims (stability {avg_stability:.3f})")
    else:
        parts.append("0 sims")

    # Psi0 drift direction.
    if psi0_delta and any(abs(d) > 1e-8 for d in psi0_delta):
        # Component with largest absolute delta.
        abs_deltas = [abs(d) for d in psi0_delta]
        max_idx = abs_deltas.index(max(abs_deltas))
        comp_name = _PSI_COMPONENTS[max_idx] if max_idx < len(_PSI_COMPONENTS) else f"dim{max_idx}"
        direction = "toward" if psi0_delta[max_idx] > 0 else "away from"
        parts.append(f"identity drifting {direction} {comp_name}")

    # CEM improvement.
    if dream_result.learning_trace is not None:
        trace = dream_result.learning_trace
        j_delta = trace.final_j - trace.initial_j
        parts.append(f"CEM J {j_delta:+.4f}")

    # Phi delta.
    phi_delta = phi_after - phi_before
    parts.append(f"phi {phi_delta:+.4f}")

    return ", ".join(parts)


def _extract_tags(dream_result: object, sim_insights: list[str]) -> list[str]:
    """Extract thematic tags from dream content. Deterministic keyword scan."""
    tags: list[str] = []

    # From simulation insights.
    insight_text = " ".join(sim_insights).lower()
    if "phi_collapse" in insight_text:
        tags.append("phi_collapse_risk")
    if "identity_resilient" in insight_text:
        tags.append("identity_strong")
    if "identity_weak" in insight_text:
        tags.append("identity_weak")
    if "collapse_recovered" in insight_text:
        tags.append("collapse_recovery")
    if "collapse_persists" in insight_text:
        tags.append("collapse_risk")
    if "high_plasticity" in insight_text:
        tags.append("high_plasticity")
    if "low_plasticity" in insight_text:
        tags.append("low_plasticity")
    if "endurance_passed" in insight_text:
        tags.append("endurance_strong")
    if "endurance_failed" in insight_text:
        tags.append("endurance_weak")

    # From skills.
    for skill in dream_result.skills_learned:
        if skill.outcome == "positive" and skill.phi_impact > INV_PHI:
            tags.append("high_impact_positive")
            break
    for skill in dream_result.skills_learned:
        if skill.outcome == "negative" and abs(skill.phi_impact) > INV_PHI:
            tags.append("high_impact_negative")
            break

    # From CEM.
    if dream_result.learning_trace is not None:
        trace = dream_result.learning_trace
        if trace.final_j > trace.initial_j:
            tags.append("cem_improved")
        elif trace.final_j < trace.initial_j:
            tags.append("cem_regressed")

    # From psi0 delta.
    if dream_result.psi0_applied:
        tags.append("identity_consolidated")

    # Mode.
    tags.append(f"mode_{dream_result.mode}")

    return tags


def format_journal_context(entries: list[DreamJournalEntry]) -> str:
    """Format recalled journal entries as context string for dream injection.

    This string is fed into the simulation and reflection phases as weak
    context — previous dreams' discoveries available for the current dream.
    """
    if not entries:
        return ""

    lines: list[str] = [
        f"[Dream Journal — {len(entries)} previous dream(s) recalled]"
    ]
    for e in entries:
        lines.append(
            f"  Dream #{e.dream_number} ({e.timestamp[:10]}, {e.mode}): "
            f"{e.key_insight}"
        )
        if e.skills_learned:
            lines.append(f"    Skills: {', '.join(e.skills_learned[:3])}")
        if e.simulation_insights:
            # Show only the most interesting insights.
            notable = [i for i in e.simulation_insights if "collapse" in i.lower() or "identity" in i.lower()]
            if not notable:
                notable = e.simulation_insights[:2]
            lines.append(f"    Insights: {', '.join(notable[:3])}")
    return "\n".join(lines)
