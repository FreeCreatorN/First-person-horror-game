"""Scope and validate the planning-sheet ice cream display freezer."""
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
TARGET = '/Game/Yastars/Mesh/IceCreamFreezer'
DESTINATION = CONTENT / TARGET.removeprefix('/Game/')
PREFIX = 'SM_IceCreamFreezer_'
PARTS = ('Body', 'TopFrame', 'GlassDoorLeft', 'GlassDoorRight', 'Liner',
         'BasketLeft', 'BasketRight', 'WheelFL', 'WheelFR', 'WheelRL', 'WheelRR')
MESH_NAMES = tuple(PREFIX + part for part in PARTS)
TEXTURE_ROOT = TARGET + '/Textures'
MATERIAL_ROOT = TARGET + '/Materials'
PARENT = 'M_IceCreamFreezer_Opaque'
GLASS = 'M_IceCreamFreezer_Glass'
BLUEPRINT = 'BP_IceCreamFreezer'
TEXTURES = {'base_color': 'T_IceCreamFreezer_BaseColor.png', 'orm': 'T_IceCreamFreezer_ORM.png'}
DOORS = {'left': 'GlassDoorLeft', 'right': 'GlassDoorRight'}
GROUPS = {'SlidingGlassDoors': ('GlassDoorLeft','GlassDoorRight'),
          'Baskets': ('BasketLeft','BasketRight'),
          'Wheels': ('WheelFL','WheelFR','WheelRL','WheelRR')}
PLANNING = {'Body':'外壳柜体','TopFrame':'上框架与滑轨','SlidingGlassDoors':'玻璃滑门（左右）',
            'Liner':'内胆','Baskets':'内部篮筐（两个）','Wheels':'万向轮（四个）'}

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
    return {'/Game/' + path.relative_to(CONTENT).with_suffix('').as_posix(): {
        'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
    } for path in sorted(DESTINATION.rglob('*.uasset'))}

def protected_snapshot():
    candidates = set(path for path in CONTENT.rglob('*.umap'))
    candidates.add(PROJECT / 'HorrorGame.uproject')
    scopes = [PROJECT / 'Config', CONTENT / 'Yastars' / 'Mesh',
              CONTENT / '__ExternalActors__', CONTENT / '__ExternalObjects__']
    scopes.extend(CONTENT / root / folder for root in ('Yastar', 'Yastars') for folder in ('UI', 'Items'))
    for folder in scopes:
        candidates.update(path for path in folder.rglob('*') if path.is_file())
    return {path.relative_to(PROJECT).as_posix(): digest(path) for path in sorted(candidates)
            if path.is_file() and not path.is_relative_to(DESTINATION)}

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

def read_export():
    manifest = read(MANIFEST)
    assert manifest['success'] is True
    rows = {row['name']: row for row in manifest['assets']}
    assert len(rows) == len(manifest['assets']) == 11 and set(rows) == set(MESH_NAMES)
    resolution = manifest['baked_resolution']
    assert isinstance(resolution, int) and resolution >= 512
    total_tris = sum(int(row['triangles']) for row in rows.values())
    assert 1800 <= total_tris <= 3400, ('Planning-sheet triangle budget', total_tris)
    expected = {MATERIAL_ROOT + '/' + PARENT, MATERIAL_ROOT + '/' + GLASS, TARGET + '/' + BLUEPRINT}
    inputs = {MANIFEST.name: digest(MANIFEST)}
    sources = manifest['sha256']
    for name, row in rows.items():
        assert Path(row['fbx']).name == name + '.fbx'
        assert int(row['triangles']) >= 12 and int(row['collision_hulls']) >= 1
        assert row['slots'] and len(row['slots']) == len(set(row['slots']))
        assert set(row['slots']) <= {'M_Freezer_Opaque', 'M_Freezer_Glass'}
        minimum, maximum = row['bounds_min_m'], row['bounds_max_m']
        assert len(minimum) == len(maximum) == 3 and all(a < b for a, b in zip(minimum, maximum))
        expected.add(TARGET + '/' + name)
        path = source(row['fbx'])
        assert digest(path) == sources[row['fbx']].lower(), ('Source hash mismatch', row['fbx'])
        inputs[row['fbx']] = digest(path)
    for relative in TEXTURES.values():
        path = source(relative)
        assert digest(path) == sources[relative].lower(), ('Source hash mismatch', relative)
        inputs[relative] = digest(path)
        assert image_dimensions(path) == [resolution, resolution]
        expected.add(TEXTURE_ROOT + '/' + path.stem)
    assert set(manifest['doors']) == set(DOORS)
    for key, component in DOORS.items():
        spec = manifest['doors'][key]
        assert spec['mesh'] == PREFIX + component
        assert len(spec['closed_ue_cm']) == len(spec['pivot_m']) == 3
        sign = 1 if key == 'left' else -1
        assert 15 <= sign * float(spec['travel_cm']) <= 90, spec
        pivot = spec['pivot_m']
        expected_closed = [100 * pivot[0], -100 * pivot[1], 100 * pivot[2]]
        assert all(abs(a-b) < .003 for a,b in zip(spec['closed_ue_cm'], expected_closed)), spec
    return manifest, rows, expected, inputs
