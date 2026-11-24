"""Self-contained source/import contract for the new cardboard box set."""
from hashlib import sha256
import json
import math
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ASSET = HERE.parent
PROJECT = ASSET.parents[1]
CONTENT = PROJECT / 'Content'
EXPORTS = ASSET / 'Exports'
MANIFEST = EXPORTS / 'export_report.json'
TARGET = '/Game/Yastars/Mesh/CardboardBoxSet'
DESTINATION = CONTENT / TARGET.removeprefix('/Game/')
PREFIX = 'SM_CardboardBox_'
PARTS = ('A_Sealed', 'B_Body', 'B_FlapFront', 'B_FlapBack', 'B_FlapLeft',
         'B_FlapRight', 'C_Body', 'C_Lid', 'D_Damaged', 'E_Stack', 'F_Fruit',
         'G_Water', 'H_Noodles')
MESH_NAMES = tuple(PREFIX + part for part in PARTS)
VARIANTS = ('Standard', 'Damaged', 'Fruit', 'Water', 'Noodles')
MATERIAL_VARIANTS = (*VARIANTS, 'Tape', 'Edge')
MATERIAL_NAMES = tuple('M_Cardboard_' + name for name in MATERIAL_VARIANTS)
TEXTURE_ROOT = TARGET + '/Textures'
MATERIAL_ROOT = TARGET + '/Materials'
ASSEMBLIES = {
    'BP_CardboardBox_B_Open': ('B_Body', 'B_FlapFront', 'B_FlapBack', 'B_FlapLeft', 'B_FlapRight'),
    'BP_CardboardBox_C_Storage': ('C_Body', 'C_Lid'),
}
VARIANT_PARTS = {'A': ('A_Sealed',), 'B': ASSEMBLIES['BP_CardboardBox_B_Open'],
                 'C': ASSEMBLIES['BP_CardboardBox_C_Storage'], 'D': ('D_Damaged',),
                 'E': ('E_Stack',), 'F': ('F_Fruit',), 'G': ('G_Water',), 'H': ('H_Noodles',)}


def digest(path):
    value = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix + '.tmp')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    pending.replace(path)


def source(relative):
    path = (EXPORTS / relative).resolve()
    assert path.is_relative_to(EXPORTS.resolve()) and path.is_file(), str(path)
    return path


def packages():
    return {'/Game/' + path.relative_to(CONTENT).with_suffix('').as_posix():
            {'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}
            for path in sorted(DESTINATION.rglob('*.uasset'))}


def protected_snapshot():
    candidates = set(CONTENT.rglob('*.umap'))
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
    """Five 2K box pairs, two 512px edge/tape pairs, and one shared 2K normal."""
    raw = manifest['textures']
    result = {}
    for variant in MATERIAL_VARIANTS:
        entry = raw.get(variant, raw.get(variant.lower()))
        assert isinstance(entry, dict), ('Missing texture pair', variant)
        result[variant] = {key: entry[key] for key in ('base_color', 'orm')}
    result['normal'] = raw['normal']
    assert isinstance(result['normal'], str)
    return result


def read_export():
    manifest = read(MANIFEST)
    assert manifest.get('success') is True
    assert manifest.get('normal_convention') == 'OpenGL +Y', 'Expected declared source normal convention'
    rows = {row['name']: row for row in manifest['assets']}
    assert len(rows) == len(manifest['assets']) == len(MESH_NAMES) and set(rows) == set(MESH_NAMES)
    expected = {TARGET + '/' + name for name in (*MESH_NAMES, *ASSEMBLIES)}
    expected.update(MATERIAL_ROOT + '/' + name for name in MATERIAL_NAMES)
    inputs = {MANIFEST.name: digest(MANIFEST)}
    declared = manifest.get('sha256', {})
    for name, row in rows.items():
        assert row['fbx'] == name + '.fbx'
        assert int(row['triangles']) >= 2 and int(row['collision_hulls']) >= 1
        assert row['slots'] and len(row['slots']) == len(set(row['slots']))
        assert set(row['slots']) <= set(MATERIAL_NAMES), row['slots']
        point(row['pivot_m'])
        low, high = point(row['bounds_min_m']), point(row['bounds_max_m'])
        assert all(a < b for a, b in zip(low, high)), name
        path = source(row['fbx'])
        inputs[row['fbx']] = digest(path)
        if row['fbx'] in declared:
            assert inputs[row['fbx']] == declared[row['fbx']].lower(), str(path)
    budgets = {variant: sum(int(rows[PREFIX + part]['triangles']) for part in parts)
               for variant, parts in VARIANT_PARTS.items()}
    assert all(200 <= count <= 800 for count in budgets.values()), ('Variant LOD0 triangle budgets', budgets)
    textures = texture_spec(manifest)
    filenames = {textures[v][channel]: (2048 if v in VARIANTS else 512)
                 for v in MATERIAL_VARIANTS for channel in ('base_color', 'orm')}
    filenames[textures['normal']] = 2048
    assert len(filenames) == 15
    for filename, resolution in filenames.items():
        path = source(filename)
        assert image_dimensions(path) == [resolution, resolution], str(path)
        inputs[filename] = digest(path)
        if filename in declared:
            assert inputs[filename] == declared[filename].lower(), str(path)
        expected.add(TEXTURE_ROOT + '/' + path.stem)
    return manifest, rows, expected, inputs
