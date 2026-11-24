"""Re-cut hotel guest-bath door walls against their front inside corners.

This stage moves only two existing wall actors per bath. Door and fixture
changes and the level save are owned by the caller. Importing has no effects.
"""
from math import isclose
import re

try:
    import unreal
except ImportError:
    unreal = None

TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
DOOR_PATTERN = re.compile(r'^OTS_HotelV4_Door_Room([234]0[1-9])_BathDoor$')
PREFIX = 'OTS_HotelV4_'
CUBE = '/Engine/BasicShapes/Cube.Cube'
ROUGH_WIDTH = 93.0
ROUGH_HEIGHT = 209.0
CLEAR_WIDTH = 85.0
CLEAR_HEIGHT = 205.0
SLIDE_TRAVEL = 90.0
EPS = .02


def _require(condition, info):
    if not condition:
        raise RuntimeError(str(info))


def _xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def _close(a, b):
    return isclose(a, b, abs_tol=EPS, rel_tol=0.)


def _same_box(a, b):
    return all(_close(a[end][i], b[end][i]) for end in (0,1) for i in range(3))


def _bounds(component):
    origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    center, half = _xyz(origin), _xyz(extent)
    return [[center[i] + sign * half[i] for i in range(3)] for sign in (-1.,1.)]


def _wall_state(actor):
    _require(isinstance(actor, unreal.StaticMeshActor) and actor.get_attach_parent_actor() is None, actor.get_actor_label())
    comp = actor.static_mesh_component
    _require(comp.static_mesh and comp.static_mesh.get_path_name() == CUBE, actor.get_actor_label())
    for name, val in zip(('forward', 'right', 'up'), (actor.get_actor_forward_vector(), actor.get_actor_right_vector(), actor.get_actor_up_vector())):
        expected = dict(forward=[1.,0.,0.], right=[0.,1.,0.], up=[0.,0.,1.])[name]
        _require(all(_close(a,b) for a,b in zip(_xyz(val),expected)), (actor.get_actor_label(), name, _xyz(val)))
    return dict(bounds=_bounds(comp), actor=actor.get_path_name(),
                mesh=comp.static_mesh.get_path_name(),
                materials=[m.get_path_name() if m is not None else None
                           for m in (comp.get_material(i) for i in range(comp.get_num_materials()))],
                collision=str(comp.get_collision_enabled()), profile=str(comp.get_collision_profile_name()),
                actor_collision=bool(actor.get_actor_enable_collision()),
                rotation=_xyz(actor.get_actor_forward_vector()), folder=str(actor.get_folder_path()),
                tags=[str(tag) for tag in actor.tags])


def _by_label(actor_subsystem):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    _require(world and world.get_path_name().startswith(TARGET + '.'), 'Expected original old-town level')
    actors = list(actor_subsystem.get_all_level_actors())
    # Non-hotel actor labels may legitimately be duplicated. Only names used
    # by the bathroom operation must be unique.
    by = {}
    for actor in actors:
        name = actor.get_actor_label()
        if name.startswith(PREFIX) and ('_Bath' in name or '_Basin' in name or '_WetRiser' in name):
            _require(name not in by, 'Ambiguous bathroom label: ' + name)
            by[name] = actor
    return by


def _desired_plan(room_id, old_location, walls):
    door_label = PREFIX + 'Door_Room' + room_id + '_BathDoor'
    stem = PREFIX + 'Room' + room_id
    right_names = [stem + '_BathRight_%02d' % i for i in range(3)]
    near, far, header = (walls[n]['bounds'] for n in right_names)
    front = walls[stem + '_BathFront_00']['bounds']
    back = walls[stem + '_BathRear_00']['bounds']
    left = walls[stem + '_BathLeft_00']['bounds']
    xmin, ymin, z = near[0]
    xmax, ymax, top = far[1]
    old_x, cy, old_z = old_location
    _require(all(_close(a,b) for a,b in ((xmin,front[1][0]), (xmax,back[1][0]),
             (old_z,z), (cy,(ymin+ymax)*.5), (ymax-ymin,12.), (xmax-xmin,234.),
             (near[1][0],old_x-ROUGH_WIDTH*.5), (far[0][0],old_x+ROUGH_WIDTH*.5),
             (header[0][0],near[1][0]), (header[1][0],far[0][0]),
             (header[0][2],z+ROUGH_HEIGHT))), ('Unexpected existing opening', room_id, old_location, near, far, header))
    x1 = xmin + ROUGH_WIDTH
    center = xmin + ROUGH_WIDTH*.5
    wall_stop = back[0][0]
    stow = [[x1,ymin,z],[wall_stop,ymax,z+CLEAR_HEIGHT]]
    _require(wall_stop-x1 >= CLEAR_WIDTH+10., ('Insufficient stow wall', room_id, stow))
    _require(far[0][0] > x1, ('Old far segment already at corner', room_id))
    replacement = {
        right_names[0]: [[x1,ymin,z], [far[0][0],ymax,top]],
        right_names[1]: far,
        right_names[2]: [[xmin,ymin,z+ROUGH_HEIGHT],[x1,ymax,top]],
    }
    # Surface track stays on dry/guest side (+world Y). Do not reduce the
    # bathroom footprint or use a recessed panel which would hit the solid wall.
    approach = [[center,cy+75.,z], [center,cy-45.,z]]
    use_basin = [xmin+137.,cy-83.5,z]
    basin_route = approach + [[use_basin[0],cy-45.,z],use_basin]
    return dict(room_id=room_id, door_label=door_label,
        old_location=list(old_location), new_location=[center,cy,z], floor_z=z,
        wall_labels=right_names, wall_source=walls, wall_targets=replacement,
        rough_opening_bounds=[[xmin,ymin,z],[x1,ymax,z+ROUGH_HEIGHT]],
        clear_opening_bounds=[[xmin+4.,ymin,z],[x1-4.,ymax,z+CLEAR_HEIGHT]],
        stow_wall_bounds=stow, stow_wall_width_cm=wall_stop-x1,
        room_bounds=[[front[1][0],left[1][1],z],[wall_stop,ymin,top]],
        approach_route=approach, basin_approach_route=basin_route,
        basin_label=stem+'_Basin', basin_collision_labels=[],
        basin_target=[wall_stop-25.,cy-83.5,z],
        slide_world_cm=[SLIDE_TRAVEL,0.,0.],
        suggested_leaf_world_y=cy+11., suggested_leaf_root_local_y=-11.)


def plan_bathroom_openings(actor_subsystem, labels=None):
    """Read exact current transforms; build a JSON-compatible plan, no mutation."""
    by = _by_label(actor_subsystem)
    all_rooms = {m.group(1) for n in by if (m := DOOR_PATTERN.fullmatch(n))}
    if labels is None:
        _require(len(all_rooms)==27, ('Expected 27 guest bathroom doors',len(all_rooms)))
        rooms = all_rooms
    else:
        rooms = {(m.group(1) if (m := DOOR_PATTERN.fullmatch(str(n))) else str(n)) for n in labels}
        _require(rooms and rooms <= all_rooms, ('Unmatched guest bath identifiers', sorted(rooms-all_rooms)))
    plans = []
    for rid in sorted(rooms):
        stem = PREFIX + 'Room' + rid
        wall_names = [stem + n for n in ('_BathFront_00','_BathLeft_00','_BathRear_00','_BathRight_00','_BathRight_01','_BathRight_02')]
        _require(all(n in by for n in wall_names), ('Guest bath wall actors missing', rid))
        door = by[PREFIX + 'Door_Room' + rid + '_BathDoor']
        _require(abs(door.get_actor_forward_vector().x+1.) < EPS, ('Unexpected door orientation',rid))
        p = _desired_plan(rid,_xyz(door.get_actor_location()),{n:_wall_state(by[n]) for n in wall_names})
        p['basin_collision_labels'] = sorted(n for n in by if n.startswith(p['basin_label']+'_Collision'))
        _require(p['basin_label'] in by and p['basin_collision_labels'], ('Basin not found',rid))
        plans.append(p)
    return plans


def _resize_x(actor, target):
    state = _wall_state(actor)
    old = state['bounds']
    _require(all(_close(old[k][i],target[k][i]) for k in (0,1) for i in (1,2)),
             ('Only wall X span may change', actor.get_actor_label(),old,target))
    size = target[1][0]-target[0][0]
    _require(size > 1., ('Invalid partition segment width',actor.get_actor_label(),size))
    scale = actor.get_actor_scale3d()
    scale.x *= size/(old[1][0]-old[0][0])
    location = actor.get_actor_location()
    location.x += ((target[0][0]+target[1][0])-(old[0][0]+old[1][0]))*.5
    actor.modify()
    actor.set_actor_scale3d(scale)
    _require(actor.set_actor_location(location,False,True), ('Could not move wall actor',actor.get_actor_label()))
    _require(_same_box(_bounds(actor.static_mesh_component),target),
             ('Wall bounds did not update',actor.get_actor_label(),_bounds(actor.static_mesh_component),target))


def apply_bathroom_walls(actor_subsystem, plans):
    """Move the short wall and header; no actors/assets are removed or saved."""
    by = _by_label(actor_subsystem)
    # Validate the entire set before the first modification.
    for p in plans:
        for name, before in p['wall_source'].items():
            actual = _wall_state(by[name])
            _require(actual == before, ('Bathroom source changed after planning',name))
    for p in plans:
        for name,target in p['wall_targets'].items():
            if not _same_box(p['wall_source'][name]['bounds'],target):
                _resize_x(by[name],target)
    return verify_bathroom_walls(actor_subsystem,plans)


def verify_bathroom_walls(actor_subsystem, plans):
    """Check exact retained geometry, material, actor identity and collision."""
    by = _by_label(actor_subsystem)
    reports = []
    for p in plans:
        n0,n1,nh = p['wall_labels']
        shape = {}
        for name, before in p['wall_source'].items():
            actual = _wall_state(by[name])
            target = p['wall_targets'].get(name,before['bounds'])
            _require(_same_box(actual['bounds'],target), ('Incorrect bath wall bounds',name,actual['bounds'],target))
            _require(all(actual[key] == value for key,value in before.items() if key!='bounds'),
                     ('Wall actor, material or collision changed',name))
            shape[name] = actual['bounds']
        first, second, head = shape[n0],shape[n1],shape[nh]
        cut = p['rough_opening_bounds']
        _require(all(_close(a,b) for a,b in (
            (first[0][0],cut[1][0]), (first[1][0],second[0][0]),
            (head[0][0],cut[0][0]), (head[1][0],cut[1][0]),
            (head[0][2],cut[1][2]), (head[1][2],first[1][2]))),
            ('Opening header or contiguous stow wall has a gap',p['room_id']))
        opening_x = cut[1][0]-cut[0][0]
        _require(_close(opening_x,ROUGH_WIDTH) and p['stow_wall_width_cm'] >= CLEAR_WIDTH+10.,
                 ('Insufficient doorway or stow width',p['room_id']))
        reports.append(dict(room_id=p['room_id'],passed=True,
            rough_opening_bounds=cut, clear_opening_bounds=p['clear_opening_bounds'],
            stow_wall_width_cm=p['stow_wall_width_cm'],room_bounds=p['room_bounds'],
            wall_actor_count=len(shape), resized_actor_labels=[n for n,t in p['wall_targets'].items()
                if not _same_box(t,p['wall_source'][n]['bounds'])]))
    return dict(passed=True,bathrooms=len(reports),checks=reports,
                moved_wall_actor_count=sum(len(r['resized_actor_labels']) for r in reports),
                wall_actor_count_unchanged=True, original_level=TARGET)
