"""Reposition guest basins and their existing colliders in the original hotel.

The shared basin, material packages, walls and ground-floor basins are not
edited. The calling script owns saving and independently validating the map.
"""
import re
from pathlib import Path
import hashlib

import OldTownNonLightEmission as scope


TARGET = scope.TARGET
BASIN = '/Game/CodexGenerated/Hotel/Meshes/SM_Hotel_Washbasin.SM_Hotel_Washbasin'
GUEST = re.compile(r'OTS_HotelV4_Room([234]0[1-9])_Basin')
GROUND = ('OTS_HotelV4_PublicWCBasin0', 'OTS_HotelV4_PublicWCBasin1', 'OTS_HotelV4_StaffWCBasin')
EPS = .06
CAP_ROOT = '/Game/CodexGenerated/Hotel/Meshes/BasinConnections_20261113'
CAP_NAME = 'SM_Hotel_Basin_StackCleanoutCap'
CAP_LABEL = '_StackCleanoutCap_20261113'
# Source riser center (12,0), outer radius 2.5, top at 66.0 cm. The existing
# chrome collar spans 64.4–65.6. This plug sits above the trap side branch.
CAP_LOCAL = [12., 0., 65.93]
CAP_RADIUS = 2.52
CAP_HEIGHT = .34


def _v(value):
    return [float(value.x), float(value.y), float(value.z)]


def _pose(actor):
    rot = actor.get_actor_rotation()
    return dict(location=_v(actor.get_actor_location()), scale=_v(actor.get_actor_scale3d()),
                rotation=[float(rot.pitch), float(rot.yaw), float(rot.roll)])


def _bounds(actor):
    center, extent = actor.get_actor_bounds(False)
    center, extent = _v(center), _v(extent)
    return [[a - b for a, b in zip(center, extent)], [a + b for a, b in zip(center, extent)]]


def _state(actor):
    ue = scope.unreal
    c = actor.get_component_by_class(ue.StaticMeshComponent)
    mesh = c.get_editor_property('static_mesh') if c is not None else None
    materials = [scope._path(c.get_material(i)) for i in range(c.get_num_materials())] if c else []
    return dict(label=actor.get_actor_label(), mesh=scope._path(mesh), materials=materials,
                collision=str(c.get_collision_enabled()) if c else None, bounds=_bounds(actor),
                **_pose(actor))


def _scene(actor_subsystem):
    actors = scope._actors(actor_subsystem)
    by = {a.get_actor_label(): a for a in actors}
    labels = sorted(a.get_actor_label() for a in actors if GUEST.fullmatch(a.get_actor_label()))
    if len(labels) != 27 or len(set(labels)) != 27 or any(name not in by for name in GROUND):
        raise RuntimeError('Unexpected guest/ground basin inventory: ' + str(labels))
    return by, labels


def _add(a, b):
    return [x + y for x, y in zip(a, b)]


def _near(a, b, tolerance=EPS):
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_near(x, y, tolerance) for x, y in zip(a, b))
    return abs(a - b) <= tolerance


def _overlap(left, right):
    return all(min(left[1][i], right[1][i]) - max(left[0][i], right[0][i]) > EPS for i in range(3))


def _walls(by, prefix, side):
    token = prefix + '_Bath' + side + '_'
    return [_bounds(a) for n, a in by.items() if n.startswith(token)]


def _span(bounds, axis):
    return [min(row[0][axis] for row in bounds), max(row[1][axis] for row in bounds)]


def _room_target(by, label, basin, collider, openings):
    prefix = label.removesuffix('_Basin')
    if basin['mesh'] != BASIN or not _near(basin['rotation'], [0., 0., 0.]):
        raise RuntimeError('Unexpected source basin asset/orientation: ' + label)
    if not _near(basin['scale'], [4 / 3, 7 / 6, 1.]) or not _near(collider['scale'], [.6, .7, .85]):
        raise RuntimeError('Unexpected source basin/collision scale: ' + label)
    if (collider['mesh'] != '/Engine/BasicShapes/Cube.Cube' or not _near(collider['rotation'], [0., 0., 0.])
            or not _near(collider['location'], _add(basin['location'], [0., 0., 42.5]))):
        raise RuntimeError('Unexpected independent basin collider: ' + label)
    right = _walls(by, prefix, 'Right')
    rear = _walls(by, prefix, 'Rear')
    front = _walls(by, prefix, 'Front')
    left = _walls(by, prefix, 'Left')
    if not all((right, rear, front, left)):
        raise RuntimeError('Missing bathroom perimeter: ' + prefix)
    # Place the basin across the rear wall, rather than blocking the 94 cm
    # dry approach along the right wall. Its local -X user edge points inward.
    rear_inside = _span(rear, 0)[0]
    right_inside = _span(right, 1)[0]
    front_inside = _span(front, 0)[1]
    left_inside = _span(left, 1)[1]
    center = [rear_inside - 25., right_inside - 77.5, basin['location'][2]]
    scale = [48. / 45., basin['scale'][1], basin['scale'][2]]
    target_bounds = [[center[0] - 24., center[1] - 35., basin['bounds'][0][2]],
                     [center[0] + 24., center[1] + 35., basin['bounds'][1][2]]]
    if not (front_inside < target_bounds[0][0] < target_bounds[1][0] < rear_inside
            and left_inside < target_bounds[0][1] < target_bounds[1][1] < right_inside):
        raise RuntimeError('Basin target leaves original bathroom: ' + label)
    names = ('_WetRiser', '_Toilet_Collision0', '_ShowerScreen_Collision0', '_ShowerTray')
    neighboring = {suffix: _bounds(by[prefix + suffix]) for suffix in names}
    for name, bounds in neighboring.items():
        if _overlap(target_bounds, bounds):
            raise RuntimeError('Basin target intersects ' + name + ': ' + label)
    corridor_width = target_bounds[0][0] - neighboring['_ShowerScreen_Collision0'][1][0]
    if corridor_width < 68.:
        raise RuntimeError('Shower screen to basin clear span below 68 cm: ' + label)
    door_center = front_inside + 46.5
    if openings and label in openings:
        door_center = float(openings[label])
    approach = [[door_center, right_inside + 40., center[2]],
                [door_center, right_inside - 39., center[2]],
                [target_bounds[0][0] - 36., right_inside - 39., center[2]],
                [target_bounds[0][0] - 36., center[1], center[2]]]
    delta = [x - y for x, y in zip(center, basin['location'])]
    return dict(label=label, before=basin, collider_before=collider, center=center, scale=scale,
                collider_center=_add(collider['location'], delta), collider_scale=[.48, .7, .85],
                target_bounds=target_bounds, facing=[-1., 0., 0.], approach=approach,
                room_interior=[front_inside, rear_inside, left_inside, right_inside],
                screen_to_basin_clear_cm=corridor_width, cap_label=label + CAP_LABEL)


def _package_hash(asset_path):
    project = Path(scope.unreal.Paths.project_dir()).resolve()
    package = asset_path.split('.', 1)[0]
    filename = project / ('Content/' + package.removeprefix('/Game/') + '.uasset')
    return dict(file=str(filename), sha256=hashlib.sha256(filename.read_bytes()).hexdigest())


def plan_guest_basins(actor_subsystem=None, openings=None):
    """Plan the 27 room-facing basins against measured room boundaries."""
    by, labels = _scene(actor_subsystem)
    targets = []
    for label in labels:
        collider_label = label + '_Collision0'
        if collider_label not in by or label + CAP_LABEL in by:
            raise RuntimeError('Missing original collider or already repaired: ' + label)
        targets.append(_room_target(by, label, _state(by[label]), _state(by[collider_label]), openings))
    return dict(target_level=TARGET, basin_asset=BASIN, basin_asset_hash=_package_hash(BASIN),
                targets=targets, ground={n: _state(by[n]) for n in GROUND},
                cap=dict(local=CAP_LOCAL, radius_cm=CAP_RADIUS, height_cm=CAP_HEIGHT,
                         source_riser_top_cm=66., source_riser_radius_cm=2.5,
                         contact_overlap_cm=66. - (CAP_LOCAL[2] - CAP_HEIGHT / 2.)),
                minimum_screen_clear_cm=min(row['screen_to_basin_clear_cm'] for row in targets))


def _cap_asset(basin):
    from CreateOldTownDetailedProps import PropMeshBuilder, _create_or_update_asset

    ue = scope.unreal
    assetlib = ue.EditorAssetLibrary
    path = CAP_ROOT + '/' + CAP_NAME
    if assetlib.does_asset_exist(path):
        mesh = assetlib.load_asset(path)
        if (not isinstance(mesh, ue.StaticMesh) or
                assetlib.get_metadata_tag(mesh, 'HotelBasinSource') != BASIN):
            raise RuntimeError('Unowned cleanout cap asset already exists: ' + path)
        return mesh
    c = basin.get_component_by_class(ue.StaticMeshComponent)
    dark = c.get_material(2)
    if dark is None:
        raise RuntimeError('Basin drain stack material is missing')
    builder = PropMeshBuilder(CAP_NAME)
    builder.cylinder((0., 0., 0.), CAP_RADIUS, CAP_HEIGHT, 'M_P2_OldMetal', radial_steps=48)
    assetlib.make_directory(CAP_ROOT)
    mesh = _create_or_update_asset(CAP_ROOT, CAP_NAME, builder, {'M_P2_OldMetal': dark})
    assetlib.set_metadata_tag(mesh, 'HotelBasinSource', BASIN)
    if not assetlib.save_loaded_asset(mesh, False):
        raise RuntimeError('Could not save owned basin cleanout cap')
    return mesh


def _set_actor_location_and_scale(actor, position, scale):
    ue = scope.unreal
    if not actor.set_actor_location(ue.Vector(*position), False, True):
        if not _near(_v(actor.get_actor_location()), position):
            raise RuntimeError('Unable to move ' + actor.get_actor_label())
    actor.set_actor_scale3d(ue.Vector(*scale))


def _spawn_cap(actor_subsystem, basin, mesh, row):
    ue = scope.unreal
    component = basin.get_component_by_class(ue.StaticMeshComponent)
    pos = component.get_world_transform().transform_location(ue.Vector(*CAP_LOCAL))
    actor = actor_subsystem.spawn_actor_from_class(ue.StaticMeshActor, pos, basin.get_actor_rotation(), False)
    if actor is None:
        raise RuntimeError('Unable to spawn basin cleanout cap: ' + row['label'])
    actor.set_actor_label(row['cap_label'])
    actor.set_folder_path(basin.get_folder_path())
    actor.set_editor_property('tags', [ue.Name('HotelGuestBasinConnection_20261113')])
    actor.set_actor_scale3d(basin.get_actor_scale3d())
    c = actor.get_component_by_class(ue.StaticMeshComponent)
    c.set_static_mesh(mesh)
    c.set_collision_profile_name('NoCollision')
    c.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
    c.set_material(0, component.get_material(2))
    rule = ue.AttachmentRule.KEEP_WORLD
    if not actor.attach_to_actor(basin, ue.Name('None'), rule, rule, rule, False):
        actor_subsystem.destroy_actor(actor)
        raise RuntimeError('Could not attach the drain cap to its basin: ' + row['label'])
    return actor


def verify_guest_basins(actor_subsystem=None, expected=None, verify_approach=False):
    """Verify saved target geometry, exact collision dimensions and optional access."""
    if expected is None:
        raise ValueError('Pass the original basin plan or apply report for readback')
    expected = expected.get('plan', expected)
    ue = scope.unreal
    by, labels = _scene(actor_subsystem)
    if sorted(row['label'] for row in expected['targets']) != labels:
        raise RuntimeError('Basin target inventory changed')
    if expected['ground'] != {n: _state(by[n]) for n in GROUND}:
        raise RuntimeError('Ground-floor basins changed')
    if expected['basin_asset_hash'] != _package_hash(BASIN):
        raise RuntimeError('The original shared basin package changed')
    results = []
    for row in expected['targets']:
        label = row['label']
        basin, collider, cap = by[label], by[label + '_Collision0'], by[row['cap_label']]
        state, collision, cap_state = _state(basin), _state(collider), _state(cap)
        for actual, before, position, scale in ((state, row['before'], row['center'], row['scale']),
                                               (collision, row['collider_before'], row['collider_center'], row['collider_scale'])):
            if (not _near(actual['location'], position) or not _near(actual['scale'], scale)
                    or not _near(actual['rotation'], before['rotation'])
                    or any(actual[field] != before[field] for field in ('mesh', 'materials', 'collision'))):
                raise RuntimeError('Basin/collider readback differs from plan: ' + label)
        c = basin.get_component_by_class(ue.StaticMeshComponent)
        expected_cap_pos = _v(c.get_world_transform().transform_location(ue.Vector(*CAP_LOCAL)))
        cap_extent = [CAP_RADIUS * row['scale'][0], CAP_RADIUS * row['scale'][1], CAP_HEIGHT * row['scale'][2] / 2.]
        cap_bounds = [[x - e for x, e in zip(expected_cap_pos, cap_extent)],
                      [x + e for x, e in zip(expected_cap_pos, cap_extent)]]
        cap_component = cap.get_component_by_class(ue.StaticMeshComponent)
        cap_parent = cap.get_attach_parent_actor()
        expected_mesh = CAP_ROOT + '/' + CAP_NAME + '.' + CAP_NAME
        expected_materials = [state['materials'][2]]
        expected_collision = ue.CollisionEnabled.NO_COLLISION
        checks = dict(
            location=_near(cap_state['location'], expected_cap_pos),
            scale=_near(cap_state['scale'], row['scale']),
            bounds=_near(cap_state['bounds'], cap_bounds),
            mesh=cap_state['mesh'] == expected_mesh,
            collision=cap_component.get_collision_enabled() == expected_collision,
            materials=cap_state['materials'] == expected_materials,
            parent=cap_parent == basin,
        )
        if not all(checks.values()):
            expected_cap = dict(location=expected_cap_pos, scale=row['scale'], bounds=cap_bounds,
                                mesh=expected_mesh, collision=str(expected_collision),
                                materials=expected_materials, parent=scope._path(basin))
            actual_cap = dict(cap_state, parent=scope._path(cap_parent),
                              component_parent=scope._path(cap_component.get_attach_parent()),
                              relative_location=_v(cap_component.get_editor_property('relative_location')),
                              relative_scale=_v(cap_component.get_editor_property('relative_scale3d')),
                              collision_profile=str(cap_component.get_collision_profile_name()))
            raise RuntimeError('Drain cap fit/attachment/material differs: {} checks={} actual={} expected={}'
                               .format(label, checks, actual_cap, expected_cap))
        if not _near(state['bounds'], row['target_bounds']):
            raise RuntimeError('Basin footprint not as planned: ' + label)
        approach = None
        if verify_approach:
            from ValidateEnterableStreet import sample_route
            world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
            approach = sample_route(world, row['approach'])
            if approach['failures']:
                raise RuntimeError('Guest basin route blocked: ' + label + ': ' + str(approach['failures'][:5]))
        results.append(dict(label=label, basin=state, collider=collision, cap=cap_state,
                            clear_span_cm=row['screen_to_basin_clear_cm'], approach=approach))
    return dict(passed=True, target_level=TARGET, basin_count=len(results), ground_unchanged=True,
                shared_asset_unchanged=True, minimum_screen_clear_cm=expected['minimum_screen_clear_cm'],
                approach_validated=verify_approach, targets=results)


def apply_guest_basins(actor_subsystem=None, expected=None, openings=None, verify_approach=False):
    """Apply an inspected plan without saving any map or original assets.

    Optional openings maps a basin actor label to its new doorway center X.
    When a prior plan is supplied, its original component states are rechecked
    before any change; it can be applied after the door wall segments change.
    """
    ue = scope.unreal
    plan = plan_guest_basins(actor_subsystem, openings) if expected is None else expected.get('plan', expected)
    by, labels = _scene(actor_subsystem)
    if sorted(row['label'] for row in plan['targets']) != labels:
        raise RuntimeError('Basin target inventory changed after planning')
    if plan['basin_asset_hash'] != _package_hash(BASIN):
        raise RuntimeError('Shared basin asset changed after planning')
    if plan['ground'] != {n: _state(by[n]) for n in GROUND}:
        raise RuntimeError('Ground-floor basins changed after planning')
    for row in plan['targets']:
        name = row['label']
        if (row['cap_label'] in by or row['before'] != _state(by[name])
                or row['collider_before'] != _state(by[name + '_Collision0'])):
            raise RuntimeError('Guest basin source state changed after planning: ' + name)
    actor_subsystem = actor_subsystem or ue.get_editor_subsystem(ue.EditorActorSubsystem)
    cap_mesh = _cap_asset(by[labels[0]])
    changed, new = [], []
    try:
        for row in plan['targets']:
            name = row['label']
            basin, collider = by[name], by[name + '_Collision0']
            changed.append((basin, row['before']))
            _set_actor_location_and_scale(basin, row['center'], row['scale'])
            changed.append((collider, row['collider_before']))
            _set_actor_location_and_scale(collider, row['collider_center'], row['collider_scale'])
            new.append(_spawn_cap(actor_subsystem, basin, cap_mesh, row))
        verification = verify_guest_basins(actor_subsystem, plan, verify_approach)
    except Exception:
        for actor in reversed(new):
            actor_subsystem.destroy_actor(actor)
        for actor, state in reversed(changed):
            _set_actor_location_and_scale(actor, state['location'], state['scale'])
        raise
    return dict(passed=True, map_saved=False, plan=plan, verification=verification,
                cap_asset=scope._path(cap_mesh), cap_asset_hash=_package_hash(scope._path(cap_mesh)),
                moved_basins=len(new), added_caps=len(new))
