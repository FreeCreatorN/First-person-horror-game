"""Independent saved-world verification for the approved 27-room V4 hotel.

This module never saves a world or asset. Apply calls ``audit(world, plan,
baseline)`` before saving; ``main`` independently loads the saved BuildReport.
"""
import json
import math
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, sha, xyz
from PolishOldTownDetails import actor_bounds
from ValidateEnterableStreet import validate_main_home, refresh_world_collision
from AuditOldTownRevision import _support, _step_probe, _route_samples, _capsule_components

WORK = ROOT / 'Saved/CodexOutputs/HotelRedesign_20261008_V4'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
RADIUS, HEIGHT = 34., 180.


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def refresh(actors):
    """Register loaded collision without changing existing named profiles."""
    profiles = [(c, str(c.get_collision_profile_name())) for a in actors
                for c in a.get_components_by_class(unreal.PrimitiveComponent)]
    refreshed = refresh_world_collision(actors)
    for component, profile in profiles:
        if profile != 'Custom' and str(component.get_collision_profile_name()) != profile:
            component.set_collision_profile_name(profile)
    return refreshed


def _points(row):
    return row.get('foot_waypoints') or row.get('points') or []


def _bounds(row):
    if 'world_min' in row and 'world_max' in row:
        return row['world_min'], row['world_max']
    return row.get('world_bounds_cm') or row.get('bounds_cm')


def _floor(row):
    value = row.get('floor', row.get('from_floor'))
    return int(value) if value is not None else None


def _near(first, second, tolerance=.15):
    return len(first) == len(second) and all(abs(float(a)-float(b)) <= tolerance
                                          for a, b in zip(first, second))


def _asset_path(value):
    return str(value).split('.')[0]


def _clear_bounds(row):
    return row.get('clear_bounds') or row.get('clear_bounds_cm') or _bounds(row)


def _named(row, token):
    name = ''.join(str(row.get(k, '')) for k in ('role', 'id', 'key', 'name', 'kind')).lower()
    return token.lower() in name.replace('_', '').replace('-', '').replace(' ', '')


def _sd_bounds(row):
    """Read measured clear bounds and convert world cm to the reviewed s,d axes."""
    lo, hi = _clear_bounds(row)
    return [(lo[1]+3500.)/100., (lo[0]-9000.)/100.,
            (hi[1]+3500.)/100., (hi[0]-9000.)/100.]


def route_probe(world, points, stairs=False):
    """Probe actual support, Pawn blocking, and standing/step headroom."""
    samples, failures, previous = [], [], None
    step = 14. if stairs else 25.
    tolerance = 23. if stairs else 10.05
    maximum_delta = 45.1 if stairs else 10.05
    for foot in _route_samples(points, step=step):
        support = _support(world, foot, above=45., below=45.)
        item = dict(planned_foot_cm=foot, support_z_cm=support, passed=False)
        if support is not None:
            probe = _step_probe(world, foot[:2]+[support], RADIUS, HEIGHT)
            item.update(probe=probe, passed=abs(support-foot[2]) <= tolerance and probe['passed']
                        and (previous is None or abs(support-previous) <= maximum_delta))
            previous = support
        if not item['passed']:
            failures.append(item)
        samples.append(item)
    return dict(passed=len(points) >= 2 and bool(samples) and not failures,
                samples=samples, sample_count=len(samples), failures=failures,
                capsule_radius_cm=RADIUS, capsule_height_cm=HEIGHT,
                scope='Real floor support and Pawn capsule; excludes runtime input and lift operation.')


def audit(world, plan, baseline, actors=None):
    """Verify exact assembly, circulation and preservation, without saving."""
    actors = list(actors if actors is not None else
                  unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by = {a.get_actor_label(): a for a in actors}
    result = dict(passed=False, target_level=TARGET, checks=[], errors=[], routes=[], stairs=[],
                  shaft_probes=[], mechanical_doors=[], statistics={}, reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
                  scope='Architecture, supported physical routes, and preservation; not building-code approval.')

    def check(name, passed, **details):
        result['checks'].append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            result['errors'].append(name)

    def section(name, callback):
        try:
            callback()
        except Exception:
            check(name+':exception', False, traceback=traceback.format_exc())

    check('target_world', world.get_path_name().startswith(TARGET+'.'))
    check('unique_actor_labels', len(by) == len(actors))

    def program():
        rooms = plan.get('rooms', [])
        ids = [r['id'] for r in rooms]
        floor_counts = Counter(_floor(r) for r in rooms)
        check('27_unique_guest_rooms', len(ids) == len(set(ids)) == 27, rooms=len(ids))
        check('nine_rooms_on_each_upper_floor', dict(floor_counts) == {1: 9, 2: 9, 3: 9},
              counts={str(k): v for k, v in floor_counts.items()})
        floors = plan.get('floor_z_cm', [])
        check('four_aligned_storeys', len(floors) == 4 and all(b > a for a, b in zip(floors, floors[1:])),
              floor_z_cm=floors)
        doors = {r['id']: r for r in plan.get('doors', [])}
        bad = [r['id'] for r in rooms if r.get('door_id') not in doors or
               _floor(doors[r['door_id']]) != _floor(r)]
        check('guest_rooms_have_same_floor_doors', not bad, failed_rooms=bad)
        routes = plan.get('routes', [])
        route_ids = {r['id'] for r in routes}
        covered = {r.get('room_id') for r in routes if r.get('room_id')}
        for room in rooms:
            declared = room.get('route_ids', [])
            if room.get('route_id'):
                declared = list(declared)+[room['route_id']]
            if declared and set(declared) <= route_ids:
                covered.add(room['id'])
        check('all_guest_rooms_have_physical_routes', set(ids) <= covered,
              missing=sorted(set(ids)-covered))
        public = {int(r['floor']) for r in routes if r.get('kind', r.get('category')) == 'public'
                  and r.get('floor') is not None}
        check('public_circulation_on_all_four_floors', public == {0, 1, 2, 3}, covered_floors=sorted(public))
        rear_id = plan.get('rear_escape_route_id')
        rear = [r for r in routes if r['id'] == rear_id or r.get('kind') == 'rear_escape']
        check('rear_exit_route_is_explicit', len(rear) == 1, route_ids=[r['id'] for r in rear])
        if len(rear) == 1:
            points = _points(rear[0])
            # V4 hotel envelope is X9000..10040, Y-3500..3500; the route must
            # travel behind the east wall, round its north end, and back west.
            outside = any(q[0] > 10040 for q in points)
            north = any(q[1] > 3500 for q in points)
            returned = bool(points) and points[-1][0] < 9000
            check('rear_exit_rounds_north_end_to_street', outside and north and returned,
                  east_of_rear_wall=outside, north_of_end=north, returns_to_front=returned)
    section('program', program)

    def design_intent():
        spaces = plan.get('spatial_program', [])
        check('measured_space_program_present', bool(spaces))
        entries = [r for r in plan.get('placed_doors', []) if _named(r, 'mainentry')]
        check('main_door_exact_building_centre', len(entries) == 1 and
              abs(by[entries[0]['actor']].get_actor_location().y) <= 1.,
              axes_y_cm=[xyz(by[r['actor']].get_actor_location())[1] for r in entries])
        counters = [r for r in plan.get('placed_boxes', [])+plan.get('placed_props', [])
                    if _named(r, 'receptioncounter') and not _named(r, 'top')]
        axes = []
        for row in counters:
            lo, hi = actor_bounds(by[row['actor']])
            axes.append((lo[1]+hi[1])/2.)
        check('reception_counter_opposes_centred_door', len(axes) == 1 and abs(axes[0]) <= 1.,
              counter_axes_y_cm=axes)
        offices = [r for r in spaces if _named(r, 'office') and not _named(r, 'corridor')
                   and not _named(r, 'passage')]
        office_bounds = [_sd_bounds(r) for r in offices]
        check('all_three_offices_on_left', len(offices) == 3 and
              all(_floor(r) == 0 and sd[0] >= 23.-.01 and sd[2] <= 27.6+.01
                  for r, sd in zip(offices, office_bounds)), measured_sd_m=office_bounds)
        toilets = [r for r in spaces if _named(r, 'publicwc')]
        toilet_bounds = [_sd_bounds(r) for r in toilets]
        check('public_wc_at_front_right', len(toilets) == 1 and _floor(toilets[0]) == 0 and
              toilet_bounds[0][0] >= 41.2-.01 and toilet_bounds[0][2] <= 47.+.01 and
              toilet_bounds[0][1] >= 2.6-.01 and toilet_bounds[0][3] <= 5.8+.01,
              measured_sd_m=toilet_bounds)
        centre = [r for r in spaces if (_named(r, 'central') or _named(r, 'safety')) and _named(r, 'stair')]
        centre_bounds = [_sd_bounds(r) for r in centre]
        counts = Counter(_floor(r) for r in centre)
        matched = dict(counts) == {0: 1, 1: 1, 2: 1, 3: 1}
        matched = matched and all(sd[0] >= 40.72-.01 and sd[2] <= 46.6+.01 and
                                  sd[1] >= 7.-.01 and sd[3] <= 10.2+.01 for sd in centre_bounds)
        matched = matched and all(_near(centre_bounds[0], other, .001) for other in centre_bounds[1:])
        check('rear_right_safety_stair_aligned_on_every_floor', matched, measured_sd_m=centre_bounds,
              counts={str(k): v for k, v in counts.items()})
        corridors = [r for r in spaces if _named(r, 'corridor') and not _named(r, 'staff')
                     and not _named(r, 'office') and not _named(r, 'service')]
        corridor_floors = {_floor(r) for r in corridors}
        corridor_details = []
        for row in corridors:
            lo, hi = _clear_bounds(row)
            width = hi[0]-lo[0]
            check('public_corridor_clear_220cm:'+row['id'], abs(width-220.) <= .15,
                  width_cm=width, clear_bounds=[lo, hi])
            corridor_details.append(dict(id=row['id'], floor=_floor(row), width_cm=width))
        check('measured_220cm_corridors_cover_all_floors', corridor_floors == {0, 1, 2, 3},
              corridors=corridor_details)
        front_columns=[r for r in plan.get('placed_boxes',[]) if r['role']=='column' and _floor(r)==0 and r['world_min'][0]<9500]
        intrusion=[]
        for row in front_columns:
            lo,hi=actor_bounds(by[row['actor']])
            if lo[0]<9240.-.15:intrusion.append(dict(actor=row['actor'],actual_front_x_cm=lo[0]))
        check('ground_columns_leave_entire_220cm_gallery',bool(front_columns) and not intrusion,
              checked_columns=len(front_columns),intrusion=intrusion)
        room_details = []
        for room in plan.get('rooms', []):
            lo, hi = _clear_bounds(room)
            sd = _sd_bounds(room)
            width, depth = hi[1]-lo[1], hi[0]-lo[0]
            left = sd[2] <= 30.+.01
            right = sd[0] >= 47.-.01
            wanted_width = 460. if left else 405.
            good = (left or right) and abs(width-wanted_width) <= .15 and abs(depth-760.) <= .15
            check('guest_room_clear_dimensions:'+room['id'], good, clear_width_cm=width,
                  clear_depth_cm=depth, wing='left' if left else 'right', measured_sd_m=sd)
            room_details.append(dict(room_id=room['id'], floor=_floor(room), wing='left' if left else 'right'))
        wing_counts = Counter((r['floor'], r['wing']) for r in room_details)
        check('five_left_and_four_right_rooms_per_upper_floor',
              dict(wing_counts) == {(floor, wing): count for floor in (1, 2, 3)
                                   for wing, count in (('left', 5), ('right', 4))},
              counts=[dict(floor=k[0], wing=k[1], rooms=v) for k, v in sorted(wing_counts.items())])
    section('design_intent', design_intent)

    def geometry():
        boxes = plan.get('placed_boxes', [])
        check('placed_box_manifest_present', bool(boxes))
        for row in boxes + [c for r in plan.get('placed_props', []) for c in r.get('colliders', [])]:
            label = row['actor']
            actor = by.get(label)
            details = {}
            good = actor is not None
            if good:
                component = actor.get_component_by_class(unreal.StaticMeshComponent)
                expected = _bounds(row)
                actual = actor_bounds(actor)
                error = max(abs(actual[j][i]-expected[j][i]) for j in (0, 1) for i in range(3))
                good = component is not None and component.static_mesh is not None and error <= .15
                if row.get('asset'):
                    good = good and _asset_path(component.static_mesh.get_path_name()) == _asset_path(row['asset'])
                if row.get('material_asset'):
                    material = component.get_material(0)
                    good = good and material is not None and _asset_path(material.get_path_name()) == _asset_path(row['material_asset'])
                if row.get('collision') is not None:
                    good = good and str(component.get_collision_profile_name()) == ('BlockAll' if row['collision'] else 'NoCollision')
                details = dict(bounds_error_cm=error)
                if not good:
                    details.update(expected_bounds=expected, actual_bounds=actual)
            check('box:'+row.get('id', label), good, **details)
        for row in plan.get('placed_props', []):
            actor = by.get(row['actor'])
            good = actor is not None
            if good:
                component = actor.get_component_by_class(unreal.StaticMeshComponent)
                good = component is not None and component.static_mesh is not None
                good = good and _asset_path(component.static_mesh.get_path_name()) == _asset_path(row['asset'])
                good = good and _near(xyz(actor.get_actor_location()), row['position_cm'])
                scale = row.get('actor_scale', row.get('scale', [1., 1., 1.]))
                good = good and _near(xyz(actor.get_actor_scale3d()), scale, .001)
                rotation = actor.get_actor_rotation()
                wanted = row.get('rotation', [0., row.get('yaw', 0.), 0.])
                actual = [rotation.pitch, rotation.yaw, rotation.roll]
                good = good and all(abs((a-b+180.) % 360.-180.) <= .15 for a, b in zip(actual, wanted))
                expected = _bounds(row)
                if expected:
                    actual_bounds = actor_bounds(actor)
                    good = good and max(abs(actual_bounds[j][i]-expected[j][i]) for j in (0, 1) for i in range(3)) <= .2
            check('fixture:'+row.get('id', row['actor']), good)
        planned_doors = {r['id'] for r in plan.get('doors', [])}
        planned_windows = {r['id'] for r in plan.get('windows', [])}
        check('all_door_instances_assembled', {r['id'] for r in plan.get('placed_doors', [])} == planned_doors)
        check('all_window_instances_assembled', {r['id'] for r in plan.get('placed_windows', [])} == planned_windows)
        for row in plan.get('placed_doors', []) + plan.get('placed_windows', []):
            actor = by.get(row['actor'])
            good = actor is not None
            if good:
                if row.get('blueprint'):
                    blueprint = row['blueprint']
                    good = actor.get_class().get_path_name() == blueprint+'.'+blueprint.rsplit('/', 1)[1]+'_C'
                good = good and _near(xyz(actor.get_actor_location()), row.get('actor_position_cm', row['position_cm']))
                if row.get('yaw') is not None:
                    good = good and abs((actor.get_actor_rotation().yaw-row['yaw']+180.) % 360.-180.) <= .15
                if row.get('components'):
                    components = {c.get_name(): c for c in actor.get_components_by_class(unreal.SceneComponent)}
                    good = good and set(components) == {c['name'] for c in row['components']}
                    for spec in row['components']:
                        component = components.get(spec['name'])
                        if component is None:
                            good = False
                            continue
                        parent = component.get_attach_parent()
                        good = good and (parent.get_name() if parent else None) == spec.get('parent')
                        if spec.get('parent') is None:
                            continue
                        good = good and _near(xyz(component.get_editor_property('relative_location')), spec['relative_location'])
                        rotation = component.get_editor_property('relative_rotation')
                        actual = [rotation.pitch, rotation.yaw, rotation.roll]
                        good = good and all(abs((a-b+180.) % 360.-180.) <= .15
                                            for a, b in zip(actual, spec['relative_rotation']))
                        if spec.get('asset'):
                            good = good and component.static_mesh is not None and _asset_path(component.static_mesh.get_path_name()) == _asset_path(spec['asset'])
                        if spec.get('collision') and isinstance(component, unreal.PrimitiveComponent):
                            good = good and component.get_collision_enabled().value == getattr(unreal.CollisionEnabled, spec['collision']).value
            check('opening:'+row['id'], good)
    section('geometry', geometry)

    def envelope_continuity():
        floors=plan['floor_z_cm']
        for floor in range(3):
            z=floors[floor+1]-18.
            sides={'Street':[[9010.,s*100-3500.,z] for s in (.5,12.,21.,38.,52.,68.)],
                'Rear':[[10030.,s*100-3500.,z] for s in (.5,12.,21.,38.,52.,68.)],
                'SouthEnd':[[9000.+d*100,-3490.,z] for d in (1.,5.,9.)],
                'NorthEnd':[[9000.+d*100,3490.,z] for d in (1.,5.,9.)]}
            for side,points in sides.items():
                probes=[]
                for foot in points:
                    blockers=_capsule_components(world,foot,3.,10.)
                    labels=sorted({c.get_owner().get_actor_label() for c in blockers if c.get_owner().get_actor_label().startswith('OTS_HotelV4_F%d_%sWall_'%(floor,side))})
                    probes.append(dict(foot_cm=foot,owned_wall_blockers=labels,passed=bool(labels)))
                check('continuous_envelope_at_F%d_slab_%s'%(floor+1,side),all(p['passed'] for p in probes),probes=probes)
    section('envelope_continuity',envelope_continuity)

    def door_mechanics():
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        tested = set()
        for row in plan.get('placed_doors', []):
            actual = by.get(row['actor'])
            if actual is None:
                check('door_mechanical_instance:'+row['id'], False)
                continue
            blueprint = row.get('blueprint', actual.get_class().get_path_name())
            position = xyz(actual.get_actor_location())
            # Locked lift gates are checked in their actual persisted state.
            # Testing an isolated clone never opens the actual lift shaft.
            if row.get('locked'):
                foot = position[:2]+[position[2]+2.]
                blockers = _capsule_components(world, foot, RADIUS, HEIGHT)
                owned = [c.get_name() for c in blockers if c.get_owner() == actual]
                check('locked_gate_blocks:'+row['id'], any('LeafCollision' in name for name in owned), blockers=owned)
            if blueprint in tested:
                continue
            tested.add(blueprint)
            stage = position[:2]+[position[2]+50000.]
            clone = subsystem.spawn_actor_from_class(actual.get_class(), unreal.Vector(*stage),
                                                     actual.get_actor_rotation(), False)
            check('mechanical_clone_spawn:'+row['id'], clone is not None)
            if clone is None:
                continue
            clone.set_actor_label('OTS_TransientDoorTest_V4_'+row['id'])
            test = dict(door_id=row['id'], blueprint=blueprint, clone_only=True,
                        foot_cm=stage[:2]+[stage[2]+2.])
            try:
                components = {c.get_name(): c for c in clone.get_components_by_class(unreal.SceneComponent)}
                specs = {c['name']: c for c in row.get('components', [])}
                slider = row.get('kind') == 'slider' or 'LeftSlider' in components
                if slider:
                    left, right = components['LeftSlider'], components['RightSlider']
                    initial_left = xyz(left.get_editor_property('relative_location'))
                    initial_right = xyz(right.get_editor_property('relative_location'))
                    left.set_relative_location(unreal.Vector(0., initial_left[1], initial_left[2]), False, True)
                    right.set_relative_location(unreal.Vector(0., initial_right[1], initial_right[2]), False, True)
                else:
                    hinge = components['DoorHinge']
                    hinge.set_relative_rotation(unreal.Rotator(pitch=0., yaw=0., roll=0.), False, True)
                closed = _capsule_components(world, test['foot_cm'], RADIUS, HEIGHT)
                owned_closed = [c.get_name() for c in closed if c.get_owner() == clone]
                test['closed_blockers'] = sorted(owned_closed)
                closed_good = any('LeafCollision' in name for name in owned_closed)
                check('mechanical_closed_leaf_blocks:'+row['id'], closed_good, blueprint=blueprint, blockers=owned_closed)
                if slider:
                    # Locked gates start closed, so their original positions
                    # cannot be used as the fully open mechanical test state.
                    offset = float(row['width'])/2.+3.
                    left.set_relative_location(unreal.Vector(-offset, initial_left[1], initial_left[2]), False, True)
                    right.set_relative_location(unreal.Vector(offset, initial_right[1], initial_right[2]), False, True)
                else:
                    wanted = specs.get('DoorHinge', {}).get('relative_rotation')
                    if wanted is None:
                        wanted = [0., float(row.get('hinge_side', 1))*90., 0.]
                    hinge.set_relative_rotation(unreal.Rotator(pitch=wanted[0], yaw=wanted[1], roll=wanted[2]), False, True)
                inward = row.get('inward')
                if inward is None:
                    angle = math.radians(float(actual.get_actor_rotation().yaw))
                    inward = [-math.sin(angle), math.cos(angle)]
                length = math.hypot(inward[0], inward[1])
                assert length > 0., 'Door has zero inward vector.'
                direction = [inward[0]/length, inward[1]/length]
                test['open_crossing_samples'] = []
                opened = []
                for offset in (-80., 0., 80.):
                    foot = [test['foot_cm'][0]+direction[0]*offset,
                            test['foot_cm'][1]+direction[1]*offset, test['foot_cm'][2]]
                    blockers = _capsule_components(world, foot, RADIUS, HEIGHT)
                    opened.extend(blockers)
                    test['open_crossing_samples'].append(dict(foot_cm=foot,
                        blockers=sorted({c.get_owner().get_actor_label()+':'+c.get_name() for c in blockers})))
                open_blockers = sorted({c.get_owner().get_actor_label()+':'+c.get_name() for c in opened})
                test['open_blockers'] = open_blockers
                check('mechanical_open_aperture_clear:'+row['id'], not opened, blueprint=blueprint, blockers=open_blockers)
                test['passed'] = closed_good and not opened
            except Exception:
                test['passed'] = False
                test['exception'] = traceback.format_exc()
                check('mechanical_test_exception:'+row['id'], False, traceback=test['exception'])
            finally:
                removed = bool(subsystem.destroy_actor(clone))
                test['temporary_clone_removed'] = removed
                check('mechanical_clone_removed:'+row['id'], removed)
                result['mechanical_doors'].append(test)
        check('unique_door_blueprints_physically_tested', bool(tested), tested=len(tested))
    section('door_mechanics', door_mechanics)

    def circulation():
        routes = plan.get('routes', [])
        check('physical_route_manifest_present', bool(routes))
        check('unique_route_ids', len({r['id'] for r in routes}) == len(routes))
        for row in routes:
            probe = route_probe(world, _points(row))
            result['routes'].append(dict(id=row['id'], kind=row.get('kind'), floor=row.get('floor'),
                                         room_id=row.get('room_id'), result=probe))
            check('route:'+row['id'], probe['passed'], sample_count=probe['sample_count'], failures=probe['failures'][:3])
        staircase_routes = plan.get('stair_routes', [])
        if not staircase_routes:
            staircase_routes = [r for r in plan.get('staircases', []) if _points(r)]
        check('physical_stair_routes_present', bool(staircase_routes))
        coverage = {}
        for row in staircase_routes:
            stair_id = row.get('stair_id', row.get('staircase_id', row.get('group')))
            first = row.get('from_floor', row.get('floor'))
            last = row.get('to_floor', int(first)+1 if first is not None else None)
            if stair_id is not None and first is not None and last is not None:
                coverage.setdefault(str(stair_id), set()).add((int(first), int(last)))
            probe = route_probe(world, _points(row), stairs=True)
            result['stairs'].append(dict(id=row['id'], stair_id=stair_id, from_floor=first, to_floor=last, result=probe))
            check('stair:'+row['id'], probe['passed'], sample_count=probe['sample_count'], failures=probe['failures'][:3])
        expected = {(0, 1), (1, 2), (2, 3)}
        check('three_staircases_connect_every_floor', len(coverage) == 3 and all(expected <= pairs for pairs in coverage.values()),
              coverage={name: sorted(pairs) for name, pairs in coverage.items()})
    section('circulation', circulation)

    def lift_shaft():
        shafts = [r for r in plan.get('shafts', []) if r.get('kind', 'lift') in ('lift', 'elevator')]
        counts = Counter(_floor(r) for r in shafts)
        check('one_lift_shaft_on_each_floor', dict(counts) == {0: 1, 1: 1, 2: 1, 3: 1},
              counts={str(k): v for k, v in counts.items()})
        if len(shafts) != 4:
            return
        bounds = [_bounds(row) for row in shafts]
        axes = [[bound[j][i] for j in (0, 1) for i in (0, 1)] for bound in bounds]
        check('lift_shaft_same_axis_all_storeys', all(_near(axes[0], other, .01) for other in axes[1:]),
              horizontal_bounds_cm=axes)
        floors = plan['floor_z_cm']
        for row in shafts:
            lo, hi = _bounds(row)
            floor = _floor(row)
            foot_z = floors[floor]+1.
            probes = row.get('wall_probe_points') or [
                [lo[0], (lo[1]+hi[1])/2, foot_z], [hi[0], (lo[1]+hi[1])/2, foot_z],
                [(lo[0]+hi[0])/2, lo[1], foot_z], [(lo[0]+hi[0])/2, hi[1], foot_z]]
            walls = []
            for point in probes:
                blockers = _capsule_components(world, point, 6., HEIGHT)
                walls.append(dict(foot_cm=point, blockers=sorted({c.get_owner().get_actor_label()+':'+c.get_name() for c in blockers}), passed=bool(blockers)))
            # A closed gate may form the fourth side; this checks actual
            # blocking rather than assuming a labelled shaft is enclosed.
            check('lift_enclosure_F%d' % floor, len(walls) >= 4 and all(p['passed'] for p in walls), probes=walls)
            interior = [(lo[0]+hi[0])/2, (lo[1]+hi[1])/2, foot_z]
            support = _support(world, interior, above=15., below=15.) if floor else None
            if floor:
                check('lift_slab_void_F%d' % floor, support is None, centre_foot_cm=interior, unexpected_support_z_cm=support)
            result['shaft_probes'].append(dict(id=row['id'], floor=floor, walls=walls,
                                                centre_foot_cm=interior, nearby_support_z_cm=support))
        entered = []
        for route in plan.get('routes', []):
            for point in _route_samples(_points(route), step=25.):
                for shaft in shafts:
                    lo, hi = _bounds(shaft)
                    if all(lo[i]+.5 < point[i] < hi[i]-.5 for i in range(3)):
                        entered.append(dict(route=route['id'], shaft=shaft['id'], foot_cm=point))
                        break
                if entered and entered[-1]['route'] == route['id']:
                    break
        check('no_route_enters_locked_lift_shaft', not entered, intrusions=entered[:10])
    section('lift_shaft', lift_shaft)

    def preservation():
        states = {name: actor_state(actor) for name, actor in by.items()}
        removed = set(baseline.get('removed_actor_labels', plan.get('removed_actor_labels', [])))
        preserved = baseline.get('preserved_actors')
        if preserved is None:
            preserved = {n: s for n, s in baseline.get('actors', {}).items() if n not in removed}
        check('nonhotel_preservation_baseline_present', bool(preserved))
        overrides=baseline.get('allowed_surface_overrides',{})
        changed = [n for n, state in preserved.items() if states.get(n) != overrides.get(n,state)]
        check('all_nonhotel_actors_match_approved_surface_overrides' if overrides else 'all_nonhotel_actors_unchanged',
              not changed, checked=len(preserved), approved_visual_overrides=len(overrides), changed=changed[:20])
        if changed:
            name = changed[0]
            result['preservation_difference_sample'] = dict(actor=name, before=preserved[name], after=states.get(name))
        created = set(plan.get('new_actor_labels', []))
        check('new_actor_manifest_present', bool(created))
        check('exact_current_actor_set', set(by) == set(preserved) | created,
              unexpected=sorted(set(by)-set(preserved)-created), missing=sorted((set(preserved)|created)-set(by)))
        expected_created = plan.get('expected_actor_states', {})
        if expected_created:
            check('new_actor_states_cover_manifest', set(expected_created) == created,
                  missing=sorted(created-set(expected_created)), unexpected=sorted(set(expected_created)-created))
            changed_created = [n for n, state in expected_created.items() if states.get(n) != state]
            check('all_new_actor_saved_states_match', not changed_created,
                  checked=len(expected_created), changed=changed_created[:20])
            if changed_created:
                name = changed_created[0]
                result['new_actor_difference_sample'] = dict(actor=name, before=expected_created[name], after=states.get(name))
        check('old_hotel_removed', not ((removed-created) & set(by)), remaining=sorted((removed-created) & set(by)))
        assets = baseline.get('shared_asset_sha256', {})
        changed_assets = [path for path, digest in assets.items() if not Path(path).is_file() or sha(Path(path)) != digest]
        check('shared_assets_unchanged', bool(assets) and not changed_assets, checked=len(assets), changed=changed_assets)
        protected = baseline.get('protected_map_sha256', {})
        changed_maps = [path for path, digest in protected.items() if not Path(path).is_file() or sha(Path(path)) != digest]
        check('protected_maps_unchanged', bool(protected) and not changed_maps, checked=len(protected), changed=changed_maps)
        main_home = validate_main_home(actors)
        check('MainHome_interaction_structure_preserved', main_home == baseline.get('main_home'), current=main_home)
        temporary = [n for n, state in states.items() if 'TemporaryInspection' in state['tags'] or n.startswith('OTS_TransientDoorTest_')]
        check('temporary_inspection_objects_absent', not temporary, remaining=temporary)
        result['preservation'] = dict(preserved_actors=len(preserved), removed_actors=len(removed),
                                       new_actors=len(created), shared_assets=len(assets), protected_maps=len(protected))
    section('preservation', preservation)
    result['passed'] = not result['errors']
    result['statistics'] = dict(checks=len(result['checks']), actors=len(actors), rooms=len(plan.get('rooms', [])),
                                route_samples=sum(r['result']['sample_count'] for r in result['routes']),
                                stair_samples=sum(r['result']['sample_count'] for r in result['stairs']),
                                preserved_actors=result.get('preservation', {}).get('preserved_actors', 0))
    return result


def main():
    build = read(WORK / 'BuildReport.json')
    plan = build.get('hotel_v4') or build.get('plan') or build.get('hotel_architecture')
    assert plan is not None, 'Saved BuildReport has no V4 hotel plan.'
    baseline_path = WORK / 'PreservationBaseline.json'
    baseline = read(baseline_path if baseline_path.exists() else WORK / 'InputSnapshot.json')
    target = build['target_level']
    assert target == TARGET, 'Unexpected audit target.'
    mapfile = ROOT / ('Content/'+target.removeprefix('/Game/')+'.umap')
    digest = sha(mapfile)
    assert digest == build['map_sha256'], 'Saved map no longer matches the V4 build.'
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    refreshed = refresh(actors)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result = audit(world, plan, baseline, actors)
    result.update(map_sha256=digest, source='fresh_persisted_map_load', registered_collision_components=refreshed,
                  persisted_map_unchanged=sha(mapfile) == digest)
    if not result['persisted_map_unchanged']:
        result['passed'] = False
        result['errors'].append('persisted_map_changed_during_read_only_audit')
    write('ArchitectureAudit.json', result)
    assert result['passed'], result['errors'][:20]
    unreal.log('HOTEL_V4_AUDIT_PASS '+str(result['statistics']))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('AuditFailure.json', dict(passed=False, traceback=traceback.format_exc()))
        raise
