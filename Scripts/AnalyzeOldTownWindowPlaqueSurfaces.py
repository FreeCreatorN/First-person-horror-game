"""Read-only diagnosis of the published V4 window and room plaque geometry.

This reads saved manifests; it does not import Unreal or modify maps/assets.
Visible Engine Cube faces are compared with actual planned wall boxes.
"""
import itertools
import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / 'Saved/CodexOutputs/HotelRedesign_20261008_V4/BuildReport.json'
OUT = ROOT / 'Saved/CodexOutputs/SurfaceSeparation_20261009'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def component_bounds(opening, component):
    components = {c['name']: c for c in opening['components']}
    center = component['relative_location'][:]
    parent = component.get('parent')
    while parent:
        c = components[parent]
        assert all(abs(v) < 1e-6 for v in c['relative_rotation']), c['name']
        center = [a+b for a,b in zip(center, c['relative_location'])]
        parent = c.get('parent')
    scale = component['relative_scale']
    yaw = math.radians(opening['yaw'])
    ct, st = math.cos(yaw), math.sin(yaw)
    world = []
    for signs in itertools.product((-1, 1), repeat=3):
        x, y, z = [center[i]+signs[i]*scale[i]*50 for i in range(3)]
        world.append([opening['position_cm'][0]+ct*x-st*y,
                      opening['position_cm'][1]+st*x+ct*y,
                      opening['position_cm'][2]+z])
    return [[min(p[i] for p in world) for i in range(3)],
            [max(p[i] for p in world) for i in range(3)]]


def coplanar_faces(a, b):
    result = []
    for axis in range(3):
        others = [i for i in range(3) if i != axis]
        for side in range(2):
            if abs(a[side][axis]-b[side][axis]) > .005:
                continue
            lengths = [min(a[1][i], b[1][i])-max(a[0][i], b[0][i]) for i in others]
            if min(lengths) > .005:
                result.append(dict(axis='XYZ'[axis], side='min' if side == 0 else 'max',
                                   plane_cm=a[side][axis], overlap_area_cm2=lengths[0]*lengths[1]))
    return result


def separated_window_components(opening):
    """Candidate render geometry; PaneCollision is deliberately unchanged.

    Existing visible Frame components block physics, so changing their transforms
    directly also changes their collision bounds. A caller requiring exact collider
    preservation must keep their original hidden collision equivalent and render
    these corrected dimensions independently, or produce equivalent WPO geometry.
    """
    rows = deepcopy(opening['components'])
    w, h, depth = float(opening['width']), float(opening['height']), float(opening['depth'])
    for c in rows:
        name = c['name']
        if name.startswith('Frame'):
            c['relative_scale'][1] = (depth+.5)/100
        if name in ('FrameLeft', 'FrameRight'):
            c['relative_location'][0] += .1 if name == 'FrameLeft' else -.1
            c['relative_scale'][2] = (h-.2)/100
        elif name == 'FrameTop':
            c['relative_location'][2] -= .1
        elif name == 'FrameBottom':
            c['relative_location'][2] += .1
        elif name.endswith('Sash'):
            direction = 1 if name.startswith('Left') else -1
            c['relative_location'][0] = direction*(w/4-2)
            c['relative_scale'][0] = (w/2-4.4)/100
            c['relative_scale'][2] = (h-8.4)/100
        elif name.endswith('MeetingRail'):
            c['relative_scale'][2] = (h-8.2)/100
    return rows


def inspect(plan):
    """All positive-area, same-facing Cube frame/wall and internal window pairs."""
    walls = [r for r in plan['placed_boxes'] if r['role'] == 'wall']
    frame_wall, internal = [], []
    for opening in plan['placed_windows']:
        visible = [c for c in opening['components'] if c.get('asset') == '/Engine/BasicShapes/Cube.Cube'
                   and not c.get('hidden')]
        boxes = {c['name']: component_bounds(opening, c) for c in visible}
        for name, bounds in boxes.items():
            if name.startswith('Frame'):
                for wall in walls:
                    overlaps = coplanar_faces(bounds, [wall['world_min'], wall['world_max']])
                    if overlaps:
                        frame_wall.append(dict(window=opening['id'], actor=opening['actor'], component=name,
                                               wall=wall['id'], faces=overlaps))
        for a, b in itertools.combinations(boxes, 2):
            overlaps = coplanar_faces(boxes[a], boxes[b])
            if overlaps:
                internal.append(dict(window=opening['id'], actor=opening['actor'], components=[a, b],
                                     faces=overlaps))
    return frame_wall, internal


def main():
    build = read(CURRENT)
    plan = build['hotel_v4']
    frame_wall, internal = inspect(plan)
    separated = deepcopy(plan)
    for opening in separated['placed_windows']:
        opening['components'] = separated_window_components(opening)
    proposed_wall, proposed_internal = inspect(separated)
    plaques = [r for r in plan['placed_boxes'] if r['id'].endswith('_NumberPlaque')]
    numbers = [r for r in plan['placed_props'] if r['asset_key'].startswith('RoomNumber_')]
    asset_manifest = read(ROOT/'SourceArt/OldTownHotelArchitecture_20261005/ImportManifest.json')
    number_asset = next(r for r in asset_manifest['assets'] if r['key'] == 'RoomNumber_201')
    axis_verification = read(ROOT/'SourceArt/OldTownHotelOpenings_20261004/UnrealAxisVerification.json')
    report = dict(scope='Read-only published V4 manifest diagnosis; live saved-map verification belongs to parent audit.',
                  source_map_sha256=build['map_sha256'], windows=len(plan['placed_windows']),
                  windows_with_wall_frame_coplanarity=len({r['window'] for r in frame_wall}),
                  frame_wall_component_pairs=len(frame_wall), frame_wall_face_pairs=sum(len(r['faces']) for r in frame_wall),
                  internal_component_pairs=len(internal), internal_face_pairs=sum(len(r['faces']) for r in internal),
                  frame_wall=frame_wall, internal_window=internal,
                  root_cause={'structural_cut': 'Window plan has no rough dimensions; hole uses clear pane width and height.',
                              'frame': 'Frame lies 4 cm outside the cut on every edge, with front/back faces exactly on wall faces.',
                              'sash': 'Horizontal and vertical rails overlap at their corners and share front/back face planes.',
                              'glass': 'Glass Sash spans the full pane, so its top/bottom faces coincide with horizontal rail top/bottom faces.'},
                  recommendation={'fixed_frames': 'Four Frame depths become depth+0.5 cm, protruding 0.25 cm on BOTH wall faces. Left X+=0.1; Right X-=0.1; both height=h-0.2. Top Z-=0.1; Bottom Z+=0.1.',
                                  'rails': 'Trim MeetingRail to h-8.2 so it ends 0.1 cm short of each horizontal rail.',
                                  'glass': 'Inset glass vertical ends to z=4.2..h-4.2 and meeting-rail side edge by 0.2 cm; retain hidden PaneCollision original dimensions.',
                                  'asset_safety': 'Apply per-instance component changes or new generated BP variants; never alter shared Yastar meshes/materials or protected map files.',
                                  'collision_safety': 'Original Frame components have blocking collision; actual scale/location changes would alter bounds. Preserve old hidden Frame collider geometry and use new NoCollision visible frames, or equivalent render-only WPO. PaneCollision stays unchanged.'},
                  simulated_after={'frame_wall_component_pairs':len(proposed_wall), 'internal_component_pairs':len(proposed_internal),
                                   'passed': not proposed_wall and not proposed_internal,
                                   'note':'Candidate manifest-only geometry validation; no map or asset has been changed by this script.'},
                  proposed_window_component_overrides=[dict(actor=old['actor'], window=old['id'],
                       components=[dict(name=b['name'], changes={k:dict(before=a[k],after=b[k])
                                   for k in ('relative_location','relative_scale') if a[k]!=b[k]},
                                   original_collision=a['collision']) for a,b in zip(old['components'],new['components'])
                                   if a!=b]) for old,new in zip(plan['placed_windows'],separated['placed_windows'])],
                  doorway_object={'purpose': 'room-number plaque and extruded room digits',
                                  'plaque_count': len(plaques), 'number_count': len(numbers),
                                  'plaque_dimensions_cm': [44,24,3], 'plaque_height_above_floor_cm': [159,183],
                                  'digits_height_cm': 12, 'digits_thickness_cm': .25,
                                  'digits_world_axis_thickness': 'X', 'yaw_degrees': 90,
                                  'front_orientation': 'Source text front is local -Y; verified UE import reflects Y, so yaw 90 faces corridor -X.',
                                  'ue_axis_verification': axis_verification,
                                  'example_plaque': plaques[0], 'example_digits': numbers[0], 'example_asset': number_asset})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'WindowPlaqueDiagnosis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('windows','windows_with_wall_frame_coplanarity','frame_wall_component_pairs',
                                           'frame_wall_face_pairs','internal_component_pairs','internal_face_pairs')}, indent=2))


if __name__ == '__main__':
    main()
