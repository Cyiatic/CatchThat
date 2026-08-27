from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from .core import (
    add_capture_to_session,
    build_catalog,
    build_archive,
    capture_session_status,
    decrypt_bundle,
    encrypt_bundle,
    export_evidence,
    export_bundle,
    finalize_capture_session,
    import_transcript,
    import_bundle,
    init_capture_session,
    load_json,
    merge_transcripts,
    redact_archive,
    render_text,
    validate_archive,
    verify_catalog,
    verify_build,
    verify_evidence,
    verify_transcript_coverage,
)


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _password_from_args(args: argparse.Namespace) -> str:
    if args.password_file:
        password = args.password_file.read_text(encoding="utf-8").rstrip("\r\n")
    else:
        password = getpass.getpass("Bundle password: ")
    if not password:
        raise ValueError("A non-empty bundle password is required")
    return password


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

    bundle_export = subparsers.add_parser("export-bundle", help="export an archive or viewer directory as a portable ZIP")
    bundle_export.add_argument("--input", required=True, type=_path)
    bundle_export.add_argument("--output", required=True, type=_path)

    bundle_import = subparsers.add_parser("import-bundle", help="safely extract a portable archive bundle")
    bundle_import.add_argument("--input", required=True, type=_path)
    bundle_import.add_argument("--output", required=True, type=_path)

    bundle_encrypt = subparsers.add_parser("encrypt-bundle", help="encrypt a portable bundle with a password-protected AES-GCM envelope")
    bundle_encrypt.add_argument("--input", required=True, type=_path)
    bundle_encrypt.add_argument("--output", required=True, type=_path)
    bundle_encrypt.add_argument("--password-file", type=_path, help="read the password from a private file; otherwise prompt securely")

    bundle_decrypt = subparsers.add_parser("decrypt-bundle", help="decrypt and safely extract a password-protected bundle")
    bundle_decrypt.add_argument("--input", required=True, type=_path)
    bundle_decrypt.add_argument("--output", required=True, type=_path)
    bundle_decrypt.add_argument("--password-file", type=_path, help="read the password from a private file; otherwise prompt securely")

    redact = subparsers.add_parser("redact", help="create a safe-share archive without private content or identities")
    redact.add_argument("--input", required=True, type=_path)
    redact.add_argument("--output", required=True, type=_path)
    redact.add_argument("--profile", default="safe-share", choices=("safe-share",))

    evidence = subparsers.add_parser("export-evidence", help="export a message-free provenance and integrity report")
    evidence.add_argument("--input", required=True, type=_path)
    evidence.add_argument("--output", required=True, type=_path)

    evidence_verify = subparsers.add_parser("verify-evidence", help="verify a metadata-only evidence report")
    evidence_verify.add_argument("input", type=_path)

    catalog = subparsers.add_parser("build-catalog", help="build a local launcher for multiple normalized archives")
    catalog.add_argument("--input", action="append", required=True, type=_path, help="archive JSON; repeat for each chat")
    catalog.add_argument("--output", required=True, type=_path)

    catalog_verify = subparsers.add_parser("verify-catalog", help="verify a local multi-archive catalog")
    catalog_verify.add_argument("input", type=_path)

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

    session = subparsers.add_parser("capture-session", help="track overlapping attended Snapchat capture ranges")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_init = session_commands.add_parser("init", help="create an empty capture session ledger")
    session_init.add_argument("--output", required=True, type=_path)
    session_init.add_argument("--title")
    session_init.add_argument("--thread-id")
    session_add = session_commands.add_parser("add", help="add one saved visible-DOM capture range")
    session_add.add_argument("--session", required=True, type=_path)
    session_add.add_argument("--input", required=True, type=_path)
    session_status = session_commands.add_parser("status", help="show range coverage and next capture action")
    session_status.add_argument("--session", required=True, type=_path)
    session_finalize = session_commands.add_parser("finalize", help="merge session ranges into an archive")
    session_finalize.add_argument("--session", required=True, type=_path)
    session_finalize.add_argument("--output", required=True, type=_path)
    session_finalize.add_argument("--reached-start", action="store_true")
    session_finalize.add_argument("--reached-end", action="store_true")
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

        if args.command == "export-bundle":
            summary = export_bundle(args.input, args.output)
            print(f"Exported bundle: {args.output}")
            print(f"Files: {summary['files']}")
            print(f"Bytes: {summary['bytes']}")
            return 0

        if args.command == "import-bundle":
            summary = import_bundle(args.input, args.output)
            print(f"Imported bundle: {args.output}")
            print(f"Files: {summary['files']}")
            print(f"Verified viewer: {bool(summary['verified'])}")
            return 0

        if args.command == "encrypt-bundle":
            summary = encrypt_bundle(args.input, args.output, _password_from_args(args))
            print(f"Encrypted bundle: {args.output}")
            print(f"Bytes: {summary['bytes']}")
            return 0

        if args.command == "decrypt-bundle":
            summary = decrypt_bundle(args.input, args.output, _password_from_args(args))
            print(f"Decrypted bundle: {args.output}")
            print(f"Files: {summary['files']}")
            print(f"Verified viewer: {bool(summary['verified'])}")
            return 0

        if args.command == "redact":
            archive = redact_archive(args.input, args.output, profile=args.profile)
            print(f"Redacted archive: {args.output}")
            print(f"Messages retained: {len(archive['messages'])}")
            print(f"Profile: {args.profile}")
            return 0

        if args.command == "export-evidence":
            evidence = export_evidence(args.input, args.output)
            print(f"Exported evidence report: {args.output}")
            print(f"Archive SHA-256: {evidence['archive']['sha256']}")
            print(f"Coverage: {evidence['coverage'].get('status', 'unverified')}")
            return 0

        if args.command == "verify-evidence":
            errors = verify_evidence(args.input)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 2
            print(f"Verified evidence report: {args.input}")
            return 0

        if args.command == "build-catalog":
            summary = build_catalog(args.input, args.output)
            print(f"Built archive catalog: {args.output / 'index.html'}")
            print(f"Archives: {summary['archives']}")
            return 0

        if args.command == "verify-catalog":
            errors = verify_catalog(args.input)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 2
            print(f"Verified archive catalog: {args.input}")
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

        if args.command == "capture-session":
            if args.session_command == "init":
                init_capture_session(args.output, title=args.title, thread_id=args.thread_id)
                print(f"Created capture session: {args.output}")
                return 0
            if args.session_command == "add":
                status = add_capture_to_session(args.session, args.input)
                print(f"Added capture to session: {args.session}")
                print(f"Ranges: {status['capture_count']}")
                print(f"Coverage: {status['coverage'].get('status', 'unverified')}")
                return 0
            if args.session_command == "status":
                status = capture_session_status(args.session)
                print(f"Session: {status['session']}")
                print(f"Ranges: {status['capture_count']}")
                print(f"Messages: {status['message_count']}")
                print(f"Coverage: {status['coverage'].get('status', 'unverified')}")
                if status.get("next_action"):
                    print(f"Next action: {status['next_action']}")
                return 0
            if args.session_command == "finalize":
                summary = finalize_capture_session(
                    args.session,
                    args.output,
                    reached_start=args.reached_start,
                    reached_end=args.reached_end,
                )
                print(f"Finalized capture session: {args.output}")
                print(f"Messages: {summary['messages']}")
                print(f"Coverage: {summary['coverage'].get('status', 'unverified')}")
                return 0
    except (OSError, RuntimeError, ValueError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1
