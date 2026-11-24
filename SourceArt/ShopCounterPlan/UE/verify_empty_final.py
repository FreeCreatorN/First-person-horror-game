"""Verify scoped saved packages and the independent reload receipt."""
import sys
from pathlib import Path
import empty_manifest as C
manifest,rows,expected,sources=C.read_export()
r=C.read(C.HERE/'ue_empty_replacement_report.json')
assert r['success'],r.get('error')
assert r['source_hashes']==sources and r['target_root']==C.TARGET
actual=C.packages();assert actual==r['packages']
optional={C.LEGACY_GLASS} if r['legacy_glass'].get('retained_inactive') else set()
assert set(actual)==expected|optional
assert len(r['meshes'])==10
bp=r['blueprint'];assert bp['planning_category_count']==8 and bp['static_mesh_count']==10 and bp['empty_counter']
assert r['materials']['glass_translucent']
protected=C.verify_protected(C.read(C.HERE/'empty_protected_sha256.json'))
fresh=None;p=C.HERE/'empty_fresh_verification.json'
if p.exists():
    candidate=C.read(p)
    if candidate.get('source_hashes')==sources:
        assert candidate['success'],candidate.get('error')
        assert candidate['package_hashes']==actual and candidate['verified_in_fresh_editor']
        fresh=candidate
if '--require-fresh' in sys.argv:assert fresh,'Fresh reload receipt missing'
C.write(C.HERE/'empty_final_verification.json',{'success':True,'target_root':C.TARGET,'run_id':r['run_id'],
    'mode':r['mode'],'mesh_count':10,'package_count':len(actual),'planning_category_count':8,
    'triangles':sum(row['triangles'] for row in rows.values()),'empty_counter':True,'blueprint':bp,
    'verified_in_fresh_editor':bool(fresh),'protected_paths_verified':protected,'legacy_glass':r['legacy_glass'],
    'backup_directory':r['backup_directory'],'asset_paths_preserved':r['asset_paths_preserved']})
print('EMPTY_COUNTER_SAVED_PACKAGES_VERIFIED',len(actual),protected,'fresh='+str(bool(fresh)))
