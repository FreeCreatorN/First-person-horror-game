"""Read the exact saved street components after the user widened the scope."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import InspectOldTownRealismInput as native
from PolishOldTownHotel import actor_state,sha
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')
def main():
    inp=read(WORK/'RealismInput.json');old=read(Path(inp['baseline_snapshot_file']))
    assert sha(MAP)==inp['source_map_sha256']
    for p,h in inp['original_400_shared_asset_sha256'].items():assert sha(Path(p))==h,p
    protected={p:sha(Path(p)) for p in inp['protected_map_sha256']}
    changes=[dict(file=p,old_sha256=h,new_sha256=protected[p]) for p,h in inp['protected_map_sha256'].items() if protected[p]!=h]
    assert all(Path(r['file']).resolve()==ROOT/'Content/Yastar/Maps/L_Main.umap' for r in changes)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    by={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    assert {n:actor_state(a) for n,a in by.items()}==old['actors']
    native.WORK=WORK/'StreetNative';native.MATERIAL_CACHE.clear();native.MESH_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    labels=set(by)-set(inp['hotel_actor_labels']);records={}
    for i,n in enumerate(sorted(labels)):
        records[n]=[native.component_record(c) for c in by[n].get_components_by_class(unreal.SceneComponent)]
        if i%500==0:unreal.log('STREET_NATIVE_INPUT '+str(i)+'/'+str(len(labels)))
    assert not native.LIMITATIONS,native.LIMITATIONS[:10]
    assert sha(MAP)==inp['source_map_sha256'] and all(sha(Path(p))==h for p,h in protected.items())
    assert all(sha(Path(p))==h for p,h in native.SOURCE_FILES.items())
    result=dict(passed=True,source='fresh_persisted_map_load_read_only',source_map_sha256=sha(MAP),
        scope='Whole map: hotel and surrounding streets; poses, collisions and MainHome protected',
        component_records=records,actor_labels=sorted(labels),actor_count=len(labels),
        materials=native.MATERIAL_CACHE,meshes={p:{k:v for k,v in r.items() if k!='_positions'} for p,r in native.MESH_CACHE.items()},
        source_asset_file_sha256=native.SOURCE_FILES,protected_map_sha256=protected,
        protected_input_changes=changes,input_inventory_file=str(WORK/'RealismInput.json'),input_inventory_sha256=sha(WORK/'RealismInput.json'),
        original_400_shared_asset_sha256=inp['original_400_shared_asset_sha256'])
    write('RealismStreetInput.json',result)
    write('UserSavedInputRebase.json',dict(passed=True,current_input=protected,prior_input=inp['protected_map_sha256'],changes=changes,source_map_sha256=sha(MAP),original_shared_assets_unchanged=True))
    unreal.log('REALISM_STREET_INPUT_PASS '+str(len(records)))
if __name__=='__main__':
    try:main()
    except Exception:write('StreetInputFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
