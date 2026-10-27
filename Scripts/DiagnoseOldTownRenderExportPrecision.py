"""Compare skipped scan faces with the immutable fresh Native render export."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cross_length(points):
    a, b, c = points
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    return math.sqrt(sum(x*x for x in cross))


def main():
    attribution_path = WORK / 'ScanDegenerateFaces.json'
    attribution = json.loads(attribution_path.read_text(encoding='utf-8'))
    snapshot_path = WORK / 'AfterSnapshot.json'
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    build_path = WORK / 'BuildReport.json'
    build = json.loads(build_path.read_text(encoding='utf-8'))
    offsets = {r['id']: r['offset_cm'] for r in build['surface_repair']['material_overrides']}
    native_files = {}
    cache = {}
    rows = []
    for skipped in attribution['rows']:
        asset = skipped['mesh']
        mesh_name = asset.rsplit('.', 1)[-1]
        if asset not in cache:
            candidates = list((WORK / 'AppearanceNative/NativeMeshes').glob(mesh_name + '_*.json'))
            assert len(candidates) == 1, candidates
            path = candidates[0]
            native = json.loads(path.read_text(encoding='utf-8'))
            assert native['asset'] == asset
            faces = []
            for section in native['sections']:
                indices = section['triangle_indices']
                assert len(indices) % 3 == 0
                for i in range(0, len(indices), 3):
                    ids = indices[i:i+3]
                    faces.append(dict(section=section['section_index'], indices=ids,
                        points=[section['vertices_cm'][j] for j in ids]))
            cache[asset] = faces
            native_files[str(path.resolve())] = sha(path)
        face = cache[asset][skipped['face_index']]
        points = face['points']
        rounded = [[round(v, 4) for v in p] for p in points]
        native_cross = cross_length(points)
        rounded_cross = cross_length(rounded)
        actor = snapshot['actors'][skipped['actor']]
        components = [c for c in actor['components'] if c['name'] == skipped['component']]
        assert len(components) == 1
        pose = components[0]
        assert pose['rotation'] == [0.0, 0.0, 0.0], pose
        offset = offsets[skipped['id']]
        full_world = [[pose['location'][i] + p[i]*pose['scale'][i] + offset[i]
            for i in range(3)] for p in points]
        historical_world = [[round(pose['location'][i] + p[i]*pose['scale'][i], 4) + offset[i]
            for i in range(3)] for p in rounded]
        world_cross = cross_length(full_world)
        historical_world_cross = cross_length(historical_world)
        reproduced_error = max(abs(a[i]-b[i]) for a, b in
            zip(historical_world, skipped['points_world_cm']) for i in range(3))
        rows.append(dict(actor=skipped['actor'], component=skipped['component'], asset=asset,
            face_index=skipped['face_index'], section_index=face['section'], vertex_indices=face['indices'],
            actual_native_local_points_cm=points, actual_native_cross_magnitude_cm2=native_cross,
            historical_round4_local_points_cm=rounded, historical_round4_cross_magnitude_cm2=rounded_cross,
            persisted_component_pose=pose, expected_material_wpo_cm=offset,
            simulated_unrounded_world_points_cm=full_world,
            simulated_unrounded_world_cross_magnitude_cm2=world_cross,
            reproduced_two_stage_round4_world_points_cm=historical_world,
            reproduced_two_stage_round4_world_cross_magnitude_cm2=historical_world_cross,
            reproduced_two_stage_world_max_error_cm=reproduced_error,
            historical_export_world_points_cm=skipped['points_world_cm'],
            historical_export_world_cross_magnitude_cm2=skipped['mathematical_cross_magnitude_cm2'],
            precision_collapse_confirmed=native_cross > 1e-10 and world_cross > 1e-10 and
                historical_world_cross == 0 and reproduced_error < 1e-8 and
                skipped['mathematical_cross_magnitude_cm2'] == 0 and len({tuple(p) for p in points}) == 3))
    report = dict(schema='OldTownRealismRenderExportPrecisionDiagnosisV1',
        passed=len(rows) == 12 and all(row['precision_collapse_confirmed'] for row in rows),
        created_utc=datetime.now(timezone.utc).isoformat(),
        historical_geometry_sha256=attribution['geometry_sha256'], historical_map_sha256=attribution['map_sha256'],
        attribution_file=str(attribution_path.resolve()), attribution_sha256=sha(attribution_path),
        persisted_pose_input_file=str(snapshot_path.resolve()), persisted_pose_input_sha256=sha(snapshot_path),
        material_wpo_input_file=str(build_path.resolve()), material_wpo_input_sha256=sha(build_path),
        native_mesh_file_sha256=native_files,
        unchanged_scanner_file=attribution['scanner_file'], unchanged_scanner_sha256=attribution['scanner_sha256'],
        repaired_exporter_file=str((ROOT / 'Scripts/InspectOldTownSurfaceInput.py').resolve()),
        repaired_exporter_sha256=sha(ROOT / 'Scripts/InspectOldTownSurfaceInput.py'),
        original_rounding_function_file=str((ROOT / 'Scripts/PolishOldTownHotel.py').resolve()),
        original_rounding_function_file_sha256=sha(ROOT / 'Scripts/PolishOldTownHotel.py'),
        original_rounding_sites=['mesh LOD0 local vertex before world transformation',
            'world transformed vertex before material WPO addition'],
        corrected_serialization='unrounded native floats at both original rounding sites',
        affected_instances=len({row['actor'] for row in rows}), affected_meshes=len(cache),
        confirmed_precision_collapses=len(rows), actual_native_degenerate_faces=0, rows=rows)
    output = WORK / 'RenderExportPrecisionDiagnosis.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False))
    assert report['passed']


if __name__ == '__main__':
    main()
