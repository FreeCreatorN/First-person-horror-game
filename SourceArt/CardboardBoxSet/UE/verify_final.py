"""Verify package hashes and independent reload evidence without launching UE."""
from pathlib import Path
import sys
import carton_manifest as C

manifest, rows, expected, sources = C.read_export()
report = C.read(C.HERE / 'ue_import_report.json')
assert report['success'], report.get('error')
assert report['target_root'] == C.TARGET and report['source_hashes'] == sources
actual = C.packages()
assert actual == report['packages'] and set(actual) == expected
assert len(report['meshes']) == 13 and len(report['materials']) == 7
assert set(report['blueprints']) == set(C.ASSEMBLIES)
for name, parts in C.ASSEMBLIES.items():
    assert report['blueprints'][name]['static_mesh_count'] == len(parts)
    assert report['blueprints'][name]['interaction_events_installed'] is False
for row in actual.values():
    assert Path(row['file']).is_file() and row['bytes'] >= 256
protected = C.verify_protected(C.read(C.HERE / 'protected_content_sha256.json'))
fresh = None
path = C.HERE / 'fresh_editor_verification.json'
if path.exists():
    candidate = C.read(path)
    if candidate.get('source_hashes') == sources:
        assert candidate['success'], candidate.get('error')
        assert candidate['package_hashes'] == actual and candidate['verified_in_fresh_editor']
        fresh = candidate
if '--require-fresh' in sys.argv:
    assert fresh, 'Fresh editor reload missing'
C.write(C.HERE / 'final_verification.json', {
    'success': True, 'target_root': C.TARGET, 'run_id': report['run_id'],
    'package_count': len(actual), 'mesh_count': 13, 'material_count': 7, 'texture_count': 15,
    'variant_triangles': {variant: sum(rows[C.PREFIX + part]['triangles'] for part in parts)
                          for variant, parts in C.VARIANT_PARTS.items()},
    'blueprints': report['blueprints'], 'materials': report['materials'],
    'protected_paths_verified': protected, 'verified_in_running_editor': True,
    'verified_in_fresh_editor': bool(fresh),
    'lightmap_uv_available': {name: row['lightmap_uv_available'] for name, row in report['meshes'].items()},
})
print('CARTON_SAVED_PACKAGES_VERIFIED', len(actual), protected, 'fresh=' + str(bool(fresh)))
