"""Tests for fingerprint ledger — append-only JSONL storage."""

from __future__ import annotations

import pytest

from luna.fingerprint.generator import Fingerprint
from luna.fingerprint.ledger import FingerprintLedger


def _make_fingerprint(step: int = 0) -> Fingerprint:
    return Fingerprint(
        agent_name="LUNA",
        psi0_hash="abc123",
        state_hash="def456",
        composite=f"composite_{step:04d}",
        timestamp=f"2026-01-01T00:00:{step:02d}Z",
        step_count=step,
    )


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "fingerprints.jsonl"


@pytest.fixture
def ledger(ledger_path):
    return FingerprintLedger(ledger_path)


class TestFingerprintLedger:
    """Tests for FingerprintLedger."""

    @pytest.mark.asyncio
    async def test_append_and_read(self, ledger):
        """Append a fingerprint and read it back."""
        fp = _make_fingerprint(step=1)
        await ledger.append(fp)

        records = await ledger.read_all()
        assert len(records) == 1
        assert records[0].agent_name == "LUNA"
        assert records[0].step_count == 1

    @pytest.mark.asyncio
    async def test_append_multiple(self, ledger):
        """Multiple appends accumulate in order."""
        for i in range(5):
            await ledger.append(_make_fingerprint(step=i))

        records = await ledger.read_all()
        assert len(records) == 5
        assert [r.step_count for r in records] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_read_empty(self, ledger):
        """Reading from non-existent ledger returns empty list."""
        records = await ledger.read_all()
        assert records == []

    @pytest.mark.asyncio
    async def test_read_latest(self, ledger):
        """read_latest returns the N most recent entries."""
        for i in range(10):
            await ledger.append(_make_fingerprint(step=i))

        latest = await ledger.read_latest(3)
        assert len(latest) == 3
        assert [r.step_count for r in latest] == [7, 8, 9]

    @pytest.mark.asyncio
    async def test_read_latest_more_than_available(self, ledger):
        """read_latest with N > total returns all entries."""
        await ledger.append(_make_fingerprint(step=0))
        latest = await ledger.read_latest(5)
        assert len(latest) == 1

    @pytest.mark.asyncio
    async def test_count(self, ledger):
        """count() returns the number of entries."""
        assert await ledger.count() == 0
        for i in range(3):
            await ledger.append(_make_fingerprint(step=i))
        assert await ledger.count() == 3

    @pytest.mark.asyncio
    async def test_append_only(self, ledger):
        """Ledger is append-only — existing entries are never modified."""
        fp1 = _make_fingerprint(step=1)
        await ledger.append(fp1)

        fp2 = _make_fingerprint(step=2)
        await ledger.append(fp2)

        records = await ledger.read_all()
        assert records[0].step_count == 1  # First entry unchanged

    @pytest.mark.asyncio
    async def test_roundtrip_serialization(self, ledger):
        """Fingerprint survives JSON serialization roundtrip."""
        fp = Fingerprint(
            agent_name="Test",
            psi0_hash="a" * 32,
            state_hash="b" * 32,
            composite="c" * 64,
            timestamp="2026-02-28T12:00:00Z",
            step_count=999,
        )
        await ledger.append(fp)
        records = await ledger.read_all()
        assert records[0] == fp

    def test_path_property(self, ledger, ledger_path):
        """path property returns the ledger file path."""
        assert ledger.path == ledger_path

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path):
        """Ledger creates parent directories if needed."""
        deep_path = tmp_path / "a" / "b" / "c" / "ledger.jsonl"
        ledger = FingerprintLedger(deep_path)
        await ledger.append(_make_fingerprint())
        assert deep_path.exists()
