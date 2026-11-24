"""Verify saved files, sources and the fresh-editor verification receipt."""
from pathlib import Path
import sys
from counter_manifest import HERE, TARGET, packages, read, read_export, verify_protected, write

manifest, rows, expected, source_hashes = read_export()
imported = read(HERE / 'ue_import_report.json')
assert imported['success'], imported.get('error')
assert imported['target_root'] == TARGET and imported['source_hashes'] == source_hashes
actual = packages()
assert actual == imported['packages'] and set(actual) == expected
assert imported['materials']['glass_translucent'] is True
assert len(imported['meshes']) == 9
assert imported['blueprint']['blueprint_ready'] is True
assert imported['blueprint']['interaction_events_installed'] is False
for package, data in actual.items():
    assert data['bytes'] >= 256 and Path(data['file']).is_file(), package
protected = verify_protected(read(HERE / 'protected_content_sha256.json'))
fresh_path = HERE / 'fresh_editor_verification.json'
fresh = None
if fresh_path.exists():
    fresh = read(fresh_path)
    assert fresh['success'] and fresh['source_hashes'] == source_hashes, fresh.get('error')
    assert fresh['package_hashes'] == actual and fresh['verified_in_fresh_editor'] is True
if '--require-fresh' in sys.argv:
    assert fresh is not None, 'Fresh editor reload has not been verified'
write(HERE / 'final_verification.json', {
    'success': True, 'target_root': TARGET, 'run_id': imported['run_id'],
    'mode': imported['mode'], 'import_world': imported['world'],
    'mesh_count': len(rows), 'package_count': len(actual),
    'triangles': sum(row['triangles'] for row in rows.values()),
    'meshes': imported['meshes'], 'blueprint': imported['blueprint'],
    'verified_in_fresh_editor': fresh is not None,
    'doors': manifest['doors'], 'materials': imported['materials'],
    'protected_paths_verified': protected,
})
print('SHOP_COUNTER_SAVED_PACKAGES_VERIFIED', len(actual), protected, 'fresh=' + str(fresh is not None))
