"""Pure geometry delta for the saved V4 hotel's stair, rail and window details.

This module has no Unreal dependency and never writes files or changes its input.
All geometry uses world centimetres. The caller applies the returned delta and
updates the corresponding placed-actor manifests after verifying the saved map.
"""
from copy import deepcopy
import hashlib
import json
import math
import re


ACTOR_PREFIX = 'OTS_HotelV4_'
CUBE = '/Engine/BasicShapes/Cube.Cube'
EPSILON = 1.e-5
PIPE_HEIGHT = 102.
POST_BOTTOM = .3
PLATE_BOTTOM = -.4
PLATE_TOP = .8
PLATE_HALF = 3.5
POST_HALF = 2.5
POST_CROSS_OFFSETS_M = (1.36, 1.84)
REAR_WALL_RENDER_OFFSET_CM = [.045, 0., -.045]


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _world(s, d, z):
    return [9000. + 100. * d, 100. * s - 3500., float(z)]


def _point(family, longitudinal_m, cross_m, z_cm):
    if family['axis'] == 's':
        return _world(longitudinal_m, cross_m, z_cm)
    assert family['axis'] == 'd', family
    return _world(cross_m, longitudinal_m, z_cm)


def _box(key, role, centre_xy, z0, z1, half_cm, floor, material='dark', **extra):
    x, y = centre_xy[:2]
    row = dict(id=key, key=key, role=role,
               world_min=[x-half_cm, y-half_cm, float(z0)],
               world_max=[x+half_cm, y+half_cm, float(z1)],
               material=material, floor=floor, collision=True,
               actor=ACTOR_PREFIX+key, asset=CUBE)
    row.update(extra)
    return row


def _tube(key, start, end, diameter_cm, floor, stair_id, role='stair_handrail'):
    difference = [end[i]-start[i] for i in range(3)]
    length = math.sqrt(sum(v*v for v in difference))
    assert length > EPSILON, key
    radius = diameter_cm/2.
    return dict(id=key, key=key, actor=ACTOR_PREFIX+key, role=role,
                start_cm=list(start), end_cm=list(end),
                endpoints_cm=[list(start), list(end)],
                position_cm=[(start[i]+end[i])/2. for i in range(3)],
                direction=[v/length for v in difference], length_cm=length,
                diameter_cm=float(diameter_cm), radius_cm=radius,
                material='green', collision=True, floor=floor,
                stair_id=stair_id,
                world_min=[min(start[i], end[i])-radius for i in range(3)],
                world_max=[max(start[i], end[i])+radius for i in range(3)])


def _subtract(lo, hi, cut_lo, cut_hi):
    """Subtract one axis-aligned solid into disjoint, nonempty boxes."""
    if not all(min(hi[i], cut_hi[i]) > max(lo[i], cut_lo[i])+.001
               for i in range(3)):
        return [(list(lo), list(hi))]
    a = [max(lo[i], cut_lo[i]) for i in range(3)]
    b = [min(hi[i], cut_hi[i]) for i in range(3)]
    low, high, result = list(lo), list(hi), []
    for i in range(3):
        if a[i] > low[i]+.001:
            q = high[:]
            q[i] = a[i]
            result.append((low[:], q))
            low[i] = a[i]
        if b[i] < high[i]-.001:
            q = low[:]
            q[i] = b[i]
            result.append((q, high[:]))
            high[i] = b[i]
    return result


def _opening(row):
    x, y, z = row['position_cm']
    width = float(row.get('rough_width_cm', row['width']))
    height = float(row.get('rough_height_cm', row['height']))
    depth = max(14., float(row.get('depth', 20.))/2.+2.)
    if abs(row['inward'][0]) > .5:
        return [[x-depth, y-width/2., z], [x+depth, y+width/2., z+height]]
    return [[x-width/2., y-depth, z], [x+width/2., y+depth, z+height]]


def _same_point(a, b):
    return all(abs(a[i]-b[i]) < EPSILON for i in range(3))


def _overlap_volume(lo, hi, other_lo, other_hi):
    return math.prod(max(0., min(hi[i], other_hi[i])-max(lo[i], other_lo[i]))
                     for i in range(3))


def _assert_plate_supported(plate, support):
    lo, hi = plate['world_min'], plate['world_max']
    sl, sh = support['world_min'], support['world_max']
    assert all(lo[i] >= sl[i]-EPSILON and hi[i] <= sh[i]+EPSILON
               for i in (0, 1)), (plate['id'], support['id'], lo, hi, sl, sh)
    assert abs(lo[2]-(sh[2]+PLATE_BOTTOM)) < EPSILON, plate['id']
    assert abs(hi[2]-(sh[2]+PLATE_TOP)) < EPSILON, plate['id']
    return dict(plate=plate['id'], support=support['id'],
                support_area_cm2=49., support_top_z_cm=sh[2], passed=True)


def make_detail_delta(currentPlan):
    """Return a self-contained, nonmutating delta for the current saved V4 plan.

    ``windows`` is the full raw opening list; ``updated_windows`` is its 12-row
    stair subset. ``rear_wall_boxes`` is separate from ``added_boxes``. Every
    returned box has a stable ``id`` and intended ``actor`` label. Existing
    flight posts keep their labels; removed horizontal rail/well-guard actors
    are replaced by ``rail_tubes`` and grounded platform posts.
    """
    input_hash = _digest(currentPlan)
    source_boxes = currentPlan.get('placed_boxes') or currentPlan['boxes']
    by_id = {row['id']: row for row in source_boxes}
    assert len(by_id) == len(source_boxes), 'Duplicate source box ids'
    floors = list(currentPlan.get('floor_z_cm') or currentPlan['floor_z'])
    assert len(floors) == 4, floors
    rise = (floors[1]-floors[0])/24.
    assert all(abs(floors[f+1]-floors[f]-24.*rise) < EPSILON for f in range(3))
    assert abs(rise*12.-183.625) < EPSILON, rise
    families = currentPlan['stair_geometry']
    assert {q['id'] for q in families} == {'South', 'North', 'Central'}
    modified, added, tubes, supports, joins = [], [], [], [], []
    removed = [r['id'] for r in source_boxes
               if re.fullmatch(r'(South|North|Central)_F[0-2]_Handrail[01]_\d\d', r['id'])
               or re.fullmatch(r'(South|North|Central)_F[0-2]_WellGuard[01]', r['id'])]
    assert sum('_Handrail' in q for q in removed) == 198
    assert sum('_WellGuard' in q for q in removed) == 18

    for family in families:
        name, axis = family['id'], family['axis']
        rect = family['clear_global_sd_m']
        long0 = rect[0] if axis == 's' else rect[1]
        cross0 = rect[1] if axis == 's' else rect[0]
        run0, run1 = long0+1.4, long0+1.4+3.08
        cross = [cross0+v for v in POST_CROSS_OFFSETS_M]
        platform_top_tubes = {}
        for f in range(4):
            z = floors[f]
            support_id = '%s_F%d_%sLanding' % (name, f, 'Top' if f == 3 else 'Lower')
            support = by_id[support_id]
            ends = [_point(family, run0-.14, c, z+PIPE_HEIGHT) for c in cross]
            key = '%s_F%d_LandingTopPipe' % (name, f)
            top_tube = _tube(key, ends[0], ends[1], 6., f, name)
            tubes.append(top_tube)
            platform_top_tubes[(f, 'whole')] = top_tube
            tubes.append(_tube('%s_F%d_LandingMidPipe' % (name, f),
                               _point(family, run0-.14, cross[0], z+55.),
                               _point(family, run0-.14, cross[1], z+55.),
                               4., f, name, role='stair_guard_midrail'))
            for end_index, c in enumerate(cross):
                foot = _point(family, run0-.14, c, z)
                post = _box('%s_F%d_LandingPost%d' % (name, f, end_index), 'guard',
                            foot, z+POST_BOTTOM, z+PIPE_HEIGHT, POST_HALF, f,
                            stair_id=name, support_id=support_id,
                            support_top_z_cm=z, detail_kind='platform_post')
                plate = _box(post['id']+'_Baseplate', 'stair_baseplate', foot,
                             z+PLATE_BOTTOM, z+PLATE_TOP, PLATE_HALF, f,
                             stair_id=name, support_id=support_id,
                             support_top_z_cm=z, detail_kind='platform_baseplate')
                added.extend((post, plate))
                supports.append(_assert_plate_supported(plate, support))
        for f in range(3):
            z, upper = floors[f], floors[f+1]
            mid = z+12.*rise
            half_support_id = '%s_F%d_HalfLanding' % (name, f)
            half_support = by_id[half_support_id]
            half_ends = [_point(family, run1+.14, c, mid+PIPE_HEIGHT) for c in cross]
            half_pipe = _tube('%s_F%d_HalfLandingTopPipe' % (name, f),
                              half_ends[0], half_ends[1], 6., f, name)
            tubes.append(half_pipe)
            tubes.append(_tube('%s_F%d_HalfLandingMidPipe' % (name, f),
                               _point(family, run1+.14, cross[0], mid+55.),
                               _point(family, run1+.14, cross[1], mid+55.),
                               4., f, name, role='stair_guard_midrail'))
            for end_index, c in enumerate(cross):
                foot = _point(family, run1+.14, c, mid)
                key = '%s_F%d_HalfLandingPost%d' % (name, f, end_index)
                post = _box(key, 'guard', foot, mid+POST_BOTTOM, mid+PIPE_HEIGHT,
                            POST_HALF, f, stair_id=name, support_id=half_support_id,
                            support_top_z_cm=mid, detail_kind='platform_post')
                plate = _box(key+'_Baseplate', 'stair_baseplate', foot,
                             mid+PLATE_BOTTOM, mid+PLATE_TOP, PLATE_HALF, f,
                             stair_id=name, support_id=half_support_id,
                             support_top_z_cm=mid, detail_kind='platform_baseplate')
                added.extend((post, plate))
                supports.append(_assert_plate_supported(plate, half_support))
            for flight, c in enumerate(cross):
                start_z = z if flight == 0 else upper
                first = _point(family, run0-.14, c, start_z+PIPE_HEIGHT)
                last = half_ends[flight]
                pipe = _tube('%s_F%d_Flight%dSlopedPipe' % (name, f, flight),
                             first, last, 6., f, name)
                pipe.update(flight=flight, slope_degrees=math.degrees(math.atan2(12.*rise, 336.)),
                            tread_centre_clearance_cm=PIPE_HEIGHT)
                tubes.append(pipe)
                whole = platform_top_tubes[(f if flight == 0 else f+1, 'whole')]
                assert _same_point(first, whole['endpoints_cm'][flight])
                assert _same_point(last, half_pipe['endpoints_cm'][flight])
                joins.append(dict(pipe=pipe['id'], start_connects_to=whole['id'],
                                  end_connects_to=half_pipe['id'], passed=True))
                for i in range(11):
                    key = '%s_F%d_Guard%d_%02d' % (name, f, flight, i)
                    source = by_id[key]
                    tread_key = '%s_F%d_%sTread%02d' % (
                        name, f, 'First' if flight == 0 else 'Second',
                        i if flight == 0 else 10-i)
                    tread = by_id[tread_key]
                    top = z+(i+1)*rise if flight == 0 else z+(23-i)*rise
                    assert abs(tread['world_max'][2]-top) < EPSILON, (key, tread_key)
                    foot = _point(family, run0+(i+.5)*.28, c, top)
                    post = deepcopy(source)
                    post.update(world_min=[foot[0]-POST_HALF, foot[1]-POST_HALF, top+POST_BOTTOM],
                                world_max=[foot[0]+POST_HALF, foot[1]+POST_HALF, top+PIPE_HEIGHT],
                                stair_id=name, flight=flight, support_id=tread_key,
                                support_top_z_cm=top, detail_kind='grounded_flight_post')
                    assert post['actor'] == source['actor']
                    modified.append(post)
                    plate = _box(key+'_Baseplate', 'stair_baseplate', foot,
                                 top+PLATE_BOTTOM, top+PLATE_TOP, PLATE_HALF, f,
                                 stair_id=name, flight=flight, support_id=tread_key,
                                 support_top_z_cm=top, detail_kind='flight_baseplate')
                    added.append(plate)
                    supports.append(_assert_plate_supported(plate, tread))
                    t = ((run0+(i+.5)*.28)-(run0-.14))/3.36
                    tube_centre_z = first[2]+t*(last[2]-first[2])
                    assert abs(tube_centre_z-(top+PIPE_HEIGHT)) < EPSILON, key

    windows = deepcopy(currentPlan['windows'])
    updated_windows, window_checks = [], []
    for row in windows:
        if row.get('kind') != 'stair':
            continue
        f = int(row['floor'])
        row['position_cm'][2] = floors[f]+12.*rise+80.
        if 'Central' in row['id']:
            row['position_cm'][1] += 25.
        row['height'] = 75.
        if 'rough_height_cm' in row:
            row['rough_height_cm'] = 75.
        row['opening_bounds'] = _opening(row)
        row['detail_kind'] = 'high_stair_window'
        row['sill_above_half_landing_cm'] = 80.
        row['outer_frame_top_z_cm'] = row['position_cm'][2]+75.+4.
        ceiling = floors[f+1]-20. if f < 3 else 1480.
        assert row['outer_frame_top_z_cm'] < ceiling-EPSILON, row['id']
        if 'Central' in row['id']:
            left = row['position_cm'][1]-row['width']/2.-4.
            right = row['position_cm'][1]+row['width']/2.+4.
            assert left >= 1020.-EPSILON and right <= 1160.+EPSILON, row['id']
        updated_windows.append(deepcopy(row))
        window_checks.append(dict(window=row['id'], frame_top_z_cm=row['outer_frame_top_z_cm'],
                                  ceiling_bottom_z_cm=ceiling,
                                  ceiling_margin_cm=ceiling-row['outer_frame_top_z_cm'], passed=True))
    assert len(updated_windows) == 12

    old_rear = [row for row in source_boxes if re.fullmatch(r'F[0-3]_RearWall_\d+', row['id'])]
    assert old_rear, 'No V4 rear wall fragments found'
    removed.extend(row['id'] for row in old_rear)
    # The enclosure builder generated a second wall exactly inside the shared
    # rear envelope. Its old low window cut would obstruct the new high window.
    # The full envelope below supplies the same 20cm physical back boundary.
    redundant_back = [row for row in source_boxes
                      if re.fullmatch(r'F[0-3]_CentralSafetyStair_Back_\d+', row['id'])]
    assert len(redundant_back) == 18, len(redundant_back)
    assert {row['floor'] for row in redundant_back} == set(range(4))
    for row in redundant_back:
        lo, hi, f = row['world_min'], row['world_max'], row['floor']
        assert abs(lo[0]-10020.) < EPSILON and abs(hi[0]-10040.) < EPSILON, row['id']
        assert lo[1] >= -3500.-EPSILON and hi[1] <= 3500.+EPSILON, row['id']
        assert lo[2] >= floors[f]-EPSILON, row['id']
        assert hi[2] <= (floors[f+1] if f < 3 else 1480.)+EPSILON, row['id']
    removed.extend(row['id'] for row in redundant_back)
    removed_set = set(removed)
    for window in updated_windows:
        hole_lo, hole_hi = window['opening_bounds']
        if 'Central' in window['id']:
            blockers = [row for row in redundant_back
                        if _overlap_volume(row['world_min'], row['world_max'],
                                           hole_lo, hole_hi) > .001]
            assert blockers and {row['floor'] for row in blockers} == {window['floor']}, window['id']
        for row in source_boxes:
            if row['id'] in removed_set or row['role'] not in ('wall', 'dado'):
                continue
            assert _overlap_volume(row['world_min'], row['world_max'], hole_lo, hole_hi) < .001, (
                'Retained wall would obstruct high stair window', window['id'], row['id'])
    cuts = [_opening(row) for row in currentPlan['doors']] + [row['opening_bounds'] for row in windows]
    rear_wall_boxes = []
    for f, z in enumerate(floors):
        top = floors[f+1] if f < 3 else 1480.
        parts = [([10020., -3500., z], [10040., 3500., top])]
        for cut_lo, cut_hi in cuts:
            parts = [piece for lo, hi in parts for piece in _subtract(lo, hi, cut_lo, cut_hi)]
        for i, (lo, hi) in enumerate(parts):
            key = 'F%d_RearWall_%02d' % (f, i)
            assert all(hi[a] > lo[a]+.001 for a in range(3)), key
            rear_wall_boxes.append(dict(id=key, key=key, role='wall', world_min=lo, world_max=hi,
                                        material='plaster', floor=f, collision=True,
                                        actor=ACTOR_PREFIX+key, asset=CUBE,
                                        detail_kind='recut_rear_envelope',
                                        render_offset_hint_cm=REAR_WALL_RENDER_OFFSET_CM[:]))
            for cut_lo, cut_hi in cuts:
                assert not all(min(hi[a], cut_hi[a]) > max(lo[a], cut_lo[a])+.001
                               for a in range(3)), (key, cut_lo, cut_hi)
    old_hole_fill_checks = []
    for old_window in currentPlan['windows']:
        if old_window.get('kind') != 'stair':
            continue
        old_lo, old_hi = old_window['opening_bounds']
        f = old_window['floor']
        envelope_lo = [10020., -3500., floors[f]]
        envelope_hi = [10040., 3500., floors[f+1] if f < 3 else 1480.]
        expected = _overlap_volume(old_lo, old_hi, envelope_lo, envelope_hi)
        covered = sum(_overlap_volume(old_lo, old_hi, row['world_min'], row['world_max'])
                      for row in rear_wall_boxes if row['floor'] == f)
        assert expected > 0. and abs(expected-covered) < .001, (
            'Old stair opening must be fully closed', old_window['id'], expected, covered)
        old_hole_fill_checks.append(dict(window=old_window['id'],
                                         expected_wall_volume_cm3=expected,
                                         replaced_wall_volume_cm3=covered, passed=True))

    assert len(modified) == 198
    assert len([q for q in added if q['role'] == 'stair_baseplate']) == 240
    assert len([q for q in added if q.get('detail_kind') == 'platform_post']) == 42
    assert len(tubes) == 60
    assert len([q for q in tubes if 'SlopedPipe' in q['id']]) == 18
    assert len(supports) == 240
    assert len(currentPlan['rooms']) == 27
    assert len(currentPlan['stair_routes']) == 9
    assert input_hash == _digest(currentPlan), 'Input plan was modified'
    return dict(schema_version=1, recipe='HotelDetailGroundedPostsConnectedPipesHighWindowsV1',
                modified_boxes=modified, added_boxes=added, removed_box_ids=removed,
                rail_tubes=tubes, windows=windows, updated_windows=updated_windows,
                rear_wall_boxes=rear_wall_boxes,
                constraints=dict(passed=True, source_plan_sha256=input_hash,
                                 grounded_plate_count=len(supports), plate_support_checks=supports,
                                 connected_flight_count=len(joins), rail_endpoint_checks=joins,
                                 window_checks=window_checks,
                                 removed_redundant_central_backwalls=len(redundant_back),
                                 removed_redundant_central_backwall_ids=[row['id'] for row in redundant_back],
                                 old_window_holes_filled_checks=old_hole_fill_checks,
                                 preserved_room_count=27, preserved_stair_route_count=9,
                                 preserved_room_and_route_sha256=_digest({k:currentPlan[k] for k in
                                     ('rooms', 'routes', 'stair_routes', 'staircases', 'slab_voids')}),
                                 clear_tread_width_cm=140., rail_level_clear_width_cm=133.,
                                 baseplate_level_clear_width_cm=132.5,
                                 assumed_visible_support_offset_tolerance_cm=.18,
                                 required_saved_map_checks=['physical stair routes and headroom',
                                     'new post and plate support', 'same floor and half landing pipe joints',
                                     'rear wall opening assembly and envelope continuity',
                                     'full exposed near-coplanar render triangle scan',
                                     'inside and outside captures from actual saved map']))
