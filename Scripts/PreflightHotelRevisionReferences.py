"""Offline exact Actor-reference preflight; reads fresh Native exports only.

Does not import Unreal, load/save assets, or modify any Content/Config file.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelRevision_20261019'
MAP = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
OWN_TAG = 'HotelRedesign_20261008_V4'
DOOR_PREFIX = '/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door'


def read(name):
    return json.loads((WORK / name).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()


def native_text(path):
    raw = Path(path).read_bytes()
    return raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')


def identity(label, scene, texts):
    metadata = scene['actors'][label]
    first = texts[label].splitlines()[0]
    name = re.search(r'\bName="([^"]+)"', first).group(1)
    export = re.search(r'\bExportPath="([^"]+)"', first).group(1)
    path = export.split("'", 1)[1].rsplit("'", 1)[0]
    assert name == metadata['name'], (label, name, metadata['name'])
    assert path.endswith(':PersistentLevel.' + name), (label, path)
    assert label.startswith('OTS_HotelV4_') and OWN_TAG in metadata['tags'], label
    return dict(label=label, original_fname=name, original_path=path,
                class_path=metadata['class'], own_tags=metadata['tags'],
                folder=metadata['folder'], ownership_verified=True,
                native_file=scene['full_existing_actor_native'][label]['file'],
                native_text_sha256=scene['full_existing_actor_native'][label]['native_text_sha256'])


def structured_attachments(result, scene):
    """SceneComponent AttachParent is transient and absent from ObjectExporter."""
    deleted = {row['label']: row for row in result['deletion_targets']}
    replacing = {row['label']: row for row in result['replacement_targets']}
    targets = dict(deleted, **replacing)
    by_path = {row['original_path']: label for label, row in targets.items()}
    allowed, internal, bad_deleted, bad_replacing = [], [], [], []
    for component_key, component in scene['exact_scene_components'].items():
        parent = component['parent']
        if not parent:
            continue
        target = next((label for path, label in by_path.items() if parent.startswith(path + '.')), None)
        if target is None:
            continue
        owner_label = component_key.split('::', 1)[0]
        if owner_label == target:
            continue
        row = dict(component_key=component_key, owner_label=owner_label,
                   target_label=target, original_parent_path=parent)
        if target in deleted:
            (internal if owner_label in deleted else bad_deleted).append(row)
            continue
        expected_component = 'DoorHinge' if owner_label.endswith('_MovingHinges') else 'OpeningRoot'
        expected = owner_label in (target + '_FixedHinges', target + '_MovingHinges')
        owner = scene['actors'][owner_label]
        if expected and OWN_TAG in owner['tags'] and parent == replacing[target]['original_path'] + '.' + expected_component:
            row.update(expected_parent_component=expected_component, ownership_verified=True)
            allowed.append(row)
        else:
            bad_replacing.append(row)
    expected_count = 2 * sum(row['kind'] == 'swing' for row in read('Doors.json')['doors'] if row['label'] in replacing)
    result.update(
        transient_attachments_require_structured_scene_evidence=True,
        structured_component_attachment_scan=True,
        replacement_allowed_hinge_attachments=allowed,
        replacement_allowed_hinge_attachment_count=len(allowed),
        replacement_expected_hinge_attachment_count=expected_count,
        deletion_internal_attachments_removed_together=internal,
        deletion_external_attachments=bad_deleted,
        replacement_unexpected_attachments=bad_replacing,
    )
    result['passed'] = result['passed'] and not bad_deleted and not bad_replacing and len(allowed) == expected_count
    return result


def main():
    inspection = read('Inspection.json')
    assert inspection['passed']
    before_sha = sha(MAP)
    assert before_sha == inspection['source_map_sha256'], 'Map changed since fresh read-only inspection'
    scene = read('BeforeScene.json')
    assert scene['actor_count'] == len(scene['actors']) == len(scene['full_existing_actor_native']) == 7986
    front_doors = {'OTS_HotelV4_Door_' + name for name in
                   ('SouthFrontExit', 'NorthFrontExit', 'ServiceEntry')}
    removed = set(front_doors)
    removed.update(door + suffix for door in front_doors if not door.endswith('ServiceEntry')
                   for suffix in ('_FixedHinges', '_MovingHinges'))
    removed.update('OTS_HotelV4_' + name for name in
                   ('ExitThreshold_0', 'ExitThreshold_64', 'ServiceEntryThreshold'))
    removed.update('OTS_HotelV4_' + name + '_DoorTrim' for name in
                   ('CleanLinenShelf', 'DirtyLinenShelf', 'ChangingShelf', 'EquipmentShelf'))
    assert len(removed) == 14 and removed.issubset(scene['actors'])
    all_doors = {label for label, row in scene['actors'].items()
                 if label.startswith('OTS_HotelV4_Door_') and row['class'].startswith(DOOR_PREFIX)}
    replacing = all_doors - front_doors
    assert len(all_doors) == 96 and len(replacing) == 93

    texts = {}
    for label, row in scene['full_existing_actor_native'].items():
        text = native_text(row['file'])
        assert hashlib.sha256(text.encode()).hexdigest() == row['native_text_sha256'], label
        texts[label] = text
    targets = {label: identity(label, scene, texts) for label in sorted(removed | replacing)}
    by_name = {row['original_fname']: label for label, row in targets.items()}
    assert len(by_name) == len(targets)
    pattern = re.compile(r'PersistentLevel\.(' + '|'.join(
        sorted(map(re.escape, by_name), key=len, reverse=True)) + r')(?![A-Za-z0-9_])')
    deletion_external, deletion_internal, allowed_hinges, unexpected_replacements = [], [], [], []
    self_counts = {label: 0 for label in targets}
    for owner_label, text in texts.items():
        for line_number, line in enumerate(text.splitlines(), 1):
            # Deduplicate multiple mentions of the same target on a serialized line.
            for target_label in sorted({by_name[m.group(1)] for m in pattern.finditer(line)}):
                if owner_label == target_label:
                    self_counts[target_label] += 1
                    continue
                row = dict(owner_label=owner_label, target_label=target_label,
                           line_number=line_number, serialized_line=line.strip())
                if target_label in removed:
                    (deletion_internal if owner_label in removed else deletion_external).append(row)
                    continue
                expected_hinge = owner_label in (target_label + '_FixedHinges', target_label + '_MovingHinges')
                if expected_hinge and line.strip().startswith('AttachParent='):
                    identity(owner_label, scene, texts)
                    owner_components = scene['actors'][owner_label]['components']
                    expected_component = 'DoorHinge' if owner_label.endswith('_MovingHinges') else 'OpeningRoot'
                    assert len(owner_components) == 1 and owner_components[0]['parent'] == expected_component, row
                    assert row['serialized_line'].rstrip('"\'').endswith('.' + expected_component), row
                    row.update(expected_parent_component=expected_component, ownership_verified=True)
                    allowed_hinges.append(row)
                else:
                    unexpected_replacements.append(row)
    result = dict(
        passed=not deletion_external and not unexpected_replacements,
        source_map_sha256=before_sha,
        fresh_inspection_file=str(WORK / 'Inspection.json'),
        before_scene_sha256=sha(WORK / 'BeforeScene.json'),
        native_actor_files_checked=len(texts), native_text_hashes_verified=True,
        deletion_target_count=len(removed), replacement_door_count=len(replacing),
        deletion_targets=[dict(targets[label], excluded_self_native_line_count=self_counts[label])
                          for label in sorted(removed)],
        replacement_targets=[dict(targets[label], excluded_self_native_line_count=self_counts[label])
                             for label in sorted(replacing)],
        deletion_external_hard_references=deletion_external,
        deletion_internal_references_removed_together=deletion_internal,
        replacement_allowed_hinge_attach_parent_references=allowed_hinges,
        replacement_unexpected_hard_references=unexpected_replacements,
        scan_rule='Exact PersistentLevel Actor FNames including component references; own Native self references excluded. Only own fixed/moving hinge AttachParent references may point to retained replacement doors. References internal to the removed assembly are recorded separately.',
        read_only=True, unreal_not_loaded=True,
    )
    result = structured_attachments(result, scene)
    assert sha(MAP) == before_sha, 'Map changed while offline reference preflight ran'
    (WORK / 'FrontRemovalPreflight.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in (
        'passed', 'source_map_sha256', 'native_actor_files_checked', 'deletion_target_count',
        'replacement_door_count')}, ensure_ascii=False), flush=True)
    print('Deletion external refs:', len(deletion_external),
          '; deletion internal refs:', len(deletion_internal),
          '; allowed hinge refs:', len(allowed_hinges),
          '; unexpected replacement refs:', len(unexpected_replacements), flush=True)
    assert result['passed'], 'Unexpected Actor hard references require explicit preservation handling'


if __name__ == '__main__':
    main()
