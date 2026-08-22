from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    build_archive,
    import_transcript,
    load_json,
    merge_transcripts,
    render_text,
    validate_archive,
    verify_build,
    verify_transcript_coverage,
)


def _path(value: str) -> Path:
    return Path(value).expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catchthat",
        description="Validate, import, merge, and build private offline Snapchat chat archives.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a normalized archive JSON file")
    validate.add_argument("input", type=_path)

    build = subparsers.add_parser("build", help="build a portable offline viewer")
    build.add_argument("input", type=_path)
    build.add_argument("--output", required=True, type=_path)

    verify = subparsers.add_parser("verify", help="verify a generated viewer, archive, and local assets")
    verify.add_argument("input", type=_path)

    for name in ("import-capture", "import-transcript"):
        importer = subparsers.add_parser(
            name,
            help="normalize an explicitly supplied Snapchat capture/transcript JSON file without network access",
        )
        importer.add_argument("--input", required=True, type=_path)
        importer.add_argument("--output", required=True, type=_path)

    capture_result = subparsers.add_parser(
        "capture-result",
        help="normalize one saved foreground adapter result and optionally build its offline viewer",
    )
    capture_result.add_argument("--input", required=True, type=_path)
    capture_result.add_argument("--output", required=True, type=_path, help="normalized archive JSON path")
    capture_result.add_argument("--build-output", type=_path, help="optional generated viewer directory")
    capture_result.add_argument("--text-output", type=_path, help="optional readable Person: message transcript")
    capture_result.add_argument("--timezone", help="override the archive display timezone for --text-output")

    for name in ("merge-captures", "merge-transcripts"):
        merge = subparsers.add_parser(name, help="merge overlapping attended Snapchat capture ranges")
        merge.add_argument("--input", action="append", required=True, type=_path, help="capture JSON; repeat for each range")
        merge.add_argument("--output", required=True, type=_path)
        merge.add_argument("--reached-start", action="store_true", help="attest that the oldest chat boundary was reached")
        merge.add_argument("--reached-end", action="store_true", help="attest that the newest chat boundary was reached")

    coverage = subparsers.add_parser("verify-coverage", help="verify the range-coverage report in a capture or archive")
    coverage.add_argument("input", type=_path)

    export = subparsers.add_parser("export-text", help="print a readable Person: message transcript")
    export.add_argument("input", type=_path)
    export.add_argument("--output", type=_path)
    export.add_argument("--timezone", help="override the archive display timezone")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            archive = load_json(args.input)
            errors = validate_archive(archive)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 2
            print(f"Valid archive: {args.input}")
            print(f"Messages: {len(archive['messages'])}")
            print(f"Participants: {len(archive['participants'])}")
            return 0

        if args.command == "build":
            missing = build_archive(args.input, args.output)
            print(f"Built offline viewer: {args.output / 'index.html'}")
            if missing:
                print("Missing local assets:")
                for reference in missing:
                    print(f"- {reference}")
            return 0

        if args.command == "verify":
            errors = verify_build(args.input)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 2
            print(f"Verified offline viewer: {args.input}")
            return 0

        if args.command in {"import-capture", "import-transcript"}:
            archive = import_transcript(args.input, args.output)
            print(f"Imported local capture archive: {args.output}")
            print(f"Messages: {len(archive['messages'])}")
            print(f"Participants: {len(archive['participants'])}")
            coverage = archive.get("metadata", {}).get("coverage")
            if isinstance(coverage, dict):
                print(f"Coverage: {coverage.get('status', 'unverified')}")
            return 0

        if args.command == "capture-result":
            archive = import_transcript(args.input, args.output)
            print(f"Imported local capture archive: {args.output}")
            print(f"Messages: {len(archive['messages'])}")
            print(f"Participants: {len(archive['participants'])}")
            coverage = archive.get("metadata", {}).get("coverage")
            if isinstance(coverage, dict):
                print(f"Coverage: {coverage.get('status', 'unverified')}")
            if args.build_output:
                missing = build_archive(args.output, args.build_output)
                print(f"Built offline viewer: {args.build_output / 'index.html'}")
                if missing:
                    print("Missing local assets:")
                    for reference in missing:
                        print(f"- {reference}")
            if args.text_output:
                args.text_output.parent.mkdir(parents=True, exist_ok=True)
                args.text_output.write_text(render_text(archive, args.timezone) + "\n", encoding="utf-8", newline="\n")
                print(f"Wrote readable transcript: {args.text_output}")
            return 0

        if args.command in {"merge-captures", "merge-transcripts"}:
            summary = merge_transcripts(
                args.input,
                args.output,
                reached_start=args.reached_start,
                reached_end=args.reached_end,
            )
            coverage = summary["coverage"]
            print(f"Merged capture ranges: {args.output}")
            print(f"Messages: {summary['messages']}")
            print(f"Participants: {summary['participants']}")
            print(f"Duplicate overlap records: {summary['duplicates']}")
            print(f"Conflicting overlap records: {summary['conflicts']}")
            print(f"Coverage: {coverage['status']} ({coverage['range_count']} range(s))")
            for note in coverage.get("notes", []):
                print(f"Coverage note: {note}")
            if coverage.get("next_action"):
                print(f"Next action: {coverage['next_action']}")
            return 0

        if args.command == "verify-coverage":
            coverage = verify_transcript_coverage(args.input)
            print(f"Coverage: {coverage.get('status', 'unverified')}")
            print(f"Ranges: {coverage.get('range_count', 0)}")
            print(f"Unique messages: {coverage.get('unique_message_count', 0)}")
            print(f"Complete: {bool(coverage.get('complete'))}")
            for note in coverage.get("notes", []):
                print(f"Coverage note: {note}")
            if coverage.get("next_action"):
                print(f"Next action: {coverage['next_action']}")
            return 0 if coverage.get("complete") else 2

        if args.command == "export-text":
            archive = load_json(args.input)
            errors = validate_archive(archive)
            if errors:
                raise ValueError("Archive validation failed:\n- " + "\n- ".join(errors))
            text = render_text(archive, args.timezone)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(text + "\n", encoding="utf-8", newline="\n")
                print(f"Wrote readable transcript: {args.output}")
            else:
                print(text)
            return 0
    except (OSError, ValueError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1
