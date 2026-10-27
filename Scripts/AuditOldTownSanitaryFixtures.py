"""Independent saved-world fixture and existing architectural regression checks."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OptimizeOldTownSanitaryFixtures import expected_actor,collision_signature
from PolishOldTownHotel import sha
WORK=ROOT/'Saved/CodexOutputs/SanitaryFixtures_20261011'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    import AuditOldTownHotelDetails as hotel
    hotel.WORK=WORK;hotel.main()
    build=read(WORK/'BuildReport.json');repair=build['fixture_optimization'];before=read(WORK/'InputSnapshot.json')['actors'];after=read(WORK/'AfterSnapshot.json')['actors']
    checks=[];errors=[]
    def check(n,ok,**v):
        checks.append(dict(name=n,passed=bool(ok),**v))
        if not ok:errors.append(n)
    rows={r['actor']:r for r in build['hotel_v4']['placed_props'] if r.get('asset_key') in ('Toilet','Washbasin')}
    newcams={r['camera'] for r in repair['new_cameras']}
    check('exact_complete_actor_manifest',set(after)==set(before)|newcams)
    for n,old in before.items():
        expected=expected_actor(old,rows[n]['asset'],rows[n]['asset_key']) if n in rows else old
        check('approved_saved_actor_state:'+n,after.get(n)==expected)
    for n in repair['preserved_fixture_collision_actors']:check('fixture_collision_unchanged:'+n,after[n]==before[n])
    for asset in repair['new_assets']:
        original=unreal.load_asset(asset['source']);new=unreal.load_asset(asset['asset'])
        check('mesh_collision_unchanged:'+asset['asset_key'],collision_signature(original)==collision_signature(new)==asset['collision_signature'])
        check('original_mesh_file_unchanged:'+asset['asset_key'],sha(Path(asset['source_file']))==asset['source_sha256'])
        check('new_faces_in_correct_material_slot:'+asset['asset_key'],asset['added_triangles_per_material_section'][0]>0 and asset['added_triangles_per_material_section'][1]==0)
    digest=sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap');check('persisted_map_unchanged',digest==build['map_sha256'])
    report=dict(passed=not errors,target_level=build['target_level'],map_sha256=digest,source='fresh_persisted_map_load',persisted_map_unchanged=digest==build['map_sha256'],checks=checks,errors=errors,statistics=dict(checks=len(checks),toilets=30,basins=30,unchanged_existing_actors=len(before)-60,preserved_fixture_collision_actors=60))
    write('FixtureSavedAudit.json',report);assert report['passed'],errors[:20]
    unreal.log('SANITARY_FIXTURES_SAVED_AUDIT_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:write('FixtureAuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
