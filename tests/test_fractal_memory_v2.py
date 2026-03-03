"""Phase 7 — Fractal Memory V2: thin async adapter tests.

14 tests covering MemoryEntry, MemoryManager CRUD, Format A/B parsing,
search, index updates, and error handling.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from luna.memory.memory_manager import (
    MemoryEntry,
    MemoryManager,
    _parse_file,
    _validate_level,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path):
    """Build a minimal LunaConfig pointing at tmp_path as fractal_root."""
    from dataclasses import replace
    from luna.core.config import (
        ConsciousnessSection,
        HeartbeatSection,
        LunaConfig,
        LunaSection,
        MemorySection,
        ObservabilitySection,
        PipelineSection,
    )

    return LunaConfig(
        luna=LunaSection(
            version="2.2.0-test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(checkpoint_file="cs.json"),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(),
        root_dir=tmp_path,
    )


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# 1-2: MemoryEntry dataclass
# ---------------------------------------------------------------------------


def test_entry_defaults():
    now = datetime.now(timezone.utc)
    e = MemoryEntry(id="test_1", content="hello", memory_type="seed")
    assert e.keywords == []
    assert e.phi_resonance == 0.0
    assert e.metadata == {}
    assert e.created_at >= now


def test_entry_custom_values():
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    e = MemoryEntry(
        id="x",
        content="c",
        memory_type="leaf",
        keywords=["a", "b"],
        phi_resonance=0.618,
        created_at=dt,
        updated_at=dt,
        metadata={"k": "v"},
    )
    assert e.keywords == ["a", "b"]
    assert e.phi_resonance == 0.618
    assert e.created_at == dt
    assert e.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# 3-4: Initialization & empty reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_validates_root(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)
    assert mm.root == tmp_path / "fractal"


@pytest.mark.asyncio
async def test_read_level_empty(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)
    # Level dir doesn't exist yet — should return empty.
    entries = await mm.read_level("seeds")
    assert entries == []


# ---------------------------------------------------------------------------
# 5-8: Write / read / index / count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_then_read_level(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)
    entry = MemoryEntry(
        id="mem_001", content="test content", memory_type="seed", keywords=["test"],
    )
    path = await mm.write_memory(entry, "seeds")
    assert path.exists()

    entries = await mm.read_level("seeds")
    assert len(entries) == 1
    assert entries[0].id == "mem_001"
    assert entries[0].content == "test content"


@pytest.mark.asyncio
async def test_write_creates_index(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)
    entry = MemoryEntry(id="idx_1", content="x", memory_type="leaf")
    await mm.write_memory(entry, "leaves")

    index_path = tmp_path / "fractal" / "leaves" / "index.json"
    assert index_path.exists()
    with open(index_path) as f:
        index = json.load(f)
    assert "idx_1" in index["memories"]
    assert index["count"] == 1


@pytest.mark.asyncio
async def test_read_recent_across_levels(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    # Write entries to two different levels.
    e1 = MemoryEntry(
        id="old", content="old", memory_type="seed",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    e2 = MemoryEntry(
        id="new", content="new", memory_type="leaf",
        created_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
        updated_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    await mm.write_memory(e1, "seeds")
    await mm.write_memory(e2, "leaves")

    recent = await mm.read_recent(limit=2)
    assert len(recent) == 2
    assert recent[0].id == "new"  # Most recent first.


@pytest.mark.asyncio
async def test_count_by_level(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    e1 = MemoryEntry(id="a", content="a", memory_type="seed")
    e2 = MemoryEntry(id="b", content="b", memory_type="seed")
    e3 = MemoryEntry(id="c", content="c", memory_type="leaf")
    await mm.write_memory(e1, "seeds")
    await mm.write_memory(e2, "seeds")
    await mm.write_memory(e3, "leaves")

    counts = await mm.count_by_level()
    assert counts["seeds"] == 2
    assert counts["leaves"] == 1
    assert counts["roots"] == 0
    assert counts["branches"] == 0


# ---------------------------------------------------------------------------
# 9-10: Search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_keyword(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    e1 = MemoryEntry(
        id="s1", content="phi stuff", memory_type="seed",
        keywords=["phi", "math"], phi_resonance=0.8,
    )
    e2 = MemoryEntry(
        id="s2", content="unrelated", memory_type="seed",
        keywords=["cooking"],
    )
    await mm.write_memory(e1, "seeds")
    await mm.write_memory(e2, "seeds")

    results = await mm.search(["phi"])
    assert len(results) == 1
    assert results[0].id == "s1"


@pytest.mark.asyncio
async def test_search_no_match(tmp_path: Path):
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    e = MemoryEntry(id="s3", content="x", memory_type="seed", keywords=["abc"])
    await mm.write_memory(e, "seeds")

    results = await mm.search(["xyz"])
    assert results == []


# ---------------------------------------------------------------------------
# 11-12: Format A / Format B parsing
# ---------------------------------------------------------------------------


def test_parse_format_a(tmp_path: Path):
    data = {
        "id": "branch_abc",
        "type": "branch",
        "content": "golden ratio",
        "metadata": {"keywords": ["phi"], "phi_resonance": 0.5, "source": "test"},
        "created": "2025-06-15T10:00:00",
    }
    p = tmp_path / "test_a.json"
    _write_json(p, data)

    entry = _parse_file(p)
    assert entry is not None
    assert entry.id == "branch_abc"
    assert entry.memory_type == "branch"
    assert entry.content == "golden ratio"
    assert entry.keywords == ["phi"]
    assert entry.phi_resonance == 0.5


def test_parse_format_b(tmp_path: Path):
    data = {
        "memory_pure_v2": {
            "version": "2.0.0",
            "phi_constant": 1.618,
            "experience": {
                "id": "exp_xyz",
                "memory_type": "seed",
                "content": "test debug",
                "keywords": ["test"],
                "created_at": "2025-12-03T00:53:44.092183",
                "updated_at": "2025-12-03T00:53:44.092186",
                "phi_metrics": {"phi_resonance": 0.695},
                "session_context": {"session_id": "abc"},
            },
        }
    }
    p = tmp_path / "test_b.json"
    _write_json(p, data)

    entry = _parse_file(p)
    assert entry is not None
    assert entry.id == "exp_xyz"
    assert entry.memory_type == "seed"
    assert entry.keywords == ["test"]
    assert abs(entry.phi_resonance - 0.695) < 1e-6


# ---------------------------------------------------------------------------
# 13-14: Corrupt file / invalid level
# ---------------------------------------------------------------------------


def test_parse_corrupt_file_skipped(tmp_path: Path):
    p = tmp_path / "corrupt.json"
    p.write_text("{this is not valid json")
    entry = _parse_file(p)
    assert entry is None


def test_invalid_level_raises():
    with pytest.raises(ValueError, match="Invalid memory level"):
        _validate_level("galaxies")
