"""Luna — Consciousness engine for the 4-agent ecosystem.

Architecture:
    luna/
    ├── core/           # LunaEngine, config (TOML)
    ├── consciousness/  # ConsciousnessState, checkpoints, Phi_IIT
    ├── phi_engine/     # Re-exports from luna_common.phi_engine
    ├── llm_bridge/     # Provider-agnostic LLM cognitive substrate
    ├── pipeline/       # Filesystem JSON protocol between agents
    ├── orchestrator/   # Async autonomous loop (Engine + Pipeline + LLM)
    ├── heartbeat/      # Phi-modulated idle pulse (Phase 5)
    ├── dream/          # Nocturnal consolidation cycle (Phase 6)
    ├── memory/         # Fractal memory V2 async adapter (Phase 7)
    ├── chat/           # Human-facing conversation interface (Phase 8)
    └── _legacy/        # Stubs for backward compatibility

Shared library (imported, never modified):
    luna_common/        # Matrices, evolution, schemas, constants, phi_engine
"""

__version__ = "2.2.0-dev"
