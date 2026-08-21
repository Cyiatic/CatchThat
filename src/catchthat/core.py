from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import re
import shutil
import sysconfig
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


SCHEMA_VERSION = 1
_MISSING = object()
_TIMESTAMP_OFFSET = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$", re.IGNORECASE)
_CONTENT_KINDS = frozenset({"visible_text", "media_placeholder", "mixed", "empty"})
_MEDIA_KINDS = frozenset({"image", "video", "audio", "file", "sticker", "snap", "unknown"})
_SAVED_STATES = frozenset({"saved", "unsaved", "unknown"})
_RETENTION_STATES = frozenset({"kept_in_chat", "view_once", "expires", "unknown"})


def _load_json_value(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_json(path: Path) -> dict[str, Any]:
    value = _load_json_value(path)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate[-1:].lower() == "z":
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalise_timestamp(value: Any) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def _has_timestamp_timezone(value: Any) -> bool:
    return isinstance(value, str) and bool(_TIMESTAMP_OFFSET.search(value.strip()))


def _is_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _normalise_local_reference(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("\\", "/")
    if _is_http_url(candidate) or candidate.lower().startswith("data:"):
        return None
    if candidate.startswith("/") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", candidate):
        return None
    parts = [part for part in candidate.split("/") if part not in {"", "."}]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _clean(value: Any) -> str:
    return re.sub(r"[ \t\f\v]+", " ", str(value or "")).strip()


def _first(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return default


def _validate_timestamp(value: Any, field: str, errors: list[str]) -> None:
    if parse_timestamp(value) is None or not _has_timestamp_timezone(value):
        errors.append(f"{field} must be an ISO-8601 timestamp with a timezone")


def _validate_local_reference(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a relative local asset path or null")
    elif _normalise_local_reference(value) is None:
        errors.append(f"{field} must be a safe relative local asset path")


def _validate_media(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in _MEDIA_KINDS:
        errors.append(f"{field}.kind must be one of {sorted(_MEDIA_KINDS)}")
    if not isinstance(value.get("label"), str) or not value["label"].strip():
        errors.append(f"{field}.label must be a non-empty string")
    _validate_local_reference(value.get("path"), f"{field}.path", errors)
    if value.get("source_url") is not None and not _is_http_url(value["source_url"]):
        errors.append(f"{field}.source_url must be an HTTP(S) URL or null")
    if value.get("placeholder") is not None and not isinstance(value["placeholder"], str):
        errors.append(f"{field}.placeholder must be a string or null")
    if value.get("alt") is not None and not isinstance(value["alt"], str):
        errors.append(f"{field}.alt must be a string or null")
    if value.get("size_bytes") is not None:
        size = value["size_bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            errors.append(f"{field}.size_bytes must be a non-negative integer or null")


def _validate_indicator(value: Any, field: str, states: frozenset[str], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    if value.get("state") not in states:
        errors.append(f"{field}.state must be one of {sorted(states)}")
    for key in ("evidence", "label"):
        if key in value and value[key] is not None and not isinstance(value[key], str):
            errors.append(f"{field}.{key} must be a string or null")
    if "visible" in value and not isinstance(value["visible"], bool):
        errors.append(f"{field}.visible must be boolean")


def _validate_source_ref(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    if not isinstance(value.get("kind"), str) or not value["kind"].strip():
        errors.append(f"{field}.kind must be a non-empty string")
    if not isinstance(value.get("label"), str) or not value["label"].strip():
        errors.append(f"{field}.label must be a non-empty string")
    if value.get("url") is not None and not _is_http_url(value["url"]):
        errors.append(f"{field}.url must be an HTTP(S) URL or null")


def _validate_provenance(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    if value.get("source_file") is not None:
        if not isinstance(value["source_file"], str) or _normalise_local_reference(value["source_file"]) is None:
            errors.append(f"{field}.source_file must be a safe relative source path")
    for key in ("source_id", "source_url", "capture_id"):
        if value.get(key) is not None and not isinstance(value[key], str):
            errors.append(f"{field}.{key} must be a string or null")
    if value.get("source_url") is not None and not _is_http_url(value["source_url"]):
        errors.append(f"{field}.source_url must be an HTTP(S) URL")
    if "record_index" in value:
        index = value["record_index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            errors.append(f"{field}.record_index must be a non-negative integer")
    if "id_generated" in value and not isinstance(value["id_generated"], bool):
        errors.append(f"{field}.id_generated must be boolean")
    if "notes" in value and (
        not isinstance(value["notes"], list) or any(not isinstance(note, str) for note in value["notes"])
    ):
        errors.append(f"{field}.notes must be an array of strings")


def _validate_capture_range(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object or null")
        return
    version = value.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        errors.append(f"{field}.version must be 1")
    for key in ("rendered_count", "skipped_without_timestamp"):
        if key in value:
            count = value[key]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                errors.append(f"{field}.{key} must be a non-negative integer")
    for key in ("oldest_message_id", "newest_message_id", "selector", "capture_id"):
        if key in value and value[key] is not None and not isinstance(value[key], str):
            errors.append(f"{field}.{key} must be a string or null")
    for key in ("oldest_timestamp", "newest_timestamp"):
        if key in value and value[key] is not None:
            _validate_timestamp(value[key], f"{field}.{key}", errors)
    for key in ("scroll_top", "scroll_height", "viewport_height"):
        if key in value:
            number = value[key]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or number < 0:
                errors.append(f"{field}.{key} must be a non-negative number")
    for key in ("at_start", "at_end"):
        if key in value and not isinstance(value[key], bool):
            errors.append(f"{field}.{key} must be boolean")
    if "selector_notes" in value and (
        not isinstance(value["selector_notes"], list)
        or any(not isinstance(note, str) for note in value["selector_notes"])
    ):
        errors.append(f"{field}.selector_notes must be an array of strings")


def _validate_coverage(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object or null")
        return
    if value.get("status") not in {"verified", "partial", "unverified"}:
        errors.append(f"{field}.status must be verified, partial, or unverified")
    if "complete" in value and not isinstance(value["complete"], bool):
        errors.append(f"{field}.complete must be boolean")
    for key in ("range_count", "unique_message_count", "duplicate_message_count", "conflict_count"):
        if key in value:
            count = value[key]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                errors.append(f"{field}.{key} must be a non-negative integer")
    for key in ("start_confirmed", "end_confirmed", "ranges_linked"):
        if key in value and not isinstance(value[key], bool):
            errors.append(f"{field}.{key} must be boolean")
    if "notes" in value and (
        not isinstance(value["notes"], list) or any(not isinstance(note, str) for note in value["notes"])
    ):
        errors.append(f"{field}.notes must be an array of strings")
    if "next_action" in value and not isinstance(value["next_action"], str):
        errors.append(f"{field}.next_action must be a string")
    if "unlinked_ranges" in value and (
        not isinstance(value["unlinked_ranges"], list)
        or any(not isinstance(item, str) for item in value["unlinked_ranges"])
    ):
        errors.append(f"{field}.unlinked_ranges must be an array of strings")
    if "ranges" in value:
        if not isinstance(value["ranges"], list) or any(not isinstance(item, dict) for item in value["ranges"]):
            errors.append(f"{field}.ranges must be an array of objects")


def validate_archive(archive: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(archive, dict):
        return ["archive must be a JSON object"]
    if archive.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}; got {archive.get('schema_version')!r}")

    metadata = archive.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        for field in ("kind", "title"):
            if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                errors.append(f"metadata.{field} must be a non-empty string")
        for field in ("thread_id", "channel_id"):
            if field in metadata and metadata[field] is not None and not isinstance(metadata[field], str):
                errors.append(f"metadata.{field} must be a string or null")
        if metadata.get("captured_at") is not None:
            _validate_timestamp(metadata["captured_at"], "metadata.captured_at", errors)
        if "display_timezone" in metadata and (
            not isinstance(metadata["display_timezone"], str) or not metadata["display_timezone"].strip()
        ):
            errors.append("metadata.display_timezone must be a non-empty string")
        for field in ("capture_range", "coverage"):
            if field in metadata and metadata[field] is not None:
                ( _validate_capture_range if field == "capture_range" else _validate_coverage )(
                    metadata[field], f"metadata.{field}", errors
                )
        if "thread_identity" in metadata and metadata["thread_identity"] is not None:
            identity = metadata["thread_identity"]
            if not isinstance(identity, dict) or any(
                not isinstance(value, (str, type(None))) for value in identity.values()
            ):
                errors.append("metadata.thread_identity must be an object of strings or nulls")
        if "selector_notes" in metadata and (
            not isinstance(metadata["selector_notes"], list)
            or any(not isinstance(note, str) for note in metadata["selector_notes"])
        ):
            errors.append("metadata.selector_notes must be an array of strings")
        source = metadata.get("source")
        if source is not None:
            if not isinstance(source, dict):
                errors.append("metadata.source must be an object")
            else:
                for key in ("type", "label", "source_name", "capture_method"):
                    if key in source and source[key] is not None and not isinstance(source[key], str):
                        errors.append(f"metadata.source.{key} must be a string or null")
                if source.get("url") is not None and not _is_http_url(source["url"]):
                    errors.append("metadata.source.url must be an HTTP(S) URL")
                if "read_only" in source and not isinstance(source["read_only"], bool):
                    errors.append("metadata.source.read_only must be boolean")
                for key in ("notes", "capture_files"):
                    if key in source and (
                        not isinstance(source[key], list) or any(not isinstance(item, str) for item in source[key])
                    ):
                        errors.append(f"metadata.source.{key} must be an array of strings")
                if "thread_identity" in source and source["thread_identity"] is not None:
                    if not isinstance(source["thread_identity"], dict):
                        errors.append("metadata.source.thread_identity must be an object or null")
                if "selector_notes" in source and (
                    not isinstance(source["selector_notes"], list)
                    or any(not isinstance(note, str) for note in source["selector_notes"])
                ):
                    errors.append("metadata.source.selector_notes must be an array of strings")

    participants = archive.get("participants")
    if not isinstance(participants, list) or not participants:
        errors.append("participants must be a non-empty array")
        participant_ids: set[str] = set()
    else:
        participant_ids = set()
        for index, participant in enumerate(participants):
            if not isinstance(participant, dict):
                errors.append(f"participants[{index}] must be an object")
                continue
            participant_id = participant.get("id")
            if not isinstance(participant_id, str) or not participant_id.strip():
                errors.append(f"participants[{index}].id must be a non-empty string")
            elif participant_id in participant_ids:
                errors.append(f"participants[{index}].id duplicates {participant_id!r}")
            else:
                participant_ids.add(participant_id)
            if not isinstance(participant.get("display_name") or participant.get("username"), str):
                errors.append(f"participants[{index}] needs display_name or username as a string")
            for field in ("display_name", "username", "avatar_alt"):
                if field in participant and participant[field] is not None and not isinstance(participant[field], str):
                    errors.append(f"participants[{index}].{field} must be a string or null")
            if "avatar_path" in participant:
                _validate_local_reference(participant["avatar_path"], f"participants[{index}].avatar_path", errors)
            if participant.get("avatar_ref") is not None and not _is_http_url(participant["avatar_ref"]):
                errors.append(f"participants[{index}].avatar_ref must be an HTTP(S) URL")

    messages = archive.get("messages")
    if not isinstance(messages, list):
        errors.append("messages must be an array")
        messages = []
    seen_message_ids: set[str] = set()
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"messages[{index}] must be an object")
            continue
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id.strip():
            errors.append(f"messages[{index}].id must be a non-empty string")
        elif message_id in seen_message_ids:
            errors.append(f"messages[{index}].id duplicates {message_id!r}")
        else:
            seen_message_ids.add(message_id)
        author_id = message.get("author_id")
        if not isinstance(author_id, str) or not author_id.strip():
            errors.append(f"messages[{index}].author_id must be a non-empty string")
        elif participant_ids and author_id not in participant_ids:
            errors.append(f"messages[{index}].author_id {author_id!r} is not in participants")
        _validate_timestamp(message.get("timestamp"), f"messages[{index}].timestamp", errors)
        if not isinstance(message.get("content", ""), str):
            errors.append(f"messages[{index}].content must be a string")
        if message.get("content_kind", "visible_text") not in _CONTENT_KINDS:
            errors.append(f"messages[{index}].content_kind must be one of {sorted(_CONTENT_KINDS)}")
        if "grouped" in message and not isinstance(message["grouped"], bool):
            errors.append(f"messages[{index}].grouped must be boolean")
        for field in ("media", "source_refs"):
            if field in message and not isinstance(message[field], list):
                errors.append(f"messages[{index}].{field} must be an array")
        if isinstance(message.get("media"), list):
            for media_index, media in enumerate(message["media"]):
                _validate_media(media, f"messages[{index}].media[{media_index}]", errors)
        if isinstance(message.get("source_refs"), list):
            for ref_index, ref in enumerate(message["source_refs"]):
                _validate_source_ref(ref, f"messages[{index}].source_refs[{ref_index}]", errors)
        for field, states in (("saved_state", _SAVED_STATES), ("retention", _RETENTION_STATES)):
            if field in message and message[field] is not None:
                _validate_indicator(message[field], f"messages[{index}].{field}", states, errors)
        for field in ("reply_to", "message_link"):
            if field in message and message[field] is not None and not isinstance(message[field], str):
                errors.append(f"messages[{index}].{field} must be a string or null")
        if message.get("message_link") is not None and not _is_http_url(message["message_link"]):
            errors.append(f"messages[{index}].message_link must be an HTTP(S) URL")
        if message.get("edited_at") is not None:
            _validate_timestamp(message["edited_at"], f"messages[{index}].edited_at", errors)
        if "provenance" in message:
            _validate_provenance(message["provenance"], f"messages[{index}].provenance", errors)
    return errors


def _stable_identifier(value: str, fallback_index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"author-{slug or fallback_index + 1}"


def _message_digest(record: dict[str, Any], index: int) -> str:
    comparable = {
        "timestamp": _first(record, "timestamp", "Timestamp", "created_at", "createdAt", "Date", default=""),
        "author": _first(record, "author_id", "authorId", "author", "sender_id", "sender", default=""),
        "content": _first(record, "content", "text", "message", "visible_text", default=""),
        "media": _first(record, "media", "media_placeholders", "attachments", default=[]),
    }
    encoded = json.dumps(comparable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return f"local-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _raw_message_id(record: dict[str, Any], index: int) -> str | None:
    value = _first(record, "id", "ID", "message_id", "messageId", "Message ID", default=None)
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def _normalise_media(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        if _is_http_url(value):
            path_name = Path(urlparse(value).path).name or "media"
            return {
                "kind": _media_kind(path_name),
                "label": path_name,
                "source_url": value.strip(),
                "placeholder": "Media reference visible in the source; bytes were not captured.",
            }
        path = _normalise_local_reference(value)
        label = Path(value).name or "media"
        result: dict[str, Any] = {"kind": _media_kind(label), "label": label}
        if path:
            result["path"] = path
        else:
            result["placeholder"] = "Media placeholder; no local bytes were supplied."
        return result
    if not isinstance(value, dict):
        return {"kind": "unknown", "label": "Media", "placeholder": str(value)}
    raw_kind = _first(value, "kind", "type", "media_type", default=None)
    kind = str(raw_kind).lower().strip() if raw_kind else "unknown"
    if kind not in _MEDIA_KINDS:
        kind = _media_kind(_first(value, "name", "filename", "label", default="media"))
    label = _first(value, "label", "name", "filename", "alt", default=None)
    result = {"kind": kind, "label": _clean(label or kind.title())}
    path = _first(value, "path", "local_path", default=None)
    source_url = _first(value, "source_url", "url", "ref", "source_ref", default=None)
    if _normalise_local_reference(path):
        result["path"] = _normalise_local_reference(path)
    if _is_http_url(source_url):
        result["source_url"] = str(source_url).strip()
    placeholder = _first(value, "placeholder", "description", "note", default=None)
    if placeholder is not None and str(placeholder).strip():
        result["placeholder"] = _clean(placeholder)
    elif not result.get("path"):
        result["placeholder"] = "Media reference visible in the source; bytes were not captured."
    alt = _first(value, "alt", "alt_text", default=None)
    if alt is not None:
        result["alt"] = _clean(alt)
    size = _first(value, "size_bytes", "size", default=None)
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        result["size_bytes"] = size
    return result


def _media_kind(value: Any) -> str:
    extension = Path(str(value).split("?", 1)[0].split("#", 1)[0]).suffix.lower().lstrip(".")
    if extension in {"png", "jpg", "jpeg", "gif", "webp", "svg", "heic"}:
        return "image"
    if extension in {"mp4", "webm", "mov", "m4v"}:
        return "video"
    if extension in {"mp3", "wav", "ogg", "m4a"}:
        return "audio"
    if extension in {"webp", "tgs"}:
        return "sticker"
    return "unknown"


def _normalise_indicator(value: Any, kind: str) -> dict[str, Any] | None:
    if value is None:
        return None
    allowed = _SAVED_STATES if kind == "saved" else _RETENTION_STATES
    if isinstance(value, str):
        evidence = _clean(value)
        lower = evidence.casefold()
        if kind == "saved":
            state = "saved" if "save" in lower or "keep" in lower else "unsaved" if "unsave" in lower else "unknown"
        else:
            state = "view_once" if "view once" in lower or "one time" in lower else "expires" if any(word in lower for word in ("delete", "disappear", "expire")) else "kept_in_chat" if "keep" in lower else "unknown"
        return {"state": state if state in allowed else "unknown", "evidence": evidence, "visible": True}
    if isinstance(value, dict):
        raw_state = str(_first(value, "state", "status", default="unknown")).casefold().strip()
        aliases = {
            "keep": "saved" if kind == "saved" else "kept_in_chat",
            "saved_in_chat": "saved" if kind == "saved" else "kept_in_chat",
            "view-once": "view_once",
            "view once": "view_once",
            "deleted": "expires",
            "unknown": "unknown",
        }
        state = aliases.get(raw_state, raw_state)
        if state not in allowed:
            state = "unknown"
        result: dict[str, Any] = {
            "state": state,
            "visible": bool(value.get("visible", True)),
        }
        for key in ("evidence", "label"):
            if value.get(key) is not None and str(value[key]).strip():
                result[key] = _clean(value[key])
        return result
    return {"state": "unknown", "evidence": _clean(value), "visible": True}


def _normalise_source_ref(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        if not _is_http_url(value):
            return {"kind": "visible_reference", "label": _clean(value)} if _clean(value) else None
        return {"kind": "visible_link", "label": Path(urlparse(value).path).name or "Source link", "url": value.strip()}
    if not isinstance(value, dict):
        return None
    url = _first(value, "url", "source_url", "href", default=None)
    label = _first(value, "label", "title", "name", default=None)
    result = {
        "kind": _clean(_first(value, "kind", "type", default="visible_reference")) or "visible_reference",
        "label": _clean(label or (Path(urlparse(str(url)).path).name if _is_http_url(url) else "Source reference")),
    }
    if _is_http_url(url):
        result["url"] = str(url).strip()
    return result


def _normalise_transcript_participant(record: dict[str, Any], index: int) -> dict[str, Any]:
    participant_id = _first(record, "id", "user_id", "author_id", "sender_id", "userId", default=None)
    display_name = _first(record, "display_name", "displayName", "name", "label", default=None)
    username = _first(record, "username", "user_name", "handle", default=None)
    if participant_id is None:
        participant_id = _stable_identifier(str(display_name or username or "participant"), index)
    if display_name is None:
        display_name = username or str(participant_id)
    participant: dict[str, Any] = {"id": str(participant_id), "display_name": _clean(display_name)}
    if username is not None:
        participant["username"] = _clean(username)
    avatar = _first(record, "avatar_path", "avatar_file", "avatar", default=None)
    avatar_ref = _first(record, "avatar_ref", "avatar_url", default=None)
    if isinstance(avatar, dict):
        avatar = _first(avatar, "path", "local_path", "url", default=None)
    if _is_http_url(avatar):
        avatar_ref = avatar
    elif _normalise_local_reference(avatar):
        participant["avatar_path"] = _normalise_local_reference(avatar)
    if _is_http_url(avatar_ref):
        participant["avatar_ref"] = str(avatar_ref).strip()
    avatar_alt = _first(record, "avatar_alt", "avatarAlt", default=None)
    if avatar_alt is not None:
        participant["avatar_alt"] = _clean(avatar_alt)
    return participant


def _author_details(record: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    author_value = _first(record, "author", "Author", "sender", "user", default=_MISSING)
    author_object = author_value if isinstance(author_value, dict) else {}
    explicit_id = _first(record, "author_id", "authorId", "sender_id", "senderId", "user_id", "userId", default=_MISSING)
    if explicit_id is _MISSING:
        explicit_id = _first(author_object, "id", "user_id", "author_id", "sender_id", "userId", default=_MISSING)
    if explicit_id is not _MISSING and explicit_id is not None and str(explicit_id).strip():
        raw_id = str(explicit_id).strip()
        generated = False
    elif isinstance(author_value, str) and author_value.strip():
        raw_id = author_value.strip()
        generated = True
    elif author_object:
        author_label = _first(author_object, "display_name", "displayName", "name", "username", default=None)
        if author_label is None or not str(author_label).strip():
            raw_id = "unknown"
        else:
            raw_id = str(author_label).strip()
        generated = True
    else:
        raw_id = "unknown"
        generated = True
    details = {
        "id": raw_id,
        "display_name": _first(author_object, "display_name", "displayName", "name", default=None),
        "username": _first(author_object, "username", "user_name", "handle", default=None),
        "avatar_path": _first(author_object, "avatar_path", "avatar_file", "avatar_ref", "avatar_url", default=None),
        "avatar_alt": _first(author_object, "avatar_alt", "avatarAlt", default=None),
    }
    if details["display_name"] is None and details["username"] is None and isinstance(author_value, str):
        details["display_name"] = author_value.strip()
    return raw_id, generated, details


def _normalise_required_timestamp(value: Any, index: int) -> str:
    timestamp = normalise_timestamp(value)
    if timestamp is None or not _has_timestamp_timezone(value):
        raise ValueError(f"message {index} timestamp must be an ISO-8601 timestamp with a timezone")
    return timestamp


def _normalise_transcript_message(
    record: dict[str, Any],
    index: int,
    source_file: str,
    participant_aliases: dict[str, str],
    participants: list[dict[str, Any]],
    participant_by_id: dict[str, dict[str, Any]],
    default_source_url: str | None = None,
) -> dict[str, Any]:
    raw_id = _raw_message_id(record, index)
    id_generated = raw_id is None
    message_id = raw_id or _message_digest(record, index)
    timestamp = _normalise_required_timestamp(
        _first(record, "timestamp", "Timestamp", "created_at", "createdAt", "Date", default=None), index
    )
    author_key, generated_author, author_details = _author_details(record)
    resolved_author_id = participant_aliases.get(author_key) or participant_aliases.get(author_key.casefold())
    if resolved_author_id is None:
        resolved_author_id = _stable_identifier(author_key, index) if generated_author else author_key
        if resolved_author_id not in participant_by_id:
            details = {key: value for key, value in author_details.items() if value is not None}
            details["id"] = resolved_author_id
            participant = _normalise_transcript_participant(details, len(participants))
            participant_by_id[resolved_author_id] = participant
            participants.append(participant)
            for alias in (author_key, participant.get("id"), participant.get("username"), participant.get("display_name")):
                if isinstance(alias, str) and alias:
                    participant_aliases[alias] = resolved_author_id
                    participant_aliases[alias.casefold()] = resolved_author_id

    content_value = _first(record, "content", "Contents", "visible_text", "text", "message", "Message", default="")
    content = content_value if isinstance(content_value, str) else str(content_value)
    media_value = _first(record, "media", "media_placeholders", "attachments", default=[])
    if media_value is None:
        media_value = []
    elif not isinstance(media_value, list):
        media_value = [media_value]
    media = [_normalise_media(item) for item in media_value]
    explicit_kind = _first(record, "content_kind", "content_type", default=None)
    content_kind = str(explicit_kind).strip() if explicit_kind else "mixed" if content.strip() and media else "media_placeholder" if media else "visible_text" if content.strip() else "empty"
    if content_kind not in _CONTENT_KINDS:
        content_kind = "mixed" if content.strip() and media else "media_placeholder" if media else "visible_text" if content.strip() else "empty"
    message: dict[str, Any] = {
        "id": message_id,
        "author_id": resolved_author_id,
        "timestamp": timestamp,
        "content": content.strip(),
        "content_kind": content_kind,
        "media": media,
        "source_refs": [],
        "provenance": {
            "source_file": source_file,
            "record_index": index,
        },
    }
    if id_generated:
        message["provenance"]["id_generated"] = True
    source_id = _first(record, "source_id", "source_message_id", default=raw_id)
    if source_id is not None and str(source_id).strip():
        message["provenance"]["source_id"] = str(source_id).strip()
    source_url = _first(record, "source_url", "source_link", default=default_source_url)
    if _is_http_url(source_url):
        message["provenance"]["source_url"] = str(source_url).strip()
    for field, kind in (("saved_state", "saved"), ("saved", "saved"), ("retention", "retention"), ("retention_indicator", "retention")):
        if field in record:
            indicator = _normalise_indicator(record[field], kind)
            if indicator is not None:
                message["saved_state" if kind == "saved" else "retention"] = indicator
    refs_value = _first(record, "source_refs", "source_references", "links", default=[])
    if refs_value is None:
        refs_value = []
    elif not isinstance(refs_value, list):
        refs_value = [refs_value]
    message["source_refs"] = [ref for item in refs_value if (ref := _normalise_source_ref(item)) is not None]
    for field in ("reply_to", "message_link"):
        value = record.get(field)
        if value is not None and str(value).strip():
            message[field] = str(value).strip()
    edited_at = _first(record, "edited_at", "editedAt", "edited", default=None)
    if edited_at is not None:
        message["edited_at"] = _normalise_required_timestamp(edited_at, index)
    if isinstance(record.get("grouped"), bool):
        message["grouped"] = record["grouped"]
    notes = record.get("provenance", {}).get("notes") if isinstance(record.get("provenance"), dict) else None
    if isinstance(notes, list):
        message["provenance"]["notes"] = [str(note) for note in notes if isinstance(note, str)]
    return message


def _transcript_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records = value
    elif isinstance(value, dict):
        records_value = value.get("messages")
        if isinstance(records_value, list):
            records = records_value
        else:
            nested = value.get("transcript") or value.get("conversation") or value.get("data")
            if isinstance(nested, dict) and isinstance(nested.get("messages"), list):
                records = nested["messages"]
            elif any(key in value for key in ("id", "message_id", "timestamp", "created_at")):
                records = [value]
            else:
                raise ValueError("Transcript JSON must contain a messages array")
    else:
        raise ValueError("Transcript JSON must be an object or an array")
    invalid = [index for index, record in enumerate(records) if not isinstance(record, dict)]
    if invalid:
        raise ValueError(f"Transcript messages must be objects; invalid indexes: {invalid}")
    return records


def _transcript_metadata(value: Any) -> dict[str, Any]:
    return value.get("metadata", {}) if isinstance(value, dict) and isinstance(value.get("metadata"), dict) else {}


def _capture_range_summary(source_file: str, records: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    capture_range = metadata.get("capture_range") if isinstance(metadata.get("capture_range"), dict) else {}
    ordered = sorted(
        records,
        key=lambda record: (
            str(_first(record, "timestamp", "Timestamp", "created_at", "createdAt", "Date", default="")),
            str(_raw_message_id(record, 0) or _message_digest(record, 0)),
        ),
    )
    first = ordered[0] if ordered else {}
    last = ordered[-1] if ordered else {}
    first_id = _raw_message_id(first, 0) or (_message_digest(first, 0) if first else None)
    last_id = _raw_message_id(last, 0) or (_message_digest(last, 0) if last else None)
    first_timestamp = _first(first, "timestamp", "Timestamp", "created_at", "createdAt", "Date", default=None)
    last_timestamp = _first(last, "timestamp", "Timestamp", "created_at", "createdAt", "Date", default=None)
    ids = {
        _raw_message_id(record, index) or _message_digest(record, index)
        for index, record in enumerate(records)
    }
    return {
        "source_file": source_file,
        "message_count": len(records),
        "rendered_count": capture_range.get("rendered_count", len(records)),
        "message_ids": ids,
        "oldest_message_id": capture_range.get("oldest_message_id") or first_id,
        "oldest_timestamp": capture_range.get("oldest_timestamp") or first_timestamp,
        "newest_message_id": capture_range.get("newest_message_id") or last_id,
        "newest_timestamp": capture_range.get("newest_timestamp") or last_timestamp,
        "at_start": bool(capture_range.get("at_start")),
        "at_end": bool(capture_range.get("at_end")),
        "has_capture_range": bool(capture_range),
        "selector": capture_range.get("selector"),
        "scroll_top": capture_range.get("scroll_top"),
        "scroll_height": capture_range.get("scroll_height"),
        "viewport_height": capture_range.get("viewport_height"),
    }


def _coverage_report(
    ranges: list[dict[str, Any]],
    duplicate_count: int = 0,
    conflict_count: int = 0,
    reached_start: bool = False,
    reached_end: bool = False,
) -> dict[str, Any]:
    ordered = sorted(ranges, key=lambda item: (str(item.get("oldest_timestamp") or ""), str(item.get("source_file") or "")))
    unlinked_ranges: list[str] = []
    public_ranges: list[dict[str, Any]] = []
    previous_ids: set[str] | None = None
    for item in ordered:
        ids = item.get("message_ids") if isinstance(item.get("message_ids"), set) else set()
        overlap = len(previous_ids & ids) if previous_ids is not None else 0
        if previous_ids is not None and overlap == 0:
            unlinked_ranges.append(f"{public_ranges[-1]['source_file']} -> {item['source_file']}")
        public_ranges.append(
            {
                key: item.get(key)
                for key in (
                    "source_file",
                    "message_count",
                    "rendered_count",
                    "oldest_message_id",
                    "oldest_timestamp",
                    "newest_message_id",
                    "newest_timestamp",
                    "at_start",
                    "at_end",
                    "has_capture_range",
                    "selector",
                    "scroll_top",
                    "scroll_height",
                    "viewport_height",
                )
            }
            | {"overlap_with_previous": overlap}
        )
        previous_ids = ids
    first = ordered[0] if ordered else {}
    last = ordered[-1] if ordered else {}
    start_confirmed = bool(reached_start or first.get("at_start"))
    end_confirmed = bool(reached_end or last.get("at_end"))
    all_ranges_tagged = bool(ordered) and all(
        item.get("has_capture_range") and item.get("oldest_message_id") and item.get("newest_message_id")
        for item in ordered
    )
    linked = all_ranges_tagged and not unlinked_ranges
    if start_confirmed and end_confirmed and linked and conflict_count == 0:
        status = "verified"
    elif ordered or start_confirmed or end_confirmed:
        status = "partial"
    else:
        status = "unverified"
    notes: list[str] = []
    if not start_confirmed:
        notes.append("The oldest boundary has not been confirmed; capture a range at the top of the open chat.")
    if not end_confirmed:
        notes.append("The newest boundary has not been confirmed; capture a range at the bottom of the open chat.")
    if unlinked_ranges:
        notes.append("Adjacent capture ranges do not overlap; recapture those transitions with at least one shared message.")
    if conflict_count:
        notes.append("Overlapping ranges contain conflicting records; review the source captures before treating coverage as complete.")
    notes.append("Range verification only describes messages rendered in the user-controlled DOM; unseen or deleted messages remain unknown.")
    if conflict_count:
        next_action = "Review the conflicting overlap records before rebuilding the archive."
    elif unlinked_ranges:
        next_action = "Recapture each gap with at least one message shared by adjacent ranges, then merge again."
    elif not start_confirmed and not end_confirmed:
        next_action = "Return to the open chat, reach both oldest and newest boundaries, and capture overlapping ranges at each end."
    elif not start_confirmed:
        next_action = "Return to the open chat, reach the oldest visible boundary, then capture an overlapping range."
    elif not end_confirmed:
        next_action = "Return to the open chat, reach the newest visible boundary, then capture an overlapping range."
    elif not linked:
        next_action = "Merge overlapping ranges so every transition shares at least one stable message ID."
    else:
        next_action = "No further capture step is required for the observed rendered range."
    return {
        "version": 1,
        "status": status,
        "complete": status == "verified",
        "range_count": len(ordered),
        "unique_message_count": len(set().union(*(item.get("message_ids", set()) for item in ordered))) if ordered else 0,
        "duplicate_message_count": duplicate_count,
        "conflict_count": conflict_count,
        "start_confirmed": start_confirmed,
        "end_confirmed": end_confirmed,
        "ranges_linked": linked,
        "unlinked_ranges": unlinked_ranges,
        "ranges": public_ranges,
        "notes": notes,
        "next_action": next_action,
    }


def _message_fingerprint(record: dict[str, Any]) -> str:
    comparable = {key: value for key, value in record.items() if key not in {"grouped", "provenance"}}
    return json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def merge_transcripts(
    input_paths: list[Path],
    output_path: Path,
    reached_start: bool = False,
    reached_end: bool = False,
) -> dict[str, Any]:
    """Merge overlapping user-captured ranges without performing any browser work."""

    if not input_paths:
        raise ValueError("At least one transcript capture is required")
    resolved_inputs = [path.resolve() for path in input_paths]
    output_path = output_path.resolve()
    if any(path.parent != output_path.parent for path in resolved_inputs):
        raise ValueError("merge-captures requires captures and output in the same directory")
    if len({str(path) for path in resolved_inputs}) != len(resolved_inputs):
        raise ValueError("merge-captures received the same capture more than once")

    first_value = _load_json_value(resolved_inputs[0])
    first_metadata = _transcript_metadata(first_value)
    merged_metadata = dict(first_metadata)
    merged_source = dict(first_metadata.get("source") or {})
    merged_source.update(
        {
            "label": "Merged Snapchat visible chat captures",
            "type": "snapchat_visible_dom",
            "capture_method": "foreground_visible_dom",
            "read_only": True,
            "capture_files": [path.name for path in resolved_inputs],
        }
    )
    merged_notes = list(merged_source.get("notes") or [])
    note = "Merged from overlapping, user-controlled visible Snapchat chat ranges."
    if note not in merged_notes:
        merged_notes.append(note)
    merged_source["notes"] = merged_notes
    merged_metadata["source"] = merged_source
    merged_metadata.pop("capture_range", None)

    participants_by_id: dict[str, dict[str, Any]] = {}
    messages_by_id: dict[str, dict[str, Any]] = {}
    thread_ids: set[str] = set()
    source_urls: set[str] = set()
    ranges: list[dict[str, Any]] = []
    duplicate_count = 0
    conflict_count = 0

    for capture_path in resolved_inputs:
        value = _load_json_value(capture_path)
        records = _transcript_records(value)
        metadata = _transcript_metadata(value)
        ranges.append(_capture_range_summary(capture_path.name, records, metadata))
        thread_id = metadata.get("thread_id") or metadata.get("channel_id")
        if thread_id is not None:
            thread_ids.add(str(thread_id))
        source = metadata.get("source") if isinstance(metadata.get("source"), dict) else {}
        source_url = source.get("url")
        if isinstance(source_url, str) and source_url.strip():
            parsed = urlparse(source_url)
            source_urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
        raw_participants = value.get("participants", []) if isinstance(value, dict) else []
        if isinstance(raw_participants, list):
            for participant in raw_participants:
                if not isinstance(participant, dict):
                    continue
                participant_id = str(
                    participant.get("id") or participant.get("username") or participant.get("display_name") or ""
                ).strip()
                if not participant_id:
                    continue
                existing = participants_by_id.setdefault(participant_id, {})
                for key, item in participant.items():
                    if item not in (None, "") and existing.get(key) in (None, ""):
                        existing[key] = item
        for index, record in enumerate(records):
            message_id = _raw_message_id(record, index) or _message_digest(record, index)
            existing = messages_by_id.get(message_id)
            if existing is None:
                messages_by_id[message_id] = dict(record)
                continue
            duplicate_count += 1
            if _message_fingerprint(existing) != _message_fingerprint(record):
                conflict_count += 1
            if existing.get("grouped") is True and record.get("grouped") is False:
                existing["grouped"] = False

    if len(thread_ids) > 1:
        raise ValueError(f"Capture files contain multiple thread IDs: {sorted(thread_ids)}")
    if len(source_urls) > 1 and not thread_ids:
        raise ValueError("Capture files point to multiple chat URLs without a shared thread ID")
    if thread_ids:
        merged_metadata["thread_id"] = next(iter(thread_ids))
    coverage = _coverage_report(
        ranges,
        duplicate_count=duplicate_count,
        conflict_count=conflict_count,
        reached_start=reached_start,
        reached_end=reached_end,
    )
    merged_metadata["coverage"] = coverage
    merged_messages = list(messages_by_id.values())
    merged_messages.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")))
    merged = {
        "schema_version": SCHEMA_VERSION,
        "metadata": merged_metadata,
        "participants": list(participants_by_id.values()),
        "messages": merged_messages,
    }
    write_json(output_path, merged)
    return {
        "messages": len(merged_messages),
        "participants": len(merged["participants"]),
        "duplicates": duplicate_count,
        "conflicts": conflict_count,
        "coverage": coverage,
    }


def verify_transcript_coverage(input_path: Path) -> dict[str, Any]:
    archive = _load_json_value(input_path.resolve())
    metadata = _transcript_metadata(archive)
    coverage = metadata.get("coverage")
    if isinstance(coverage, dict):
        return coverage
    capture_range = metadata.get("capture_range")
    records = _transcript_records(archive)
    if isinstance(capture_range, dict):
        oldest = capture_range.get("oldest_message_id")
        newest = capture_range.get("newest_message_id")
        return _coverage_report(
            [
                {
                    **_capture_range_summary(input_path.name, records, metadata),
                    "oldest_message_id": oldest or _capture_range_summary(input_path.name, records, metadata).get("oldest_message_id"),
                    "newest_message_id": newest or _capture_range_summary(input_path.name, records, metadata).get("newest_message_id"),
                }
            ]
        )
    return {
        "version": 1,
        "status": "unverified",
        "complete": False,
        "range_count": 0,
        "unique_message_count": len(records),
        "duplicate_message_count": 0,
        "conflict_count": 0,
        "start_confirmed": False,
        "end_confirmed": False,
        "ranges_linked": False,
        "unlinked_ranges": [],
        "ranges": [],
        "notes": ["This transcript has not been produced by the overlap-aware range merge workflow."],
        "next_action": "Capture overlapping ranges at the oldest and newest boundaries, then merge them before treating the archive as complete.",
    }


def _source_notes(source_input: dict[str, Any]) -> list[str]:
    notes = [
        "Imported from a user-supplied transcript or visible Snapchat capture JSON file.",
        "No login automation, credential inspection, private API, message sending, crawler, or remote media download was used.",
        "Per-message source_file and record_index preserve the input record location.",
    ]
    provided = source_input.get("notes")
    if isinstance(provided, list):
        notes.extend(str(note) for note in provided if isinstance(note, str) and note.strip())
    return list(dict.fromkeys(notes))


def import_transcript(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Normalize an explicitly supplied transcript or visible capture JSON file."""

    input_path = input_path.resolve()
    if not input_path.is_file():
        raise ValueError(f"Transcript file does not exist: {input_path}")
    value = _load_json_value(input_path)
    records = _transcript_records(value)
    input_metadata = _transcript_metadata(value)
    raw_participants = value.get("participants", []) if isinstance(value, dict) else []
    if not isinstance(raw_participants, list):
        raise ValueError("Transcript participants must be an array when provided")
    participants: list[dict[str, Any]] = []
    participant_by_id: dict[str, dict[str, Any]] = {}
    participant_aliases: dict[str, str] = {}
    for index, participant_record in enumerate(raw_participants):
        if not isinstance(participant_record, dict):
            raise ValueError(f"Transcript participants[{index}] must be an object")
        participant = _normalise_transcript_participant(participant_record, index)
        if participant["id"] in participant_by_id:
            raise ValueError(f"Transcript participants[{index}] duplicates {participant['id']!r}")
        participant_by_id[participant["id"]] = participant
        participants.append(participant)
        for alias in (participant.get("id"), participant.get("username"), participant.get("display_name")):
            if isinstance(alias, str) and alias:
                participant_aliases[alias] = participant["id"]
                participant_aliases[alias.casefold()] = participant["id"]

    source_input = input_metadata.get("source") if isinstance(input_metadata.get("source"), dict) else {}
    source_url = source_input.get("url") if _is_http_url(source_input.get("url")) else None
    messages = [
        _normalise_transcript_message(
            record,
            index,
            input_path.name,
            participant_aliases,
            participants,
            participant_by_id,
            default_source_url=source_url,
        )
        for index, record in enumerate(records)
    ]
    messages.sort(key=lambda item: (item["timestamp"], item["id"]))
    metadata: dict[str, Any] = {
        "kind": input_metadata.get("kind") or (value.get("kind") if isinstance(value, dict) else None) or "snapchat_chat",
        "title": input_metadata.get("title") or (value.get("title") if isinstance(value, dict) else None) or "Imported Snapchat conversation",
        "thread_id": input_metadata.get("thread_id") or input_metadata.get("channel_id") or (value.get("thread_id") if isinstance(value, dict) else None),
        "captured_at": input_metadata.get("captured_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "display_timezone": input_metadata.get("display_timezone") or "UTC",
        "source": {
            "type": source_input.get("type") or "user_supplied_transcript",
            "label": source_input.get("label") or "User-supplied Snapchat transcript",
            "source_name": input_path.name,
            "capture_method": source_input.get("capture_method") or "supplied_json",
            "read_only": bool(source_input.get("read_only", True)),
            "notes": _source_notes(source_input),
        },
        "thread_identity": input_metadata.get("thread_identity") or source_input.get("thread_identity"),
    }
    if source_url:
        metadata["source"]["url"] = source_url
    for key in ("selector_notes",):
        value_for_key = input_metadata.get(key) or source_input.get(key)
        if isinstance(value_for_key, list):
            metadata[key] = [str(note) for note in value_for_key if isinstance(note, str)]
            metadata["source"][key] = metadata[key]
    for field in ("capture_range", "coverage"):
        if isinstance(input_metadata.get(field), dict):
            metadata[field] = input_metadata[field]
    if input_metadata.get("synthetic") is True or (isinstance(value, dict) and value.get("synthetic") is True):
        metadata["synthetic"] = True
    if metadata.get("thread_identity") is None:
        metadata.pop("thread_identity", None)
    archive = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "participants": participants,
        "messages": messages,
    }
    errors = validate_archive(archive)
    if errors:
        raise ValueError("Imported transcript did not produce a valid archive:\n- " + "\n- ".join(errors))
    write_json(output_path, archive)
    return archive


def _asset_references(archive: dict[str, Any]) -> set[str]:
    references: set[str] = set()

    def collect(value: Any) -> None:
        reference = _normalise_local_reference(value)
        if reference:
            references.add(reference)

    for participant in archive.get("participants", []) if isinstance(archive.get("participants"), list) else []:
        if isinstance(participant, dict):
            collect(participant.get("avatar_path"))
    for message in archive.get("messages", []) if isinstance(archive.get("messages"), list) else []:
        if not isinstance(message, dict):
            continue
        for media in message.get("media", []) if isinstance(message.get("media"), list) else []:
            if isinstance(media, dict):
                collect(media.get("path"))
    return references


def _copy_referenced_assets(archive: dict[str, Any], source_root: Path, output_root: Path) -> list[str]:
    missing: list[str] = []
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    for reference in sorted(_asset_references(archive)):
        source = (source_root / reference).resolve()
        try:
            source.relative_to(source_root)
        except ValueError:
            missing.append(reference)
            continue
        destination = output_root / reference
        if not source.is_file():
            missing.append(reference)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return missing


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_manifest(archive: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    references = {"archive.json", "app.js", "index.html"} | _asset_references(archive)
    files: list[dict[str, Any]] = []
    for reference in sorted(references):
        path = output_dir / reference
        if path.is_file():
            files.append({"path": reference, "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {"manifest_version": 1, "archive_schema_version": archive["schema_version"], "files": files}


def verify_build(output_dir: Path) -> list[str]:
    output_dir = output_dir.resolve()
    errors: list[str] = []
    if not output_dir.is_dir():
        return [f"viewer directory does not exist: {output_dir}"]
    manifest_path = output_dir / "manifest.json"
    manifest_paths: set[str] = set()
    if not manifest_path.is_file():
        errors.append("manifest.json is missing")
        manifest: dict[str, Any] = {}
    else:
        try:
            manifest_value = load_json(manifest_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            manifest_value = {}
            errors.append(f"manifest.json could not be read: {error}")
        manifest = manifest_value if isinstance(manifest_value, dict) else {}
        if not isinstance(manifest_value, dict):
            errors.append("manifest.json must be a JSON object")
    if manifest:
        if manifest.get("manifest_version") != 1:
            errors.append("manifest_version must be 1")
        if manifest.get("archive_schema_version") != SCHEMA_VERSION:
            errors.append(f"manifest archive_schema_version must be {SCHEMA_VERSION}")
        entries = manifest.get("files")
        if not isinstance(entries, list):
            errors.append("manifest.files must be an array")
            entries = []
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"manifest.files[{index}] must be an object")
                continue
            reference = entry.get("path")
            if not isinstance(reference, str) or _normalise_local_reference(reference) != reference:
                errors.append(f"manifest.files[{index}].path must be a safe relative path")
                continue
            if reference in seen:
                errors.append(f"manifest.files[{index}].path duplicates {reference!r}")
                continue
            seen.add(reference)
            manifest_paths.add(reference)
            path = (output_dir / reference).resolve()
            try:
                path.relative_to(output_dir)
            except ValueError:
                errors.append(f"manifest.files[{index}].path escapes the viewer directory")
                continue
            if not path.is_file():
                errors.append(f"missing generated file: {reference}")
                continue
            size = entry.get("size_bytes")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                errors.append(f"manifest.files[{index}].size_bytes must be a non-negative integer")
            elif path.stat().st_size != size:
                errors.append(f"size mismatch: {reference}")
            expected_hash = entry.get("sha256")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                errors.append(f"manifest.files[{index}].sha256 must be a SHA-256 hex digest")
            elif _sha256(path) != expected_hash:
                errors.append(f"hash mismatch: {reference}")
        for required in ("archive.json", "app.js", "index.html"):
            if required not in seen:
                errors.append(f"manifest is missing required file: {required}")
    archive_path = output_dir / "archive.json"
    archive: dict[str, Any] | None = None
    if not archive_path.is_file():
        errors.append("archive.json is missing")
    else:
        try:
            archive = load_json(archive_path)
            errors.extend(f"archive: {error}" for error in validate_archive(archive))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            errors.append(f"archive.json could not be read: {error}")
    if archive is not None:
        expected_files = {"archive.json", "app.js", "index.html"} | _asset_references(archive)
        errors.extend(f"manifest is missing expected file: {reference}" for reference in sorted(expected_files - manifest_paths))
        errors.extend(f"missing referenced local asset: {reference}" for reference in sorted(_asset_references(archive)) if not (output_dir / reference).is_file())
    for required in ("index.html", "app.js"):
        if not (output_dir / required).is_file():
            errors.append(f"{required} is missing")
    return errors


def _template_path() -> Path:
    package_template = Path(__file__).resolve().parent / "viewer" / "template.html"
    source_template = Path(__file__).resolve().parents[2] / "viewer" / "template.html"
    installed_template = Path(sysconfig.get_path("data")) / "viewer" / "template.html"
    for candidate in (package_template, source_template, installed_template):
        if candidate.is_file():
            return candidate
    return source_template


def build_archive(input_path: Path, output_dir: Path, template_path: Path | None = None) -> list[str]:
    archive = load_json(input_path)
    errors = validate_archive(archive)
    if errors:
        raise ValueError("Archive validation failed:\n- " + "\n- ".join(errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "archive.json", archive)
    missing = _copy_referenced_assets(archive, input_path.parent, output_dir)
    template = template_path or _template_path()
    if not template.is_file():
        raise FileNotFoundError(f"Viewer template not found: {template}")
    template_text = template.read_text(encoding="utf-8")
    script_open = "  <script data-catchthat-app>\n"
    script_start = template_text.rfind(script_open)
    script_end = template_text.rfind("\n  </script>", script_start)
    if script_start == -1 or script_end == -1:
        raise ValueError("Viewer template is missing its executable script block")
    app_script = template_text[script_start + len(script_open) : script_end]
    template_text = template_text[:script_start] + '  <script src="app.js" defer></script>' + template_text[script_end + len("\n  </script>") :]
    payload = json.dumps(archive, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    (output_dir / "app.js").write_text(
        "window.__ARCHIVE_DATA__ = " + payload + ";\nwindow.__CATCHTHAT_BUILD__ = {manifest: 'manifest.json'};\n\n" + app_script + "\n",
        encoding="utf-8",
        newline="\n",
    )
    title = html.escape(str(archive["metadata"]["title"]), quote=True)
    template_text = template_text.replace("{{ARCHIVE_TITLE}}", title)
    (output_dir / "index.html").write_text(template_text, encoding="utf-8", newline="\n")
    write_json(output_dir / "manifest.json", _build_manifest(archive, output_dir))
    return missing


def _display_name_map(archive: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for participant in archive.get("participants", []) if isinstance(archive.get("participants"), list) else []:
        if isinstance(participant, dict) and isinstance(participant.get("id"), str):
            result[participant["id"]] = str(participant.get("display_name") or participant.get("username") or participant["id"])
    return result


def render_text(archive: dict[str, Any], timezone_name: str | None = None) -> str:
    names = _display_name_map(archive)
    display_timezone = timezone_name or str(archive.get("metadata", {}).get("display_timezone") or "UTC")
    try:
        zone = ZoneInfo(display_timezone)
    except Exception:
        zone = timezone.utc
    lines: list[str] = []
    for message in archive.get("messages", []) if isinstance(archive.get("messages"), list) else []:
        timestamp = parse_timestamp(message.get("timestamp"))
        local_time = timestamp.astimezone(zone).strftime("%Y-%m-%d %H:%M") if timestamp else str(message.get("timestamp") or "")
        text = str(message.get("content") or "").strip()
        media = message.get("media") if isinstance(message.get("media"), list) else []
        if media:
            labels = ", ".join(str(item.get("label") or item.get("kind") or "media") for item in media if isinstance(item, dict))
            text = f"{text} [{labels}]".strip()
        if not text:
            text = "[No visible text]"
        indicator_parts: list[str] = []
        for field in ("saved_state", "retention"):
            indicator = message.get(field)
            if isinstance(indicator, dict) and indicator.get("state") not in {None, "unknown"}:
                indicator_parts.append(str(indicator["state"]))
        suffix = f" ({', '.join(indicator_parts)})" if indicator_parts else ""
        lines.append(f"{names.get(message.get('author_id'), message.get('author_id', 'Unknown'))}: {text} [{local_time}]{suffix}")
    return "\n".join(lines)
