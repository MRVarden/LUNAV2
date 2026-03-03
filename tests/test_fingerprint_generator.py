"""Tests for fingerprint generator — HMAC-SHA256 identity fingerprinting."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from luna.fingerprint.generator import Fingerprint, FingerprintGenerator


def _make_consciousness(
    agent_name="LUNA",
    psi=None,
    psi0=None,
    step_count=42,
):
    """Create a mock ConsciousnessState."""
    cs = MagicMock()
    cs.agent_name = agent_name
    cs.psi = np.array(psi or [0.25, 0.35, 0.25, 0.15])
    cs.psi0 = np.array(psi0 or [0.25, 0.35, 0.25, 0.15])
    cs.step_count = step_count
    return cs


class TestFingerprint:
    """Tests for the Fingerprint frozen dataclass."""

    def test_frozen(self):
        """Fingerprint is immutable."""
        fp = Fingerprint(
            agent_name="LUNA", psi0_hash="abc", state_hash="def",
            composite="ghi", timestamp="2026-01-01", step_count=0,
        )
        with pytest.raises(AttributeError):
            fp.composite = "changed"  # type: ignore[misc]

    def test_to_dict(self):
        """to_dict serializes all fields."""
        fp = Fingerprint(
            agent_name="LUNA", psi0_hash="abc", state_hash="def",
            composite="ghi", timestamp="2026-01-01", step_count=42,
        )
        d = fp.to_dict()
        assert d["agent_name"] == "LUNA"
        assert d["step_count"] == 42
        assert d["composite"] == "ghi"

    def test_from_dict_roundtrip(self):
        """from_dict(to_dict()) is identity."""
        fp = Fingerprint(
            agent_name="LUNA", psi0_hash="abc", state_hash="def",
            composite="ghi", timestamp="2026-01-01", step_count=42,
        )
        restored = Fingerprint.from_dict(fp.to_dict())
        assert restored == fp


class TestFingerprintGenerator:
    """Tests for FingerprintGenerator."""

    @pytest.fixture
    def secret_path(self, tmp_path):
        return tmp_path / "fingerprint.key"

    @pytest.fixture
    def generator(self, secret_path):
        return FingerprintGenerator(secret_path)

    def test_generate_creates_secret(self, secret_path):
        """Generator creates secret file if it doesn't exist."""
        assert not secret_path.exists()
        FingerprintGenerator(secret_path)
        assert secret_path.exists()

    def test_generate_fingerprint(self, generator):
        """generate() produces a valid Fingerprint."""
        cs = _make_consciousness()
        fp = generator.generate(cs)
        assert isinstance(fp, Fingerprint)
        assert fp.agent_name == "LUNA"
        assert fp.step_count == 42
        assert len(fp.composite) == 64  # SHA256 hex

    def test_deterministic(self, generator):
        """Same state produces same fingerprint (except timestamp)."""
        cs = _make_consciousness()
        fp1 = generator.generate(cs)
        fp2 = generator.generate(cs)
        assert fp1.psi0_hash == fp2.psi0_hash
        assert fp1.state_hash == fp2.state_hash
        assert fp1.composite == fp2.composite

    def test_different_state_different_fingerprint(self, generator):
        """Different states produce different fingerprints."""
        cs1 = _make_consciousness(step_count=1)
        cs2 = _make_consciousness(step_count=2)
        fp1 = generator.generate(cs1)
        fp2 = generator.generate(cs2)
        assert fp1.composite != fp2.composite

    def test_different_psi_different_fingerprint(self, generator):
        """Different psi produces different fingerprints."""
        cs1 = _make_consciousness(psi=[0.25, 0.35, 0.25, 0.15])
        cs2 = _make_consciousness(psi=[0.50, 0.20, 0.20, 0.10])
        fp1 = generator.generate(cs1)
        fp2 = generator.generate(cs2)
        assert fp1.state_hash != fp2.state_hash

    def test_verify_same_state(self, generator):
        """verify() returns True for matching state."""
        cs = _make_consciousness()
        fp = generator.generate(cs)
        assert generator.verify(fp, cs) is True

    def test_verify_different_state(self, generator):
        """verify() returns False for different state."""
        cs1 = _make_consciousness(step_count=1)
        cs2 = _make_consciousness(step_count=2)
        fp = generator.generate(cs1)
        assert generator.verify(fp, cs2) is False

    def test_load_existing_secret(self, secret_path):
        """Generator reuses existing secret file."""
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_bytes(b"test_secret_key_1234567890123456")

        gen = FingerprintGenerator(secret_path)
        cs = _make_consciousness()
        fp = gen.generate(cs)
        assert isinstance(fp, Fingerprint)

    def test_different_secrets_different_fingerprints(self, tmp_path):
        """Different HMAC secrets produce different composites."""
        path1 = tmp_path / "key1"
        path1.write_bytes(b"secret_one_32_bytes_exactly_here")
        path2 = tmp_path / "key2"
        path2.write_bytes(b"secret_two_32_bytes_exactly_here")

        gen1 = FingerprintGenerator(path1)
        gen2 = FingerprintGenerator(path2)

        cs = _make_consciousness()
        fp1 = gen1.generate(cs)
        fp2 = gen2.generate(cs)
        assert fp1.composite != fp2.composite
