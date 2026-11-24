"""Check saved freezer packages and the independent fresh-editor receipt."""
import sys
from pathlib import Path
from freezer_manifest import HERE,TARGET,packages,read,read_export,verify_protected,write
manifest,rows,expected,sources=read_export()
report=read(HERE/'ue_import_report.json');assert report['success'],report.get('error')
assert report['target_root']==TARGET and report['source_hashes']==sources
actual=packages();assert actual==report['packages'] and set(actual)==expected
assert report['materials']['glass_translucent']
assert len(report['meshes'])==11
assert report['blueprint']['planning_category_count']==6 and report['blueprint']['static_mesh_count']==11
assert report['blueprint']['interaction_events_installed'] is False
for row in actual.values():assert Path(row['file']).is_file() and row['bytes']>=256
protected=verify_protected(read(HERE/'protected_content_sha256.json'))
fresh=None;path=HERE/'fresh_editor_verification.json'
if path.exists():
    candidate=read(path)
    if candidate.get('source_hashes')==sources:
        assert candidate['success'],candidate.get('error')
        assert candidate['package_hashes']==actual and candidate['verified_in_fresh_editor']
        fresh=candidate
if '--require-fresh' in sys.argv:assert fresh,'Fresh editor reload missing'
write(HERE/'final_verification.json',{'success':True,'target_root':TARGET,'run_id':report['run_id'],
    'package_count':len(actual),'mesh_count':11,'planning_category_count':6,
    'triangles':sum(row['triangles'] for row in rows.values()),'blueprint':report['blueprint'],
    'materials':report['materials'],'doors':manifest['doors'],'protected_paths_verified':protected,
    'verified_in_fresh_editor':bool(fresh)})
print('FREEZER_SAVED_PACKAGES_VERIFIED',len(actual),protected,'fresh='+str(bool(fresh)))
