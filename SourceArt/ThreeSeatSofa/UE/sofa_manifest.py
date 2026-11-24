"""Frozen Blender source contract for the three-seat upholstered sofa."""
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ASSET = HERE.parent
PROJECT = ASSET.parents[1]
CONTENT = PROJECT / 'Content'
EXPORTS = ASSET / 'Exports'
MANIFEST = EXPORTS / 'export_report.json'
TARGET = '/Game/Yastars/Mesh/ThreeSeatSofa'
DESTINATION = CONTENT / TARGET.removeprefix('/Game/')
TEXTURE_ROOT = TARGET + '/Textures'
MATERIAL_ROOT = TARGET + '/Materials'
PARENT = 'M_Sofa_Textured'
PREFIX = 'SM_Sofa_'
BLUEPRINT_PREFIX = 'BP_'
SAFE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


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
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    pending.replace(path)


def source(relative):
    assert isinstance(relative, str) and relative, relative
    path = (EXPORTS / relative).resolve()
    assert path.is_relative_to(EXPORTS.resolve()) and path.is_file(), str(path)
    return path


def packages():
    return {'/Game/' + path.relative_to(CONTENT).with_suffix('').as_posix():
            {'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}
            for path in sorted(DESTINATION.rglob('*.uasset'))}


def protected_snapshot():
    """Hash all existing Content and Config, including every map/external actor."""
    candidates = {PROJECT / 'HorrorGame.uproject'}
    for folder in (CONTENT, PROJECT / 'Config'):
        candidates.update(path for path in folder.rglob('*') if path.is_file())
    return {path.relative_to(PROJECT).as_posix(): digest(path) for path in sorted(candidates)
            if path.is_file() and not path.is_relative_to(DESTINATION)}


def verify_protected(baseline):
    current = protected_snapshot()
    changed = sorted(p for p in baseline.keys() | current.keys() if baseline.get(p) != current.get(p))
    assert not changed, ('Unrelated project files changed', changed)
    return len(current)


def image_dimensions(path):
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', str(path)
    return list(struct.unpack('>II', header[16:24]))


def point(value):
    assert len(value) == 3 and all(math.isfinite(float(v)) for v in value), value
    return [float(v) for v in value]


def ue_position(pivot):
    x, y, z = point(pivot)
    return [100 * x, -100 * y, 100 * z]


def texture_spec(manifest):
    """Every fabric owns a BaseColor/ORM/normal triplet."""
    raw = manifest['textures']
    assert isinstance(raw, dict)
    result = {}
    for name, pair in raw.items():
        assert name.startswith('M_Sofa_') and SAFE_NAME.fullmatch(name), name
        assert isinstance(pair, dict), (name, pair)
        result[name] = {channel: pair[channel] for channel in ('base_color', 'orm', 'normal')}
    assert result and PARENT not in result
    return result


def generic_spec(manifest):
    result = {}
    for name, raw in manifest.get('generic_materials', {}).items():
        assert name.startswith('M_Sofa_') and SAFE_NAME.fullmatch(name), name
        assert name != PARENT
        kind = raw.get('type', raw.get('blend_mode', 'solid')).lower()
        assert kind in ('solid', 'translucent'), (name, kind)
        color = list(map(float, raw['color']))
        assert len(color) in (3, 4) and all(math.isfinite(v) and 0 <= v <= 1 for v in color)
        color = color[:3] + [color[3] if len(color) == 4 else 1.]
        color_space = raw.get('color_space', manifest.get('generic_color_space', 'srgb')).lower()
        assert color_space in ('srgb', 'linear'), (name, color_space)
        row = dict(type=kind, color=color, color_space=color_space, roughness=float(raw['roughness']),
                   metallic=float(raw.get('metallic', 0)), opacity=float(raw.get('opacity', 1)),
                   ior=float(raw.get('ior', 1.45)), two_sided=bool(raw.get('two_sided', False)))
        assert all(math.isfinite(row[key]) and 0 <= row[key] <= 1
                   for key in ('roughness', 'metallic', 'opacity')), name
        assert math.isfinite(row['ior']) and 1 <= row['ior'] <= 3, name
        result[name] = row
    return result


def assemblies(manifest, rows):
    result = {}
    for name, parts in manifest.get('assemblies', {}).items():
        assert name.startswith(BLUEPRINT_PREFIX) and SAFE_NAME.fullmatch(name), name
        assert isinstance(parts, list) and parts, name
        resolved = []
        for part in parts:
            assert isinstance(part, str), part
            mesh_name = part if part.startswith(PREFIX) else PREFIX + part
            assert mesh_name in rows, (name, mesh_name)
            resolved.append(mesh_name)
        assert len(resolved) == len(set(resolved)), name
        result[name] = resolved
    assert set(result) == {'BP_ThreeSeatSofa'}, sorted(result)
    assert set(result['BP_ThreeSeatSofa']) == set(rows)
    return result


def read_export():
    manifest = read(MANIFEST)
    assert manifest.get('success') is True
    assert digest(ASSET / 'ThreeSeatSofa.blend') == manifest['source_sha256'], 'Source blend hash mismatch'
    assert manifest.get('normal_convention') == 'OpenGL +Y'
    assert isinstance(manifest['assets'], list) and manifest['assets']
    rows = {row['name']: row for row in manifest['assets']}
    assert len(rows) == len(manifest['assets']), 'Duplicate mesh names'
    assert set(rows) == {PREFIX + part for part in (
        'Base','Arm_L','Arm_R','Seat_01','Seat_02','Seat_03','Back_01','Back_02','Back_03',
        'Foot_FL','Foot_FR','Foot_BL','Foot_BR','Pillow_L','Pillow_R')}, sorted(rows)
    textures = texture_spec(manifest)
    generic = generic_spec(manifest)
    material_names = set(textures)
    assert not material_names & set(generic), 'Duplicate material specifications'
    material_names |= set(generic)
    expected = {MATERIAL_ROOT + '/' + name for name in material_names | {PARENT}}
    inputs = {MANIFEST.name: digest(MANIFEST)}
    declared = manifest.get('sha256', {})
    for name, row in rows.items():
        assert name.startswith(PREFIX) and SAFE_NAME.fullmatch(name), name
        assert row['fbx'] == name + '.fbx'
        assert isinstance(row['triangles'], int) and row['triangles'] >= 2
        assert isinstance(row['collision_hulls'], int) and row['collision_hulls'] >= 1
        assert row['slots'] and len(row['slots']) == len(set(row['slots']))
        assert set(row['slots']) <= material_names, (name, row['slots'], material_names)
        point(row['pivot_m'])
        low, high = point(row['bounds_min_m']), point(row['bounds_max_m'])
        assert all(a < b for a, b in zip(low, high)), name
        expected.add(TARGET + '/' + name)
        inputs[row['fbx']] = digest(source(row['fbx']))
    total = sum(row['triangles'] for row in rows.values())
    assert 2000 <= total <= 15000, ('Whole-sofa LOD0 triangle budget', total)
    grouped = assemblies(manifest, rows)
    expected.update(TARGET + '/' + name for name in grouped)
    filenames = {pair[channel] for pair in textures.values()
                 for channel in ('base_color', 'orm', 'normal')}
    assert len(filenames) == 3 * len(textures), 'Fabric texture triplets must be unique'
    stems = set()
    for filename in filenames:
        path = source(filename)
        assert path.suffix.lower() == '.png' and SAFE_NAME.fullmatch(path.stem)
        width, height = image_dimensions(path)
        assert min(width, height) >= 512 and max(width, height) <= 8192, (filename, width, height)
        assert path.stem not in stems, 'Texture package name collision'
        stems.add(path.stem)
        inputs[filename] = digest(path)
        expected.add(TEXTURE_ROOT + '/' + path.stem)
    for filename, value in inputs.items():
        if filename in declared:
            assert value == declared[filename].lower(), ('Source hash mismatch', filename)
    return manifest, rows, expected, inputs


if __name__ == '__main__':
    import sys
    manifest, rows, expected, sources = read_export()
    if '--snapshot' in sys.argv:
        assert not list(DESTINATION.rglob('*')), 'Target is not new'
        write(HERE / 'protected_content_sha256.json', protected_snapshot())
    print('SOFA_PREFLIGHT', len(rows), sum(row['triangles'] for row in rows.values()),
          len(assemblies(manifest, rows)), len(expected))
