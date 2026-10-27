"""Immutable old courtyard boundary meshes for the original old-town map.

``recipes()`` and ``validate_recipe()`` run outside Unreal, without file I/O.
``build_assets(dest_root, materials)`` runs inside Unreal and creates three
new StaticMeshes in a caller-selected /Game/CodexGenerated/Hotel/... folder.
It neither loads a level nor edits any existing material, mesh or blueprint.

Material keys, in fixed slot order: plaster, brick, concrete, metal, rust.
Values may be existing MaterialInterface objects or existing asset paths.
All dimensions are centimetres. Local X runs along each wall; Y is its
thickness; Z=0 is ground contact. MainWall spans X=-1860..1860 and includes
a permanently closed double gate at X=-810..-310. SideWall700/600 have the
same finish and may be placed at yaw 90 by the caller. Each returned record
contains the exact recipe hash, measured mesh bounds and collision boxes.

The meshes are closed box/cylinder primitives merged into one mesh with
five material slots. Plaster skins are partitioned around exposed-brick
patches, rather than coplanar overlaid decals. Corrugations and hardware
have distinct outward depths. Repeated builds only read an existing asset
when both its recipe and material bindings match the immutable metadata.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path


SCHEMA = 'HotelFrontCourtyardBoundaryV1'
MATERIAL_ORDER = ('plaster', 'brick', 'concrete', 'metal', 'rust')
METADATA_KEY = 'CodexHotelFrontBoundaryRecipe'


def _box(parts, name, center, size, material):
    parts.append(dict(name=name, kind='box', center=list(center),
                      size=list(size), material=material))


def _cylinder(parts, name, center, radius, length, material, axis='Z'):
    parts.append(dict(name=name, kind='cylinder', center=list(center),
                      radius=float(radius), length=float(length), axis=axis,
                      radial_sides=12, material=material))


def _bounds_box(center, size):
    return [[c-s/2. for c, s in zip(center, size)],
            [c+s/2. for c, s in zip(center, size)]]


def _pier(parts, boxes, name, x):
    # Separate touching solids: the cap is 300 cm high including its top.
    _box(parts, name+'_Foot', [x, 0., 17.5], [48., 48., 35.], 'concrete')
    _box(parts, name+'_Body', [x, 0., 163.5], [44., 44., 257.], 'plaster')
    _box(parts, name+'_Cap', [x, 0., 296.], [52., 52., 8.], 'concrete')
    # Collision follows the cap envelope; it never crosses either gate jamb.
    boxes.append(_bounds_box([x, 0., 150.], [52., 52., 300.]))


def _wall_bay(parts, boxes, name, a, b, expose=False):
    if b <= a:
        raise ValueError('Wall bay has no width: '+name)
    mid, width = (a+b)/2., b-a
    _box(parts, name+'_Footing', [mid, 0., 16.], [width, 26., 32.], 'concrete')
    # Brick core's faces are at Y=+-11. Plaster is one cm thick and ends
    # at Y=+-12, so exposed brick sits one cm behind the plaster surface.
    _box(parts, name+'_BrickCore', [mid, 0., 156.], [width, 22., 248.], 'brick')
    _box(parts, name+'_BackPlaster', [mid, 11.5, 156.], [width, 1., 248.], 'plaster')
    if expose:
        patch_width = min(86., width*.30)
        patch_a = a+width*.15
        patch_b = patch_a+patch_width
        _box(parts, name+'_FrontUpperPlaster', [mid, -11.5, 190.],
             [width, 1., 180.], 'plaster')
        for suffix, lo, hi in (('L', a, patch_a), ('R', patch_b, b)):
            if hi-lo > .001:
                _box(parts, name+'_FrontLowerPlaster'+suffix,
                     [(lo+hi)/2., -11.5, 66.], [hi-lo, 1., 68.], 'plaster')
        # Raised individual brick courses add a few chipped edges inside
        # the unplastered opening; fronts remain recessed behind the skin.
        for row in range(4):
            z = 39.+15.*row
            for brick in range(3):
                lo = patch_a+brick*patch_width/3.+.8
                hi = patch_a+(brick+1)*patch_width/3.-.8
                _box(parts, name+'_ExposedBrick%d_%d' % (row, brick),
                     [(lo+hi)/2., -11.15, z], [hi-lo, .3, 12.], 'brick')
    else:
        _box(parts, name+'_FrontPlaster', [mid, -11.5, 156.],
             [width, 1., 248.], 'plaster')
    _box(parts, name+'_Coping', [mid, 0., 284.], [width, 32., 8.], 'concrete')
    boxes.append(_bounds_box([mid, 0., 144.], [width, 32., 288.]))


def _closed_gate(parts, boxes):
    # Opening is 500 cm wide. Jambs meet the masonry and do not narrow it.
    for side, x in (('L', -812.), ('R', -308.)):
        _box(parts, 'GateJamb'+side, [x, 0., 140.], [4., 10., 280.], 'metal')
    _box(parts, 'GateLintel', [-560., 0., 277.], [508., 10., 6.], 'metal')
    _box(parts, 'GateLintelCoping', [-560., 0., 284.],
         [500., 32., 8.], 'concrete')
    # A low concrete sill closes the under-door sightline to the map edge.
    _box(parts, 'GateSill', [-560., 0., 2.5], [500., 26., 5.], 'concrete')
    boxes.append(_bounds_box([-560., 0., 2.5], [500., 26., 5.]))
    # 0.3 cm at each jamb; 0.6 cm between leaves. The 2.4 cm centre lap
    # covers that join, so no straight-through view to the empty map edge.
    for side, a, b, hinge_x in (
            ('L', -809.7, -560.3, -807.7),
            ('R', -559.7, -310.3, -312.3)):
        mid, width = (a+b)/2., b-a
        prefix = 'Gate'+side
        _box(parts, prefix+'_Sheet', [mid, 0., 139.5], [width, 7., 269.], 'metal')
        for facing in (-1, 1):
            # Alternating sheet ribs use a second depth, not coplanar strips.
            count = 20
            for index in range(count):
                x = a+5.+index*(width-10.)/(count-1)
                _box(parts, prefix+'_Rib%d_%02d' % (facing, index),
                     [x, facing*4.5, 139.5], [3.2, 2., 259.], 'metal')
            for z in (19., 141., 260.):
                _box(parts, prefix+'_CrossRail%d_%d' % (facing, z),
                     [mid, facing*7., z], [width-6., 3., 6.], 'rust')
            # Each pull joins two mounting feet, and works from either side.
            pull_x = b-19. if side == 'L' else a+19.
            for z in (125., 151.):
                _box(parts, prefix+'_PullFoot%d_%d' % (facing, z),
                     [pull_x, facing*10., z], [4., 7., 4.], 'rust')
            _cylinder(parts, prefix+'_Pull%d' % facing,
                      [pull_x, facing*13., 138.], 1.8, 29., 'metal')
        for index, z in enumerate((39., 139.5, 240.)):
            _cylinder(parts, prefix+'_Hinge%d' % index,
                      [hinge_x, -7.5, z], 2.2, 15., 'rust')
            _box(parts, prefix+'_HingeStrap%d' % index,
                 [hinge_x+(12. if side == 'L' else -12.), -6.1, z],
                 [25., 1.8, 6.], 'rust')
        # Sparse rust patches lie proud of the panel, behind the corrugations.
        for index, (fraction, z) in enumerate(((.18, 54.), (.72, 89.), (.48, 218.))):
            _box(parts, prefix+'_Rust%d' % index,
                 [a+width*fraction, -3.65, z], [15.+index*4., .3, 9.+index*2.], 'rust')
        boxes.append(_bounds_box([mid, 0., 139.5], [width, 16., 269.]))
    _box(parts, 'GateCentreLap', [-560., -6.1, 139.5], [2.4, 2., 269.], 'metal')
    # Keep the physical barrier opaque at the visual centre lap as well.
    # The overlapping collision union leaves no 0.6 cm ray-through slit.
    boxes.append(_bounds_box([-560., 0., 139.5], [2.4, 16., 269.]))
    # Two overlapped clasp halves attach to their respective leaves.
    _box(parts, 'GateLatchPlateL', [-570., -10., 118.], [22., 4., 7.], 'rust')
    _box(parts, 'GateLatchPlateR', [-549.5, -10., 118.], [18., 4., 7.], 'metal')
    _cylinder(parts, 'GateLatchPin', [-560., -13., 118.], 1.7, 10., 'rust')


def _recipe(key, length, piers, gate=False):
    parts, boxes = [], []
    for index, x in enumerate(piers):
        _pier(parts, boxes, 'Pier%02d' % index, x)
    for index, (left, right) in enumerate(zip(piers, piers[1:])):
        if gate and left == -836. and right == -284.:
            continue
        _wall_bay(parts, boxes, 'Bay%02d' % index,
                  left+22., right-22., expose=index % 3 == 1)
    if gate:
        _closed_gate(parts, boxes)
    return dict(schema=SCHEMA, key=key, asset_type='Courtyard'+key,
                units='centimetres', along_axis='+X', thickness_axis='Y',
                ground_origin_z_cm=0., dimensions_cm=[float(length), 52., 300.],
                expected_bounds=[[-length/2., -26., 0.], [length/2., 26., 300.]],
                wall_height_cm=280., coping_height_cm=288., pier_height_cm=300.,
                closed_gate_opening=([-810., -310.] if gate else None),
                gate_leaf_gap_cm=(.6 if gate else None),
                gate_centre_lap_width_cm=(2.4 if gate else None),
                purpose=('Opaque old courtyard wall and solid closed double gate'
                         if gate else 'Matching short courtyard return wall'),
                primitives=parts, collision_boxes=boxes,
                collision_strategy='separate aligned boxes for bays, piers, sill and gate leaves')


def _return_recipe(key, length):
    # The parent main wall already supplies the end pier. Returning wall
    # bodies enter that pier below its 300 cm cap, avoiding two coplanar
    # cap faces at a right-angle corner. Only the free-standing centre pier
    # is retained. Both ends remain full-thickness, opaque ordinary wall.
    parts, boxes = [], []
    _pier(parts, boxes, 'PierCentre', 0.)
    _wall_bay(parts, boxes, 'BayL', -length/2., -22., expose=True)
    _wall_bay(parts, boxes, 'BayR', 22., length/2., expose=False)
    row = _recipe(key, length, [], gate=False)
    row['primitives'] = parts
    row['collision_boxes'] = boxes
    row['purpose'] = 'Matching return wall with plain 288 cm ends and one 300 cm centre pier'
    row['end_connection'] = dict(end_piers=False, end_coping_height_cm=288.,
                                 centre_pier_height_cm=300.,
                                 strategy='plain wall ends join inside the main wall pier below its cap')
    return row


def recipes():
    """Return fresh JSON-safe recipes; no Unreal import and no writes."""
    return {
        'MainWall': _recipe('MainWall', 3720.,
                            [-1834., -1490., -1160., -836., -284.,
                             140., 564., 988., 1412., 1834.], gate=True),
        'SideWall700': _return_recipe('SideWall700', 700.),
        'SideWall600': _return_recipe('SideWall600', 600.),
    }


def _part_bounds(part):
    if part['kind'] == 'box':
        extent = [v/2. for v in part['size']]
    elif part['kind'] == 'cylinder':
        extent = [part['radius']]*3
        extent['XYZ'.index(part['axis'])] = part['length']/2.
    else:
        raise ValueError('Unsupported primitive: '+str(part['kind']))
    return [[part['center'][i]-extent[i] for i in range(3)],
            [part['center'][i]+extent[i] for i in range(3)]]


def validate_recipe(recipe):
    """Check dimensions, sealed gate geometry and bounded closed collision."""
    parts = recipe['primitives']
    if not parts or len({p['name'] for p in parts}) != len(parts):
        raise ValueError('Missing or duplicate primitive names')
    for part in parts:
        sizes = part['size'] if part['kind'] == 'box' else [part['radius'], part['length']]
        if (min(sizes) <= 0 or part['material'] not in MATERIAL_ORDER or
                not all(math.isfinite(float(v)) for v in part['center']+sizes)):
            raise ValueError('Invalid primitive: '+part['name'])
    bounds = [_part_bounds(p) for p in parts]
    measured = [[min(b[0][i] for b in bounds) for i in range(3)],
                [max(b[1][i] for b in bounds) for i in range(3)]]
    expected = recipe['expected_bounds']
    if any(abs(measured[j][i]-expected[j][i]) > 1.e-6
           for j in range(2) for i in range(3)):
        raise ValueError('Unexpected render bounds: '+str(measured))
    for lo, hi in recipe['collision_boxes']:
        if not all(expected[0][i] <= lo[i] < hi[i] <= expected[1][i] for i in range(3)):
            raise ValueError('Collision exceeds render bounds')
    gate = recipe['closed_gate_opening'] is not None
    if gate:
        by_name = {p['name']: p for p in parts}
        left = _part_bounds(by_name['GateL_Sheet'])
        right = _part_bounds(by_name['GateR_Sheet'])
        lap = _part_bounds(by_name['GateCentreLap'])
        if abs(right[0][0]-left[1][0]-.6) > 1.e-6:
            raise ValueError('Gate leaves must have a 0.6 cm join')
        if not lap[0][0] < left[1][0] < right[0][0] < lap[1][0]:
            raise ValueError('Centre lap does not cover the gate join')
        if by_name['GateSill']['size'][2] != left[0][2]:
            raise ValueError('Gate sill does not meet door bottoms')
    triangles = sum(12 if p['kind'] == 'box' else 4*p['radial_sides'] for p in parts)
    return dict(passed=True, bounds=measured, primitive_count=len(parts),
                closed_primitive_count=len(parts), material_slot_count=5,
                estimated_triangle_count=triangles,
                collision_box_count=len(recipe['collision_boxes']),
                opaque_gate=gate, coplanar_plaster_overlays=False)


def _result(value):
    if isinstance(value, tuple):
        import unreal
        if len(value) > 1 and value[1] != unreal.GeometryScriptOutcomePins.SUCCESS:
            raise RuntimeError('GeometryScript operation failed: '+str(value[1]))
        return value[0]
    return value


def _dynamic_mesh(unreal, parts):
    mesh = unreal.DynamicMesh()
    method = next((getattr(mesh, name, None)
                   for name in ('enable_material_i_ds', 'enable_material_ids')
                   if callable(getattr(mesh, name, None))), None)
    if method is None:
        raise RuntimeError('DynamicMesh material ID API unavailable')
    method()
    for part in parts:
        options = unreal.GeometryScriptPrimitiveOptions()
        options.set_editor_property('material_id', MATERIAL_ORDER.index(part['material']))
        transform = unreal.Transform(
            location=unreal.Vector(*part['center']),
            rotation=unreal.Rotator(pitch=90. if part.get('axis') == 'X' else 0.,
                                    yaw=0., roll=90. if part.get('axis') == 'Y' else 0.),
            scale=unreal.Vector(1., 1., 1.))
        if part['kind'] == 'box':
            mesh = _result(unreal.GeometryScript_Primitives.append_box(
                mesh, options, transform, *part['size'], 0, 0, 0,
                unreal.GeometryScriptPrimitiveOriginMode.CENTER))
        else:
            mesh = _result(unreal.GeometryScript_Primitives.append_cylinder(
                mesh, options, transform, part['radius'], part['length'],
                part['radial_sides'], 1, True,
                unreal.GeometryScriptPrimitiveOriginMode.CENTER))
    return mesh


def _apply_collision(unreal, mesh, boxes):
    parts = []
    for index, (lo, hi) in enumerate(boxes):
        _box(parts, 'Collision%02d' % index,
             [(a+b)/2. for a, b in zip(lo, hi)],
             [b-a for a, b in zip(lo, hi)], 'concrete')
    generation = unreal.GeometryScriptCollisionFromMeshOptions()
    for key, value in dict(method=unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES,
                           auto_detect_spheres=False, auto_detect_capsules=False,
                           auto_detect_boxes=True).items():
        generation.set_editor_property(key, value)
    options = unreal.GeometryScriptSetStaticMeshCollisionOptions()
    options.set_editor_property('mark_as_customized', True)
    unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(
        _dynamic_mesh(unreal, parts), mesh, generation, options)


def build_assets(dest_root, materials):
    """Create/read immutable meshes and return JSON-safe records keyed by recipe.

    Requires a dedicated directory under /Game/CodexGenerated/Hotel/. Existing
    material assets are read only. An existing mesh is never changed or saved.
    The immutable SHA includes every primitive, collision box and material path.
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
            raise ValueError('Existing material missing for slot: '+key)
        material_objects.append(material)
    material_paths = {key: obj.get_path_name()
                      for key, obj in zip(MATERIAL_ORDER, material_objects)}
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
        path = '%s/SM_Hotel_%s_L%d_%s' % (
            dest_root, row['asset_type'], int(row['dimensions_cm'][0]), digest[:10])
        created = not assets.does_asset_exist(path)
        if not created:
            mesh = unreal.load_asset(path)
            if not isinstance(mesh, unreal.StaticMesh):
                raise RuntimeError('Existing destination is not a StaticMesh: '+path)
            if assets.get_metadata_tag(mesh, METADATA_KEY) != encoded:
                raise RuntimeError('Refusing to overwrite an existing asset: '+path)
        else:
            dynamic = _dynamic_mesh(unreal, row['primitives'])
            create = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
            for prop, value in dict(enable_recompute_normals=True,
                                    enable_recompute_tangents=True, enable_nanite=False,
                                    enable_collision=False).items():
                create.set_editor_property(prop, value)
            mesh = _result(unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
                dynamic, path, create))
            copy = unreal.GeometryScriptCopyMeshToAssetOptions()
            for prop, value in dict(enable_recompute_normals=True,
                                    enable_recompute_tangents=True, replace_materials=True,
                                    new_materials=material_objects,
                                    new_material_slot_names=[unreal.Name(n) for n in MATERIAL_ORDER],
                                    emit_transaction=False).items():
                copy.set_editor_property(prop, value)
            lod = unreal.GeometryScriptMeshWriteLOD()
            lod.set_editor_property('lod_index', 0)
            _result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
                dynamic, mesh, copy, lod, True))
            _apply_collision(unreal, mesh, row['collision_boxes'])
            assets.set_metadata_tag(mesh, METADATA_KEY, encoded)
            if not assets.save_loaded_asset(mesh, False):
                raise RuntimeError('Could not save new courtyard mesh: '+path)
        actual = mesh.get_bounds()
        measured = [[float(getattr(actual.origin, axis)-getattr(actual.box_extent, axis))
                     for axis in ('x', 'y', 'z')],
                    [float(getattr(actual.origin, axis)+getattr(actual.box_extent, axis))
                     for axis in ('x', 'y', 'z')]]
        if any(abs(measured[j][i]-row['expected_bounds'][j][i]) > .001
               for j in range(2) for i in range(3)):
            raise RuntimeError('Built mesh has unexpected local bounds: '+path+str(measured))
        bound_materials = [slot.get_editor_property('material_interface').get_path_name()
                           for slot in mesh.get_editor_property('static_materials')]
        if bound_materials != [material_paths[k] for k in MATERIAL_ORDER]:
            raise RuntimeError('Built mesh has unexpected material slots: '+path)
        content_root = Path(unreal.Paths.convert_relative_path_to_full(
            unreal.Paths.project_content_dir()))
        package_file = content_root.joinpath(*path[len('/Game/'):].split('/')).with_suffix('.uasset')
        if not package_file.is_file():
            raise RuntimeError('Immutable mesh has no saved package file: '+str(package_file))
        asset_file_sha256 = hashlib.sha256(package_file.read_bytes()).hexdigest()
        output[key] = dict(asset=mesh.get_path_name(), package=path, created=created,
                           file=str(package_file), file_sha256=asset_file_sha256,
                           bounds=measured, expected_bounds=deepcopy(row['expected_bounds']),
                           dimensions_cm=row['dimensions_cm'][:], ground_origin_z_cm=0.,
                           along_axis='+X', thickness_axis='Y',
                           materials=material_paths.copy(), recipe_sha256=digest,
                           recipe=deepcopy(row), geometry_proof=validate_recipe(row),
                           collision_boxes=deepcopy(row['collision_boxes']))
    return output
