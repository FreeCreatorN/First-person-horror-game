"""Strict offline scene/native verification for explicit Hotel package copies.

No Unreal import, filesystem writes or work at import time. Package mappings
are applied once to complete package/object path tokens, never to a basename.
Actor labels, internal names, dictionary keys and ordinary identity fields are
preserved. Every scene field, including physical light properties, is checked.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re


EXPECTED_ACTOR_COUNT = 7986
SNAPSHOT_FIELDS = frozenset({
    "actor_count", "actors", "exact_scene_components", "lights",
    "full_light_properties", "actor_properties", "full_existing_actor_native",
})
IDENTITY_FIELDS = frozenset({
    "name", "label", "actor_label", "component_name", "root_name",
    "parent_name", "folder", "folder_path", "tags", "component_tags", "socket",
})
_PACKAGE = re.compile(r"^/[\w]+/(?:[\w-]+/)*[\w-]+$", re.UNICODE)
_NATIVE_IDENTITY_LINE = re.compile(
    r"^\s*(?:ActorLabel|FolderPath|Tags(?:\(\d+\))?|ComponentTags(?:\(\d+\))?)\s*="
)
_ORIGINAL_WORLD = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
_PRIVATE_WORLD_ROOT = "/Game/CodexGenerated/Hotel/Maps/"
_QUALIFIED_SHORT_WORLD_OBJECT = re.compile(
    r"(?<![\w/\\:])(?P<class>/[\w]+/(?:[\w-]+/)*[\w-]+\.[\w-]+)'"
    r"(?P<world>[\w-]+):(?P<scene>PersistentLevel(?:\.[^\x00-\x20\"'<>(),;{}\[\]\\=]+)?)'",
    re.UNICODE,
)


class SceneVerificationError(AssertionError):
    """A fail-closed comparison failure with JSON-safe first-difference evidence."""

    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def _mapping_items(mapping):
    if not isinstance(mapping, Mapping):
        raise TypeError("mapping must be a package-name to package-name mapping")
    items, seen = [], set()
    for source, destination in mapping.items():
        if not isinstance(source, str) or not isinstance(destination, str):
            raise TypeError("package mapping keys and values must be strings")
        if not _PACKAGE.fullmatch(source) or not _PACKAGE.fullmatch(destination):
            raise ValueError("Only complete long package names are accepted: " + repr((source, destination)))
        if source.casefold() in seen:
            raise ValueError("Case-insensitive duplicate source package: " + source)
        seen.add(source.casefold())
        items.append((source, destination))
    return tuple(sorted(items))


@lru_cache(maxsize=16)
def _rules(items):
    package_rules, object_rules = {}, {}
    roots = set()
    for source, destination in items:
        source_name, destination_name = source.rsplit("/", 1)[1], destination.rsplit("/", 1)[1]
        package_rules[source] = destination
        roots.add(source.split("/", 2)[1])
        for source_object, destination_object in (
            (source_name, destination_name),
            (source_name + "_C", destination_name + "_C"),
            ("Default__" + source_name + "_C", "Default__" + destination_name + "_C"),
        ):
            object_rules[source + "." + source_object] = destination + "." + destination_object
    # One simultaneous pass avoids transitive A->B->C rewriting. Parse the full
    # top-level object token for constant-time lookup, including large mappings.
    if roots:
        token_pattern = re.compile(
            r"(?<![\w/\\:])/(?:" + "|".join(re.escape(root) for root in sorted(roots))
            + r")/[^\x00-\x20\"'<>(),;{}\[\]\\=]+", re.UNICODE
        )
    else:
        token_pattern = re.compile(r"(?!x)x")
    return package_rules, object_rules, token_pattern


def _rewrite_token(token, rules):
    package_rules, object_rules, _ = rules
    first_dot = token.find(".")
    if first_dot >= 0:
        boundaries = [offset for offset in (token.find(":", first_dot + 1), token.find(".", first_dot + 1)) if offset >= 0]
        end = min(boundaries) if boundaries else len(token)
        source = token[:end]
        destination = object_rules.get(source)
        if destination is not None:
            return destination + token[end:]
    return package_rules.get(token, token)


def _rewrite_string(value, rules):
    return rules[2].sub(lambda match: _rewrite_token(match.group(0), rules), value)


@lru_cache(maxsize=16)
def _short_world_rules(items):
    """Only the approved original-world/private-staging-world relationship.

    A generic BP/mesh/package mapping never establishes that its basename is a
    world name. Short names are allowed only inside a class-qualified object
    reference rooted at PersistentLevel, not in names, labels or arbitrary text.
    """
    result = {}
    for source, destination in items:
        if source == _ORIGINAL_WORLD:
            other = destination
        elif destination == _ORIGINAL_WORLD:
            other = source
        else:
            continue
        if other != _ORIGINAL_WORLD and not (
            other.startswith(_PRIVATE_WORLD_ROOT) and other.rsplit("/", 1)[1].startswith("L_")
        ):
            continue
        source_name, destination_name = source.rsplit("/", 1)[1], destination.rsplit("/", 1)[1]
        if source_name in result and result[source_name] != destination_name:
            raise ValueError("Ambiguous approved short world name: " + source_name)
        result[source_name] = destination_name
    return result


def _rewrite_qualified_short_worlds(text, world_rules):
    def replace(match):
        destination = world_rules.get(match.group("world"))
        if destination is None:
            return match.group(0)
        return match.group("class") + "'" + destination + ":" + match.group("scene") + "'"
    return _QUALIFIED_SHORT_WORLD_OBJECT.sub(replace, text)


def _normalize(value, rules):
    if isinstance(value, str):
        return _rewrite_string(value, rules)
    if isinstance(value, list):
        return [_normalize(item, rules) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize(item, rules) for item in value)
    if isinstance(value, dict):
        # Native JSON may represent a TopLevelAssetPath as a structured
        # package_name + asset_name pair. Treat the pair as a complete path;
        # never replace an isolated asset_name/basename by itself.
        result = {
            key: deepcopy(item) if key in IDENTITY_FIELDS else _normalize(item, rules)
            for key, item in value.items()
        }
        if value.get("struct") == "TopLevelAssetPath" and isinstance(value.get("fields"), dict):
            fields = value["fields"]
            package, asset = fields.get("package_name"), fields.get("asset_name")
            if isinstance(package, str) and isinstance(asset, str):
                combined = package + "." + asset
                patched = _rewrite_token(combined, rules)
                if patched != combined:
                    new_package, new_asset = patched.split(".", 1)
                    result["fields"]["package_name"] = new_package
                    result["fields"]["asset_name"] = new_asset
        return result
    return value


def normalize_asset_paths(value, mapping):
    """Return a new JSON-like value with only exact mapped object paths changed.

    Dictionary keys and identity values stay verbatim. UObject paths, generated
    classes, CDO paths and world/owned subobject path prefixes are supported.
    Case changes, pointer-address scrubbing and numeric tolerances are excluded.
    """
    return _normalize(value, _rules(_mapping_items(mapping)))


def normalize_native_text(text, mapping):
    """Normalize complete path tokens in native exports; retain every other byte.

    ExportPath/Archetype/class references can change. Name=, labels, tags and
    folder identities are not renamed, and line endings/whitespace stay exact.
    """
    if not isinstance(text, str):
        raise TypeError("native text must be a decoded string")
    items = _mapping_items(mapping)
    rules, short_worlds = _rules(items), _short_world_rules(items)
    return "".join(
        line if _NATIVE_IDENTITY_LINE.match(line) else
        _rewrite_qualified_short_worlds(_rewrite_string(line, rules), short_worlds)
        for line in text.splitlines(keepends=True)
    )


def read_native_text(path):
    """Read strict UTF-8 or UTF-16 native text, retaining original line endings."""
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    # ObjectExporter normally writes a BOM; also accept explicit UTF-16 exports
    # without one, using the initial ASCII 'Begin Object' region to detect order.
    sample = raw[:128]
    if len(sample) >= 8:
        if sample[1::2].count(0) > len(sample) // 8:
            return raw.decode("utf-16-le")
        if sample[0::2].count(0) > len(sample) // 8:
            return raw.decode("utf-16-be")
    return raw.decode("utf-8-sig")


def _text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _first_difference(expected, current, path="$" ):
    if type(expected) is not type(current):
        return dict(path=path, kind="type", expected_type=type(expected).__name__,
                    actual_type=type(current).__name__)
    if isinstance(expected, dict):
        if set(expected) != set(current):
            return dict(path=path, kind="dictionary_keys",
                        missing_keys=sorted(set(expected) - set(current)),
                        unexpected_keys=sorted(set(current) - set(expected)))
        for key in sorted(expected):
            difference = _first_difference(expected[key], current[key], path + "[" + repr(key) + "]")
            if difference:
                return difference
    elif isinstance(expected, (list, tuple)):
        if len(expected) != len(current):
            return dict(path=path, kind="length", expected=len(expected), actual=len(current))
        for index, (left, right) in enumerate(zip(expected, current)):
            difference = _first_difference(left, right, path + "[" + str(index) + "]")
            if difference:
                return difference
    elif expected != current:
        return dict(path=path, kind="value", expected=expected, actual=current)
    return None


def _native_difference(expected, current):
    left, right = expected.splitlines(), current.splitlines()
    for index in range(max(len(left), len(right))):
        expected_line = left[index] if index < len(left) else None
        current_line = right[index] if index < len(right) else None
        if expected_line != current_line:
            return dict(line=index + 1, expected_line=expected_line, actual_line=current_line)
    # splitlines hides CRLF/LF and final-newline differences, but they are not
    # permitted. Report a character offset when visible lines otherwise match.
    for index in range(min(len(expected), len(current))):
        if expected[index] != current[index]:
            return dict(character_offset=index, expected_fragment=repr(expected[max(0,index-60):index+60]),
                        actual_fragment=repr(current[max(0,index-60):index+60]))
    return dict(kind="trailing_text_or_line_endings", expected_characters=len(expected),
                actual_characters=len(current))


def compare_scene(expected, current, mapping):
    """Strictly compare complete base.snapshot documents or raise with evidence.

    Native files are re-read and checked against their recorded decoded-text
    SHA256. Only expected native text is normalized; current text remains raw.
    File output locations intentionally differ and are evidence, not scene state.
    """
    items = _mapping_items(mapping)
    report = dict(passed=False, expected_actor_count=EXPECTED_ACTOR_COUNT,
                  package_mapping_sha256=_fingerprint(dict(items)),
                  identity_fields_preserved=sorted(IDENTITY_FIELDS),
                  dictionary_keys_preserved=True, numeric_tolerance=0,
                  physical_light_properties_excluded=False,
                  native_actor_records_verified=0)

    def fail(message, difference):
        report["first_difference"] = difference
        raise SceneVerificationError(message, report)

    if not isinstance(expected, dict) or not isinstance(current, dict):
        fail("Scene snapshots must be dictionaries", dict(kind="snapshot_type"))
    if not SNAPSHOT_FIELDS.issubset(expected) or not SNAPSHOT_FIELDS.issubset(current):
        fail("Incomplete scene snapshot", dict(kind="missing_snapshot_fields",
             expected_missing=sorted(SNAPSHOT_FIELDS - set(expected)),
             actual_missing=sorted(SNAPSHOT_FIELDS - set(current))))
    if set(expected) != set(current):
        fail("Scene snapshot keys changed", dict(kind="snapshot_keys",
             missing=sorted(set(expected) - set(current)), unexpected=sorted(set(current) - set(expected))))
    for side, document in (("expected", expected), ("current", current)):
        for field in ("actors", "actor_properties", "full_existing_actor_native"):
            if not isinstance(document[field], dict) or len(document[field]) != EXPECTED_ACTOR_COUNT:
                fail("Incomplete Actor coverage", dict(kind="actor_coverage", side=side,
                     field=field, expected=EXPECTED_ACTOR_COUNT,
                     actual=len(document[field]) if isinstance(document[field], dict) else None))
        if document["actor_count"] != EXPECTED_ACTOR_COUNT:
            fail("Actor count changed", dict(kind="actor_count", side=side,
                 expected=EXPECTED_ACTOR_COUNT, actual=document["actor_count"]))
        if set(document["actors"]) != set(document["actor_properties"]) or set(document["actors"]) != set(document["full_existing_actor_native"]):
            fail("Actor identity sets differ within snapshot", dict(kind="inconsistent_actor_identity_sets", side=side))

    normalized = normalize_asset_paths({key: value for key, value in expected.items()
                                       if key != "full_existing_actor_native"}, dict(items))
    observed = {key: value for key, value in current.items() if key != "full_existing_actor_native"}
    difference = _first_difference(normalized, observed)
    if difference:
        fail("Scene state differs outside the explicit asset-path mapping", difference)

    expected_native = expected["full_existing_actor_native"]
    current_native = current["full_existing_actor_native"]
    if set(expected_native) != set(current_native):
        fail("Native Actor names/labels changed", dict(kind="native_actor_keys",
             missing=sorted(set(expected_native) - set(current_native)),
             unexpected=sorted(set(current_native) - set(expected_native))))
    verified_hashes = {}
    for label in sorted(expected_native):
        texts = {}
        for side, record in (("expected", expected_native[label]), ("current", current_native[label])):
            if not isinstance(record, dict) or not {"file", "native_text_sha256"}.issubset(record):
                fail("Missing native evidence metadata", dict(kind="native_record", actor=label, side=side))
            try:
                text = read_native_text(record["file"])
            except Exception as error:
                fail("Native evidence is unreadable", dict(kind="native_read", actor=label,
                     side=side, file=record["file"], error=str(error)))
            actual_sha = _text_sha(text)
            if actual_sha != record["native_text_sha256"]:
                fail("Native evidence changed after snapshot", dict(kind="native_evidence_hash", actor=label,
                     side=side, file=record["file"], recorded=record["native_text_sha256"], actual=actual_sha))
            texts[side] = text
        normalized_text = normalize_native_text(texts["expected"], dict(items))
        expected_sha, current_sha = _text_sha(normalized_text), _text_sha(texts["current"])
        if expected_sha != current_sha:
            fail("Full native Actor state differs outside the explicit asset-path mapping",
                 dict(kind="native_text", actor=label, expected_file=expected_native[label]["file"],
                      actual_file=current_native[label]["file"], normalized_expected_sha256=expected_sha,
                      actual_sha256=current_sha, first_native_difference=_native_difference(normalized_text, texts["current"])))
        verified_hashes[label] = current_sha
        report["native_actor_records_verified"] += 1
    report.update(passed=True, actor_count=EXPECTED_ACTOR_COUNT,
                  structured_scene_sha256=_fingerprint(normalized),
                  normalized_native_actor_hashes_sha256=_fingerprint(verified_hashes),
                  all_scene_fields_compared=True, all_light_properties_compared=True,
                  actor_internal_names_and_labels_unchanged=True)
    return report
