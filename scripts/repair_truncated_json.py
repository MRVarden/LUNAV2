#!/usr/bin/env python3
"""Repair truncated JSON files in memory_fractal/.

These files were cut off mid-write (probably a crash).
Strategy: read the valid portion, attempt to close open braces/brackets,
and save a repaired version.
"""

import json
import os
import re
from pathlib import Path

MEMORY_ROOT = Path(__file__).parent.parent / "memory_fractal"

# Maximum file size to attempt repair (prevent reading huge crafted files)
_MAX_REPAIR_SIZE: int = 10 * 1024 * 1024  # 10 MB


def _assert_confined(path: Path, root: Path = MEMORY_ROOT) -> None:
    """Assert that path resolves to somewhere under root."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved) + os.sep) and resolved != root_resolved:
        raise RuntimeError(f"SECURITY: Path escapes MEMORY_ROOT: {resolved}")


def find_truncated_json(dirpath: Path) -> list[Path]:
    """Find JSON files that fail to parse."""
    broken = []
    for fpath in sorted(dirpath.glob("*.json")):
        if fpath.name in ("index.json",) or fpath.name.endswith(".bak"):
            continue
        try:
            with open(fpath) as f:
                json.load(f)
        except json.JSONDecodeError:
            broken.append(fpath)
    return broken


def repair_truncated(fpath: Path) -> bool:
    """Attempt to repair a truncated JSON file by closing open structures."""
    _assert_confined(fpath)
    if fpath.is_symlink():
        print(f"  SKIP (symlink): {fpath}")
        return False
    if fpath.stat().st_size > _MAX_REPAIR_SIZE:
        print(f"  SKIP (too large: {fpath.stat().st_size}): {fpath}")
        return False
    with open(fpath) as f:
        content = f.read()

    # Strip trailing whitespace and incomplete values
    content = content.rstrip()

    # Remove trailing incomplete key-value (e.g. "key": )
    content = re.sub(r',?\s*"[^"]*":\s*$', '', content)

    # Remove trailing comma
    content = content.rstrip().rstrip(',')

    # Count open/close braces and brackets
    open_braces = content.count('{') - content.count('}')
    open_brackets = content.count('[') - content.count(']')

    # Close arrays first, then objects
    content += ']' * open_brackets
    content += '}' * open_braces

    # Validate the repair
    try:
        data = json.loads(content)
        # Save the repaired file
        with open(fpath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except json.JSONDecodeError:
        return False


def main() -> None:
    repaired = 0
    failed = 0

    for dirname in ["seeds", "roots", "branches", "leaves"]:
        dirpath = MEMORY_ROOT / dirname
        if not dirpath.is_dir():
            continue

        broken = find_truncated_json(dirpath)
        if not broken:
            continue

        print(f"\n{dirname}/: {len(broken)} broken files")
        for fpath in broken:
            if repair_truncated(fpath):
                print(f"  REPAIRED: {fpath.name}")
                repaired += 1
            else:
                print(f"  FAILED:   {fpath.name}")
                failed += 1

    print(f"\nDone: {repaired} repaired, {failed} failed")


if __name__ == "__main__":
    main()
