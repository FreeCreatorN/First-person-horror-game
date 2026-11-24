"""Shared preflight and on-disk verification for the three rack variants."""
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
TARGET = '/Game/Yastars/Mesh/MetalShelvingRack'
DESTINATION = CONTENT / TARGET.removeprefix('/Game/')
PARENT_NAME = 'M_MetalShelvingRack'
VARIANTS = {'7Level': (7, 29), '4Level': (4, 20), '4Level_Low': (4, 20)}


def digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(data)
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


def package_file(package):
    assert package.startswith(TARGET + '/'), package
    return CONTENT / (package.removeprefix('/Game/') + '.uasset')


def packages():
    return {
        '/Game/' + path.relative_to(CONTENT).with_suffix('').as_posix(): {
            'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
        }
        for path in sorted(DESTINATION.rglob('*.uasset'))
    }


def protected_files():
    candidates = set(CONTENT.rglob('*.umap'))
    candidates.add(PROJECT / 'HorrorGame.uproject')
    scopes = [PROJECT / 'Config', CONTENT / 'Yastars' / 'Mesh']
    scopes.extend(CONTENT / root / folder for root in ('Yastar', 'Yastars') for folder in ('UI', 'Items'))
    for folder in scopes:
        candidates.update(path for path in folder.rglob('*') if path.is_file())
    return sorted(path for path in candidates if path.is_file() and not path.is_relative_to(DESTINATION))


def protected_snapshot():
    return {path.relative_to(PROJECT).as_posix(): digest(path) for path in protected_files()}


def verify_protected(baseline):
    current = protected_snapshot()
    changed = sorted(path for path in baseline.keys() | current.keys() if baseline.get(path) != current.get(path))
    assert not changed, ('Unrelated project files changed during import', changed)
    return len(current)


def png_size(path):
    with path.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', str(path)
    return list(struct.unpack('>II', header[16:24]))


def read_export():
    value = read(MANIFEST)
    assert value['success'] is True
    rows = {row['name']: row for row in value['assets']}
    assert len(rows) == len(value['assets']) == len(VARIANTS)
    baked_resolution = value['baked_resolution']
    assert isinstance(baked_resolution, int) and baked_resolution >= 512
    expected = {TARGET + '/Materials/' + PARENT_NAME}
    inputs = {MANIFEST.name: digest(MANIFEST)}
    for suffix, (level_count, hulls) in VARIANTS.items():
        name = 'SM_MetalShelvingRack_' + suffix
        row = rows[name]
        assert row['levels'] == level_count and row['collision_hulls'] == hulls
        assert row['slots'] == ['M_Rack_Baked'] and row['triangles'] > 0
        assert row['material'] == 'MI_MetalShelvingRack_' + suffix
        for coordinate in ('bounds_min_m', 'bounds_max_m'):
            assert len(row[coordinate]) == 3
        minimum, maximum = row['bounds_min_m'], row['bounds_max_m']
        assert 2.4 < maximum[0] - minimum[0] < 2.45 and .51 < maximum[1] - minimum[1] < .56
        height = 1.599 if suffix.endswith('_Low') else 2.189
        assert abs((maximum[2] - minimum[2]) - height) < .01 and abs(minimum[2]) < .005
        assert Path(row['fbx']).name == name + '.fbx'
        expected.add(TARGET + '/' + name)
        expected.add(TARGET + '/Materials/' + row['material'])
        for key in ('fbx', 'base_color', 'orm'):
            relative = row[key]
            path = source(relative)
            assert path.stat().st_size > 24, str(path)
            expected_digest = value['sha256'][relative].lower()
            assert digest(path) == expected_digest, ('Source hash mismatch', relative)
            inputs[relative] = expected_digest
            if key == 'fbx':
                continue
            semantic = 'BaseColor' if key == 'base_color' else 'ORM'
            assert path.name == f'T_MetalShelvingRack_{suffix}_{semantic}.png', path.name
            assert png_size(path) == [baked_resolution, baked_resolution], str(path)
            expected.add(TARGET + '/Textures/' + path.stem)
    assert len(expected) == 13
    return value, expected, inputs
