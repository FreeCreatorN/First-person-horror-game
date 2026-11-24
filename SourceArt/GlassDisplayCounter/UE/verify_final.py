"""Verify saved cabinet content, preserving the live Unreal session."""

from pathlib import Path
import sys

from cabinet_manifest import BLUEPRINT, HERE, TARGET, packages, read, read_export, verify_protected, write


manifest, _, expected, source_hashes = read_export()
imported = read(HERE / 'ue_import_report.json')
assert imported['success'], imported.get('error')
assert imported['target_root'] == TARGET and imported['source_hashes'] == source_hashes
actual = packages()
assert set(actual) == expected
blueprint_package = TARGET + '/' + BLUEPRINT
graph_file = HERE / 'ue_blueprint_graph_report.json'
graph = None
if graph_file.exists():
    graph = read(graph_file)
    assert graph['success'] and graph['asset'].split('.')[0] == blueprint_package
    assert graph['blueprint_sha256'] == actual[blueprint_package]['sha256']
    assert len(graph['events']) == 2 and all(graph['events'].values())
    assert all(actual[key] == imported['packages'][key] for key in expected if key != blueprint_package)
else:
    assert actual == imported['packages']
if '--require-slide-events' in sys.argv:
    assert graph is not None, 'Blueprint door events have not been verified'
assert imported['materials']['glass_translucent'] is True
assert len(imported['meshes']) == 3 and imported['blueprint']
assert set(imported['meshes']) == {row['name'] for row in manifest['assets']}
for package, data in actual.items():
    assert data['bytes'] >= 256 and Path(data['file']).is_file(), package
protected = verify_protected(read(HERE / 'protected_content_sha256.json'))
write(HERE / 'final_verification.json', {
    'success': True,
    'target_root': TARGET,
    'run_id': imported['run_id'],
    'mode': imported['mode'],
    'import_world': imported['world'],
    'mesh_count': len(imported['meshes']),
    'package_count': len(actual),
    'meshes': imported['meshes'],
    'blueprint': imported['blueprint'],
    'blueprint_graph': graph,
    'doors': imported['doors'],
    'materials': imported['materials'],
    'protected_paths_verified': protected,
})
print('GLASS_COUNTER_SAVED_PACKAGES_VERIFIED', len(actual), protected)
