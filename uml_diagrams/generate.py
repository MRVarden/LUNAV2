#!/usr/bin/env python3
"""Luna v7.0 — UML Diagram Generator.

Introspects the Luna codebase via AST parsing and generates
PlantUML (.puml) source files for 6 architecture diagrams.

Usage: python3 generate.py
Output: uml_diagrams/output/*.puml
"""

from __future__ import annotations

import ast
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════

LUNA_ROOT = Path(__file__).resolve().parent.parent
LUNA_SRC = LUNA_ROOT / "luna"
LUNA_COMMON_SRC = LUNA_ROOT.parent / "luna_common"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ══════════════════════════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════════════════════════

PLANTUML_THEME = """\
skinparam backgroundColor #1A1A2E
skinparam defaultFontName "Segoe UI"
skinparam defaultFontSize 13
skinparam defaultFontColor #E0E0E0
skinparam shadowing false

skinparam package {
    BackgroundColor #16213E
    BorderColor #0F3460
    FontColor #E0E0E0
    StereotypeFontColor #E94560
}

skinparam class {
    BackgroundColor #0F3460
    BorderColor #533483
    FontColor #E0E0E0
    AttributeFontColor #B0B0B0
    StereotypeFontColor #E94560
    HeaderBackgroundColor #16213E
    ArrowColor #53A8B6
}

skinparam component {
    BackgroundColor #0F3460
    BorderColor #533483
    FontColor #E0E0E0
    ArrowColor #E94560
}

skinparam sequence {
    ParticipantBackgroundColor #0F3460
    ParticipantBorderColor #533483
    ParticipantFontColor #E0E0E0
    ArrowColor #533483
    LifeLineBorderColor #0F3460
    LifeLineBackgroundColor #16213E
    DividerBackgroundColor #16213E
    DividerBorderColor #533483
    DividerFontColor #E0E0E0
    GroupBackgroundColor #FFFFFF
    GroupBorderColor #000000
    BoxBackgroundColor #16213E
    BoxBorderColor #0F3460
}

skinparam state {
    BackgroundColor #0F3460
    BorderColor #533483
    FontColor #E0E0E0
    ArrowColor #E94560
    StartColor #E94560
    EndColor #E94560
}

skinparam note {
    BackgroundColor #16213E
    BorderColor #533483
    FontColor #E0E0E0
}

skinparam arrow {
    Color #53A8B6
    FontColor #E0E0E0
}

skinparam title {
    FontColor #E94560
    FontSize 18
    FontStyle bold
}

skinparam legend {
    BackgroundColor #16213E
    BorderColor #0F3460
    FontColor #E0E0E0
}
"""

# ══════════════════════════════════════════════════════════════════
#  AST INTROSPECTION
# ══════════════════════════════════════════════════════════════════

@dataclass
class ClassInfo:
    name: str
    module: str  # e.g. "luna.consciousness.state"
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    is_dataclass: bool = False
    is_abstract: bool = False

@dataclass
class ModuleInfo:
    name: str  # e.g. "luna.consciousness.state"
    path: Path
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # imported module names

def _module_name(path: Path, root: Path, package: str) -> str:
    """Convert a file path to a dotted module name."""
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    return f"{package}.{'.'.join(parts)}"

def _parse_file(path: Path, root: Path, package: str) -> ModuleInfo | None:
    """Parse a single Python file and extract class/import info."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None

    mod_name = _module_name(path, root, package)
    module = ModuleInfo(name=mod_name, path=path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module.imports.append(node.module)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{_attr_name(base)}")

            methods = []
            attributes = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    if not item.name.startswith("_"):
                        methods.append(item.name)
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if not item.target.id.startswith("_"):
                        attributes.append(item.target.id)

            # Detect dataclass decorator
            is_dc = any(
                (isinstance(d, ast.Name) and d.id == "dataclass")
                or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
                for d in node.decorator_list
            )

            # Detect ABC
            is_abc = "ABC" in bases or "abc.ABC" in bases

            ci = ClassInfo(
                name=node.name,
                module=mod_name,
                bases=bases,
                methods=methods[:8],  # Cap at 8 for readability
                attributes=attributes[:6],  # Cap at 6
                is_dataclass=is_dc,
                is_abstract=is_abc,
            )
            module.classes.append(ci)

    return module

def _attr_name(node: ast.Attribute) -> str:
    """Recursively extract dotted name from an ast.Attribute."""
    if isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    elif isinstance(node.value, ast.Attribute):
        return f"{_attr_name(node.value)}.{node.attr}"
    return node.attr

def scan_package(root: Path, package: str) -> list[ModuleInfo]:
    """Scan a Python package directory and return all modules."""
    modules = []
    for py in sorted(root.rglob("*.py")):
        if "__pycache__" in str(py) or py.name.startswith("_legacy"):
            continue
        mod = _parse_file(py, root, package)
        if mod and mod.classes:
            modules.append(mod)
    return modules

# ══════════════════════════════════════════════════════════════════
#  GENERATORS
# ══════════════════════════════════════════════════════════════════

def _subpackage(mod_name: str) -> str:
    """Extract the Luna subpackage name (e.g. 'consciousness' from 'luna.consciousness.state')."""
    parts = mod_name.split(".")
    if len(parts) >= 3:
        return parts[1]
    return parts[-1]

# Color coding for subpackages
_SUBPACKAGE_COLORS = {
    "consciousness": "#1A0A2E",
    "llm_bridge": "#2E0A1A",
    "dream": "#2E1A2E",
    "affect": "#2E1A0A",
    "identity": "#0A2E1A",
    "memory": "#0A1A2E",
    "chat": "#16213E",
    "core": "#16213E",
    "heartbeat": "#0D2137",
    "safety": "#1A2E0A",
    "observability": "#16213E",
    "api": "#0D2137",
    "cli": "#0D2137",
    "orchestrator": "#16213E",
}


def generate_01_overview(luna_modules: list[ModuleInfo]) -> str:
    """Diagram 1: Architecture Overview — component diagram showing all subpackages and their key classes."""
    lines = [
        "@startuml 01_luna_architecture_overview",
        PLANTUML_THEME,
        'title Luna v7.0 — Architecture Overview\\nAuto-generated from source code',
        "",
    ]

    # Group by subpackage
    subpackages: dict[str, list[ClassInfo]] = {}
    for mod in luna_modules:
        sub = _subpackage(mod.name)
        if sub not in subpackages:
            subpackages[sub] = []
        subpackages[sub].extend(mod.classes)

    # Emit packages
    for sub, classes in sorted(subpackages.items()):
        color = _SUBPACKAGE_COLORS.get(sub, "#16213E")
        label = sub.replace("_", " ").title()
        lines.append(f'package "{label}" as {sub} {color} {{')
        for cls in classes:
            stereotype = ""
            if cls.is_dataclass:
                stereotype = " <<dataclass>>"
            elif cls.is_abstract:
                stereotype = " <<abstract>>"
            lines.append(f'  component [{cls.name}]{stereotype} as {sub}_{cls.name}')
        lines.append("}")
        lines.append("")

    # Emit key connections (hardcoded — these are the architectural spine)
    connections = [
        ("chat_ChatSession", "consciousness_ConsciousnessState", "owns"),
        ("chat_ChatSession", "llm_bridge_LLMBridge", "uses"),
        ("chat_ChatSession", "consciousness_Thinker", "think()"),
        ("chat_ChatSession", "consciousness_Decider", "decide()"),
        ("chat_ChatSession", "consciousness_Reactor", "react()"),
        ("chat_ChatSession", "consciousness_Evaluator", "evaluate()"),
        ("chat_ChatSession", "affect_AffectEngine", "process_event()"),
        ("chat_ChatSession", "dream_DreamCycle", "dream trigger"),
        ("consciousness_Thinker", "consciousness_ObservationFactory", "tick()"),
        ("consciousness_Thinker", "identity_IdentityContext", "context"),
        ("consciousness_Reactor", "consciousness_ConsciousnessState", "evolve()"),
        ("consciousness_Evaluator", "consciousness_LearnableParams", "update"),
        ("affect_AffectEngine", "affect_Appraisal", "appraise()"),
        ("affect_Appraisal", "affect_EmotionRepertoire", "interpret()"),
        ("dream_DreamCycle", "dream_DreamLearning", "learning"),
        ("dream_DreamCycle", "dream_DreamReflection", "reflection"),
        ("dream_DreamCycle", "dream_DreamSimulation", "simulation"),
        ("identity_IdentityContext", "identity_IdentityLedger", "ledger"),
        ("identity_IdentityContext", "identity_IdentityBundle", "bundle"),
    ]

    for src, dst, label in connections:
        # Only emit if both endpoints exist
        src_exists = any(f"{_subpackage(m.name)}_{c.name}" == src for m in luna_modules for c in m.classes)
        dst_exists = any(f"{_subpackage(m.name)}_{c.name}" == dst for m in luna_modules for c in m.classes)
        if src_exists and dst_exists:
            lines.append(f'{src} --> {dst} : {label}')

    # Legend
    lines.append("")
    lines.append("legend right")
    lines.append("  Luna v7.0 Architecture")
    lines.append("  Auto-generated from source")
    lines.append("  Ψ = (P, R, I, E) on simplex")
    lines.append("  dΨ/dt = Gt·dt + Gx·dx + Gc·dc")
    lines.append("    - Φ·M·Ψ + κ·(Ψ₀ − Ψ)")
    lines.append("end legend")
    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


def generate_02_common_classes(common_modules: list[ModuleInfo]) -> str:
    """Diagram 2: luna_common class diagram."""
    lines = [
        "@startuml 02_luna_common_classes",
        PLANTUML_THEME,
        'title luna_common v7.0 — Shared Classes\\nAuto-generated from source code',
        "",
    ]

    for mod in common_modules:
        for cls in mod.classes:
            stereotype = " <<dataclass>>" if cls.is_dataclass else (" <<abstract>>" if cls.is_abstract else "")
            lines.append(f'class {cls.name}{stereotype} {{')
            for attr in cls.attributes:
                lines.append(f'  +{attr}')
            for method in cls.methods:
                lines.append(f'  +{method}()')
            lines.append("}")
            # Inheritance
            for base in cls.bases:
                if base not in ("ABC", "object"):
                    lines.append(f'{base} <|-- {cls.name}')
            lines.append("")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_03_core_architecture(luna_modules: list[ModuleInfo]) -> str:
    """Diagram 3: Detailed class diagram of all Luna classes."""
    lines = [
        "@startuml 03_luna_core_architecture",
        PLANTUML_THEME,
        "left to right direction",
        'title Luna v7.0 — Core Architecture\\nAuto-generated from source code',
        "",
    ]

    # Group by subpackage
    subpackages: dict[str, list[ClassInfo]] = {}
    for mod in luna_modules:
        sub = _subpackage(mod.name)
        if sub not in subpackages:
            subpackages[sub] = []
        subpackages[sub].extend(mod.classes)

    for sub, classes in sorted(subpackages.items()):
        color = _SUBPACKAGE_COLORS.get(sub, "#16213E")
        label = sub.replace("_", " ").title()
        lines.append(f'package "{label}" as pkg_{sub} {color} {{')
        for cls in classes:
            stereotype = ""
            if cls.is_dataclass:
                stereotype = " <<dataclass>>"
            elif cls.is_abstract:
                stereotype = " <<abstract>>"
            lines.append(f'  class {cls.name}{stereotype} {{')
            for attr in cls.attributes:
                lines.append(f'    +{attr}')
            for method in cls.methods:
                lines.append(f'    +{method}()')
            lines.append("  }")
            # Inheritance
            for base in cls.bases:
                if base not in ("ABC", "object", "Exception"):
                    lines.append(f'  {base} <|-- {cls.name}')
        lines.append("}")
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_04_consciousness_pipeline(luna_modules: list[ModuleInfo]) -> str:
    """Diagram 4: Consciousness pipeline — component flow."""
    # This is architectural knowledge, not purely introspected
    return f"""@startuml 04_consciousness_pipeline
{PLANTUML_THEME}
title Luna v7.0 — Consciousness Pipeline\\nAuto-generated architecture diagram

package "Input" #1A0A2E {{
  component [Watcher] as WAT
  component [ChatSession] as CS
}}

package "Cognition" #0D2137 {{
  component [Thinker] as THK
  component [Decider] as DEC
  component [ObservationFactory] as OBF
  component [EndogenousSource] as ENDO
  component [InitiativeEngine] as INIT
}}

package "Consciousness" #1A0A2E {{
  component [Reactor] as RCT
  component [ConsciousnessState] as PSI
  component [Evaluator] as EVAL
  component [LearnableParams] as LP
}}

package "Affect" #2E1A0A {{
  component [AffectEngine] as AFF
  component [Appraisal] as APR
  component [EmotionRepertoire] as REP
}}

package "Identity" #0A2E1A {{
  component [IdentityContext] as IDC
  component [IdentityLedger] as IDL
  component [IdentityBundle] as IDB
  component [RecoveryShell] as REC
}}

package "Memory" #0A1A2E {{
  component [CausalGraph] as CG
  component [MemoryManager] as MEM
  component [CycleStore] as CYC
  component [EpisodicMemory] as EM
}}

package "Expression" #2E0A1A {{
  component [LLMBridge] as LLM
  component [VoiceValidator] as VV
  component [PromptBuilder] as PB
  component [CircuitBreaker] as CB
}}

package "Autonomy" #1A2E0A {{
  component [AutonomyWindow] as AW
}}

package "Dream" #2E1A2E {{
  component [DreamCycle] as DC
  component [SleepManager] as SM
  component [DreamLearning] as DL
  component [DreamReflection] as DR
  component [DreamSimulation] as DS
}}

package "Infrastructure" #16213E {{
  component [EpochReset] as ER
  component [KillSwitch] as KS
  component [Heartbeat] as HB
  component [TelemetryCollector] as TC
}}

' Core pipeline
CS --> THK : think(stimulus)
THK --> DEC : Thought
DEC --> CS : ConsciousDecision
CS --> RCT : input evolve
CS -[#53A8B6]-> RCT : output evolve
RCT --> PSI : evolve(info_deltas)
CS --> EVAL : evaluate cycle
EVAL --> LP : update params
EVAL --> CYC : RewardVector

' Cognition
THK --> OBF : factory observations
THK --> IDC : identity context
DEC --> IDC : identity context
ENDO --> THK : impulses
INIT --> CS : initiative actions

' Expression
CS -[#F5A623]-> LLM : chat
LLM --> CB : circuit breaker
LLM --> VV : validate output
PB --> LLM : voice prompt

' Affect
CS --> AFF : process_event
AFF --> APR : appraise
APR --> REP : interpret

' Memory
CS --> EM : record episode
CS --> CYC : write CycleRecord
CS --> CG : update causalities

' Dream
CS --> DC : dream trigger
DC --> DL : learning
DC --> DR : reflection
DC --> DS : simulation

' Autonomy
CS --> AW : evaluate ghost

' Infrastructure
KS --> CS : kill sentinel
WAT --> CS : environment events

' Identity
IDC --> IDL : ledger
IDC --> IDB : bundle
EVAL --> IDC : constitution_integrity

note right of PSI
  Consciousness Equation:
  dΨ/dt = Gt·dt + Gx·dx + Gc·dc
  - Φ·M·Ψ + κ·(Ψ₀ - Ψ)
  ----
  Ψ₀ = normalize(core + φ⁻³·adaptive)
end note

note right of DEC
  Dominance rank (lexicographic):
  Safety > Integration > Reflection
  > Perception > Expression > Transversal
end note

@enduml"""


def generate_05_sensorimotor_cycle() -> str:
    """Diagram 5: Sensorimotor cycle — one complete chat turn (sequence diagram)."""
    return f"""@startuml 05_sensorimotor_cycle
{PLANTUML_THEME}
title Luna v7.0 — Sensorimotor Cycle\\nOne complete chat turn (auto-generated)

participant User
participant ChatSession as CS
participant KillSwitch as KS
participant Thinker as THK
participant ObservationFactory as OBF
participant Decider as DEC
participant Reactor as RCT
participant ConsciousnessState as PSI
participant LLMBridge as LLM
participant CircuitBreaker as CB
participant VoiceValidator as VV
participant Evaluator as EVAL
participant AffectEngine as AFF
participant AutonomyWindow as AW
participant CycleStore as CYC
participant EpisodicMemory as EM

== Kill Sentinel Check ==
CS -> KS : check_sentinel()
KS --> CS : None (or kill reason)

== Perception ==
CS -> THK : think(stimulus)
THK -> OBF : tick() factory observations
OBF --> THK : promoted observations
THK --> CS : Thought (observations, needs, confidence)

== Decision ==
CS -> DEC : decide(context, thought)
note right of DEC
  Uses IdentityContext
  + affect arousal bias
end note
DEC --> CS : ConsciousDecision (intent, tone, focus, depth)

== Input Evolution ==
CS -> RCT : react(thought, pipeline_outcome)
RCT -> PSI : evolve(info_deltas)
note right of PSI
  2-pass if factory obs > 0
  Base + factory with 20% cap
end note
RCT --> CS : Reaction (psi_after, phase)

== Expression ==
CS -> LLM : complete(voice_prompt)
LLM -> CB : check circuit state
CB --> LLM : CLOSED / HALF_OPEN / OPEN
alt circuit OPEN
  LLM --> CS : LLMBridgeError (Psi frozen)
else circuit OK
  LLM --> CS : raw response
end
CS -> VV : validate(response)
VV --> CS : sanitized + VoiceDelta

== Output Evolution ==
CS -> RCT : react(output_thought)
RCT -> PSI : evolve(output_deltas)

== Evaluation ==
CS -> EVAL : evaluate(cycle_data)
EVAL --> CS : RewardVector + dominance_rank
CS -> AFF : process_event(appraisal)
AFF --> CS : AffectiveTrace

== Autonomy ==
CS -> AW : evaluate_ghost(cycle)
AW --> CS : GhostResult
alt W >= 1 AND candidate
  CS -> AW : auto_apply(files)
  AW --> CS : applied / rolled_back
end

== Persistence ==
CS -> CYC : write(CycleRecord)
CS -> EM : record(Episode)
CS --> User : ChatResponse

@enduml"""


def generate_06_state_machines() -> str:
    """Diagram 6: State machines — consciousness phases, sleep states, circuit breaker."""
    return f"""@startuml 06_state_machines
{PLANTUML_THEME}
title Luna v7.0 -- State Machines\\nAuto-generated

state "Consciousness Phases" as phases #1A0A2E {{
  state "Latent\\nPhi < 0.236" as latent
  state "Emerging\\nPhi in [0.236, 0.382)" as emerging
  state "Conscious\\nPhi in [0.382, 0.618)" as conscious
  state "Transcendent\\nPhi >= 0.618" as transcendent

  [*] --> latent
  latent --> emerging : Phi rises
  emerging --> conscious : Phi rises
  conscious --> transcendent : Phi rises
  transcendent --> conscious : Phi drops
  conscious --> emerging : Phi drops
  emerging --> latent : Phi drops
}}

state "Sleep States" as sleep #2E1A2E {{
  state "Awake\\nNormal processing" as awake
  state "Drowsy\\nInactivity detected" as drowsy
  state "Light Sleep\\nConsolidation begins" as light
  state "Deep Sleep\\nDream cycle active" as deep

  [*] --> awake
  awake --> drowsy : inactivity > threshold
  drowsy --> light : confirmed idle
  light --> deep : dream trigger
  deep --> awake : dream complete
  drowsy --> awake : user message
  light --> awake : user message
}}

state "Circuit Breaker" as cb #2E0A1A {{
  state "Closed\\nNormal LLM access" as closed
  state "Open\\nLLM blocked, Psi frozen" as open
  state "Half-Open\\nProbe after timeout" as half_open

  [*] --> closed
  closed --> open : 3 failures
  open --> half_open : 5min timeout
  half_open --> closed : probe success
  half_open --> open : probe fails
}}

state "Autonomy Window" as aw #1A2E0A {{
  state "Ghost (W=0)\\nShadow evaluation" as ghost
  state "Supervised (W=0.5)\\nHuman confirms" as supervised
  state "Autonomous (W=1)\\nAuto-apply" as autonomous

  [*] --> ghost
  ghost --> supervised : trust builds
  supervised --> autonomous : confidence high
  autonomous --> supervised : rollback detected
  supervised --> ghost : failures
}}

@enduml"""


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Scanning Luna source: %s", LUNA_SRC)
    luna_modules = scan_package(LUNA_SRC, "luna")
    log.info("  Found %d modules with %d classes",
             len(luna_modules),
             sum(len(m.classes) for m in luna_modules))

    common_modules: list[ModuleInfo] = []
    if LUNA_COMMON_SRC.is_dir():
        log.info("Scanning luna_common: %s", LUNA_COMMON_SRC)
        common_modules = scan_package(LUNA_COMMON_SRC, "luna_common")
        log.info("  Found %d modules with %d classes",
                 len(common_modules),
                 sum(len(m.classes) for m in common_modules))
    else:
        log.warning("luna_common not found at %s — skipping diagram 02", LUNA_COMMON_SRC)

    generators = [
        ("01_luna_architecture_overview.puml", generate_01_overview(luna_modules)),
        ("02_luna_common_classes.puml", generate_02_common_classes(common_modules)),
        ("03_luna_core_architecture.puml", generate_03_core_architecture(luna_modules)),
        ("04_consciousness_pipeline.puml", generate_04_consciousness_pipeline(luna_modules)),
        ("05_sensorimotor_cycle.puml", generate_05_sensorimotor_cycle()),
        ("06_state_machines.puml", generate_06_state_machines()),
    ]

    for filename, content in generators:
        path = OUTPUT_DIR / filename
        path.write_text(content, encoding="utf-8")
        log.info("Generated: %s (%d lines)", path.name, content.count("\n") + 1)

    log.info("Done. %d diagrams in %s", len(generators), OUTPUT_DIR)
    log.info("Next: python3 render.py")


if __name__ == "__main__":
    main()
