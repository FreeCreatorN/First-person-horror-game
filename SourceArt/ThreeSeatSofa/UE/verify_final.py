"""Verify dynamic package hashes and independent reload evidence without UE."""
from pathlib import Path
import sys
import sofa_manifest as C

manifest, rows, expected, sources = C.read_export()
groups = C.assemblies(manifest, rows)
texture_spec = C.texture_spec(manifest)
generic = C.generic_spec(manifest)
material_names = set(texture_spec) | set(generic)
report = C.read(C.HERE / 'ue_import_report.json')
assert report['success'], report.get('error')
assert report['target_root'] == C.TARGET and report['source_hashes'] == sources
actual = C.packages()
assert actual == report['packages'] and set(actual) == expected
assert set(report['meshes']) == set(rows)
assert set(report['materials']) == material_names
assert set(report['blueprints']) == set(groups)
for name, parts in groups.items():
    assert report['blueprints'][name]['static_mesh_count'] == len(parts)
    assert report['blueprints'][name]['interaction_events_installed'] is False
    assert report['blueprints'][name]['animation_installed'] is False
for row in actual.values():
    assert Path(row['file']).is_file() and row['bytes'] >= 256
protected = C.verify_protected(C.read(C.HERE / 'protected_content_sha256.json'))
fresh = None
path = C.HERE / 'fresh_editor_verification.json'
if path.exists():
    candidate = C.read(path)
    if candidate.get('source_hashes') == sources and candidate.get('import_run_id') == report['run_id']:
        assert candidate['success'], candidate.get('error')
        assert candidate['package_hashes'] == actual and candidate['verified_in_fresh_editor']
        assert set(candidate['meshes']) == set(rows)
        assert set(candidate['blueprints']) == set(groups)
        assert set(candidate['materials']) == material_names
        fresh = candidate
if '--require-fresh' in sys.argv:
    assert fresh, 'Fresh editor reload missing'
C.write(C.HERE / 'final_verification.json', dict(
    success=True, target_root=C.TARGET, run_id=report['run_id'], package_count=len(actual),
    source_blend_sha256=manifest['source_sha256'], manifest_sha256=sources[C.MANIFEST.name],
    mesh_count=len(rows), material_count=len(material_names) + 1,
    textured_material_instances=len(texture_spec), generic_material_count=len(generic),
    texture_count=3 * len(texture_spec), blueprint_count=len(groups),
    total_triangles=sum(row['triangles'] for row in rows.values()),
    look_count=manifest.get('look_count', manifest.get('product_count', len(manifest.get('looks', [])))),
    blueprints=report['blueprints'], materials=report['materials'], parent_material=report['parent_material'],
    protected_paths_verified=protected, verified_in_import_editor=True,
    verified_in_fresh_editor=bool(fresh),
    lightmap_uv_available={name: row['lightmap_uv_available'] for name, row in report['meshes'].items()},
    lod_triangles=[sum(row['lod_triangles'][lod] for row in report['meshes'].values()) for lod in range(4)],
    collision_hulls=sum(row['convex_hulls'] for row in report['meshes'].values()),
))
print('SOFA_SAVED_PACKAGES_VERIFIED', len(actual), protected, 'fresh=' + str(bool(fresh)))
