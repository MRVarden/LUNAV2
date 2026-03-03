"""Tests for PipelineRunner .env loading and env_extras injection.

Validates:
- ``_load_dotenv`` injects KEY=VALUE pairs from ``.env`` into ``os.environ``
- Existing environment variables are NOT overridden (override=False semantics)
- Missing ``.env`` file does not raise
- ``env_extras`` dict from constructor is applied to ``os.environ``
- Fallback KEY=VALUE parser works when ``python-dotenv`` is unavailable
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from luna.pipeline.runner import PipelineRunner


# =====================================================================
#  HELPERS
# =====================================================================

# Unique key prefix to avoid collisions with real env vars or parallel tests.
_PREFIX = "_LUNA_TEST_DOTENV_"


def _write_env(directory: Path, content: str) -> Path:
    """Write a ``.env`` file into *directory* and return its path."""
    env_path = directory / ".env"
    env_path.write_text(content, encoding="utf-8")
    return env_path


def _make_runner_with_env(
    tmp_path: Path,
    *,
    project_root: Path | None = None,
    env_extras: dict[str, str] | None = None,
) -> PipelineRunner:
    """Build a PipelineRunner whose ``_load_dotenv`` targets *project_root*.

    Subprocess-related IO (PipelineWriter/PipelineReader) is irrelevant for
    these tests so we just need the pipeline_root directory to exist.
    """
    root = tmp_path / "pipeline"
    root.mkdir(parents=True, exist_ok=True)
    return PipelineRunner(
        pipeline_root=root,
        sayohmy_cwd=tmp_path / "sayohmy",
        sentinel_cwd=tmp_path / "sentinel",
        testengineer_cwd=tmp_path / "testengineer",
        agent_timeout=5.0,
        project_root=project_root,
        env_extras=env_extras,
    )


# =====================================================================
#  FIXTURES
# =====================================================================


@pytest.fixture(autouse=True)
def _clean_test_env_vars() -> Generator[None, None, None]:
    """Remove any env vars injected by these tests after each test."""
    yield
    keys_to_remove = [k for k in os.environ if k.startswith(_PREFIX)]
    for key in keys_to_remove:
        os.environ.pop(key, None)


# =====================================================================
#  I. _load_dotenv basics
# =====================================================================


class TestLoadDotenv:
    """Verify _load_dotenv reads .env files into os.environ."""

    def test_load_dotenv_injects_into_environ(self, tmp_path: Path) -> None:
        """A KEY=VALUE line in .env appears in os.environ after _load_dotenv."""
        key = f"{_PREFIX}INJECT_A"
        _write_env(tmp_path, f"{key}=hello_world\n")

        # Precondition: key is absent.
        assert key not in os.environ

        PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "hello_world"

    def test_load_dotenv_does_not_override_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An env var already present in os.environ is NOT overwritten."""
        key = f"{_PREFIX}EXISTING_B"
        original_value = "original_value"

        # Pre-set the variable.
        monkeypatch.setenv(key, original_value)

        # .env file has a DIFFERENT value for the same key.
        _write_env(tmp_path, f"{key}=overridden_value\n")

        PipelineRunner._load_dotenv(tmp_path)

        assert os.environ[key] == original_value, (
            "_load_dotenv must not override pre-existing environment variables"
        )

    def test_load_dotenv_missing_file_no_error(self, tmp_path: Path) -> None:
        """Calling _load_dotenv on a directory without .env does not raise."""
        nonexistent = tmp_path / "no_such_directory"
        nonexistent.mkdir(parents=True, exist_ok=True)

        # Should return silently -- no .env file present.
        PipelineRunner._load_dotenv(nonexistent)

    def test_load_dotenv_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        """Comments (#) and blank lines in .env are ignored."""
        key = f"{_PREFIX}COMMENTS_C"
        content = (
            "# This is a comment\n"
            "\n"
            f"{key}=valid_value\n"
            "   # Another comment\n"
            "\n"
        )
        _write_env(tmp_path, content)

        PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "valid_value"

    def test_load_dotenv_handles_value_with_equals(self, tmp_path: Path) -> None:
        """Values containing '=' are preserved (only first '=' splits)."""
        key = f"{_PREFIX}EQUALS_D"
        _write_env(tmp_path, f"{key}=base64==encoded\n")

        PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "base64==encoded"


# =====================================================================
#  II. env_extras injection via constructor
# =====================================================================


class TestEnvExtras:
    """Verify env_extras dict is applied to os.environ on construction."""

    def test_env_extras_injected(self, tmp_path: Path) -> None:
        """Keys passed via env_extras appear in os.environ after init."""
        key = f"{_PREFIX}EXTRA_E"

        # Precondition.
        assert key not in os.environ

        _make_runner_with_env(tmp_path, env_extras={key: "injected_val"})

        assert os.environ.get(key) == "injected_val"

    def test_env_extras_overrides_dotenv(self, tmp_path: Path) -> None:
        """env_extras is applied AFTER _load_dotenv, so it wins on conflict."""
        key = f"{_PREFIX}OVERRIDE_F"
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_env(project_root, f"{key}=from_dotenv\n")

        _make_runner_with_env(
            tmp_path,
            project_root=project_root,
            env_extras={key: "from_extras"},
        )

        # env_extras uses os.environ.update() which overwrites.
        assert os.environ.get(key) == "from_extras"

    def test_env_extras_none_is_noop(self, tmp_path: Path) -> None:
        """Passing env_extras=None (the default) does not crash."""
        # Should not raise.
        _make_runner_with_env(tmp_path, env_extras=None)


# =====================================================================
#  III. Fallback parser when python-dotenv is missing
# =====================================================================


class TestFallbackParser:
    """Verify the manual KEY=VALUE parser works when dotenv is not installed."""

    def test_fallback_parser_when_no_dotenv(self, tmp_path: Path) -> None:
        """With python-dotenv unavailable, .env is parsed by the fallback."""
        key = f"{_PREFIX}FALLBACK_G"
        _write_env(tmp_path, f"{key}=fallback_value\n")

        # Precondition.
        assert key not in os.environ

        # Simulate ImportError for `dotenv` inside _load_dotenv.
        _real_import = builtins.__import__

        def _import_no_dotenv(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "dotenv":
                raise ImportError("simulated: no module named 'dotenv'")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_import_no_dotenv):
            PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "fallback_value"

    def test_fallback_parser_skips_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fallback parser also respects override=False semantics."""
        key = f"{_PREFIX}FALLBACK_EXIST_H"
        monkeypatch.setenv(key, "pre_existing")
        _write_env(tmp_path, f"{key}=should_not_override\n")

        _real_import = builtins.__import__

        def _import_no_dotenv(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "dotenv":
                raise ImportError("simulated: no module named 'dotenv'")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_import_no_dotenv):
            PipelineRunner._load_dotenv(tmp_path)

        assert os.environ[key] == "pre_existing"

    def test_fallback_parser_handles_whitespace(self, tmp_path: Path) -> None:
        """Fallback parser strips leading/trailing whitespace from keys and values."""
        key = f"{_PREFIX}WHITESPACE_I"
        _write_env(tmp_path, f"  {key}  =  spaced_value  \n")

        _real_import = builtins.__import__

        def _import_no_dotenv(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "dotenv":
                raise ImportError("simulated: no module named 'dotenv'")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_import_no_dotenv):
            PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "spaced_value"

    def test_fallback_parser_skips_lines_without_equals(self, tmp_path: Path) -> None:
        """Lines without '=' are silently ignored by the fallback parser."""
        key = f"{_PREFIX}NOEQ_J"
        content = (
            "THIS_LINE_HAS_NO_EQUALS\n"
            f"{key}=valid\n"
            "ALSO_INVALID\n"
        )
        _write_env(tmp_path, content)

        _real_import = builtins.__import__

        def _import_no_dotenv(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "dotenv":
                raise ImportError("simulated: no module named 'dotenv'")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_import_no_dotenv):
            PipelineRunner._load_dotenv(tmp_path)

        assert os.environ.get(key) == "valid"
        assert "THIS_LINE_HAS_NO_EQUALS" not in os.environ
        assert "ALSO_INVALID" not in os.environ
