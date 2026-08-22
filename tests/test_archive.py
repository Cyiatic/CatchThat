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
            self.assertTrue((output / "assets" / "media" / "recipe-screenshot.svg").is_file())
            self.assertTrue((output / "assets" / "media" / "bitmoji-wave.svg").is_file())
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
            self.assertIn('data-action="edge"', html)
            self.assertIn("Scroll to Top", html)
            self.assertIn("All ${filtered.length} captured rows", app)
            self.assertIn("scrollToNewest", app)
            self.assertIn("renderParticipantProfile", app)
            self.assertIn("media-card", app)
            self.assertIn("visible_profile", app)
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
                "participants": [{
                    "id": "mara",
                    "display_name": "Mara",
                    "avatar_path": "assets/avatars/mara.svg",
                    "visible_profile": {"handle": "mara", "status": "Active", "source_id": "user-mara"},
                }],
                        "messages": [
                            {
                                "id": "m-1",
                                "author_id": "mara",
                                "timestamp": "2024-01-01T00:00:00Z",
                                "content": "Visible text",
                                "media": [
                                    {"kind": "image", "label": "photo.svg", "path": "assets/images/photo.svg"},
                                    {"kind": "bitmoji", "label": "Bitmoji wave", "url": "https://example.invalid/bitmoji.webp", "alt": "Visible Bitmoji"},
                                ],
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
            self.assertEqual(message["media"][1]["kind"], "sticker")
            self.assertEqual(message["media"][1]["subtype"], "bitmoji")
            self.assertEqual(archive["participants"][0]["visible_profile"]["status"], "Active")
            self.assertNotIn(str(root), json.dumps(archive))
            built = root / "built"
            self.assertEqual(build_archive(output, built), [])
            self.assertTrue((built / "assets" / "avatars" / "mara.svg").is_file())
            self.assertTrue((built / "assets" / "images" / "photo.svg").is_file())

    def test_import_materializes_visible_avatar_pixels_as_local_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = deepcopy(self.archive)
            raw["participants"][0].pop("avatar_path", None)
            raw["participants"][0]["avatar_data_url"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            raw["participants"][0]["avatar_capture_method"] = "visible_pixels_png"
            input_path = root / "visible-capture.json"
            input_path.write_text(json.dumps(raw), encoding="utf-8")
            output = root / "archive.json"

            archive = import_transcript(input_path, output)
            participant = archive["participants"][0]
            self.assertTrue(participant["avatar_path"].startswith("assets/avatars/mara-"))
            avatar_path = root / participant["avatar_path"]
            self.assertTrue(avatar_path.is_file())
            self.assertEqual(avatar_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(participant["avatar_provenance"]["method"], "visible_pixels_png")
            self.assertTrue(participant["avatar_provenance"]["captured"])
            self.assertNotIn("avatar_data_url", json.dumps(archive))
            self.assertEqual(validate_archive(archive), [])

            built = root / "built"
            missing = build_archive(output, built)
            self.assertIn("assets/avatars/eli.svg", missing)
            self.assertTrue((built / participant["avatar_path"]).is_file())

    def test_import_tracks_nested_walk_ranges_for_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = deepcopy(self.archive)
            raw["metadata"].pop("coverage", None)
            messages = raw["messages"]
            message_ids = [message["id"] for message in messages]
            raw["metadata"]["capture_range"] = {
                "version": 1,
                "capture_id": "capture-walk",
                "rendered_count": len(messages),
                "oldest_message_id": message_ids[0],
                "oldest_timestamp": messages[0]["timestamp"],
                "newest_message_id": message_ids[-1],
                "newest_timestamp": messages[-1]["timestamp"],
                "at_start": True,
                "at_end": False,
                "ranges": [
                    {
                        "range_index": 0,
                        "rendered_count": len(message_ids[3:]),
                        "oldest_message_id": message_ids[3],
                        "oldest_timestamp": messages[3]["timestamp"],
                        "newest_message_id": message_ids[-1],
                        "newest_timestamp": messages[-1]["timestamp"],
                        "at_start": False,
                        "at_end": False,
                        "message_ids": message_ids[3:],
                    },
                    {
                        "range_index": 1,
                        "rendered_count": len(message_ids[:4]),
                        "oldest_message_id": message_ids[0],
                        "oldest_timestamp": messages[0]["timestamp"],
                        "newest_message_id": message_ids[3],
                        "newest_timestamp": messages[3]["timestamp"],
                        "at_start": True,
                        "at_end": False,
                        "message_ids": message_ids[:4],
                    },
                ],
            }
            input_path = root / "walk.json"
            input_path.write_text(json.dumps(raw), encoding="utf-8")
            archive = import_transcript(input_path, root / "archive.json")
            coverage = archive["metadata"]["coverage"]
            self.assertEqual(validate_archive(archive), [])
            self.assertEqual(coverage["range_count"], 2)
            self.assertEqual(coverage["unique_message_count"], len(messages))
            self.assertTrue(coverage["start_confirmed"])
            self.assertFalse(coverage["end_confirmed"])
            self.assertTrue(coverage["ranges_linked"])
            self.assertFalse(coverage["complete"])
            self.assertEqual(verify_transcript_coverage(root / "archive.json"), coverage)

            repeated = deepcopy(raw)
            repeated_range = repeated["metadata"]["capture_range"]
            repeated_range["at_start"] = True
            repeated_range["at_end"] = True
            for nested in repeated_range["ranges"]:
                nested.update(
                    {
                        "rendered_count": len(message_ids),
                        "oldest_message_id": message_ids[0],
                        "oldest_timestamp": messages[0]["timestamp"],
                        "newest_message_id": message_ids[-1],
                        "newest_timestamp": messages[-1]["timestamp"],
                        "at_start": True,
                        "at_end": True,
                        "message_ids": message_ids,
                    }
                )
            repeated_input = root / "repeated.json"
            repeated_input.write_text(json.dumps(repeated), encoding="utf-8")
            repeated_archive = import_transcript(repeated_input, root / "repeated.archive.json")
            repeated_coverage = repeated_archive["metadata"]["coverage"]
            self.assertTrue(repeated_coverage["start_confirmed"])
            self.assertTrue(repeated_coverage["end_confirmed"])
            self.assertTrue(repeated_coverage["repeated_boundaries"])
            self.assertFalse(repeated_coverage["range_boundaries_changed"])
            self.assertTrue(repeated_coverage["complete"])
            self.assertEqual(repeated_coverage["status"], "verified")
            self.assertIn("non-virtualized rendered DOM", " ".join(repeated_coverage["notes"]))

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
        self.assertIn("async function capture(options = {})", capture_source)
        self.assertIn('options.scroll === "older"', capture_source)
        self.assertIn('options.walk === "older"', capture_source)
        self.assertIn("scroll_action", capture_source)
        self.assertIn("scroll_walk", capture_source)
        self.assertIn("capture_walk_index", capture_source)
        self.assertIn("scopeToConversationScroller", capture_source)
        self.assertIn("scrollBy", capture_source)
        self.assertIn("scrollTo", capture_source)
        self.assertIn("scrollTo_fallback", capture_source)
        self.assertIn("message_ids", capture_source)
        self.assertIn("repeated_ranges", capture_source)
        self.assertIn("no follow-up scroll", capture_source)
        self.assertIn("visible DOM", capture_source)
        self.assertIn("timestamp-anchored", capture_source)
        self.assertIn("main li", capture_source)
        self.assertIn("[dir='auto']", capture_source)
        self.assertIn("headerAuthor", capture_source)
        self.assertIn("mediaDescriptor", capture_source)
        self.assertIn("captureVisibleAvatar", capture_source)
        self.assertIn("canvas.toDataURL", capture_source)
        self.assertIn("avatar_data_url", capture_source)
        self.assertIn("avatar_capture_method", capture_source)
        self.assertIn('item.subtype = "bitmoji"', capture_source)
        self.assertIn("visible_profile", capture_source)
        self.assertIn("avatar_alt", capture_source)
        self.assertIn("profileLink", capture_source)
        self.assertIn("favicon|site[- ]?icon|link[- ]?icon", capture_source)
        self.assertIn("currentSrc", capture_source)
        self.assertIn('const headerElement = row.querySelector("header")', capture_source)
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

    def test_merge_preserves_complementary_media_and_profile_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base_metadata = {
                "kind": "snapchat_chat",
                "title": "Mara",
                "thread_id": "thread-1",
                "source": {"url": "https://web.snapchat.com/chat/thread-1"},
                "capture_range": {
                    "version": 1,
                    "rendered_count": 1,
                    "oldest_message_id": "m1",
                    "oldest_timestamp": "2024-01-01T00:00:00Z",
                    "newest_message_id": "m1",
                    "newest_timestamp": "2024-01-01T00:00:00Z",
                    "at_start": True,
                    "at_end": True,
                },
            }
            first = root / "range-001.json"
            first.write_text(
                json.dumps(
                    {
                        "metadata": base_metadata,
                        "participants": [{"id": "mara", "display_name": "Mara", "visible_profile": {"handle": "mara"}}],
                        "messages": [{"id": "m1", "author_id": "mara", "timestamp": "2024-01-01T00:00:00Z", "content": "look", "media": [{"kind": "image", "label": "photo", "source_url": "https://example.invalid/photo"}] }],
                    }
                ),
                encoding="utf-8",
            )
            second = root / "range-002.json"
            second_metadata = deepcopy(base_metadata)
            second_metadata["source"] = {"url": "https://web.snapchat.com/chat/thread-1"}
            second.write_text(
                json.dumps(
                    {
                        "metadata": second_metadata,
                        "participants": [{"id": "mara", "display_name": "Mara", "visible_profile": {"status": "Active", "source_id": "user-mara"}}],
                        "messages": [{"id": "m1", "author_id": "mara", "timestamp": "2024-01-01T00:00:00Z", "content": "look", "media": [{"kind": "sticker", "subtype": "bitmoji", "label": "wave"}]}],
                    }
                ),
                encoding="utf-8",
            )
            merged_path = root / "merged.json"
            merge_transcripts([first, second], merged_path)
            merged = load_json(merged_path)
            self.assertEqual(merged["participants"][0]["visible_profile"], {"handle": "mara", "status": "Active", "source_id": "user-mara"})
            self.assertEqual({item["label"] for item in merged["messages"][0]["media"]}, {"photo", "wave"})

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
        self.assertIn('role="list" aria-label="Captured messages"', template)
        self.assertIn('id="selected-message" aria-live="polite"', template)
        self.assertIn("content-visibility: auto", template)
        self.assertIn("const state = { query: \"\", authorIds: new Set(participants.keys()), timestampMode: \"local\", windowStart: 0, selected: null, edgeTarget: \"oldest\" }", template)
        self.assertIn('data-action="toggle-coverage"', template)
        self.assertIn('class="evidence-button"', template)
        self.assertIn('data-action="toggle-provenance"', template)
        self.assertIn('rel="icon"', template)
        self.assertIn('viewBox="0 0 64 48"', template)
        self.assertIn('M39 18h12l9 6-9 6H39z', template)
        self.assertIn('class="rail-product"', template)
        self.assertIn("filter-toggle", template)
        self.assertIn('class="author-filter-menu"', template)
        self.assertIn('id="author-filter-trigger-label"', template)
        self.assertNotIn("outline: none", template)
        self.assertIn('aria-controls="left-rail"', template)
        self.assertNotIn('class="topbar"', template)
        self.assertNotIn('--nav-rail', template)
        self.assertIn('row.setAttribute("aria-current", "true")', template)
        self.assertIn("const selectedIndex = filtered.findIndex", template)
        self.assertIn(".coverage-banner { max-width: none;", template)
        self.assertNotIn(".search-row, .coverage-banner", template)


if __name__ == "__main__":
    unittest.main()
