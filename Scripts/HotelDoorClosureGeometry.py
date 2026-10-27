"""Independent fitted door leaves, offset hinges and rebated stops, in cm.

No Unreal imports or asset writes.  The original hinge module stays unchanged.
``geometry_for_door(row)`` returns ``moving`` and ``stops`` closed mesh data,
their primitive recipes, and the required moving leaf/handle/collider offset.
Rows need width/height; depth defaults to 20, hinge_side to -1 and
leaf_depth_offset to -5.  hinge_side=0 describes a sliding door without hinges.

Keep the existing hinge axis at depth/2+3.  Moving the wood, its collision and
its handles inward 5 cm makes its front face flush with a depth-wide frame.
Only the moving metal mounting plate and its neck's distant endpoint follow
that offset.  The fixed metal, pivot, pin and moving knuckles do not move.
"""
from copy import deepcopy
import math

import OldTownDoorHingeGeometry as original

SCHEMA = 'HotelDoorClosureV1'
DEFAULT_OFFSET_CM = -5.
LEAF_THICKNESS_CM = 4.
STOP_FRONT_GAP_CM = .25
STOP_INSET_CM = .8
STOP_THICKNESS_CM = 1.
PLATE_RELIEF_CM = .25


def _box(name, center, size, **extra):
    return dict(name=name, kind='box', center=list(center), size=list(size),
                yaw_deg=0., collision='NoCollision', **extra)


def _parameters(width, height, depth, hinge_side, leaf_depth_offset):
    values = [float(width), float(height), float(depth),
              float(leaf_depth_offset)]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Door dimensions and offsets must be finite')
    width, height, depth, leaf_depth_offset = values
    side = int(hinge_side)
    if side != hinge_side or side not in (-1, 0, 1):
        raise ValueError('hinge_side must be -1, 0 or 1')
    if width < 70 or height < 180 or depth < 4:
        raise ValueError('Unsupported door dimensions')
    return width, height, depth, side, leaf_depth_offset


def moving_hinge_specs(width, height, depth=20., hinge_side=-1,
                       leaf_depth_offset=DEFAULT_OFFSET_CM):
    """Clone the old metal recipe, changing only plate depth and neck endpoint."""
    width, height, depth, side, offset = _parameters(
        width, height, depth, hinge_side, leaf_depth_offset)
    if side == 0:
        return []
    parts = deepcopy(original.primitive_specs(width, height, depth, side)['moving'])
    for part in parts:
        if part['name'].endswith('_DoorLeaf'):
            part['center'][1] += offset
        elif part['name'].endswith('_MovingNeck'):
            first, second = deepcopy(part['bridge_endpoints_cm'])
            second[1] += offset
            delta = [b-a for a, b in zip(first, second)]
            part['bridge_endpoints_cm'] = [first, second]
            part['center'] = [(a+b)/2 for a, b in zip(first, second)]
            part['size'][0] = math.hypot(delta[0], delta[1])
            part['yaw_deg'] = math.degrees(math.atan2(delta[1], delta[0]))
    return parts


def stop_specs(width, height, depth=20., hinge_side=-1,
               leaf_depth_offset=DEFAULT_OFFSET_CM):
    """Return three-sided stops, with plate reliefs on the swinging hinge side.

    The stops overlap each jamb into the opening by .8 cm.  Their front face
    is .25 cm behind the closed wood, avoiding coplanar render surfaces.  On
    the hinge side the three 4.2 cm-high plates each have .25 cm of clearance
    above and below: that upright is four segments.  A slider has three whole
    stops.  All parts are intended to be aggregated into one static mesh.
    Uprights end at the header's bottom, so their coplanar front faces do not
    overlap at the corners.
    """
    width, height, depth, side, offset = _parameters(
        width, height, depth, hinge_side, leaf_depth_offset)
    rear = depth/2+3+offset-LEAF_THICKNESS_CM/2
    front = rear-STOP_FRONT_GAP_CM
    center_y = front-STOP_THICKNESS_CM/2
    width_strip = STOP_INSET_CM*2
    upright_top = height-STOP_INSET_CM
    parts = []
    for edge_side, edge_name in ((-1, 'Left'), (1, 'Right')):
        intervals = [(0., upright_top)]
        if side and edge_side == side:
            half_relief = 4.2/2+PLATE_RELIEF_CM
            intervals = []
            start = 0.
            for z in (22., height/2, height-22.):
                intervals.append((start, z-half_relief))
                start = z+half_relief
            intervals.append((start, upright_top))
        for index, (lo, hi) in enumerate(intervals):
            if hi <= lo:
                raise ValueError('Overlapping hinge reliefs')
            parts.append(_box('Stop'+edge_name+'_%02d'%index,
                              [edge_side*width/2, center_y, (lo+hi)/2],
                              [width_strip, STOP_THICKNESS_CM, hi-lo],
                              stop_side=edge_name, group=len(parts)))
    parts.append(_box('StopTop', [0., center_y, height],
                      [width+width_strip, STOP_THICKNESS_CM, width_strip],
                      stop_side='Top', group=len(parts)))
    return parts


def geometry_for_door(row, radial_sides=24):
    """Return closed solids in DoorHinge space (moving) / OpeningRoot (stops)."""
    width, height, depth, side, offset = _parameters(
        row['width'], row['height'], row.get('depth', 20.),
        row.get('hinge_side', -1), row.get('leaf_depth_offset', DEFAULT_OFFSET_CM))
    moving = moving_hinge_specs(width, height, depth, side, offset)
    stops = stop_specs(width, height, depth, side, offset)
    old = original.primitive_specs(width, height, depth, side) if side else None
    leaf_center_y = depth/2+3+offset
    recipe = dict(schema=SCHEMA, units='centimetres', width_cm=width,
                  height_cm=height, depth_cm=depth, hinge_side=side,
                  leaf_depth_offset_cm=offset,
                  moving_component_depth_delta_cm=offset,
                  moving_components=('DoorLeaf', 'LeafCollision', 'Handle')
                  if side else ('LeftLeaf', 'RightLeaf', 'LeftLeafCollision',
                                'RightLeafCollision', 'LeftHandle', 'RightHandle'),
                  hinge_axis_opening_root_cm=old['hinge_axis_opening_root_cm']
                  if old else None,
                  closed_leaf_y_cm=[leaf_center_y-2., leaf_center_y+2.],
                  frame_front_y_cm=depth/2,
                  stop_front_y_cm=leaf_center_y-2.-STOP_FRONT_GAP_CM,
                  stop_front_gap_cm=STOP_FRONT_GAP_CM,
                  stop_inset_cm=STOP_INSET_CM,
                  plate_vertical_relief_cm=PLATE_RELIEF_CM,
                  fixed=deepcopy(old['fixed']) if old else [],
                  moving=moving, stops=stops)
    return dict(recipe=recipe,
                moving=original.build_closed_geometry(moving, radial_sides),
                stops=original.build_closed_geometry(stops, radial_sides))


def _polygon(part):
    return original._rectangle(part['center'][:2], part['size'][:2],
                               math.radians(part.get('yaw_deg', 0.)))


def _rotate(polygon, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [(c*x-s*y, s*x+c*y) for x, y in polygon]


def _z_range(part):
    return (part['center'][2]-part['size'][2]/2,
            part['center'][2]+part['size'][2]/2)


def _z_overlaps(first, second):
    aa, bb = _z_range(first), _z_range(second)
    return min(aa[1], bb[1]) > max(aa[0], bb[0])+1.e-9


def _fixed_normalized(part, axis, direction):
    return [(direction*(x-axis[0]), y-axis[1]) for x, y in _polygon(part)]


def _moving_normalized(part, direction):
    return [(direction*x, y) for x, y in _polygon(part)]


def validate_recipe(row, angles=(0., 30., 60., 90.)):
    """Check closed solids, contact, and wood/metal clearance through a sweep.

    The sweep tests both jambs, header, fixed mounting pads/necks and stops.
    Coaxial fixed/moving bearings intentionally share their pin and are not
    treated as collisions.  This is ideal authored geometry: real mesh bounds,
    shader displacement, attachment transforms and gameplay need live checks.
    Supply more angles for finer sampling; no geometry or files are mutated.
    """
    data = geometry_for_door(row)
    r = data['recipe']
    width, height, depth = r['width_cm'], r['height_cm'], r['depth_cm']
    side, offset = r['hinge_side'], r['leaf_depth_offset_cm']
    checks = []
    checks.append(dict(check='wood_front_flush_with_frame',
                       passed=abs(r['closed_leaf_y_cm'][1]-r['frame_front_y_cm']) < 1.e-9))
    checks.append(dict(check='stop_front_clearance',
                       passed=abs(r['closed_leaf_y_cm'][0]-r['stop_front_y_cm']-
                                  STOP_FRONT_GAP_CM) < 1.e-9))
    for name in ('moving', 'stops'):
        for part in original._piece_closure(data[name]):
            checks.append(dict(check=name+'_closed_solid', **part))
    expected_parts = 6 if side else 3
    checks.append(dict(check='stop_piece_count',
                       passed=len(r['stops']) == expected_parts,
                       count=len(r['stops'])))
    overlapping_stops = []
    for index, first in enumerate(r['stops']):
        for second in r['stops'][index+1:]:
            if (_z_overlaps(first, second) and
                    original._positive_polygon_overlap(_polygon(first), _polygon(second))):
                overlapping_stops.append([first['name'], second['name']])
    checks.append(dict(check='stop_solids_do_not_overlap',
                       passed=not overlapping_stops, overlaps=overlapping_stops))
    sweep = []
    if side:
        old = original.primitive_specs(width, height, depth, side)
        checks.append(dict(check='fixed_hardware_unchanged', passed=r['fixed'] == old['fixed']))
        unchanged = [p for p in old['moving'] if p['name'].endswith('_MovingKnuckle')]
        observed = [p for p in r['moving'] if p['name'].endswith('_MovingKnuckle')]
        checks.append(dict(check='moving_bearing_axis_unchanged', passed=unchanged == observed))
        # Mount plate follows wood depth; the neck endpoint remains inside it.
        plates = {p['group']: p for p in r['moving'] if p['name'].endswith('_DoorLeaf')}
        for neck in (p for p in r['moving'] if p['name'].endswith('_MovingNeck')):
            first, second = neck['bridge_endpoints_cm']
            plate = plates[neck['group']]
            near_bearing = math.hypot(first[0], first[1]) < 1.2
            far_inside = all(abs(second[i]-plate['center'][i]) < plate['size'][i]/2
                             for i in range(3))
            # Plate intersects the rear face of the 4 cm wood by .3 cm.
            wood_back, wood_front = offset-2., offset+2.
            plate_lo = plate['center'][1]-plate['size'][1]/2
            plate_hi = plate['center'][1]+plate['size'][1]/2
            embedded = min(wood_front, plate_hi) > max(wood_back, plate_lo)
            checks.append(dict(check='moving_metal_connections', group=neck['group'],
                               passed=near_bearing and far_inside and embedded))
        direction = -side
        axis = r['hinge_axis_opening_root_cm']
        fixed = [_box('JambLeft', [-width/2-2., 0., height/2], [4., depth, height]),
                 _box('JambRight', [width/2+2., 0., height/2], [4., depth, height]),
                 _box('Header', [0., 0., height+2.], [width+8., depth, 4.])]
        fixed += [p for p in r['fixed'] if p['kind'] == 'box']
        fixed += r['stops']
        moving = [_box('WoodLeaf', [direction*(width-1)/2, offset, height/2],
                       [width-1., LEAF_THICKNESS_CM, height])]
        moving += [p for p in r['moving'] if p['kind'] == 'box']
        for angle in angles:
            if not math.isfinite(float(angle)) or not 0 <= angle <= 90:
                raise ValueError('Sweep angles must be finite and between 0 and 90')
            collisions = []
            for mobile in moving:
                poly = _rotate(_moving_normalized(mobile, direction), math.radians(angle))
                for stationary in fixed:
                    if (_z_overlaps(mobile, stationary) and
                            original._positive_polygon_overlap(
                                poly, _fixed_normalized(stationary, axis, direction))):
                        collisions.append([mobile['name'], stationary['name']])
            sweep.append(dict(angle_deg=float(angle), actual_yaw_deg=-side*float(angle),
                              passed=not collisions, unexpected_overlaps=collisions))
    return dict(schema=SCHEMA, passed=all(c['passed'] for c in checks) and
                all(s['passed'] for s in sweep), checks=checks, sampled_sweep=sweep,
                moving_triangle_count=data['moving']['triangle_count'],
                stop_triangle_count=data['stops']['triangle_count'],
                scope='Pure geometry only; no Unreal state, meshes or materials read or written')
