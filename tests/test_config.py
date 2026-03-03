"""Tests for luna.core.config.LunaConfig.

LunaConfig loads luna.toml and provides typed access to all configuration
sections: luna, consciousness, memory, pipeline, observability, heartbeat.

NOTE: This module is being implemented by SayOhMy (Phase 1).
Tests use pytest.importorskip so they are marked SKIP (not ERROR)
until the implementation is available.
"""

from pathlib import Path

import pytest

# ── Constants we can verify against ───────────────────────────
from luna_common.constants import FRACTAL_DIRS

# ── LunaConfig: skip if not yet implemented ───────────────────
config_module = pytest.importorskip(
    "luna.core.config",
    reason="luna.core.config not yet implemented (Phase 1 in progress)",
)
LunaConfig = getattr(config_module, "LunaConfig", None)
if LunaConfig is None:
    pytest.skip(
        "LunaConfig class not found in luna.core.config",
        allow_module_level=True,
    )


# ═══════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════

LUNA_TOML_PATH = Path("/home/sayohmy/LUNA/luna.toml")


@pytest.fixture
def config():
    """Load the real luna.toml from the repository root."""
    return LunaConfig.load(LUNA_TOML_PATH)


@pytest.fixture
def minimal_toml(tmp_path):
    """Create a minimal valid luna.toml for isolated tests."""
    content = """\
[luna]
version = "2.2.0-test"
agent_name = "LUNA"
data_dir = "memory_fractal"
pipeline_dir = "pipeline"

[consciousness]
checkpoint_file = "memory_fractal/consciousness_state_v2.json"
backup_on_save = true

[memory]
fractal_root = "memory_fractal"
levels = ["seeds", "roots", "branches", "leaves"]
max_memories_per_level = 500

[pipeline]
root = "pipeline"
poll_interval_seconds = 1.0
timeout_seconds = 300

[observability]
log_level = "INFO"
log_file = "logs/luna.log"
metrics_enabled = true

[heartbeat]
interval_seconds = 30
fingerprint_enabled = true
"""
    toml_file = tmp_path / "luna.toml"
    toml_file.write_text(content)
    return toml_file


# ═══════════════════════════════════════════════════════════════
#  I. LOADING
# ═══════════════════════════════════════════════════════════════

class TestConfigLoading:
    """LunaConfig.load() parses luna.toml correctly."""

    def test_load_luna_toml(self, config):
        """Loading the real luna.toml should succeed without error."""
        assert config is not None

    def test_load_returns_luna_config_instance(self, config):
        """load() returns a LunaConfig (or equivalent typed object)."""
        assert isinstance(config, LunaConfig)

    def test_load_minimal_toml(self, minimal_toml):
        """A minimal valid luna.toml loads correctly."""
        config = LunaConfig.load(minimal_toml)
        assert config is not None

    def test_config_missing_file_raises(self, tmp_path):
        """Loading a nonexistent file raises FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            LunaConfig.load(fake_path)

    def test_config_invalid_toml_raises(self, tmp_path):
        """Invalid TOML content raises an appropriate error."""
        bad_file = tmp_path / "bad.toml"
        bad_file.write_text("this is [not valid toml {{{")
        with pytest.raises(Exception):
            LunaConfig.load(bad_file)


# ═══════════════════════════════════════════════════════════════
#  II. SECTIONS
# ═══════════════════════════════════════════════════════════════

class TestConfigSections:
    """All expected configuration sections must be present."""

    def test_has_luna_section(self, config):
        """Config has a [luna] section."""
        assert hasattr(config, "luna") or hasattr(config, "version"), (
            "Config missing [luna] section"
        )

    def test_has_consciousness_section(self, config):
        """Config has a [consciousness] section."""
        assert hasattr(config, "consciousness"), "Config missing [consciousness] section"

    def test_has_memory_section(self, config):
        """Config has a [memory] section."""
        assert hasattr(config, "memory"), "Config missing [memory] section"

    def test_has_pipeline_section(self, config):
        """Config has a [pipeline] section."""
        assert hasattr(config, "pipeline"), "Config missing [pipeline] section"

    def test_has_observability_section(self, config):
        """Config has an [observability] section."""
        assert hasattr(config, "observability"), "Config missing [observability] section"

    def test_has_heartbeat_section(self, config):
        """Config has a [heartbeat] section."""
        assert hasattr(config, "heartbeat"), "Config missing [heartbeat] section"


# ═══════════════════════════════════════════════════════════════
#  III. LUNA SECTION VALUES
# ═══════════════════════════════════════════════════════════════

class TestConfigLunaValues:
    """Verify [luna] section values from the real luna.toml."""

    def test_version_is_string(self, config):
        """version field is a non-empty string."""
        section = config.luna if hasattr(config, "luna") else config
        version = getattr(section, "version", None)
        assert isinstance(version, str) and len(version) > 0

    def test_agent_name_is_luna(self, config):
        """agent_name should be 'Luna' in the default config."""
        section = config.luna if hasattr(config, "luna") else config
        name = getattr(section, "agent_name", None)
        assert name == "LUNA"

    def test_data_dir(self, config):
        """data_dir should be 'memory_fractal'."""
        section = config.luna if hasattr(config, "luna") else config
        assert getattr(section, "data_dir", None) == "memory_fractal"


# ═══════════════════════════════════════════════════════════════
#  IV. CONSCIOUSNESS SECTION VALUES
# ═══════════════════════════════════════════════════════════════

class TestConfigConsciousnessValues:
    """Verify [consciousness] section."""

    def test_checkpoint_file_path(self, config):
        """checkpoint_file points to the expected location."""
        cs = config.consciousness
        checkpoint = getattr(cs, "checkpoint_file", None)
        assert checkpoint is not None
        assert "consciousness_state" in str(checkpoint), (
            f"checkpoint_file should reference consciousness_state, got: {checkpoint}"
        )

    def test_backup_on_save(self, config):
        """backup_on_save should be a boolean."""
        cs = config.consciousness
        bos = getattr(cs, "backup_on_save", None)
        assert isinstance(bos, bool)


# ═══════════════════════════════════════════════════════════════
#  V. MEMORY SECTION VALUES
# ═══════════════════════════════════════════════════════════════

class TestConfigMemoryValues:
    """Verify [memory] section -- fractal directory structure."""

    def test_fractal_root(self, config):
        """fractal_root should be 'memory_fractal'."""
        mem = config.memory
        assert getattr(mem, "fractal_root", None) == "memory_fractal"

    def test_fractal_dirs_match_constants(self, config):
        """memory.levels must match FRACTAL_DIRS from luna_common.constants."""
        mem = config.memory
        levels = getattr(mem, "levels", None)
        assert levels is not None, "memory.levels not found in config"
        assert list(levels) == FRACTAL_DIRS, (
            f"Config levels = {levels}, expected {FRACTAL_DIRS}"
        )

    def test_max_memories_positive(self, config):
        """max_memories_per_level should be a positive integer."""
        mem = config.memory
        max_mem = getattr(mem, "max_memories_per_level", None)
        assert isinstance(max_mem, int) and max_mem > 0


# ═══════════════════════════════════════════════════════════════
#  VI. PIPELINE SECTION VALUES
# ═══════════════════════════════════════════════════════════════

class TestConfigPipelineValues:
    """Verify [pipeline] section."""

    def test_poll_interval_positive(self, config):
        """poll_interval_seconds should be a positive number."""
        pipe = config.pipeline
        interval = getattr(pipe, "poll_interval_seconds", None)
        assert interval is not None and interval > 0

    def test_timeout_positive(self, config):
        """timeout_seconds should be a positive number."""
        pipe = config.pipeline
        timeout = getattr(pipe, "timeout_seconds", None)
        assert timeout is not None and timeout > 0

    def test_timeout_greater_than_poll(self, config):
        """Timeout should be much larger than poll interval."""
        pipe = config.pipeline
        interval = getattr(pipe, "poll_interval_seconds", None)
        timeout = getattr(pipe, "timeout_seconds", None)
        if interval and timeout:
            assert timeout > interval, (
                f"timeout ({timeout}) should be > poll_interval ({interval})"
            )


# ═══════════════════════════════════════════════════════════════
#  VII. DEFAULT VALUES
# ═══════════════════════════════════════════════════════════════

class TestConfigDefaults:
    """Config should provide sensible defaults for optional fields."""

    def test_log_level_default(self, config):
        """Default log level should be a valid level string."""
        obs = config.observability
        level = getattr(obs, "log_level", None)
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert level in valid_levels, f"Unknown log level: {level}"

    def test_heartbeat_interval_reasonable(self, config):
        """Heartbeat interval should be between 1 and 600 seconds."""
        hb = config.heartbeat
        interval = getattr(hb, "interval_seconds", None)
        assert 1 <= interval <= 600, (
            f"Heartbeat interval {interval}s is outside reasonable range [1, 600]"
        )

    def test_metrics_enabled_is_bool(self, config):
        """metrics_enabled is a boolean."""
        obs = config.observability
        assert isinstance(getattr(obs, "metrics_enabled", None), bool)
