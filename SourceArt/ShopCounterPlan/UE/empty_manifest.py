"""Contract for replacing the current counter with the empty, exploded-parts version."""
from counter_manifest import (HERE, ASSET, PROJECT, CONTENT, EXPORTS, MANIFEST, TARGET, DESTINATION,
    PREFIX, TEXTURE_ROOT, MATERIAL_ROOT, PARENT, GLASS, BLUEPRINT, TEXTURES, DOORS,
    digest, read, write, source, packages, protected_snapshot, verify_protected, image_dimensions)

PARTS = ('Body', 'MetalFrame', 'GlassTop', 'GlassSurround', 'DisplayShelf', 'InteriorShelf',
         'WoodDoorLeft', 'WoodDoorRight', 'GlassDoorLeft', 'GlassDoorRight')
MESH_NAMES = tuple(PREFIX + part for part in PARTS)
LEGACY_GLASS = TARGET + '/' + PREFIX + 'FixedGlass'
GROUPS = {'WoodSlidingDoors': ('WoodDoorLeft', 'WoodDoorRight'),
          'GlassSlidingDoors': ('GlassDoorLeft', 'GlassDoorRight')}
PLANNING = {'GlassTop': '玻璃顶板', 'GlassSurround': '玻璃围挡', 'MetalFrame': '金属框架',
            'DisplayShelf': '展示层板', 'Body': '木质柜体（储物）',
            'WoodSlidingDoors': '推拉柜门', 'GlassSlidingDoors': '推拉玻璃门', 'InteriorShelf': '内部层板'}

def read_export():
    manifest = read(MANIFEST)
    assert manifest['success'] is True
    rows = {row['name']: row for row in manifest['assets']}
    assert len(rows) == len(manifest['assets']) == 10 and set(rows) == set(MESH_NAMES)
    resolution = manifest['baked_resolution']
    assert isinstance(resolution, int) and resolution >= 512
    total = sum(int(row['triangles']) for row in rows.values())
    assert 1800 <= total <= 3500, total
    assert rows[PREFIX+'GlassTop']['triangles'] == 12
    assert rows[PREFIX+'GlassSurround']['triangles'] == 36
    expected = {MATERIAL_ROOT+'/'+PARENT, MATERIAL_ROOT+'/'+GLASS, TARGET+'/'+BLUEPRINT}
    inputs = {MANIFEST.name: digest(MANIFEST)}
    sources = manifest['sha256']
    for name, row in rows.items():
        assert row['fbx'] == name+'.fbx'
        assert int(row['triangles']) >= 12 and int(row['collision_hulls']) >= 1
        assert row['slots'] and len(row['slots']) == len(set(row['slots']))
        assert set(row['slots']) <= {'M_ShopCounter_Opaque', 'M_ShopCounter_Glass'}
        minimum, maximum = row['bounds_min_m'], row['bounds_max_m']
        assert len(minimum) == len(maximum) == 3 and all(a < b for a,b in zip(minimum, maximum))
        expected.add(TARGET+'/'+name)
        path = source(row['fbx'])
        assert digest(path) == sources[row['fbx']].lower(), path
        inputs[row['fbx']] = digest(path)
    for relative in TEXTURES.values():
        path = source(relative)
        assert digest(path) == sources[relative].lower(), path
        inputs[relative] = digest(path)
        assert image_dimensions(path) == [resolution, resolution]
        expected.add(TEXTURE_ROOT+'/'+path.stem)
    assert set(manifest['doors']) == set(DOORS)
    for key, component in DOORS.items():
        spec = manifest['doors'][key]
        assert spec['mesh'] == PREFIX+component
        assert len(spec['closed_ue_cm']) == len(spec['pivot_m']) == 3
        sign = 1 if key.endswith('left') else -1
        assert 20 <= sign*float(spec['travel_cm']) <= 110
        pivot = spec['pivot_m']
        assert all(abs(a-b) < .003 for a,b in zip(spec['closed_ue_cm'], [100*pivot[0],-100*pivot[1],100*pivot[2]]))
    assert 'FixedGlass' not in PARTS
    return manifest, rows, expected, inputs
