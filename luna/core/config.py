"""Configuration loader — luna.toml -> typed dataclasses.

Loads runtime configuration from luna.toml. All Phi-derived parameters
come from luna_common.constants and are NOT overridden here.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LunaSection:
    version: str
    agent_name: str
    data_dir: str
    pipeline_dir: str


@dataclass(frozen=True, slots=True)
class ConsciousnessSection:
    checkpoint_file: str
    backup_on_save: bool = True


@dataclass(frozen=True, slots=True)
class MemorySection:
    fractal_root: str
    levels: list[str] = field(
        default_factory=lambda: ["seeds", "roots", "branches", "leaves"],
    )
    max_memories_per_level: int = 500


@dataclass(frozen=True, slots=True)
class PipelineSection:
    root: str
    poll_interval_seconds: float = 1.0
    timeout_seconds: float = 300.0
    # v2.4.0 — Self-Evolution Loop
    autonomy: str = "supervised"       # supervised | semi_autonomous | autonomous
    sayohmy_path: str = "~/SAYOHMY"
    sentinel_path: str = "~/SENTINEL"
    testengineer_path: str = "~/TESTENGINEER"
    agent_timeout: float = 120.0
    runner_enabled: bool = False        # Must be explicitly enabled


@dataclass(frozen=True, slots=True)
class ObservabilitySection:
    log_level: str = "INFO"
    log_file: str = "logs/luna.log"
    metrics_enabled: bool = True
    audit_trail_file: str = "data/audit.jsonl"
    redis_url: str = ""
    alert_webhook_url: str = ""
    prometheus_enabled: bool = True


@dataclass(frozen=True, slots=True)
class HeartbeatSection:
    interval_seconds: float = 30.0
    fingerprint_enabled: bool = True
    checkpoint_interval: int = 100  # Save checkpoint every N idle steps


@dataclass(frozen=True, slots=True)
class LLMSection:
    """Configuration for the LLM bridge (provider-agnostic)."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None    # If None, provider consults its env var.
    base_url: str | None = None   # Override for DeepSeek or local.
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class DreamSection:
    """Configuration for the dream cycle — nocturnal consolidation."""

    inactivity_threshold: float = 7200.0  # 2h of inactivity triggers dream
    consolidation_window: int = 100       # History entries to analyze
    max_dream_duration: float = 300.0     # 5min cap
    report_dir: str = "memory_fractal/dreams"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class OrchestratorSection:
    """Configuration for the autonomous orchestration loop."""

    llm_augment: bool = True           # Enrich decisions via LLM
    max_cycles: int = 0                # 0 = infinite
    checkpoint_interval: int = 1       # Save every N cycles
    cycle_timeout: float = 600.0       # Timeout per cycle (seconds)
    retry_max: int = 3                 # LLM retries
    retry_base_delay: float = 1.0      # Initial retry delay (seconds)


@dataclass(frozen=True, slots=True)
class ChatSection:
    """Configuration for the human chat interface."""

    max_history: int = 100             # Max turns kept in LLM context
    memory_search_limit: int = 5       # Memories injected per turn
    idle_heartbeat: bool = True        # idle_step() between messages
    save_conversations: bool = True    # Persist turns as seeds
    prompt_prefix: str = "luna> "      # REPL prompt


@dataclass(frozen=True, slots=True)
class MetricsSection:
    """Configuration for the metrics collection module."""

    enabled: bool = True
    cache_enabled: bool = True
    cache_dir: str = "data/metrics_cache"
    timeout_seconds: float = 60.0
    python_enabled: bool = True
    rust_enabled: bool = False
    java_enabled: bool = False
    typescript_enabled: bool = False
    c_enabled: bool = False


@dataclass(frozen=True, slots=True)
class FingerprintSection:
    """Configuration for the fingerprint module."""

    enabled: bool = True
    secret_file: str = "config/fingerprint.key"
    ledger_file: str = "data/fingerprints.jsonl"
    watermark_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SafetySection:
    """Configuration for the safety module."""

    enabled: bool = True
    snapshot_dir: str = "data/snapshots"
    max_snapshots: int = 10
    retention_days: int = 7
    max_generations_per_hour: int = 100
    max_commits_per_hour: int = 20
    watchdog_threshold: int = 3


@dataclass(frozen=True, slots=True)
class APISection:
    """Configuration for the REST API."""

    host: str = "127.0.0.1"
    port: int = 8618
    auth_enabled: bool = True
    auth_token_file: str = "config/api_token"
    rate_limit_rpm: int = 60
    trusted_proxies: tuple[str, ...] = ()  # IPs that may set X-Forwarded-For


@dataclass(frozen=True, slots=True)
class LunaConfig:
    """Typed, immutable representation of luna.toml."""

    luna: LunaSection
    consciousness: ConsciousnessSection
    memory: MemorySection
    pipeline: PipelineSection
    observability: ObservabilitySection
    heartbeat: HeartbeatSection
    llm: LLMSection = field(default_factory=LLMSection)
    orchestrator: OrchestratorSection = field(default_factory=OrchestratorSection)
    dream: DreamSection = field(default_factory=DreamSection)
    chat: ChatSection = field(default_factory=ChatSection)
    metrics: MetricsSection = field(default_factory=MetricsSection)
    fingerprint: FingerprintSection = field(default_factory=FingerprintSection)
    safety: SafetySection = field(default_factory=SafetySection)
    api: APISection = field(default_factory=APISection)

    # Absolute root from which relative paths are resolved.
    root_dir: Path = field(default_factory=lambda: Path.cwd())

    def resolve(self, relative: str) -> Path:
        """Resolve a config-relative path against root_dir."""
        return self.root_dir / relative

    @staticmethod
    def load(path: Path | str = "luna.toml") -> LunaConfig:
        """Load and validate configuration from a TOML file.

        Args:
            path: Path to luna.toml (absolute or relative to cwd).

        Returns:
            Fully populated LunaConfig.

        Raises:
            FileNotFoundError: If the TOML file does not exist.
            KeyError: If a required section or key is missing.
        """
        path = Path(path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "rb") as f:
            raw = tomllib.load(f)

        root_dir = path.parent

        luna = LunaSection(
            version=raw["luna"]["version"],
            agent_name=raw["luna"]["agent_name"],
            data_dir=raw["luna"]["data_dir"],
            pipeline_dir=raw["luna"]["pipeline_dir"],
        )

        cs = raw.get("consciousness", {})
        consciousness = ConsciousnessSection(
            checkpoint_file=cs["checkpoint_file"],
            backup_on_save=cs.get("backup_on_save", True),
        )

        ms = raw.get("memory", {})
        memory = MemorySection(
            fractal_root=ms["fractal_root"],
            levels=ms.get("levels", ["seeds", "roots", "branches", "leaves"]),
            max_memories_per_level=ms.get("max_memories_per_level", 500),
        )

        ps = raw.get("pipeline", {})
        pipeline = PipelineSection(
            root=ps["root"],
            poll_interval_seconds=ps.get("poll_interval_seconds", 1.0),
            timeout_seconds=ps.get("timeout_seconds", 300.0),
            autonomy=ps.get("autonomy", "supervised"),
            sayohmy_path=ps.get("sayohmy_path", "~/SAYOHMY"),
            sentinel_path=ps.get("sentinel_path", "~/SENTINEL"),
            testengineer_path=ps.get("testengineer_path", "~/TESTENGINEER"),
            agent_timeout=ps.get("agent_timeout", 120.0),
            runner_enabled=ps.get("runner_enabled", False),
        )

        obs = raw.get("observability", {})
        observability = ObservabilitySection(
            log_level=obs.get("log_level", "INFO"),
            log_file=obs.get("log_file", "logs/luna.log"),
            metrics_enabled=obs.get("metrics_enabled", True),
            audit_trail_file=obs.get("audit_trail_file", "data/audit.jsonl"),
            redis_url=obs.get("redis_url", ""),
            alert_webhook_url=obs.get("alert_webhook_url", ""),
            prometheus_enabled=obs.get("prometheus_enabled", True),
        )

        hb = raw.get("heartbeat", {})
        heartbeat = HeartbeatSection(
            interval_seconds=hb.get("interval_seconds", 30.0),
            fingerprint_enabled=hb.get("fingerprint_enabled", True),
            checkpoint_interval=hb.get("checkpoint_interval", 100),
        )

        llm_raw = raw.get("llm", {})
        llm = LLMSection(
            provider=llm_raw.get("provider", "anthropic"),
            model=llm_raw.get("model", "claude-sonnet-4-20250514"),
            api_key=llm_raw.get("api_key"),
            base_url=llm_raw.get("base_url"),
            max_tokens=llm_raw.get("max_tokens", 4096),
            temperature=llm_raw.get("temperature", 0.7),
        )

        orch_raw = raw.get("orchestrator", {})
        orchestrator = OrchestratorSection(
            llm_augment=orch_raw.get("llm_augment", True),
            max_cycles=orch_raw.get("max_cycles", 0),
            checkpoint_interval=orch_raw.get("checkpoint_interval", 1),
            cycle_timeout=orch_raw.get("cycle_timeout", 600.0),
            retry_max=orch_raw.get("retry_max", 3),
            retry_base_delay=orch_raw.get("retry_base_delay", 1.0),
        )

        dream_raw = raw.get("dream", {})
        dream = DreamSection(
            inactivity_threshold=dream_raw.get("inactivity_threshold", 7200.0),
            consolidation_window=dream_raw.get("consolidation_window", 100),
            max_dream_duration=dream_raw.get("max_dream_duration", 300.0),
            report_dir=dream_raw.get("report_dir", "memory_fractal/dreams"),
            enabled=dream_raw.get("enabled", True),
        )

        chat_raw = raw.get("chat", {})
        chat = ChatSection(
            max_history=chat_raw.get("max_history", 100),
            memory_search_limit=chat_raw.get("memory_search_limit", 5),
            idle_heartbeat=chat_raw.get("idle_heartbeat", True),
            save_conversations=chat_raw.get("save_conversations", True),
            prompt_prefix=chat_raw.get("prompt_prefix", "luna> "),
        )

        met_raw = raw.get("metrics", {})
        metrics = MetricsSection(
            enabled=met_raw.get("enabled", True),
            cache_enabled=met_raw.get("cache_enabled", True),
            cache_dir=met_raw.get("cache_dir", "data/metrics_cache"),
            timeout_seconds=met_raw.get("timeout_seconds", 60.0),
            python_enabled=met_raw.get("python_enabled", True),
            rust_enabled=met_raw.get("rust_enabled", False),
            java_enabled=met_raw.get("java_enabled", False),
            typescript_enabled=met_raw.get("typescript_enabled", False),
            c_enabled=met_raw.get("c_enabled", False),
        )

        fp_raw = raw.get("fingerprint", {})
        fingerprint = FingerprintSection(
            enabled=fp_raw.get("enabled", True),
            secret_file=fp_raw.get("secret_file", "config/fingerprint.key"),
            ledger_file=fp_raw.get("ledger_file", "data/fingerprints.jsonl"),
            watermark_enabled=fp_raw.get("watermark_enabled", False),
        )

        safety_raw = raw.get("safety", {})
        safety = SafetySection(
            enabled=safety_raw.get("enabled", True),
            snapshot_dir=safety_raw.get("snapshot_dir", "data/snapshots"),
            max_snapshots=safety_raw.get("max_snapshots", 10),
            retention_days=safety_raw.get("retention_days", 7),
            max_generations_per_hour=safety_raw.get("max_generations_per_hour", 100),
            max_commits_per_hour=safety_raw.get("max_commits_per_hour", 20),
            watchdog_threshold=safety_raw.get("watchdog_threshold", 3),
        )

        api_raw = raw.get("api", {})
        api = APISection(
            host=api_raw.get("host", "127.0.0.1"),
            port=api_raw.get("port", 8618),
            auth_enabled=api_raw.get("auth_enabled", True),
            auth_token_file=api_raw.get("auth_token_file", "config/api_token"),
            rate_limit_rpm=api_raw.get("rate_limit_rpm", 60),
            trusted_proxies=tuple(api_raw.get("trusted_proxies", [])),
        )

        return LunaConfig(
            luna=luna,
            consciousness=consciousness,
            memory=memory,
            pipeline=pipeline,
            observability=observability,
            heartbeat=heartbeat,
            llm=llm,
            orchestrator=orchestrator,
            dream=dream,
            chat=chat,
            metrics=metrics,
            fingerprint=fingerprint,
            safety=safety,
            api=api,
            root_dir=root_dir,
        )
