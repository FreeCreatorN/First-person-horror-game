"""Read-only evidence for the old-town lamp material masks; no Unreal dependency.

The tube test is deliberately specific to the existing FluorescentHousing mesh.
It examines actual native render triangles, including triangles that cross the
central slab despite having all their vertices outside it. CLI output is JSON;
the script never writes files or opens the editor.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


def _read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw.decode('utf-8-sig')), hashlib.sha256(raw).hexdigest()


def _triangles(section):
    vertices = section['vertices_cm']
    indices = section['triangle_indices']
    if len(indices) % 3 or any(len(v) != 3 or not all(math.isfinite(x) for x in v)
                              for v in vertices):
        raise ValueError('Malformed native vertices or triangle indices')
    if any(type(i) is not int or i < 0 or i >= len(vertices) for i in indices):
        raise ValueError('Invalid native triangle index')
    return [tuple(tuple(vertices[indices[i + j]]) for j in range(3))
            for i in range(0, len(indices), 3)]


def _cross(a, b, c):
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    return (u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0])


def _nearest_abs_y(triangle):
    low = min(v[1] for v in triangle)
    high = max(v[1] for v in triangle)
    return 0.0 if low <= 0.0 <= high else min(abs(low), abs(high))


def verify_tube_mask(geometry_file, full_y=42.5, zero_y=43.1):
    """Prove that nonzero emission touches only the two cylindrical tube sides.

    The native tube centres are X=-4/+4, Z=4 cm, radius 1.45 cm. Boolean
    intersection vertices can lie on edges of the 48-sided cylinder, up to
    0.003015 cm inside its circumcircle; 0.0045 cm is a conservative tolerance.
    A cylinder-side face must also have negligible geometric normal along Y.
    """
    geometry, source_sha = _read(geometry_file)
    sections = [s for s in geometry['sections'] if s['material_slot_index'] == 2]
    if len(sections) != 1:
        raise ValueError('Expected exactly one native Ceramic section in slot 2')
    section = sections[0]
    triangles = _triangles(section)
    tube_faces, other_faces, degenerate_faces = [], [], []
    tube_counts = Counter()
    radius_errors, normal_y = [], []
    for number, triangle in enumerate(triangles):
        cross = _cross(*triangle)
        length = math.hypot(*cross)
        if length <= 1e-12:
            degenerate_faces.append(number)
            other_faces.append(triangle)
            continue
        side_normal_y = abs(cross[1]) / length
        candidates = [(centre, max(abs(math.hypot(v[0] - centre, v[2] - 4.0)
                                              - 1.45) for v in triangle))
                      for centre in (-4.0, 4.0)]
        centre, error = min(candidates, key=lambda item: item[1])
        if error <= 0.0045 and side_normal_y <= 1e-5:
            tube_faces.append(triangle)
            tube_counts[str(int(centre))] += 1
            radius_errors.append(error)
            normal_y.append(side_normal_y)
        else:
            other_faces.append(triangle)
    nearest_other = min((_nearest_abs_y(t) for t in other_faces), default=None)
    central = [t for t in triangles if _nearest_abs_y(t) < zero_y]
    unsafe = [t for t in other_faces if _nearest_abs_y(t) < zero_y]
    checks = {
        'expected_mesh': 'FluorescentHousing_52dcb7cbc2' in geometry['asset'],
        'ceramic_slot': 'Ceramic' in section['slot_name'],
        'mask_parameters': all(math.isfinite(v) for v in (full_y, zero_y))
                           and 0.0 <= full_y < zero_y,
        'native_triangle_count': len(triangles) == section['triangle_count'] == 1358,
        'two_complete_tube_sides': dict(tube_counts) == {'-4': 261, '4': 261},
        'non_tube_count': len(other_faces) == 836,
        'no_degenerate_faces': not degenerate_faces,
        'all_non_tube_faces_excluded': not unsafe and nearest_other is not None
                                      and zero_y < nearest_other,
        'expected_socket_boundary': nearest_other is not None
                                    and abs(nearest_other - 44.5) <= 1e-5,
    }
    return {
        'passed': all(checks.values()), 'checks': checks,
        'geometry_file': str(Path(geometry_file).resolve()), 'source_sha256': source_sha,
        'asset': geometry['asset'], 'material_slot_index': 2,
        'full_y_cm': full_y, 'zero_y_cm': zero_y,
        'triangle_count': len(triangles), 'tube_side_triangles': len(tube_faces),
        'non_tube_triangles': len(other_faces), 'tube_face_counts_by_centre_x_cm': dict(tube_counts),
        'central_slab_triangle_count': len(central), 'unsafe_non_tube_triangles': len(unsafe),
        'nearest_socket_abs_y_cm': nearest_other,
        'safe_clearance_cm': nearest_other - zero_y if nearest_other is not None else None,
        'maximum_tube_radius_deviation_cm': max(radius_errors, default=None),
        'maximum_tube_abs_normal_y': max(normal_y, default=None),
        'degenerate_triangle_indices': degenerate_faces,
        'boundary_rule': 'Emission must be zero before abs(LocalY) reaches 44.5 cm.',
    }


def verify_street_lens(geometry_file):
    """Check that slot 2 is only the closed recessed lens, excluding pole/body."""
    geometry, source_sha = _read(geometry_file)
    sections = [s for s in geometry['sections'] if s['material_slot_index'] == 2]
    if len(sections) != 1:
        raise ValueError('Expected one native Glass section in slot 2')
    lens = sections[0]
    triangles = _triangles(lens)
    points = [v for t in triangles for v in t]
    bounds = [[min(v[i] for v in points) for i in range(3)],
              [max(v[i] for v in points) for i in range(3)]]
    # The source builder's sole Glass part is a 43x25x2.8 cm recessed lens
    # at (0,-108,308.7), with a small rotation. These bounds include its bevel.
    permitted = ((-21.501, 21.501), (-120.515, -95.485), (306.689, 310.712))
    edges = Counter(tuple(sorted((t[i], t[(i + 1) % 3])))
                    for t in triangles for i in range(3))
    bad_edges = sum(count != 2 for count in edges.values())
    checks = {
        'expected_mesh': 'SM_R_Street_Mod_StreetLamp_' in geometry['asset'],
        'four_material_slots': len(geometry['static_material_slots']) == 4,
        'glass_only_in_slot_2': 'Glass' in lens['slot_name'] and
                              all('Glass' not in s['slot_name'] for s in geometry['sections']
                                  if s['material_slot_index'] != 2),
        'lens_triangle_count': len(triangles) == lens['triangle_count'] == 92,
        'closed_lens': bad_edges == 0,
        'only_recessed_lens_envelope': all(permitted[i][0] <= v[i] <= permitted[i][1]
                                           for v in points for i in range(3)),
    }
    return {'passed': all(checks.values()), 'checks': checks,
            'geometry_file': str(Path(geometry_file).resolve()), 'source_sha256': source_sha,
            'asset': geometry['asset'], 'material_slot_index': 2,
            'triangle_count': len(triangles), 'bounds_cm': bounds,
            'boundary_or_nonmanifold_edges': bad_edges}


def verify_lamp_inventory(snapshot_file, source_manifest_files):
    """Cross-check every saved mesh assignment against the source fixture catalog.

    Unknown lamp/lighting names fail instead of silently being omitted. This is
    a catalog/name check; it does not semantically classify unnamed arbitrary
    meshes. Geometry preservation separately establishes no new fixture meshes.
    """
    snapshot, snapshot_sha = _read(snapshot_file)
    variants = [v for p in source_manifest_files for v in _read(p)[0]['variants']]
    known_names = {v['mesh_name'] for v in variants
                   if '/Lighting/' in v.get('source_asset', '')
                   or v.get('kind') == 'FluorescentHousing'}
    pattern = re.compile(r'/Lighting/|StreetLamp|Fluorescent|Lamp|Lantern|Sconce|'
                         r'Chandelier|Pendant|Bulb|(?:^|[_/])Light(?:[_/.]|$)', re.I)
    fixtures, unknown, lights = [], [], []
    for actor, state in snapshot['actors'].items():
        for component in state.get('components', []):
            mesh = component.get('mesh')
            if mesh:
                name = mesh.rsplit('/', 1)[-1].split('.')[0]
                if name in known_names:
                    fixtures.append({'id': actor + '::' + component['name'], 'mesh': mesh,
                                     'optical_slot': 2})
                elif pattern.search(mesh) or pattern.search(actor):
                    unknown.append({'id': actor + '::' + component['name'], 'mesh': mesh})
            if re.search(r'\.(?:Point|Spot|Rect|Directional|Sky)LightComponent$',
                         component.get('class', '')):
                lights.append({'id': actor + '::' + component['name'],
                               'class': component['class']})
    street = [f for f in fixtures if 'StreetLamp' in f['mesh']]
    tubes = [f for f in fixtures if 'FluorescentHousing' in f['mesh']]
    checks = {'nine_street_lamps': len(street) == 9, 'twenty_four_tube_fixtures': len(tubes) == 24,
              'eight_fixture_meshes': len({f['mesh'] for f in fixtures}) == 8,
              'no_unclassified_light_named_mesh': not unknown, 'nineteen_light_components': len(lights) == 19}
    return {'passed': all(checks.values()), 'checks': checks,
            'snapshot_file': str(Path(snapshot_file).resolve()), 'source_sha256': snapshot_sha,
            'map_sha256': snapshot.get('map_sha256'), 'fixtures': fixtures,
            'unclassified_light_named_meshes': unknown, 'light_components': lights,
            'catalog_fixture_mesh_names': sorted(known_names),
            'scope': 'All saved mesh assignments plus the source lighting catalog; arbitrary unnamed meshes are not semantically classified.'}


def main():
    root = Path(__file__).resolve().parents[1]
    old = root / 'Saved/CodexOutputs/OldTownRealism_20261012'
    stage = root / 'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry-file', type=Path)
    parser.add_argument('--full-y', type=float, default=42.5)
    parser.add_argument('--zero-y', type=float, default=43.1)
    parser.add_argument('--street-geometry', type=Path, action='append')
    parser.add_argument('--snapshot', type=Path,
                        default=(stage if (stage / 'AppearanceSnapshot.json').exists() else old) / 'AppearanceSnapshot.json')
    parser.add_argument('--appearance-audit', type=Path, default=old / 'AppearanceAudit.json')
    args = parser.parse_args()
    audit, _ = _read(args.appearance_audit)
    meshes = list(audit['meshes'].values())
    tube_file = args.geometry_file or Path(next(m['geometry_file'] for m in meshes
                                              if 'FluorescentHousing' in m['asset']))
    street_files = args.street_geometry or [Path(m['geometry_file']) for m in meshes
                                           if 'SM_R_Street_Mod_StreetLamp_' in m['asset']]
    manifests = [root / 'SourceArt/OldTownRealism_20261012' / name / 'ModelDataManifest.json'
                 for name in ('Street', 'Architecture', 'Furniture')]
    result = {'tube_mask': verify_tube_mask(tube_file, args.full_y, args.zero_y),
              'street_lenses': [verify_street_lens(p) for p in street_files],
              'inventory': verify_lamp_inventory(args.snapshot, manifests)}
    result['passed'] = (result['tube_mask']['passed'] and all(r['passed'] for r in result['street_lenses'])
                        and len(result['street_lenses']) == 7 and result['inventory']['passed'])
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
