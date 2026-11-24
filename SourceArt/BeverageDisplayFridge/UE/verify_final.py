"""Verify saved fridge packages and optional independent reload evidence."""
import sys
from pathlib import Path
from fridge_manifest import HERE,TARGET,packages,read,read_export,verify_protected,write
manifest,rows,expected,sources=read_export()
update=HERE/'ue_update_report.json'
r=read(update if update.exists() else HERE/'ue_import_report.json');assert r['success'],r.get('error')
assert r['target_root']==TARGET and r['source_hashes']==sources
actual=packages();assert actual==r['packages'] and set(actual)==expected
assert len(r['meshes'])==16 and r['materials']['glass_translucent']
assert r['blueprint']['planning_category_count']==9 and r['blueprint']['static_mesh_count']==16
assert r['blueprint']['interaction_events_installed'] is False and r['blueprint']['light_components']==0
for row in actual.values():assert Path(row['file']).is_file() and row['bytes']>=256
protected=verify_protected(read(HERE/('protected_update_sha256.json' if update.exists() else 'protected_content_sha256.json')))
fresh=None;path=HERE/'fresh_editor_verification.json'
if path.exists():
    candidate=read(path)
    if candidate.get('source_hashes')==sources:
        assert candidate['success'],candidate.get('error')
        assert candidate['package_hashes']==actual and candidate['verified_in_fresh_editor']
        fresh=candidate
if '--require-fresh' in sys.argv:assert fresh,'Fresh editor reload missing'
write(HERE/'final_verification.json',{'success':True,'target_root':TARGET,'run_id':r.get('run_id',r.get('started_utc')),
    'package_count':len(actual),'mesh_count':16,'planning_category_count':9,
    'triangles':sum(row['triangles'] for row in rows.values()),'blueprint':r['blueprint'],
    'materials':r['materials'],'doors':manifest['doors'],'protected_paths_verified':protected,
    'verified_in_running_editor':True,'verified_in_fresh_editor':bool(fresh)})
print('FRIDGE_SAVED_PACKAGES_VERIFIED',len(actual),protected,'fresh='+str(bool(fresh)))
