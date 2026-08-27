"""Validate that a CatchThat source/release tree is public-safe."""

from __future__ import annotations

import argparse
import json
import tomllib
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
REQUIRED_PUBLIC_FILES = {
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "SECURITY.md",
    "pyproject.toml",
}


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        return [f"package root does not exist: {root}"]
    for path in root.rglob("*"):
        if path.is_dir() and path.name in FORBIDDEN_DIRECTORY_NAMES:
            errors.append(f"forbidden private/build directory is present: {path.relative_to(root)}")
    for relative in sorted(REQUIRED_PUBLIC_FILES):
        if not (root / relative).is_file():
            errors.append(f"required public release file is missing: {relative}")

    project_version = None
    project_path = root / "pyproject.toml"
    try:
        with project_path.open("rb") as handle:
            project_version = tomllib.load(handle).get("project", {}).get("version")
    except (OSError, tomllib.TOMLDecodeError):
        pass

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
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"CatchThat plugin manifest cannot be read: {error}")
            manifest = None
        if isinstance(manifest, dict):
            if manifest.get("name") != "catchthat":
                errors.append("CatchThat plugin manifest name must be catchthat")
            if manifest.get("license") != "MIT":
                errors.append("CatchThat plugin manifest must declare the MIT license")
            if project_version and manifest.get("version") != project_version:
                errors.append("CatchThat plugin version must match pyproject.toml")
            skills_path = manifest.get("skills")
            if not isinstance(skills_path, str) or skills_path.replace("\\", "/") not in {"./skills/", "skills/"}:
                errors.append("CatchThat plugin skills path must point to ./skills/")
            interface = manifest.get("interface")
            if not isinstance(interface, dict) or not interface.get("defaultPrompt"):
                errors.append("CatchThat plugin interface.defaultPrompt is missing")
            plugin_root = manifest_path.parent.parent.resolve()
            if not (plugin_root / "skills").is_dir():
                errors.append("CatchThat plugin skills directory is missing")
            if isinstance(interface, dict):
                for field in ("composerIcon", "logo", "logoDark"):
                    value = interface.get(field)
                    if not isinstance(value, str) or not value:
                        errors.append(f"CatchThat plugin interface.{field} is missing")
                        continue
                    candidate = Path(value)
                    resolved = (plugin_root / candidate).resolve()
                    if (
                        candidate.is_absolute()
                        or ".." in candidate.parts
                        or not resolved.is_relative_to(plugin_root)
                        or not resolved.is_file()
                    ):
                        errors.append(f"CatchThat plugin interface.{field} must point to a bundled local asset")
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
