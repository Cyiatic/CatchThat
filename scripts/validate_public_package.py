"""Validate that a CatchThat source/release tree is public-safe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_DIRECTORY_NAMES = {
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    "private-data",
    "output",
}


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        return [f"package root does not exist: {root}"]
    for path in root.rglob("*"):
        if path.is_dir() and path.name in FORBIDDEN_DIRECTORY_NAMES:
            errors.append(f"forbidden private/build directory is present: {path.relative_to(root)}")
    fixture_root = root / "fixtures"
    fixture_paths = [path for path in fixture_root.rglob("*") if path.is_file()] if fixture_root.is_dir() else []
    if not fixture_paths:
        errors.append("synthetic fixture is missing")
    else:
        allowed_fixture_root = (fixture_root / "sample").resolve()
        for path in fixture_paths:
            if not path.resolve().is_relative_to(allowed_fixture_root):
                errors.append(f"non-sample fixture is not allowed: {path.relative_to(root)}")
    sample_path = fixture_root / "sample" / "archive.json"
    try:
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"synthetic fixture cannot be read: {error}")
    else:
        if not isinstance(sample, dict) or sample.get("metadata", {}).get("synthetic") is not True:
            errors.append("fixtures/sample/archive.json must declare metadata.synthetic=true")
    manifest_path = root / "plugins" / "catchthat" / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        errors.append("CatchThat plugin manifest is missing")
    skill_path = root / "plugins" / "catchthat" / "skills" / "catchthat-archive" / "SKILL.md"
    if not skill_path.is_file():
        errors.append("CatchThat plugin skill is missing")
    logo_path = root / "assets" / "catchthat-logo.png"
    if not logo_path.is_file() or logo_path.stat().st_size == 0:
        errors.append("CatchThat README logo is missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    print(f"Public package validation passed: {Path(args.root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
