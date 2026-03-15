"""Dashboard endpoint — returns full state snapshot in a single call.

Designed for the Luna Dashboard frontend at localhost:3618.
Aggregates consciousness, affect, dream, identity, and
recent cycles into one response to minimize polling overhead.

The ``orch`` dependency is a CognitiveLoop instance that owns
all subsystems as public attributes — no indirect access needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from luna.api.dependencies import get_orchestrator

log = logging.getLogger(__name__)

router = APIRouter()


def _safe_get(obj: object, *attrs: str, default=None):
    """Safely traverse nested attributes."""
    current = obj
    for attr in attrs:
        current = getattr(current, attr, None)
        if current is None:
            return default
    return current


def _to_list(val) -> list:
    """Convert numpy array or tuple to list."""
    if hasattr(val, "tolist"):
        return val.tolist()
    if isinstance(val, (list, tuple)):
        return list(val)
    return []


@router.get("/snapshot")
async def get_snapshot(orch: object = Depends(get_orchestrator)) -> dict:
    """Full dashboard state snapshot — one call, all data."""
    engine = getattr(orch, "engine", None)
    result: dict = {"timestamp": datetime.utcnow().isoformat(), "connected": True}

    # ── Consciousness ────────────────────────────────────────────
    cs = _safe_get(engine, "consciousness")
    if cs is not None:
        status = engine.get_status() if hasattr(engine, "get_status") else {}
        result["consciousness"] = {
            "psi": _to_list(cs.psi),
            "psi0": _to_list(cs.psi0),
            "psi0_core": _to_list(getattr(cs, "psi0_core", cs.psi0)),
            "psi0_adaptive": _to_list(getattr(cs, "_psi0_adaptive", [0, 0, 0, 0])),
            "step_count": getattr(cs, "step_count", 0),
            "agent_name": getattr(cs, "agent_name", "Luna"),
            "phi_iit": status.get("phi_iit", 0.0),
            "phase": status.get("phase", "unknown"),
            "emergent_phi": status.get("emergent_phi"),
            "emergent_phi_precision": status.get("emergent_phi_precision", 0),
            "emergent_phi_bootstrapping": status.get("emergent_phi_bootstrapping", True),
        }

    # ── Affect ───────────────────────────────────────────────────
    affect_engine = getattr(orch, "affect_engine", None)
    if affect_engine is not None:
        affect = getattr(affect_engine, "_affect", None)
        mood = getattr(affect_engine, "_mood", None)
        zone_tracker = getattr(affect_engine, "_zone_tracker", None)
        result["affect"] = {
            "affect": {
                "valence": getattr(affect, "valence", 0.0),
                "arousal": getattr(affect, "arousal", 0.0),
                "dominance": getattr(affect, "dominance", 0.0),
            } if affect else {"valence": 0.0, "arousal": 0.0, "dominance": 0.0},
            "mood": {
                "valence": getattr(mood, "valence", 0.0),
                "arousal": getattr(mood, "arousal", 0.0),
                "dominance": getattr(mood, "dominance", 0.0),
            } if mood else {"valence": 0.0, "arousal": 0.0, "dominance": 0.0},
            "emotions": _get_emotions(affect_engine),
            "uncovered": bool(getattr(zone_tracker, "_zones", [])),
        }

    # ── Dream ────────────────────────────────────────────────────
    sleep_mgr = getattr(orch, "sleep_manager", None)
    dream_cycle = getattr(orch, "dream_cycle", None)
    if sleep_mgr is not None:
        try:
            ds = sleep_mgr.get_status()
            state_raw = getattr(ds, "state", "awake")
            result["dream"] = {
                "state": state_raw.value if hasattr(state_raw, "value") else str(state_raw),
                "dream_count": getattr(ds, "dream_count", 0),
                "last_dream_at": getattr(ds, "last_dream_at", None),
                "last_dream_duration": getattr(ds, "last_dream_duration", 0.0),
                "total_dream_time": getattr(ds, "total_dream_time", 0.0),
                "dream_mode": None,
                "skills_learned": 0,
                "psi0_drift": [0, 0, 0, 0],
            }
        except Exception as exc:
            log.debug("Dream status unavailable: %s", exc)
    elif dream_cycle is not None:
        result["dream"] = {
            "state": "awake",
            "dream_count": getattr(dream_cycle, "_dream_count", 0),
            "last_dream_at": getattr(dream_cycle, "_last_dream_at", None),
            "last_dream_duration": getattr(dream_cycle, "_last_dream_duration", 0.0),
            "total_dream_time": getattr(dream_cycle, "_total_dream_time", 0.0),
            "dream_mode": None,
            "skills_learned": 0,
            "psi0_drift": [0, 0, 0, 0],
        }

    # Dream wiring data (v5.3) — enrich with priors if available
    if "dream" in result:
        dream_priors = getattr(orch, "dream_priors", None)
        if dream_priors is not None:
            result["dream"]["skills_learned"] = len(
                getattr(dream_priors, "skill_priors", [])
            )
            drift = (
                dream_priors.cumulative_drift()
                if hasattr(dream_priors, "cumulative_drift")
                else (0, 0, 0, 0)
            )
            result["dream"]["psi0_drift"] = list(drift)
            result["dream"]["dream_mode"] = getattr(dream_priors, "dream_mode", None)

    # ── Identity ─────────────────────────────────────────────────
    identity_ctx = _safe_get(engine, "identity_context")
    if identity_ctx is not None:
        result["identity"] = {
            "bundle_hash": getattr(identity_ctx, "bundle_hash", "")[:12] + "...",
            "integrity_ok": getattr(identity_ctx, "integrity_ok", False),
            "kappa": getattr(identity_ctx, "kappa", 0.0),
            "psi0": _to_list(getattr(identity_ctx, "psi0", [])),
            "axioms_count": len(getattr(identity_ctx, "axioms", ())),
        }

    # ── Episodic Memory ─────────────────────────────────────────
    ep_mem = getattr(orch, "episodic_memory", None)
    if ep_mem is not None:
        episodes = getattr(ep_mem, "_episodes", [])
        pinned_count = sum(1 for ep in episodes if getattr(ep, "pinned", False))
        last_ep = episodes[-1] if episodes else None
        result["episodic"] = {
            "total_episodes": getattr(ep_mem, "size", len(episodes)),
            "pinned_count": pinned_count,
            "last_episode_outcome": getattr(last_ep, "outcome", None),
            "last_episode_action": getattr(last_ep, "action_type", None),
        }

    # ── Live Reward (Evaluator in real-time) ─────────────────────
    evaluator = getattr(orch, "evaluator", None)
    if evaluator is not None and cs is not None:
        try:
            psi_now = tuple(float(x) for x in cs.psi)
            phi_iit_now = float(cs.compute_phi_iit()) if hasattr(cs, "compute_phi_iit") else 0.0
            ae = getattr(orch, "affect_engine", None)
            affect_now = getattr(ae, "_affect", None) if ae else None
            cs_store = getattr(orch, "cycle_store", None)
            last_rec = None
            if cs_store is not None and hasattr(cs_store, "read_recent"):
                recent = cs_store.read_recent(1)
                if recent:
                    last_rec = recent[0]
            live_rv = evaluator.evaluate_live(
                psi=psi_now,
                phi_iit=phi_iit_now,
                affect_state=affect_now,
                last_record=last_rec,
            )
            result["live_reward"] = {
                "components": [
                    {"name": c.name, "value": c.value, "raw": c.raw}
                    for c in live_rv.components
                ],
                "dominance_rank": live_rv.dominance_rank,
                "delta_j": live_rv.delta_j,
            }
        except Exception as exc:
            log.debug("Live reward computation failed: %s", exc)

    # ── Autonomy ─────────────────────────────────────────────────
    aw = getattr(orch, "autonomy_window", None)
    if aw is not None:
        result["autonomy"] = {
            "w": getattr(aw, "w", 0),
            "cooldown_remaining": getattr(aw, "cooldown_remaining", 0),
        }

    # ── Initiative ──────────────────────────────────────────────
    init_eng = getattr(orch, "initiative_engine", None)
    if init_eng is not None:
        need_tracker = getattr(init_eng, "_need_tracker", {})
        # Top 3 persistent needs
        top_needs = sorted(need_tracker.items(), key=lambda x: x[1], reverse=True)[:3]
        result["initiative"] = {
            "initiative_count": getattr(init_eng, "_initiative_count", 0),
            "cooldown": getattr(init_eng, "_cooldown", 5),
            "persistent_needs": [{"key": k, "turns": v} for k, v in top_needs],
            "phi_declining": init_eng.is_phi_declining() if hasattr(init_eng, "is_phi_declining") else False,
        }

    # ── Causal Graph ────────────────────────────────────────────
    cg = getattr(orch, "causal_graph", None)
    if cg is not None:
        try:
            cg_stats = cg.stats()
            result["causal_graph"] = {
                "node_count": cg_stats.get("node_count", 0),
                "edge_count": cg_stats.get("edge_count", 0),
                "confirmed_count": cg_stats.get("confirmed_count", 0),
                "avg_strength": round(cg_stats.get("avg_strength", 0.0), 4),
                "density": round(cg_stats.get("density", 0.0), 4),
            }
        except Exception as exc:
            log.debug("CausalGraph stats failed: %s", exc)

    # ── Endogenous ──────────────────────────────────────────────
    endo = getattr(orch, "endogenous", None)
    if endo is not None:
        buffer = getattr(endo, "_buffer", [])
        pending = []
        for imp in buffer[:5]:
            src = getattr(imp, "source", None)
            pending.append({
                "source": src.value if hasattr(src, "value") else str(src),
                "message": getattr(imp, "message", "")[:100],
                "urgency": round(getattr(imp, "urgency", 0.0), 3),
            })
        result["endogenous"] = {
            "buffer_size": getattr(endo, "buffer_size", 0),
            "total_emitted": getattr(endo, "total_emitted", 0),
            "last_valence": round(getattr(endo, "last_valence", 0.0), 3),
            "pending_impulses": pending,
        }

    # ── Circuit Breaker (v6.0) ──────────────────────────────────
    cb = getattr(orch, "circuit_breaker", None)
    if cb is not None:
        result["circuit_breaker"] = cb.to_dict()

    # ── Synthesis (v6.0) ─────────────────────────────────────────
    synth = getattr(orch, "synthesis", None)
    last_report = getattr(orch, "last_synthesis_report", None)
    if synth is not None:
        try:
            # Use cached report if available, otherwise run on-demand.
            if last_report is not None:
                report = last_report
            else:
                report = synth.run(window=30)
            result["synthesis"] = {
                "cycles_analyzed": report.cycles_analyzed,
                "trends": [
                    {
                        "metric": t.metric,
                        "slope": t.slope,
                        "r_squared": t.r_squared,
                        "direction": t.direction,
                        "window": t.window,
                    }
                    for t in report.trends
                ],
                "anomalies": [
                    {
                        "metric": a.metric,
                        "cycle_index": a.cycle_index,
                        "value": a.value,
                        "sigma_deviation": a.sigma_deviation,
                    }
                    for a in report.anomalies[:10]
                ],
                "cross_patterns": [
                    {
                        "metric_a": cp.metric_a,
                        "metric_b": cp.metric_b,
                        "correlation": cp.correlation,
                        "description": cp.description,
                    }
                    for cp in report.cross_patterns
                ],
                "summary": report.summary,
            }
        except Exception as exc:
            log.debug("Synthesis snapshot failed: %s", exc)

    # ── Recent Cycles ────────────────────────────────────────────
    cycle_store = getattr(orch, "cycle_store", None)
    if cycle_store is not None:
        try:
            recent = cycle_store.read_recent(20) if hasattr(cycle_store, "read_recent") else []
            result["cycles"] = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in recent
            ]
        except Exception as exc:
            log.debug("CycleStore read failed: %s", exc)

    # ── Fallback: read cycles from JSONL files ───────────────────
    if "cycles" not in result:
        result["cycles"] = _read_recent_cycles_from_disk(orch)

    return result


def _get_emotions(affect_engine) -> list[dict]:
    """Extract current top emotions from AffectEngine."""
    try:
        from luna.consciousness.emotion_repertoire import interpret
        affect = getattr(affect_engine, "_affect", None)
        mood = getattr(affect_engine, "_mood", None)
        repertoire = getattr(affect_engine, "_repertoire", None)
        event_count = getattr(affect_engine, "_event_count", 0)
        if affect and mood and repertoire:
            emotions_raw = interpret(
                affect.as_tuple(), mood.as_tuple(), repertoire,
                event_count=event_count,
            )
            return [
                {"fr": ew.fr, "en": ew.en, "weight": w, "family": ew.family}
                for ew, w in emotions_raw[:5]
            ]
    except Exception:
        pass
    return []


def _read_recent_cycles_from_disk(orch, n: int = 20) -> list[dict]:
    """Fallback: read recent CycleRecords from JSONL files on disk."""
    try:
        config = getattr(orch, "config", None)
        if config is None:
            return []
        data_dir = Path(getattr(config, "root_dir", ".")) / "data" / "cycles"
        if not data_dir.exists():
            return []
        files = sorted(data_dir.glob("cycles_*.jsonl"), reverse=True)
        if not files:
            return []
        records = []
        for line in files[0].read_text().strip().split("\n")[-n:]:
            if line.strip():
                records.append(json.loads(line))
        return records
    except Exception as exc:
        log.debug("Disk cycle read failed: %s", exc)
        return []
