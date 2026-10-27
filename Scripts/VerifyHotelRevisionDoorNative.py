"""Strict offline Native preservation for the 93 revised hotel door Actors.

Usage: python VerifyHotelRevisionDoorNative.py [before.json after.json applied.json]
The three-argument ``verify`` function returns a JSON-safe report. Nothing runs
on import, and neither verification path imports or executes Unreal.
"""
from __future__ import annotations

from copy import deepcopy
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from HotelDoorClosurePreservation import _parse_native, _render

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelRevision_20261019'
REAR = frozenset(('RearHandle', 'RearLeftHandle', 'RearRightHandle'))
TRANSFORMS = {
    'RelativeLocation': ('relative_location', ('X', 'Y', 'Z')),
    'RelativeRotation': ('relative_rotation', ('Pitch', 'Yaw', 'Roll')),
    'RelativeScale3D': ('relative_scale3d', ('X', 'Y', 'Z')),
}


def _load(value):
    return json.loads(Path(value).read_text(encoding='utf-8-sig')) if isinstance(value, (str, Path)) else value


def _read_native(record):
    raw = Path(record['file']).read_bytes()
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')
    assert hashlib.sha256(text.encode()).hexdigest() == record['native_text_sha256'], record['file']
    return text


def _component_names(scene, label):
    return {key.split('::', 1)[1] for key in scene['exact_scene_components'] if key.startswith(label + '::')}


def _canonical_actor(text, added, after):
    node = _parse_native(text)
    root_lines, component_blocks, removals = [], {}, []
    array_values = []
    array_indent = None
    for item in node['body']:
        if isinstance(item, dict):
            name = item['name']
            if name in added:
                assert after and name in REAR
                removals.append(dict(kind='new_rear_component_block', component=name,
                                     definition='Class=' in item['header']))
                continue
            key = (name, 'definition' if 'Class=' in item['header'] else 'values')
            assert key not in component_blocks, ('Duplicate component block', key)
            component_blocks[key] = item
            continue
        found = re.fullmatch(r'(\s*)BlueprintCreatedComponents\((\d+)\)=(.*?)(\r?\n)?', item)
        if found:
            array_indent = found.group(1)
            value = found.group(3)
            if value.strip().strip('"') in added:
                assert after
                removals.append(dict(kind='new_rear_created_component_array_entry', serialized=item.rstrip()))
            else:
                array_values.append((value, found.group(4) or ''))
            continue
        found = re.match(r'\s*(' + '|'.join(sorted(added)) + r')=(.*)', item) if added else None
        if found:
            assert after and found.group(2).strip() == '"' + found.group(1) + '"', item
            removals.append(dict(kind='new_rear_component_actor_pointer', serialized=item.rstrip()))
            continue
        root_lines.append(item)
    assert array_indent is not None, 'Missing BlueprintCreatedComponents array'
    # The original relative ordering is preserved. Only new rear entries are
    # removed; remaining indexes must form the same original array sequence.
    normalized_array = [array_indent + 'BlueprintCreatedComponents(' + str(i) + ')=' + value + end
                        for i, (value, end) in enumerate(array_values)]
    return dict(header=node['header'], end=node['end'], root_properties=root_lines,
                blueprint_created_components=normalized_array, blocks=component_blocks), removals


def _native_transform(line, prop, axis):
    found = re.fullmatch(r'\s*' + prop + r'=\((.*)\)\s*', line)
    assert found is not None, line
    fields = dict(part.split('=', 1) for part in found.group(1).split(','))
    assert set(fields) == set(axis), line
    values = [float(fields[key]) for key in axis]
    assert all(math.isfinite(value) for value in values), line
    return values


def _explicit_transform_exception(before_block, after_block, before_scene, after_scene, label, component):
    """Permit an explicit/inherited serialization change, never a value change."""
    ledger = []
    assert all(isinstance(item, str) for item in before_block['body'] + after_block['body'])
    key = label + '::' + component
    for prop, (local_key, axis) in TRANSFORMS.items():
        left = [line for line in before_block['body'] if re.match(r'\s*' + prop + '=', line)]
        right = [line for line in after_block['body'] if re.match(r'\s*' + prop + '=', line)]
        if left == right:
            continue
        # Both explicit but different is a real serialized value change.
        assert len(left) <= 1 and len(right) <= 1 and bool(left) != bool(right), (label, component, prop, left, right)
        a = before_scene['exact_scene_components'][key]['local'][local_key]
        b = after_scene['exact_scene_components'][key]['local'][local_key]
        assert a == b, (label, component, prop, a, b)
        for line in left + right:
            values = _native_transform(line, prop, axis)
            assert all(abs(x - y) <= .000051 for x, y in zip(values, a)), (label, component, line, a)
        before_block['body'] = [line for line in before_block['body'] if line not in left]
        after_block['body'] = [line for line in after_block['body'] if line not in right]
        ledger.append(dict(component=component, property=prop, unchanged_actual_local=a,
                           source_explicit=bool(left), target_explicit=bool(right),
                           source_native=left, target_native=right,
                           reason='Only explicit versus inherited serialization differs; both actual local arrays are exactly equal and Native six-decimal values agree.'))
    return ledger


def verify(before_scene, after_scene, applied):
    before_scene, after_scene, applied = map(_load, (before_scene, after_scene, applied))
    assert applied['passed'] and len(applied['doors']) == 93
    rows = []
    for proof in applied['doors']:
        label = proof['label']
        old_class = before_scene['actors'][label]['class']
        new_class = after_scene['actors'][label]['class']
        old_package, new_package = old_class.split('.')[0], new_class.split('.')[0]
        assert new_package == proof['blueprint'] and old_package.startswith('/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door')
        source_text = _read_native(before_scene['full_existing_actor_native'][label])
        target_text = _read_native(after_scene['full_existing_actor_native'][label])
        target_text = target_text.replace(new_package, old_package).replace(Path(new_package).name, Path(old_package).name)
        original = _component_names(before_scene, label)
        current = _component_names(after_scene, label)
        added = current - original
        assert added and added.issubset(REAR) and original.issubset(current), (label, original, current)
        before, _ = _canonical_actor(source_text, added, False)
        after, removals = _canonical_actor(target_text, added, True)
        assert set(before['blocks']) == set(after['blocks']), (label, set(before['blocks']), set(after['blocks']))
        top_fields = ('header', 'end', 'root_properties', 'blueprint_created_components')
        top_same = all(before[key] == after[key] for key in top_fields)
        serialization = []
        component_differences = []
        for key, source in before['blocks'].items():
            actual = after['blocks'][key]
            if _render(source) != _render(actual) and key[1] == 'values':
                serialization.extend(_explicit_transform_exception(source, actual, before_scene, after_scene, label, key[0]))
            if _render(source) != _render(actual):
                component_differences.append(dict(component=key[0], block=key[1], diff=list(difflib.unified_diff(
                    _render(source).splitlines(), _render(actual).splitlines(), fromfile='original', tofile='revised', lineterm=''))))
        top_diff = [] if top_same else list(difflib.unified_diff(
            json.dumps({key: before[key] for key in top_fields}, ensure_ascii=False, indent=2).splitlines(),
            json.dumps({key: after[key] for key in top_fields}, ensure_ascii=False, indent=2).splitlines(),
            fromfile='original_actor_properties', tofile='revised_actor_properties', lineterm=''))
        rows.append(dict(label=label, passed=top_same and not component_differences,
                         original_class=old_class, revised_class=new_class,
                         actor_top_level_state_exact=top_same,
                         original_component_native_state_exact=not component_differences,
                         original_component_count=len(original), added_component_names=sorted(added),
                         allowed_new_component_serialization=removals,
                         proven_explicit_inherited_transform_exceptions=serialization,
                         actor_top_level_differences=top_diff,
                         component_differences=component_differences))
    return dict(passed=all(row['passed'] for row in rows), doors=len(rows),
                source_map_sha256=applied['source_map_sha256'], map_sha256=applied['map_sha256'],
                all_native_input_text_hashes_verified=True,
                normalization='New Blueprint own package/name to original; remove only new RearHandle/RearLeftHandle/RearRightHandle definitions and pointers and their BlueprintCreatedComponents entries; retain original array order and renumber indexes; original component blocks compared by name and definition/value role. Only numeric-proof explicit/inherited transform exceptions allowed.',
                read_only=True, unreal_not_loaded=True, rows=rows)


def main():
    paths = sys.argv[1:]
    assert len(paths) in (0, 3), 'Pass beforeScene.json afterScene.json applied.json or no arguments'
    if not paths:
        paths = [WORK / name for name in ('BeforeScene.json', 'AfterScene.json', 'Applied.json')]
    result = verify(*paths)
    output = WORK / 'DoorNativePreservation.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], doors=result['doors'], report=str(output)), ensure_ascii=False))
    assert result['passed'], 'Door Native preservation mismatch; see DoorNativePreservation.json'


if __name__ == '__main__':
    main()
