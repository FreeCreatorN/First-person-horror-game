"""Independent manifest, component and reversible physics audits for openings.

Importing this module outside Unreal is supported. ``validate_manifest`` uses
the Building objects and window planner to derive coverage independently of the
fixture manifest. ``run`` also reads real component hierarchies and performs
closed/open object traces, always restoring the original hinge rotations. It
does not save the level or change assets.

Rotation arrays use Unreal's [pitch, yaw, roll] order, in degrees.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import traceback

try:
    import unreal
except ImportError:
    unreal = None

try:
    from .OldTownArchitectureSealPlan import window_plan, door_coordinates
except ImportError:
    from OldTownArchitectureSealPlan import window_plan, door_coordinates


TOLERANCE = 0.15
FORBIDDEN_WINDOW_ASSETS = (
    '/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_Residential',
    '/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_School',
)
OLD_OPENING_PREFIXES = ('OTS_Seal_Window_', 'OTS_Polish_InnerTrim_', 'OTS_Polish_Door_')


def _report():
    return {'pass': False, 'passed': False, 'checks': [], 'failures': [],
            'limitations': ['Editor object traces do not implement interaction or constitute a runtime walkthrough.']}


def _check(report, name, passed, **details):
    item = dict(details, name=name, passed=bool(passed), **{'pass': bool(passed)})
    report['checks'].append(item)
    if not passed:
        report['failures'].append(name)
    return bool(passed)


def _finish(report):
    report['pass'] = report['passed'] = not report['failures']
    report['statistics'] = dict(report.get('statistics', {}), checks=len(report['checks']),
                                failed_checks=len(report['failures']))
    return report


def _vector(value):
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)


def _near(a, b, tolerance=TOLERANCE):
    return _vector(a) and _vector(b) and all(abs(x-y) <= tolerance for x, y in zip(a, b))


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _asset_path(value):
    return str(value).split('.', 1)[0] if value else None


def _geometry(buildings):
    values = list(buildings.values()) if isinstance(buildings, dict) else list(buildings)
    if not values or any(not all(hasattr(b, name) for name in ('label', 'portals', 'world', 'floors')) for b in values):
        raise ValueError('Pass the independent plan_buildings([], revision_plan) Building objects, not opening manifest rows')
    if len({b.label for b in values}) != len(values):
        raise ValueError('Independent Building labels are duplicated')
    return values


def portal_id_for(building, portal):
    """Stable ID shared by the fixture generator and independent coverage audit."""
    return '{}::{}_{}'.format(building.label, portal['wall'], format(float(portal['coordinate']), '.12g'))


def _descends(components, name, ancestor):
    seen = set()
    while name in components and name not in seen:
        if name == ancestor:
            return True
        seen.add(name)
        name = components[name].get('parent')
    return False


def _is_blocking(row):
    return row.get('collision') in ('QUERY_ONLY', 'QUERY_AND_PHYSICS')


def _hotel_rooms(build_report):
    hotel = build_report.get('hotel_plan', build_report.get('hotel', {}))
    return hotel.get('guest_rooms', []) if isinstance(hotel, dict) else []


def _hotel_windows(build_report):
    hotel = build_report.get('hotel_plan', build_report.get('hotel', {}))
    return hotel.get('guest_windows', []) if isinstance(hotel, dict) else []


def validate_manifest(buildings, build_report):
    """Data-only coverage and mechanical graph checks; no Unreal dependency."""
    report = _report()
    try:
        geometry = _geometry(buildings)
    except Exception as error:
        _check(report, 'independent_geometry', False, reason=str(error))
        return _finish(report)
    spec = build_report.get('opening_components', {})
    _check(report, 'opening_component_schema', spec.get('schema_version') == 1)
    doors, windows = spec.get('doors', []), spec.get('windows', [])
    if not isinstance(doors, list) or not isinstance(windows, list):
        _check(report, 'opening_collections_are_lists', False)
        return _finish(report)
    base_windows = {w['name']: w for b in geometry for w in window_plan(b)}
    guest_windows = _hotel_windows(build_report)
    guest_window_ids = [w.get('window_id') for w in guest_windows]
    _check(report, 'independent_guest_window_ids', all(isinstance(n,str) and n for n in guest_window_ids)
           and len(set(guest_window_ids)) == len(guest_window_ids)
           and not set(guest_window_ids).intersection(base_windows))
    expected_windows = dict(base_windows)
    expected_windows.update({w.get('window_id'):w for w in guest_windows})
    expected_entries = {portal_id_for(b, p): (b, p) for b in geometry for p in b.portals if p.get('primary', True)}
    entry_rows = [d for d in doors if d.get('kind') == 'building_entry']
    guest_rows = [d for d in doors if d.get('kind') == 'hotel_guest']
    _check(report, 'known_door_kinds', len(entry_rows)+len(guest_rows) == len(doors))
    actual_windows = Counter(w.get('window_id') for w in windows)
    actual_entries = Counter(d.get('portal_id') for d in entry_rows)
    _check(report, 'independent_window_coverage', actual_windows == Counter(expected_windows.keys()),
           missing=list((Counter(expected_windows.keys())-actual_windows).elements()),
           unexpected=list((actual_windows-Counter(expected_windows.keys())).elements()),
           expected_count=len(expected_windows), actual_count=len(windows))
    _check(report, 'independent_entry_coverage', actual_entries == Counter(expected_entries.keys()),
           missing=list((Counter(expected_entries.keys())-actual_entries).elements()),
           unexpected=list((actual_entries-Counter(expected_entries.keys())).elements()),
           expected_count=len(expected_entries), actual_count=len(entry_rows))
    rooms = _hotel_rooms(build_report)
    room_ids = [r.get('door_id') for r in rooms]
    guest_doors = {r.get('door_id'):r for r in rooms}
    _check(report, 'independent_guest_door_coverage',
           (not guest_rows and not rooms) or
           bool(rooms) and all(isinstance(k, str) and k for k in room_ids)
           and len(set(room_ids)) == len(room_ids)
           and Counter(d.get('portal_id') for d in guest_rows) == Counter(room_ids),
           planned_guest_doors=room_ids, actual_guest_doors=[d.get('portal_id') for d in guest_rows])
    labels = [r.get('actor') for r in doors+windows]
    _check(report, 'unique_opening_actor_labels', bool(labels) and all(isinstance(k, str) and k for k in labels)
           and len(set(labels)) == len(labels), duplicated=[k for k, v in Counter(labels).items() if v > 1])

    for kind, rows in (('door', doors), ('window', windows)):
        for row in rows:
            label = str(row.get('actor', '<missing>'))
            prefix = kind+':'+label
            width = row.get('opening_width' if kind == 'door' else 'width')
            height = row.get('opening_height' if kind == 'door' else 'height')
            _check(report, prefix+':physical_dimensions', isinstance(width, (int, float)) and width > 0
                   and isinstance(height, (int, float)) and height > 0)
            center = row.get('world_center')
            axes = row.get('axes', {})
            across, inward = axes.get('across'), axes.get('inward')
            good_axes = _vector(across) and _vector(inward) and abs(_dot(across, across)-1) < .001 \
                and abs(_dot(inward, inward)-1) < .001 and abs(_dot(across, inward)) < .001 \
                and abs(across[2])+abs(inward[2]) < .001
            _check(report, prefix+':world_center_and_axes', _vector(center) and good_axes)
            expected = base_windows.get(row.get('window_id')) if kind == 'window' else expected_entries.get(row.get('portal_id'))
            if kind == 'window' and expected:
                b = next(b for b in geometry if b.label == expected['building'])
                expected_center = b.world(expected['u'], expected['v'], expected['z'])
                sign = 1 if expected['wall'] == 'Front' else -1
                normal = [0., 0., 0.]; normal[b.normal_axis] = b.inward*sign
                lateral = [0., 0., 0.]; lateral[b.u_axis] = 1.
                _check(report, prefix+':independent_window_geometry', row.get('building') == b.label
                       and width == expected['width'] and height == expected['height']
                       and _near(center, expected_center) and good_axes
                       and abs(_dot(across, lateral)) > .999 and _dot(inward, normal) > .999,
                       expected_center_cm=expected_center)
            if kind == 'door' and expected:
                b, p = expected
                exterior = door_coordinates(b, p, 0., 0., b.ground)
                lateral = [x-y for x,y in zip(door_coordinates(b,p,1.,0.,0.), door_coordinates(b,p,0.,0.,0.))]
                normal = [x-y for x,y in zip(door_coordinates(b,p,0.,1.,0.), door_coordinates(b,p,0.,0.,0.))]
                delta = [x-y for x,y in zip(center, exterior)] if _vector(center) else None
                foot = row.get('entry_foot')
                good = good_axes and delta is not None and abs(_dot(delta,lateral)) <= TOLERANCE \
                    and abs(delta[2]) <= TOLERANCE and -1. <= _dot(delta,normal) <= 21. \
                    and abs(_dot(across,lateral)) > .999 and _dot(inward,normal) > .999
                _check(report, prefix+':independent_entry_geometry', good and row.get('building') == b.label
                       and width == b.door_width and height == b.door_height
                       and _vector(foot) and abs(foot[2]-b.ground) <= TOLERANCE,
                       expected_exterior_center_cm=exterior)
            guest = (expected_windows.get(row.get('window_id')) if kind == 'window' and row.get('window_id') not in base_windows
                     else guest_doors.get(row.get('portal_id')) if kind == 'door' and row.get('kind') == 'hotel_guest' else None)
            if guest:
                expected_width = guest.get('width' if kind == 'window' else 'opening_width')
                expected_height = guest.get('height' if kind == 'window' else 'opening_height')
                expected_axes = guest.get('axes',{})
                _check(report, prefix+':independent_hotel_geometry', row.get('kind') == 'hotel_guest'
                       and row.get('building') == guest.get('building') and width == expected_width and height == expected_height
                       and _near(center,guest.get('world_center')) and good_axes
                       and _near(across,expected_axes.get('across'),.001) and _near(inward,expected_axes.get('inward'),.001),
                       expected_center_cm=guest.get('world_center'))
            declared = row.get('components', [])
            by = {c.get('name'): c for c in declared if isinstance(c, dict)}
            graph_ok = len(by) == len(declared) and bool(by) and all(isinstance(n, str) and n for n in by)
            _check(report, prefix+':unique_named_components', graph_ok)
            roots = [n for n,c in by.items() if c.get('parent') is None]
            _check(report, prefix+':single_component_root', len(roots) == 1, roots=roots)
            for name, component in by.items():
                parent = component.get('parent')
                seen = {name}; cursor = parent; cycle = False
                while cursor in by:
                    if cursor in seen:
                        cycle = True; break
                    seen.add(cursor); cursor = by[cursor].get('parent')
                valid_parent = parent is None or parent in by and parent != name
                _check(report, prefix+':component_graph:'+str(name), valid_parent and not cycle,
                       parent=parent, cycle=cycle)
                mobility, collision = component.get('mobility'), component.get('collision')
                asset = component.get('asset')
                _check(report, prefix+':component_properties:'+str(name),
                       mobility in ('STATIC','MOVABLE') and collision in ('NO_COLLISION','QUERY_ONLY','QUERY_AND_PHYSICS')
                       and (asset is None or isinstance(asset,str) and (asset.startswith('/Game/') or _asset_path(asset)=='/Engine/BasicShapes/Cube'))
                       and _vector(component.get('relative_location')) and _vector(component.get('relative_rotation'))
                       and _vector(component.get('relative_scale')) and all(
                           v > 0 if _is_blocking(component) else abs(v)>0 for v in component.get('relative_scale', [])))
            hinges = ('DoorHinge',) if kind == 'door' else ('LeftHinge','RightHinge')
            moving = ('DoorLeaf',) if kind == 'door' else ('LeftSash','LeftGlass','RightSash','RightGlass')
            closed, opened = row.get('closed_hinges', {}), row.get('open_hinges', {})
            _check(report, prefix+':complete_hinge_states', set(closed) == set(hinges) == set(opened))
            for hinge in hinges:
                c = by.get(hinge, {})
                close, op = closed.get(hinge), opened.get(hinge)
                states_ok = _vector(close) and _vector(op) and abs(close[0])+abs(close[2])+abs(op[0])+abs(op[2]) < .001 \
                    and abs(close[1]) < .001 and 75 <= abs(op[1]) <= 110
                blockers = [n for n,c in by.items() if _is_blocking(c) and _descends(by,n,hinge)]
                _check(report, prefix+':movable_hinge:'+hinge, c.get('mobility') == 'MOVABLE' and states_ok
                       and bool(blockers) and all(by[n].get('mobility') == 'MOVABLE' for n in blockers),
                       blocking_descendants=blockers, closed=close, opened=op)
            for name in moving:
                hinge = 'DoorHinge' if kind == 'door' else ('LeftHinge' if name.startswith('Left') else 'RightHinge')
                c = by.get(name, {})
                _check(report, prefix+':moving_part:'+name, bool(c.get('asset'))
                       and c.get('mobility') == 'MOVABLE' and _descends(by,name,hinge))
            frame = _asset_path(row.get('frame_asset'))
            _check(report, prefix+':independent_fixed_frame', bool(frame) and any(
                _asset_path(c.get('asset')) == frame and c.get('mobility') == 'STATIC'
                and not any(_descends(by,n,h) for h in hinges) for n,c in by.items()))
            if kind == 'door':
                _check(report, prefix+':leaf_asset_reference', _asset_path(by.get('DoorLeaf',{}).get('asset'))
                       == _asset_path(row.get('leaf_asset')) and bool(row.get('leaf_asset')))
                _check(report, prefix+':hinge_side', row.get('hinge_side') in (-1,1))
            else:
                _check(report, prefix+':opposite_window_swing', _vector(opened.get('LeftHinge'))
                       and _vector(opened.get('RightHinge')) and opened['LeftHinge'][1]*opened['RightHinge'][1] < 0)
    report['statistics'] = {'window_count': len(windows), 'building_window_count':len(base_windows),
                            'hotel_guest_window_count':len(guest_windows), 'building_entry_count': len(entry_rows),
                            'hotel_guest_door_count': len(guest_rows)}
    return _finish(report)


def _xyz(value):
    return [float(getattr(value, key)) for key in ('x','y','z')]


def _rot(value):
    return [float(getattr(value, key)) for key in ('pitch','yaw','roll')]


def _enum(value):
    return str(value).rsplit('.',1)[-1].upper().split(':',1)[0].strip(' >')


def _name(component):
    return component.get_name().removesuffix('_GEN_VARIABLE') if component is not None else None


def component_index(actor):
    """Every named SceneComponent, including boxes and both glass panes."""
    result = defaultdict(list)
    for component in actor.get_components_by_class(unreal.SceneComponent):
        result[_name(component)].append(component)
    return result


def audit_scene(report, actors, build_report):
    """Read-only component inventory checks; physics is a separate helper."""
    spec = build_report['opening_components']
    by = defaultdict(list)
    for actor in actors:
        by[actor.get_actor_label()].append(actor)
    _check(report, 'all_actor_labels_unique', all(len(v) == 1 for v in by.values()))
    removed = set(spec.get('removed_actor_labels', []))
    stale = sorted(removed.intersection(by))
    stale += sorted(n for n in by if n.startswith(OLD_OPENING_PREFIXES)
                    or n.startswith('OTS_Enterable_') and any(x in n for x in ('_WindowGlass_', '_DoorFrame_', '_DoorLeaf_', '_DoorHandle_')))
    _check(report, 'old_opening_actors_removed', not stale, stale_actor_labels=sorted(set(stale)))
    forbidden = set(map(_asset_path, FORBIDDEN_WINDOW_ASSETS+tuple(spec.get('forbidden_mesh_assets', []))))
    bars = []
    for actor in actors:
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = component.get_editor_property('static_mesh')
            if mesh is not None and _asset_path(mesh.get_path_name()) in forbidden:
                bars.append(actor.get_actor_label()+':'+_name(component))
    _check(report, 'zero_barred_window_mesh_instances', not bars, barred_components=bars)
    resolved = {}
    for row in spec['doors']+spec['windows']:
        label = row['actor']; owners = by.get(label, [])
        if not _check(report, 'opening_actor:'+label, len(owners) == 1):
            continue
        actor = owners[0]; index = component_index(actor); components = {}
        for expected in row['components']:
            name = expected['name']; actual = index.get(name, [])
            if not _check(report, 'component_exists:'+label+':'+name, len(actual) == 1):
                continue
            component = actual[0]; components[name] = component
            parent = _name(component.get_attach_parent())
            _check(report, 'component_parent:'+label+':'+name, parent == expected['parent'], actual_parent=parent)
            _check(report, 'component_mobility:'+label+':'+name,
                   component.get_editor_property('mobility') == getattr(unreal.ComponentMobility,expected['mobility']))
            _check(report, 'component_transform:'+label+':'+name,
                   _near(_xyz(component.get_editor_property('relative_location')), expected['relative_location'])
                   and _near(_rot(component.get_editor_property('relative_rotation')), expected['relative_rotation'])
                   and _near(_xyz(component.get_editor_property('relative_scale3d')), expected['relative_scale']))
            if isinstance(component, unreal.PrimitiveComponent):
                mode = getattr(unreal.CollisionEnabled,expected['collision'])
                _check(report, 'component_collision:'+label+':'+name, component.get_collision_enabled() == mode)
                if _is_blocking(expected):
                    _check(report, 'component_blocks_pawn_and_visibility:'+label+':'+name, all(
                        component.get_collision_response_to_channel(channel) == unreal.CollisionResponseType.ECR_BLOCK
                        for channel in (unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_VISIBILITY)))
            else:
                _check(report, 'scene_component_has_no_collision:'+label+':'+name, expected['collision'] == 'NO_COLLISION')
            mesh = component.get_editor_property('static_mesh') if isinstance(component,unreal.StaticMeshComponent) else None
            path = _asset_path(mesh.get_path_name()) if mesh is not None else None
            _check(report, 'component_mesh:'+label+':'+name, path == _asset_path(expected['asset']), actual_asset=path)
        unexpected = []
        for name, candidates in index.items():
            if name in {c['name'] for c in row['components']}:
                continue
            for component in candidates:
                # Editor-only icons do not participate in the fixture hierarchy.
                try:
                    editor_only = component.get_editor_property('is_editor_only')
                except Exception:
                    editor_only = False
                if not editor_only:
                    unexpected.append(name)
        _check(report, 'no_undeclared_fixture_components:'+label, not unexpected, unexpected=unexpected)
        resolved[label] = (actor,components)
    return resolved


def _trace(world, start, end):
    hit = unreal.SystemLibrary.line_trace_single_for_objects(
        world, unreal.Vector(*start), unreal.Vector(*end),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        False, [], unreal.DrawDebugTrace.NONE)
    if hit is None:
        return {'blocked':False, 'component':None, 'actor':None}
    values = hit.to_tuple()
    component, actor = values[10], values[9]
    return {'blocked':bool(values[0]), 'component':component, 'actor':actor}


def _sample_lines(row, is_door):
    center, across, normal = row['world_center'], row['axes']['across'], row['axes']['inward']
    width = row['opening_width'] if is_door else row['width']
    height = row['opening_height'] if is_door else row['height']
    samples = [(0.,0.)] if is_door else [(side*width*.25,vertical*height*.2) for side in (-1.,1.) for vertical in (-1.,1.)]
    for across_offset, z_offset in samples:
        p = [center[i]+across[i]*across_offset for i in range(3)]; p[2] += z_offset+(height*.5 if is_door else 0.)
        yield [p[i]-normal[i]*60. for i in range(3)], [p[i]+normal[i]*60. for i in range(3)]


def _component_center(component):
    if isinstance(component,unreal.PrimitiveComponent):
        center,_extent,_sphere = unreal.SystemLibrary.get_component_bounds(component)
        return _xyz(center)
    return _xyz(component.get_world_transform().translation)


def audit_physics(world, rows, resolved, report):
    """Close, trace, open, trace, then restore every original hinge rotation.

    Missing components or unavailable tracing are failures, never skips. This
    helper mutates only hinge rotation transiently; a finally block restores
    all original values even when a trace or component query raises.
    """
    for row in rows:
        label = row['actor']; is_door = 'portal_id' in row
        if label not in resolved:
            _check(report, 'mechanical_physics:'+label, False, reason='Opening actor was not resolved')
            continue
        _actor, components = resolved[label]
        hinges = ('DoorHinge',) if is_door else ('LeftHinge','RightHinge')
        if any(h not in components for h in hinges):
            _check(report, 'mechanical_physics:'+label, False, reason='Hinge component missing')
            continue
        original = {h:_rot(components[h].get_editor_property('relative_rotation')) for h in hinges}
        original_positions = {n:_xyz(c.get_world_transform().translation) for n,c in components.items()}
        pivots = {h:_xyz(components[h].get_world_transform().translation) for h in hinges}
        declared = {c['name']:c for c in row['components']}
        try:
            closed_positions = {}
            for state in ('closed','open'):
                for h in hinges:
                    rotation = row[state+'_hinges'][h]
                    components[h].set_relative_rotation(unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]),False,True)
                current_positions = {n:_xyz(c.get_world_transform().translation) for n,c in components.items()}
                _check(report, state+'_hinge_pivot_stable:'+label,
                       all(_near(current_positions[h],pivots[h]) for h in hinges))
                if state == 'closed':
                    closed_positions = {n:_component_center(c) for n,c in components.items()}
                    width = row['opening_width'] if is_door else row['width']
                    across = row['axes']['across']; center = row['world_center']; normal = row['axes']['inward']
                    coordinates = {}
                    for h in hinges:
                        delta = [current_positions[h][i]-center[i] for i in range(3)]
                        coordinates[h] = {'across_cm':_dot(delta,across),'depth_cm':_dot(delta,normal)}
                    _check(report, 'hinges_at_opening_edges:'+label, all(
                        abs(abs(p['across_cm'])-width*.5) <= 8. and abs(p['depth_cm']) <= 23.
                        for p in coordinates.values()) and (is_door or
                        coordinates['LeftHinge']['across_cm']*coordinates['RightHinge']['across_cm'] < 0),
                        hinge_coordinates=coordinates)
                else:
                    blocking_names = [n for n,c in declared.items() if _is_blocking(c)
                                      and any(_descends(declared,n,h) for h in hinges)]
                    moved = {n:math.dist(closed_positions[n], _component_center(components[n])) for n in blocking_names if n in components}
                    _check(report, 'collision_follows_hinges:'+label, bool(moved)
                           and len(moved) == len(blocking_names) and all(v > 5. for v in moved.values()),
                           collider_displacement_cm=moved)
                traces = []
                for start,end in _sample_lines(row,is_door):
                    result = _trace(world,start,end)
                    target = result['actor'] is not None and result['actor'].get_actor_label() == label
                    cname = _name(result['component'])
                    moving = cname in declared and any(_descends(declared,cname,h) for h in hinges)
                    passed = result['blocked'] and target and moving if state == 'closed' else not result['blocked']
                    traces.append({'passed':passed,'start_cm':start,'end_cm':end,'blocked':result['blocked'],
                                   'hit_actor':result['actor'].get_actor_label() if result['actor'] else None,
                                   'hit_component':cname})
                _check(report, state+'_opening_traces:'+label, all(r['passed'] for r in traces), samples=traces)
        except Exception:
            _check(report, 'mechanical_physics:'+label, False, traceback=traceback.format_exc())
        finally:
            failures = []
            for h,rotation in original.items():
                try:
                    components[h].set_relative_rotation(unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]),False,True)
                except Exception:
                    failures.append(h)
            _check(report, 'original_hinge_state_restored:'+label, not failures and all(
                _near(_rot(components[h].get_editor_property('relative_rotation')),rotation)
                for h,rotation in original.items()), restoration_failures=failures)
            _check(report, 'original_component_positions_restored:'+label, all(
                _near(_xyz(c.get_world_transform().translation),original_positions[n]) for n,c in components.items()))


def run(world, actors, buildings, build_report, reportfile=None):
    """Complete loaded-world audit. All missing prerequisites fail explicitly."""
    report = validate_manifest(buildings,build_report)
    if unreal is None or world is None:
        _check(report, 'loaded_unreal_world_required', False)
    else:
        try:
            resolved = audit_scene(report,list(actors),build_report)
            spec = build_report['opening_components']
            audit_physics(world,spec['doors']+spec['windows'],resolved,report)
        except Exception:
            _check(report, 'component_audit_exception',False,traceback=traceback.format_exc())
    _finish(report)
    if reportfile is not None:
        path = Path(reportfile); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
