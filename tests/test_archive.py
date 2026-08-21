from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from catchthat.cli import main as cli_main  # noqa: E402
from catchthat.core import (  # noqa: E402
    _template_path,
    build_archive,
    import_transcript,
    load_json,
    merge_transcripts,
    render_text,
    validate_archive,
    verify_build,
    verify_transcript_coverage,
)


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = PROJECT_ROOT / "fixtures" / "sample" / "archive.json"
        self.archive = load_json(self.fixture)

    def test_sample_archive_is_valid_and_explicitly_partial(self) -> None:
        self.assertEqual(validate_archive(self.archive), [])
        self.assertEqual(len(self.archive["messages"]), 7)
        self.assertEqual(self.archive["metadata"]["coverage"]["status"], "partial")
        self.assertEqual(self.archive["messages"][3]["content_kind"], "media_placeholder")

    def test_build_copies_viewer_data_assets_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "sample"
            self.assertEqual(build_archive(self.fixture, output), [])
            for name in ("index.html", "app.js", "archive.json", "manifest.json"):
                self.assertTrue((output / name).is_file())
            self.assertTrue((output / "assets" / "avatars" / "mara.svg").is_file())
            html = (output / "index.html").read_text(encoding="utf-8")
            app = (output / "app.js").read_text(encoding="utf-8")
            self.assertIn("CatchThat", html)
            self.assertIn('src="app.js"', html)
            self.assertIn("window.__ARCHIVE_DATA__", app)
            self.assertIn("Barely. I saved the recipe screenshot.", app)
            self.assertIn("coverage-banner", app)
            self.assertIn("This is not the whole conversation", app)
            self.assertIn("searchTextById", app)
            self.assertIn("windowSize = 240", app)
            self.assertIn("Source & provenance", html)
            self.assertNotIn("cdn.jsdelivr.net", html)
            self.assertEqual(verify_build(output), [])
            manifest = load_json(output / "manifest.json")
            self.assertEqual(manifest["manifest_version"], 1)
            self.assertIn("assets/avatars/mara.svg", {entry["path"] for entry in manifest["files"]})
            (output / "app.js").write_text(app + "\n// tampered", encoding="utf-8")
            self.assertTrue(any("hash mismatch: app.js" in error for error in verify_build(output)))

    def test_text_export_is_readable_and_preserves_media_state(self) -> None:
        output = render_text(self.archive)
        self.assertIn("Mara: Are you still up?", output)
        self.assertIn("Eli: [recipe-screenshot.png]", output)
        self.assertIn("(view_once)", output)

    def test_validation_rejects_unsafe_references_and_naive_timestamps(self) -> None:
        archive = deepcopy(self.archive)
        archive["messages"][0]["timestamp"] = "2024-03-10T01:30:00"
        archive["messages"][0]["media"] = [{"kind": "teleport", "label": "x", "path": "../x"}]
        archive["messages"][0]["provenance"] = {"source_file": "C:\\private\\chat.json"}
        archive["metadata"]["source"]["url"] = "javascript:alert(1)"
        errors = validate_archive(archive)
        self.assertTrue(any("timestamp must be an ISO-8601 timestamp with a timezone" in error for error in errors))
        self.assertTrue(any("must be one of" in error for error in errors))
        self.assertTrue(any("safe relative local asset path" in error for error in errors))
        self.assertTrue(any("source_file must be a safe relative source path" in error for error in errors))
        self.assertTrue(any("source.url must be an HTTP(S) URL" in error for error in errors))

    def test_import_preserves_provenance_indicators_and_local_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "assets" / "avatars").mkdir(parents=True)
            (root / "assets" / "images").mkdir(parents=True)
            (root / "assets" / "avatars" / "mara.svg").write_text("avatar", encoding="utf-8")
            (root / "assets" / "images" / "photo.svg").write_text("media", encoding="utf-8")
            input_path = root / "capture.json"
            input_path.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "kind": "snapchat_chat",
                            "title": "Mara and Eli",
                            "thread_id": "thread-1",
                            "display_timezone": "UTC",
                            "capture_range": {
                                "version": 1,
                                "rendered_count": 1,
                                "oldest_message_id": "m-1",
                                "oldest_timestamp": "2024-01-01T00:00:00Z",
                                "newest_message_id": "m-1",
                                "newest_timestamp": "2024-01-01T00:00:00Z",
                                "at_start": True,
                                "at_end": True,
                            },
                            "source": {
                                "type": "snapchat_visible_dom",
                                "url": "https://web.snapchat.com/chat/thread-1",
                                "notes": ["Provided by the archive owner."],
                            },
                        },
                        "participants": [{"id": "mara", "display_name": "Mara", "avatar_path": "assets/avatars/mara.svg"}],
                        "messages": [
                            {
                                "id": "m-1",
                                "author_id": "mara",
                                "timestamp": "2024-01-01T00:00:00Z",
                                "content": "Visible text",
                                "media": [{"kind": "image", "label": "photo.svg", "path": "assets/images/photo.svg"}],
                                "saved_state": "Saved in chat",
                                "retention": "View once",
                                "source_refs": [{"label": "A visible link", "url": "https://example.invalid/source"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "archive.json"
            archive = import_transcript(input_path, output)
            self.assertEqual(validate_archive(archive), [])
            message = archive["messages"][0]
            self.assertEqual(message["provenance"]["source_file"], "capture.json")
            self.assertEqual(message["provenance"]["record_index"], 0)
            self.assertEqual(message["saved_state"]["state"], "saved")
            self.assertEqual(message["retention"]["state"], "view_once")
            self.assertEqual(message["media"][0]["path"], "assets/images/photo.svg")
            self.assertNotIn(str(root), json.dumps(archive))
            built = root / "built"
            self.assertEqual(build_archive(output, built), [])
            self.assertTrue((built / "assets" / "avatars" / "mara.svg").is_file())
            self.assertTrue((built / "assets" / "images" / "photo.svg").is_file())

    def test_import_infers_author_and_stable_local_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "messages.json"
            input_path.write_text(
                json.dumps([{"timestamp": "2024-01-02T03:04:00Z", "author": "Mara", "content": "Inferred author"}]),
                encoding="utf-8",
            )
            archive = import_transcript(input_path, root / "archive.json")
            self.assertEqual(validate_archive(archive), [])
            self.assertEqual(archive["participants"][0]["id"], "author-mara")
            self.assertTrue(archive["messages"][0]["provenance"]["id_generated"])
            self.assertTrue(archive["messages"][0]["id"].startswith("local-"))

    def test_visible_capture_source_is_scoped_and_read_only(self) -> None:
        capture_source = (PROJECT_ROOT / "tools" / "snapchat_visible_capture.js").read_text(encoding="utf-8")
        self.assertIn("snapchat", capture_source.lower())
        self.assertIn("data-message-id", capture_source)
        self.assertIn("selector_notes", capture_source)
        self.assertIn("scroll_height", capture_source)
        self.assertIn("async (options = {})", capture_source)
        self.assertIn('options.scroll === "older"', capture_source)
        self.assertIn("scroll_action", capture_source)
        self.assertIn("scopeToConversationScroller", capture_source)
        self.assertIn("scrollTo", capture_source)
        self.assertIn("no follow-up scroll", capture_source)
        self.assertIn("visible DOM", capture_source)
        self.assertIn("timestamp-anchored", capture_source)
        self.assertIn("main li", capture_source)
        self.assertIn("[dir='auto']", capture_source)
        self.assertIn("headerAuthor", capture_source)
        self.assertIn("headerElement || row", capture_source)
        self.assertIn("detectedKind === \"unknown\"", capture_source)
        for forbidden in ("document.cookie", "localStorage", "sessionStorage", "fetch(", "XMLHttpRequest", "WebSocket", ".click("):
            self.assertNotIn(forbidden, capture_source)

    def test_merge_deduplicates_overlap_and_verifies_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            participant = {"id": "mara", "display_name": "Mara"}

            def write_capture(name: str, messages: list[dict[str, str]], at_start: bool, at_end: bool) -> Path:
                ordered = sorted(messages, key=lambda item: item["timestamp"])
                path = root / name
                path.write_text(
                    json.dumps(
                        {
                            "metadata": {
                                "kind": "snapchat_chat",
                                "title": "Mara",
                                "thread_id": "thread-1",
                                "source": {"url": "https://web.snapchat.com/chat/thread-1"},
                                "capture_range": {
                                    "version": 1,
                                    "rendered_count": len(messages),
                                    "oldest_message_id": ordered[0]["id"],
                                    "oldest_timestamp": ordered[0]["timestamp"],
                                    "newest_message_id": ordered[-1]["id"],
                                    "newest_timestamp": ordered[-1]["timestamp"],
                                    "at_start": at_start,
                                    "at_end": at_end,
                                },
                            },
                            "participants": [participant],
                            "messages": messages,
                        }
                    ),
                    encoding="utf-8",
                )
                return path

            first = write_capture(
                "range-001.json",
                [
                    {"id": "m1", "author_id": "mara", "timestamp": "2024-01-01T00:00:00Z", "content": "one"},
                    {"id": "m2", "author_id": "mara", "timestamp": "2024-01-01T00:01:00Z", "content": "two"},
                ],
                True,
                False,
            )
            second = write_capture(
                "range-002.json",
                [
                    {"id": "m2", "author_id": "mara", "timestamp": "2024-01-01T00:01:00Z", "content": "two"},
                    {"id": "m3", "author_id": "mara", "timestamp": "2024-01-01T00:02:00Z", "content": "three"},
                ],
                False,
                True,
            )
            merged_path = root / "merged.json"
            summary = merge_transcripts([first, second], merged_path)
            self.assertEqual(summary["messages"], 3)
            self.assertEqual(summary["duplicates"], 1)
            self.assertEqual(summary["coverage"]["status"], "verified")
            self.assertTrue(summary["coverage"]["complete"])
            self.assertEqual([message["id"] for message in load_json(merged_path)["messages"]], ["m1", "m2", "m3"])
            self.assertEqual(verify_transcript_coverage(merged_path)["status"], "verified")

    def test_partial_coverage_explains_next_action_and_cli_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "partial.json"
            capture.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "capture_range": {
                                "version": 1,
                                "rendered_count": 1,
                                "oldest_message_id": "m1",
                                "oldest_timestamp": "2024-01-01T00:00:00Z",
                                "newest_message_id": "m1",
                                "newest_timestamp": "2024-01-01T00:00:00Z",
                                "at_start": False,
                                "at_end": True,
                            }
                        },
                        "messages": [{"id": "m1", "author_id": "mara", "timestamp": "2024-01-01T00:00:00Z", "content": "one"}],
                    }
                ),
                encoding="utf-8",
            )
            coverage = verify_transcript_coverage(capture)
            self.assertEqual(coverage["status"], "partial")
            self.assertIn("oldest", coverage["next_action"])
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = cli_main(["verify-coverage", str(capture)])
            self.assertEqual(exit_code, 2)

    def test_viewer_template_is_available(self) -> None:
        self.assertTrue(_template_path().is_file())

    def test_viewer_preserves_coverage_and_deep_link_affordances(self) -> None:
        template = _template_path().read_text(encoding="utf-8")
        self.assertIn('role="status" aria-live="polite"', template)
        self.assertIn('aria-controls="left-rail"', template)
        self.assertIn('row.setAttribute("aria-current", "true")', template)
        self.assertIn("const selectedIndex = filtered.findIndex", template)
        self.assertIn(".coverage-banner { max-width: none;", template)
        self.assertNotIn(".search-row, .coverage-banner", template)


if __name__ == "__main__":
    unittest.main()
