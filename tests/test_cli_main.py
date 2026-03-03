"""Tests for CLI main entry point — wired commands.

These tests exercise the real Luna logic behind each CLI command.
Commands that start infinite loops (start, dashboard) are tested only
at the import / registration level.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from luna.cli.main import app

runner = CliRunner()


class TestCLIMain:
    """Tests for the CLI main app."""

    def test_no_args_shows_help(self):
        """No arguments shows help text."""
        result = runner.invoke(app)
        # Typer exits with 0 or 2 for help display depending on version
        assert result.exit_code in (0, 2)
        assert "luna" in result.output.lower() or "Usage" in result.output

    def test_start_command_registered(self):
        """Start command is registered in the app."""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_status_command(self):
        """Status command runs and displays engine state."""
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Agent:" in result.output
        assert "Phase:" in result.output
        assert "Step count:" in result.output

    def test_status_json(self):
        """Status with --json flag returns valid JSON."""
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "agent_name" in data
        assert "phase" in data
        assert "phi_iit" in data

    def test_evolve_command(self):
        """Evolve command runs N idle steps."""
        result = runner.invoke(app, ["evolve", "5"])
        assert result.exit_code == 0
        assert "5 step(s)" in result.output
        assert "Phase:" in result.output
        assert "PHI_IIT:" in result.output
        assert "Checkpoint saved:" in result.output

    def test_evolve_verbose(self):
        """Evolve command with --verbose shows per-step output."""
        result = runner.invoke(app, ["evolve", "3", "--verbose"])
        assert result.exit_code == 0
        assert "Step 1/3:" in result.output
        assert "Step 3/3:" in result.output

    def test_score_command(self):
        """Score command runs on current directory."""
        result = runner.invoke(app, ["score", "."])
        # Should either show metrics or say no recognized files
        assert result.exit_code == 0
        assert "Metrics for:" in result.output or "No metrics collected" in result.output

    def test_score_nonexistent_path(self):
        """Score command errors on nonexistent path."""
        result = runner.invoke(app, ["score", "/nonexistent/path/xyz"])
        assert result.exit_code == 1
        assert "Error: path does not exist" in result.output

    def test_fingerprint_command(self):
        """Fingerprint command generates a fingerprint."""
        result = runner.invoke(app, ["fingerprint"])
        assert result.exit_code == 0
        assert "Fingerprint:" in result.output

    def test_fingerprint_verify(self):
        """Fingerprint with --verify confirms integrity."""
        result = runner.invoke(app, ["fingerprint", "--verify"])
        assert result.exit_code == 0
        assert "Fingerprint:" in result.output
        assert "Verification:" in result.output

    def test_fingerprint_history_empty(self):
        """Fingerprint with --history on fresh system."""
        result = runner.invoke(app, ["fingerprint", "--history", "5"])
        assert result.exit_code == 0
        # Either shows entries or says none recorded

    def test_validate_command(self):
        """Validate command runs benchmarks and produces a verdict."""
        result = runner.invoke(app, ["validate"])
        assert result.exit_code == 0
        assert "VERDICT:" in result.output
        assert "Criteria met:" in result.output
        assert "Improvement:" in result.output

    def test_validate_verbose(self):
        """Validate --verbose shows individual criteria."""
        result = runner.invoke(app, ["validate", "--verbose"])
        assert result.exit_code == 0
        assert "VERDICT:" in result.output
        # Should show PASS/FAIL per criterion
        assert "PASS" in result.output or "FAIL" in result.output

    def test_dashboard_command_registered(self):
        """Dashboard command is registered (cannot test infinite loop)."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "refresh" in result.output.lower()

    def test_heartbeat_command(self):
        """Heartbeat command shows vital signs."""
        result = runner.invoke(app, ["heartbeat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "phi_iit" in data
        assert "overall_vitality" in data

    def test_dream_command(self):
        """Dream command shows status."""
        result = runner.invoke(app, ["dream"])
        assert result.exit_code == 0
        # Default shows dream status as JSON
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_dream_status(self):
        """Dream --status shows status JSON."""
        result = runner.invoke(app, ["dream", "--status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_memory_command(self):
        """Memory command shows recent memories or empty message."""
        result = runner.invoke(app, ["memory"])
        assert result.exit_code == 0
        assert "No memories stored yet" in result.output or "Recent memories" in result.output

    def test_memory_search(self):
        """Memory search flag."""
        result = runner.invoke(app, ["memory", "--search", "test"])
        assert result.exit_code == 0
        assert "No memories found" in result.output or "Found" in result.output

    def test_memory_stats(self):
        """Memory --stats shows statistics."""
        result = runner.invoke(app, ["memory", "--stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_memories" in data

    def test_kill_with_force(self, capsys):
        """Kill command with --force."""
        # The CRITICAL log from KillSwitch can interfere with CliRunner I/O.
        # Use catch_exceptions=False and capsys to verify output.
        import logging
        logging.disable(logging.CRITICAL)
        try:
            result = runner.invoke(app, ["kill", "--force"])
            assert result.exit_code == 0
            assert "Kill sentinel written" in result.output
            assert "Reason: manual CLI" in result.output
        finally:
            logging.disable(logging.NOTSET)

    def test_kill_cancel(self):
        """Kill command without force, user cancels."""
        result = runner.invoke(app, ["kill"], input="n\n")
        assert "Cancelled" in result.output

    def test_rollback_help(self):
        """Rollback command shows help."""
        result = runner.invoke(app, ["rollback", "--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.output.lower()
