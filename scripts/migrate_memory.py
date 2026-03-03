#!/usr/bin/env python3
"""Memory fractal migration script.

Migrations:
1. branchs/ -> branches/ (full rename, no existing branches/)
2. leafs/ -> merge into leaves/ (leaves/ already has subdirs + 1 leaf)
3. Fix index.json type fields to match directory names
4. Rebuild indexes to include all files on disk
5. Prune consciousness backups (keep first + last)
6. Remove .bak files from migrated dirs
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

MEMORY_ROOT = Path(__file__).parent.parent / "memory_fractal"

DRY_RUN = False  # Set True to preview without changes


def log(msg: str) -> None:
    print(f"  {'[DRY]' if DRY_RUN else '[OK]'} {msg}")


def _assert_confined(path: Path, root: Path = MEMORY_ROOT) -> None:
    """Assert that path resolves to somewhere under root. Prevents path traversal."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved) + os.sep) and resolved != root_resolved:
        raise RuntimeError(
            f"SECURITY: Path escapes MEMORY_ROOT. path={resolved}, root={root_resolved}"
        )


def _reject_symlinks_in(dirpath: Path) -> None:
    """Reject any symlinks found in a directory tree. Prevents symlink attacks."""
    if not dirpath.exists():
        return
    for item in dirpath.rglob("*"):
        if item.is_symlink():
            raise RuntimeError(
                f"SECURITY: Symlink detected at {item}. "
                f"Target: {item.resolve()}. Remove symlinks before migration."
            )


def migrate_branchs_to_branches() -> None:
    """Rename branchs/ to branches/."""
    src = MEMORY_ROOT / "branchs"
    dst = MEMORY_ROOT / "branches"

    if not src.exists():
        print("SKIP: branchs/ does not exist (already migrated?)")
        return
    if dst.exists():
        raise RuntimeError("Both branchs/ AND branches/ exist — manual resolution needed")

    _assert_confined(src)
    _assert_confined(dst)
    _reject_symlinks_in(src)

    print(f"\n=== Migrating branchs/ -> branches/ ===")
    if not DRY_RUN:
        shutil.move(str(src), str(dst))
    log(f"Renamed branchs/ -> branches/")

    # Fix index type
    index_path = dst / "index.json"
    if index_path.exists():
        fix_index_type(index_path, "branches")


def migrate_leafs_to_leaves() -> None:
    """Merge leafs/ JSON files into existing leaves/, then remove leafs/."""
    src = MEMORY_ROOT / "leafs"
    dst = MEMORY_ROOT / "leaves"

    if not src.exists():
        print("SKIP: leafs/ does not exist (already migrated?)")
        return

    _assert_confined(src)
    _assert_confined(dst)
    _reject_symlinks_in(src)

    print(f"\n=== Merging leafs/ into leaves/ ===")

    # Ensure leaves/ exists
    if not dst.exists():
        if not DRY_RUN:
            dst.mkdir(parents=True)
        log("Created leaves/")

    # Copy all .json files from leafs/ to leaves/ (skip .bak)
    copied = 0
    for fpath in sorted(src.glob("*.json")):
        if fpath.name.endswith(".bak"):
            continue
        dest_file = dst / fpath.name
        if dest_file.exists() and fpath.name != "index.json":
            # File already in leaves/ — skip (don't overwrite)
            log(f"SKIP (exists): {fpath.name}")
            continue
        if fpath.name == "index.json":
            # Will merge indexes separately
            continue
        if not DRY_RUN:
            shutil.copy2(str(fpath), str(dest_file))
        log(f"Copied {fpath.name}")
        copied += 1

    print(f"  Copied {copied} files from leafs/ to leaves/")

    # Merge indexes
    merge_leaf_indexes(src / "index.json", dst / "index.json")

    # Remove leafs/ directory
    if not DRY_RUN:
        shutil.rmtree(str(src))
    log(f"Removed leafs/")


def merge_leaf_indexes(src_index: Path, dst_index: Path) -> None:
    """Merge leafs/index.json memories into leaves/index.json."""
    src_data = {}
    dst_data = {}

    if src_index.exists():
        with open(src_index) as f:
            src_data = json.load(f)

    if dst_index.exists():
        with open(dst_index) as f:
            dst_data = json.load(f)

    # Start with dst memories, add src memories (src wins on conflict for completeness)
    merged_memories = {}
    merged_memories.update(dst_data.get("memories", {}))
    merged_memories.update(src_data.get("memories", {}))

    merged = {
        "type": "leaves",
        "updated": datetime.now().isoformat(),
        "count": len(merged_memories),
        "memories": merged_memories,
    }

    if not DRY_RUN:
        with open(dst_index, "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    log(f"Merged index: {len(merged_memories)} total memories (type='leaves')")


def fix_index_type(index_path: Path, expected_type: str) -> None:
    """Fix the 'type' field in an index.json to match directory name."""
    with open(index_path) as f:
        data = json.load(f)

    old_type = data.get("type", "")
    if old_type == expected_type:
        log(f"Index type already correct: {expected_type}")
        return

    data["type"] = expected_type
    data["updated"] = datetime.now().isoformat()

    if not DRY_RUN:
        with open(index_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"Fixed index type: '{old_type}' -> '{expected_type}'")


def rebuild_all_indexes() -> None:
    """Rebuild indexes for all 4 dirs to include orphan files on disk."""
    print(f"\n=== Rebuilding indexes ===")
    for dirname in ["seeds", "roots", "branches", "leaves"]:
        dirpath = MEMORY_ROOT / dirname
        if not dirpath.is_dir():
            continue
        rebuild_index(dirpath, dirname)


def rebuild_index(dirpath: Path, dirname: str) -> None:
    """Rebuild index.json to include all .json files on disk."""
    _assert_confined(dirpath)
    _reject_symlinks_in(dirpath)
    index_path = dirpath / "index.json"

    # Load existing index
    existing = {}
    if index_path.exists():
        with open(index_path) as f:
            existing = json.load(f)

    memories = existing.get("memories", {})
    added = 0

    # Scan disk for .json files not in index
    for fpath in sorted(dirpath.glob("*.json")):
        if fpath.name in ("index.json",) or fpath.name.endswith(".bak"):
            continue
        file_id = fpath.stem
        if file_id not in memories:
            # Read the file to extract metadata if possible
            try:
                with open(fpath) as f:
                    file_data = json.load(f)
                memories[file_id] = {
                    "created_at": file_data.get("created_at",
                                  file_data.get("timestamp",
                                  datetime.now().isoformat())),
                    "keywords": file_data.get("keywords", []),
                    "phi_resonance": file_data.get("phi_resonance", 0.618),
                    "emotional_tone": file_data.get("emotional_tone", "neutral"),
                }
            except (json.JSONDecodeError, KeyError):
                memories[file_id] = {
                    "created_at": datetime.now().isoformat(),
                    "keywords": [],
                    "phi_resonance": 0.618,
                    "emotional_tone": "neutral",
                }
            added += 1
            log(f"Indexed orphan: {file_id}")

    if added > 0 or existing.get("type") != dirname:
        result = {
            "type": dirname,
            "updated": datetime.now().isoformat(),
            "count": len(memories),
            "memories": memories,
        }
        if not DRY_RUN:
            with open(index_path, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        log(f"{dirname}/index.json: {added} orphans added, {len(memories)} total")
    else:
        log(f"{dirname}/index.json: already consistent ({len(memories)} entries)")


def prune_backups() -> None:
    """Keep only first and last consciousness backup."""
    print(f"\n=== Pruning backups ===")
    backups = sorted(MEMORY_ROOT.glob("consciousness_state_v2.backup_*.json"))
    if len(backups) <= 2:
        log(f"Only {len(backups)} backups — nothing to prune")
        return

    keep = {backups[0], backups[-1]}
    removed = 0
    for bak in backups:
        if bak not in keep:
            if not DRY_RUN:
                bak.unlink()
            log(f"Removed {bak.name}")
            removed += 1

    log(f"Pruned {removed} backups, kept {backups[0].name} and {backups[-1].name}")


def clean_bak_files() -> None:
    """Remove .bak files from all fractal directories."""
    print(f"\n=== Cleaning .bak files ===")
    for dirname in ["seeds", "roots", "branches", "leaves"]:
        dirpath = MEMORY_ROOT / dirname
        if not dirpath.is_dir():
            continue
        for bak in dirpath.glob("*.bak"):
            if not DRY_RUN:
                bak.unlink()
            log(f"Removed {dirname}/{bak.name}")


def main() -> None:
    print("=" * 60)
    print("Luna Memory Fractal Migration")
    print(f"Root: {MEMORY_ROOT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print("=" * 60)

    migrate_branchs_to_branches()
    migrate_leafs_to_leaves()
    rebuild_all_indexes()
    prune_backups()
    clean_bak_files()

    print("\n" + "=" * 60)
    print("Migration complete.")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if "--dry-run" in sys.argv:
        DRY_RUN = True
    main()
