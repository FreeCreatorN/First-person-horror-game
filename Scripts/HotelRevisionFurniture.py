"""Private, low service furniture for the original hotel revision.

Importing this module does not import Unreal or write files. ``recipes()`` and
``validate_recipe()`` can be inspected offline. ``build_assets(dest_root,
materials)`` runs inside Unreal and creates immutable StaticMeshes only below
the caller's new /Game/CodexGenerated/Hotel directory. It never edits supplied
materials or an existing asset. Materials must map wood/metal/ceramic/cloth to
existing material objects or object paths.

Units are centimetres. Every mesh has its ground contact at Z=0, its XY centre
at zero, its usable front toward -X, and a 70 cm depth / 90 cm maximum height.
Return values are JSON-safe records keyed by the four old shelf suffixes;
load record['asset'] when assigning the mesh. Each record includes local
render bounds, simple collision boxes and the immutable primitive recipe.
"""
from copy import deepcopy
import hashlib
import json
import math


SCHEMA = 'HotelRevisionLowFurnitureV1'
MATERIAL_ORDER = ('wood', 'metal', 'ceramic', 'cloth')
METADATA_KEY = 'CodexHotelRevisionFurnitureRecipe'


def _box(parts, name, center, size, material):
    parts.append(dict(name=name, kind='box', center=list(center),
                      size=list(size), material=material))


def _cylinder(parts, name, center, radius, length, material, axis='Z'):
    parts.append(dict(name=name, kind='cylinder', center=list(center),
                      radius=float(radius), length=float(length), axis=axis,
                      radial_sides=16, material=material))


def _base(parts, width, height=90.):
    # The four feet actually contact the floor; the plinth joins their tops.
    for xi, x in enumerate((-25., 25.)):
        for yi, y in enumerate((-width/2+8., width/2-8.)):
            _box(parts, 'Foot%d%d' % (xi, yi), [x, y, 4.], [6., 8., 8.], 'metal')
    _box(parts, 'Plinth', [0., 0., 10.], [62., width-4., 4.], 'metal')
    _box(parts, 'Back', [33.5, 0., (height+12.)/2],
         [3., width, height-12.], 'wood')
    for side in (-1, 1):
        _box(parts, 'Side' + str(side), [0., side*(width/2-1.5), (height+12.)/2],
             [64., 3., height-12.], 'wood')


def _clean_linen():
    p = []
    width = 320.
    _base(p, width)
    for index, z in enumerate((12., 40., 67., 87.)):
        _box(p, 'Shelf%02d' % index, [0., 0., z+1.5],
             [64., width-6., 3.], 'wood')
    bay = (width-6.)/5
    for index in range(1, 5):
        y = -width/2+3.+index*bay
        _box(p, 'Divider%02d' % index, [0., y, 51.], [64., 2.5, 72.], 'wood')
    for index in range(5):
        y = -width/2+3.+(index+.5)*bay
        for row, shelf_top in enumerate((15., 43.)):
            for layer in range(3):
                # Stepped folds give the linen recognisable stacked edges.
                _box(p, 'FoldedLinen%d_%d_%d' % (index, row, layer),
                     [-2.+.4*(layer%2), y+.5*(layer%2), shelf_top+2.1+4.2*layer],
                     [49.-layer, 49.-layer, 4.2], 'cloth')
        for side in (-1, 1):
            _cylinder(p, 'RolledTowel%d_%d' % (index, side),
                      [-3., y+side*13., 75.5], 5.5, 44., 'cloth', 'X')
    # A ceramic inventory plate is inset into the front of the upper rail.
    _box(p, 'InventoryPlate', [-32.6, 0., 88.5], [.8, 22., 2.5], 'ceramic')
    # These small corner guards establish the exact 70 cm outer depth.
    for side in (-1, 1):
        _box(p, 'FrontCornerGuard'+str(side), [-33.5, side*158.5, 49.5],
             [3., 3., 75.], 'metal')
    return _recipe('CleanLinenShelf', 'CleanLinenCabinet', width, p,
                   'Five open bays with folded linen and rolled towels',
                   [[[ -35., -160., 0.], [35., 160., 90.]]])


def _dirty_linen():
    p = []
    # Three genuinely separated carts, including floor-contacting wheels.
    for n, cy in enumerate((-110., 0., 110.)):
        def box(name, center, size, material):
            center = list(center); center[1] += cy
            _box(p, 'Cart%d_' % n+name, center, size, material)
        def cylinder(name, center, radius, length, material, axis):
            center = list(center); center[1] += cy
            _cylinder(p, 'Cart%d_' % n+name, center, radius, length, material, axis)
        for xi, x in enumerate((-23., 23.)):
            for yi, y in enumerate((-40., 40.)):
                cylinder('Wheel%d%d' % (xi, yi), [x, y, 6.], 6., 5., 'metal', 'Y')
                box('Caster%d%d' % (xi, yi), [x, y, 12.], [5., 5., 7.], 'metal')
        box('Base', [0., 0., 18.], [64., 98., 5.], 'metal')
        box('BagBottom', [0., 0., 22.], [60., 94., 4.], 'cloth')
        for side in (-1, 1):
            box('BagX'+str(side), [side*29., 0., 51.], [3., 94., 56.], 'cloth')
            box('BagY'+str(side), [0., side*46., 51.], [56., 3., 56.], 'cloth')
            box('TopRimX'+str(side), [side*33., 0., 80.], [4., 100., 4.], 'metal')
            box('TopRimY'+str(side), [0., side*48., 80.], [62., 4., 4.], 'metal')
            for yside in (-1, 1):
                box('Corner%d%d' % (side, yside), [side*30.5, yside*47., 50.],
                    [3., 3., 60.], 'metal')
            box('PushHandleSupport'+str(side), [30.5, side*27., 84.],
                [3., 3., 10.], 'metal')
        cylinder('PushHandle', [30.5, 0., 88.5], 1.5, 57., 'metal', 'Y')
        # Visible rumpled loads remain below the 90 cm window-safe height.
        for j, (x, y, z) in enumerate(((-10., -24., 75.), (9., 2., 77.), (-7., 25., 76.))):
            box('LinenLoad%d' % j, [x, y, z], [29., 34., 12.], 'cloth')
        box('SortLabel', [-30.9, 0., 52.], [.8, 24., 12.], 'ceramic')
        for j in range(n+1):
            box('LabelMark%d' % j, [-31.7, -4.*n+8.*j, 52.], [.8, 2., 7.], 'metal')
    return _recipe('DirtyLinenShelf', 'LinenSortingCarts', 320., p,
                   'Three labelled wheeled linen sorting bins',
                   [[[-35., y-50., 0.], [35., y+50., 90.]] for y in (-110., 0., 110.)])


def _changing():
    p = []
    width = 300.
    _base(p, width)
    _box(p, 'Top', [0., 0., 88.5], [70., width, 3.], 'wood')
    _box(p, 'Bottom', [0., 0., 13.5], [64., width-6., 3.], 'wood')
    for n in range(4):
        y = -112.5+75.*n
        _box(p, 'LockerDoor%d' % n, [-30., y, 50.], [3., 71., 73.], 'wood')
        _box(p, 'LockPlate%d' % n, [-32.1, y-21., 46.], [1.2, 8., 18.], 'metal')
        _box(p, 'Handle%d' % n, [-34., y-21., 46.], [2., 2.5, 12.], 'metal')
        _box(p, 'NumberPlate%d' % n, [-32., y+9., 72.], [1., 15., 6.], 'ceramic')
        for j in range(3):
            _box(p, 'Vent%d_%d' % (n, j), [-31.8, y, 60.+3.*j],
                 [.6, 34., 1.], 'metal')
        if n < 3:
            _box(p, 'LockerPartition%d' % n, [0., y+37.5, 51.],
                 [62., 2., 72.], 'wood')
    return _recipe('ChangingShelf', 'StaffLockersLow', width, p,
                   'Four separate staff lockers with vents, pulls and number plates',
                   [[[-35., -150., 0.], [35., 150., 90.]]])


def _equipment():
    p = []
    width = 180.
    # A 66 cm-high work surface leaves room for a short attached tool board.
    _base(p, width, height=63.)
    _box(p, 'Worktop', [0., 0., 64.5], [70., width, 3.], 'wood')
    _box(p, 'Bottom', [0., 0., 13.5], [64., width-6., 3.], 'wood')
    for n, y in enumerate((-58., 0.)):
        _box(p, 'CupboardDoor%d' % n, [-30., y, 37.], [3., 55., 46.], 'wood')
        _box(p, 'CupboardPull%d' % n, [-34., y+17., 38.], [2., 3., 12.], 'metal')
    for n, z in enumerate((22., 37.5, 53.)):
        _box(p, 'Drawer%d' % n, [-30., 60., z], [3., 52., 13.], 'wood')
        _box(p, 'DrawerPull%d' % n, [-34., 60., z], [2., 22., 2.5], 'metal')
    _box(p, 'ToolBoard', [31., 0., 77.5], [3., 174., 25.], 'wood')
    _box(p, 'ToolBoardTopRail', [28.8, 0., 89.], [1.4, 176., 2.], 'metal')
    for side in (-1, 1):
        _box(p, 'ToolBoardSideRail'+str(side), [28.8, side*87., 77.],
             [1.4, 2., 24.], 'metal')
    for n, y in enumerate((-66., -24., 18., 60.)):
        _box(p, 'ToolClip%d' % n, [27.5, y, 79.], [5., 4., 3.], 'metal')
    _box(p, 'HammerHandle', [24.5, -66., 76.5], [2.5, 3., 15.], 'wood')
    _box(p, 'HammerHead', [24.5, -66., 85.], [5., 14., 4.], 'metal')
    _box(p, 'ScrewdriverHandle', [24.5, -24., 73.], [4., 4., 9.], 'wood')
    _box(p, 'ScrewdriverBlade', [24.5, -24., 82.], [1.5, 1.5, 10.], 'metal')
    _box(p, 'SpannerShaft', [24.5, 18., 76.], [2., 3., 15.], 'metal')
    _box(p, 'SpannerJawBase', [24.5, 18., 84.], [2., 9., 2.5], 'metal')
    for side in (-1, 1):
        _box(p, 'SpannerJaw'+str(side), [24.5, 18.+side*3.8, 86.],
             [2., 2., 5.], 'metal')
    _box(p, 'PliersLeft', [24.5, 57.5, 76.], [2.5, 2.5, 16.], 'metal')
    _box(p, 'PliersRight', [24.5, 62.5, 76.], [2.5, 2.5, 16.], 'metal')
    _box(p, 'PliersPivot', [24.5, 60., 82.], [4., 8., 3.], 'metal')
    # A shallow parts tray rests directly on the worktop.
    _box(p, 'PartsTrayBottom', [-6., -40., 66.7], [34., 42., 1.4], 'ceramic')
    for side in (-1, 1):
        _box(p, 'PartsTraySideX'+str(side), [-6.+side*16., -40., 69.],
             [2., 42., 4.], 'ceramic')
        _box(p, 'PartsTraySideY'+str(side), [-6., -40.+side*20., 69.],
             [30., 2., 4.], 'ceramic')
    for n in range(6):
        _cylinder(p, 'SparePart%d' % n, [-12.+(n%2)*12., -52.+(n//2)*12., 69.],
                  2.5, 3.2, 'metal')
    return _recipe('EquipmentShelf', 'ServiceWorkbenchLow', width, p,
                   'Cupboard and drawer workbench with attached tools and parts tray',
                   [[[-35., -90., 0.], [35., 90., 90.]]])


def _recipe(key, asset_type, width, parts, purpose, collision_boxes):
    return dict(schema=SCHEMA, key=key, asset_type=asset_type,
                units='centimetres', front_axis='-X', ground_origin_z_cm=0.,
                dimensions_cm=[70., float(width), 90.],
                expected_bounds=[[-35., -width/2, 0.], [35., width/2, 90.]],
                purpose=purpose, primitives=parts,
                collision_boxes=collision_boxes,
                collision_strategy='one closed aligned box per cabinet or cart')


def recipes():
    """Return fresh immutable-build inputs, without Unreal or file I/O."""
    return {row['key']: row for row in
            (_clean_linen(), _dirty_linen(), _changing(), _equipment())}


def _part_bounds(part):
    if part['kind'] == 'box':
        extent = [v/2. for v in part['size']]
    elif part['kind'] == 'cylinder':
        extent = [part['radius']]*3
        extent['XYZ'.index(part['axis'])] = part['length']/2.
    else:
        raise ValueError('Unsupported primitive: ' + str(part['kind']))
    return [[part['center'][i]-extent[i] for i in range(3)],
            [part['center'][i]+extent[i] for i in range(3)]]


def validate_recipe(recipe):
    """Verify finite closed solids, contact bounds and safe overall dimensions."""
    parts = recipe['primitives']
    if not parts or len({p['name'] for p in parts}) != len(parts):
        raise ValueError('Missing primitives or duplicate primitive names')
    for part in parts:
        values = part['center'] + (part['size'] if part['kind'] == 'box'
                                   else [part['radius'], part['length']])
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError('Nonfinite primitive: ' + part['name'])
        sizes = part['size'] if part['kind'] == 'box' else [part['radius'], part['length']]
        if min(sizes) <= 0 or part['material'] not in MATERIAL_ORDER:
            raise ValueError('Invalid primitive: ' + part['name'])
    bounds = [_part_bounds(p) for p in parts]
    measured = [[min(b[0][i] for b in bounds) for i in range(3)],
                [max(b[1][i] for b in bounds) for i in range(3)]]
    expected = recipe['expected_bounds']
    if any(abs(measured[j][i]-expected[j][i]) > 1.e-6
           for j in range(2) for i in range(3)):
        raise ValueError('Furniture exceeds or misses specified bounds: ' + str(measured))
    for lo, hi in recipe['collision_boxes']:
        if not all(expected[0][i] <= lo[i] < hi[i] <= expected[1][i] for i in range(3)):
            raise ValueError('Collision outside render bounds')
    triangles = sum(12 if p['kind'] == 'box' else 4*p['radial_sides'] for p in parts)
    return dict(passed=True, bounds=measured, primitive_count=len(parts),
                closed_primitive_count=len(parts), estimated_triangle_count=triangles,
                collision_box_count=len(recipe['collision_boxes']))


def _result(value):
    if isinstance(value, tuple):
        import unreal
        if len(value) > 1 and value[1] != unreal.GeometryScriptOutcomePins.SUCCESS:
            raise RuntimeError('GeometryScript operation failed: ' + str(value[1]))
        return value[0]
    return value


def _enable_material_ids(mesh):
    for name in ('enable_material_i_ds', 'enable_material_ids'):
        method = getattr(mesh, name, None)
        if callable(method):
            method()
            return
    raise RuntimeError('DynamicMesh material ID API unavailable')


def _dynamic_mesh(unreal, parts):
    mesh = unreal.DynamicMesh()
    _enable_material_ids(mesh)
    for p in parts:
        options = unreal.GeometryScriptPrimitiveOptions()
        options.set_editor_property('material_id', MATERIAL_ORDER.index(p['material']))
        pitch = 90. if p.get('axis') == 'X' else 0.
        roll = 90. if p.get('axis') == 'Y' else 0.
        transform = unreal.Transform(location=unreal.Vector(*p['center']),
                                     rotation=unreal.Rotator(pitch=pitch, yaw=0., roll=roll),
                                     scale=unreal.Vector(1., 1., 1.))
        if p['kind'] == 'box':
            mesh = _result(unreal.GeometryScript_Primitives.append_box(
                mesh, options, transform, *p['size'], 0, 0, 0,
                unreal.GeometryScriptPrimitiveOriginMode.CENTER))
        else:
            mesh = _result(unreal.GeometryScript_Primitives.append_cylinder(
                mesh, options, transform, p['radius'], p['length'],
                p['radial_sides'], 1, True,
                unreal.GeometryScriptPrimitiveOriginMode.CENTER))
    return mesh


def _collision_mesh(unreal, boxes):
    parts = []
    for index, (lo, hi) in enumerate(boxes):
        _box(parts, 'Collision%02d' % index, [(a+b)/2 for a, b in zip(lo, hi)],
             [b-a for a, b in zip(lo, hi)], 'wood')
    return _dynamic_mesh(unreal, parts)


def _apply_collision(unreal, mesh, boxes):
    generation = unreal.GeometryScriptCollisionFromMeshOptions()
    generation.set_editor_property('method', unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES)
    generation.set_editor_property('auto_detect_spheres', False)
    generation.set_editor_property('auto_detect_capsules', False)
    generation.set_editor_property('auto_detect_boxes', True)
    options = unreal.GeometryScriptSetStaticMeshCollisionOptions()
    options.set_editor_property('mark_as_customized', True)
    unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(
        _collision_mesh(unreal, boxes), mesh, generation, options)


def build_assets(dest_root, materials):
    """Create four new immutable furniture assets and return JSON-safe records.

    Existing destination assets are reusable only when their full recipe and
    material bindings match exactly. No existing asset is rebuilt or saved.
    The supplied materials are loaded/read and assigned, never modified.
    """
    import unreal
    if (not isinstance(dest_root, str) or
            not dest_root.startswith('/Game/CodexGenerated/Hotel/') or
            '..' in dest_root or '.' in dest_root or '\\' in dest_root):
        raise ValueError('Use a new private /Game/CodexGenerated/Hotel/... directory')
    dest_root = dest_root.rstrip('/')
    material_objects = []
    for key in MATERIAL_ORDER:
        item = materials[key]
        material = unreal.load_asset(item) if isinstance(item, str) else item
        if not isinstance(material, unreal.MaterialInterface):
            raise ValueError('Existing material missing for slot: ' + key)
        material_objects.append(material)
    material_paths = {k: obj.get_path_name() for k, obj in zip(MATERIAL_ORDER, material_objects)}
    rows = recipes()
    for row in rows.values():
        validate_recipe(row)
    assets = unreal.EditorAssetLibrary
    assets.make_directory(dest_root)
    output = {}
    for key, row in rows.items():
        encoded = json.dumps(dict(recipe=row, materials=material_paths),
                             ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        width = int(row['dimensions_cm'][1])
        path = '%s/SM_Hotel_%s_W%d_D70_H90_%s' % (
            dest_root, row['asset_type'], width, digest[:10])
        created = not assets.does_asset_exist(path)
        if not created:
            mesh = unreal.load_asset(path)
            if not isinstance(mesh, unreal.StaticMesh):
                raise RuntimeError('Existing destination is not a StaticMesh: ' + path)
            if assets.get_metadata_tag(mesh, METADATA_KEY) != encoded:
                raise RuntimeError('Refusing to overwrite an existing asset: ' + path)
        else:
            dynamic = _dynamic_mesh(unreal, row['primitives'])
            create = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
            for k, v in dict(enable_recompute_normals=True,
                             enable_recompute_tangents=True, enable_nanite=False,
                             enable_collision=False).items():
                create.set_editor_property(k, v)
            mesh = _result(unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
                dynamic, path, create))
            copy = unreal.GeometryScriptCopyMeshToAssetOptions()
            for k, v in dict(enable_recompute_normals=True,
                             enable_recompute_tangents=True, replace_materials=True,
                             new_materials=material_objects,
                             new_material_slot_names=[unreal.Name(n) for n in MATERIAL_ORDER],
                             emit_transaction=False).items():
                copy.set_editor_property(k, v)
            lod = unreal.GeometryScriptMeshWriteLOD()
            lod.set_editor_property('lod_index', 0)
            _result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
                dynamic, mesh, copy, lod, True))
            _apply_collision(unreal, mesh, row['collision_boxes'])
            assets.set_metadata_tag(mesh, METADATA_KEY, encoded)
            if not assets.save_loaded_asset(mesh, False):
                raise RuntimeError('Could not save new furniture: ' + path)
        actual = mesh.get_bounds()
        measured = [[float(getattr(actual.origin, axis)-getattr(actual.box_extent, axis))
                     for axis in ('x', 'y', 'z')],
                    [float(getattr(actual.origin, axis)+getattr(actual.box_extent, axis))
                     for axis in ('x', 'y', 'z')]]
        if any(abs(measured[j][i]-row['expected_bounds'][j][i]) > .001
               for j in range(2) for i in range(3)):
            raise RuntimeError('Built asset has unexpected local bounds: ' + path + str(measured))
        bound_materials = [slot.get_editor_property('material_interface').get_path_name()
                           for slot in mesh.get_editor_property('static_materials')]
        if bound_materials != [material_paths[k] for k in MATERIAL_ORDER]:
            raise RuntimeError('Built asset has unexpected material slots: ' + path)
        output[key] = dict(asset=mesh.get_path_name(), package=path, created=created,
                           bounds=measured, expected_bounds=deepcopy(row['expected_bounds']),
                           dimensions_cm=row['dimensions_cm'][:],
                           ground_origin_z_cm=0., front_axis='-X',
                           materials=material_paths.copy(), recipe_sha256=digest,
                           recipe=deepcopy(row), geometry_proof=validate_recipe(row),
                           collision_boxes=deepcopy(row['collision_boxes']))
    return output
