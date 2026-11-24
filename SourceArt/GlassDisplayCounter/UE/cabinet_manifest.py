"""Validate local glass display counter exports and scope the Unreal import."""

from hashlib import sha256
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ASSET = HERE.parent
PROJECT = ASSET.parents[1]
CONTENT = PROJECT / 'Content'
EXPORTS = ASSET / 'Exports'
MANIFEST = EXPORTS / 'export_report.json'
TARGET = '/Game/Yastars/Mesh/GlassDisplayCounter'
DESTINATION = CONTENT / TARGET.removeprefix('/Game/')
BODY = 'SM_GlassDisplayCounter'
MESH_NAMES = (BODY, BODY + '_DoorLeft', BODY + '_DoorRight')
TEXTURE_ROOT = TARGET + '/Textures'
MATERIAL_ROOT = TARGET + '/Materials'
PARENT = 'M_GlassDisplayCounter_Opaque'
GLASS = 'M_GlassDisplayCounter_Glass'
BLUEPRINT = 'BP_GlassDisplayCounter'


def digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix + '.tmp')
    pending.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def source(relative):
    path = (EXPORTS / relative).resolve()
    assert path.is_relative_to(EXPORTS.resolve()) and path.is_file(), str(path)
    return path


def packages():
    return {
        '/Game/' + path.relative_to(CONTENT).with_suffix('').as_posix(): {
            'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
        }
        for path in sorted(DESTINATION.rglob('*.uasset'))
    }


def protected_snapshot():
    candidates = set(path for path in CONTENT.rglob('*.umap'))
    candidates.add(PROJECT / 'HorrorGame.uproject')
    scopes = [PROJECT / 'Config', CONTENT / 'Yastars' / 'Mesh', CONTENT / '__ExternalActors__', CONTENT / '__ExternalObjects__']
    scopes.extend(CONTENT / root / folder for root in ('Yastar', 'Yastars') for folder in ('UI', 'Items'))
    for folder in scopes:
        candidates.update(path for path in folder.rglob('*') if path.is_file())
    return {path.relative_to(PROJECT).as_posix(): digest(path)
            for path in sorted(candidates) if path.is_file() and not path.is_relative_to(DESTINATION)}


def verify_protected(baseline):
    current = protected_snapshot()
    changed = sorted(path for path in baseline.keys() | current.keys() if baseline.get(path) != current.get(path))
    assert not changed, ('Protected project files changed', changed)
    return len(current)


def image_dimensions(path):
    with path.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', str(path)
    return list(struct.unpack('>II', header[16:24]))


def instance_name(mesh):
    return mesh.replace('SM_', 'MI_', 1)


def read_export():
    manifest = read(MANIFEST)
    assert manifest['success'] is True
    rows = {row['name']: row for row in manifest['assets']}
    assert len(rows) == len(manifest['assets']) == 3 and set(rows) == set(MESH_NAMES)
    resolution = manifest['baked_resolution']
    assert isinstance(resolution, int) and resolution >= 512
    expected = {MATERIAL_ROOT + '/' + PARENT, MATERIAL_ROOT + '/' + GLASS, TARGET + '/' + BLUEPRINT}
    inputs = {MANIFEST.name: digest(MANIFEST)}
    sources = manifest['sha256']
    for name, row in rows.items():
        assert Path(row['fbx']).name == name + '.fbx'
        assert int(row['triangles']) >= 12 and int(row['collision_hulls']) >= 1
        assert len(row['slots']) == 2 and sum('glass' in slot.casefold() for slot in row['slots']) == 1
        minimum, maximum = row['bounds_min_m'], row['bounds_max_m']
        assert len(minimum) == len(maximum) == 3 and all(a < b for a, b in zip(minimum, maximum))
        expected.update((TARGET + '/' + name, MATERIAL_ROOT + '/' + instance_name(name)))
        for key in ('fbx', 'base_color', 'orm'):
            relative = row[key]
            path = source(relative)
            expected_digest = sources[relative].lower()
            assert digest(path) == expected_digest, ('Source hash mismatch', relative)
            inputs[relative] = expected_digest
            if key != 'fbx':
                assert image_dimensions(path) == [resolution, resolution], str(path)
                expected.add(TEXTURE_ROOT + '/' + path.stem)
    door_specs = manifest['doors']
    assert set(door_specs) == {'left', 'right'}
    for name, asset, sign in [('left', MESH_NAMES[1], 1), ('right', MESH_NAMES[2], -1)]:
        door = door_specs[name]
        assert door.get('mesh', asset) == asset and len(door['closed_ue_cm']) == 3
        assert 30 <= sign*float(door['travel_cm']) <= 120, door
    return manifest, rows, expected, inputs
