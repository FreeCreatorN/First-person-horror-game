"""Correct winding only in this task's own unaccepted new shape assets."""
from copy import deepcopy
from datetime import datetime,timezone
import json,sys,shutil,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import RefineOldTownSanitaryShapes as refinement
from PolishOldTownHotel import actor_state,sha
WORK=refinement.WORK;MAP=refinement.MAP
REJECTED_SHA='611b2cdc364a76388ff60e4a216dae7232ca8a4b8fc1c8d31289ce4067ee3f05'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name,value):(WORK/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    assert not (WORK/'WindingRepairApplied.json').exists(),'Winding repair already saved.'
    build=read(WORK/'BuildReport.json');saved=read(WORK/'AfterSnapshot.json')
    assert sha(MAP)==build['map_sha256']==saved['source_map_sha256']==REJECTED_SHA
    repair=build['sanitary_shape_refinement'];assert repair['source_map_sha256']==refinement.SOURCE_SHA
    for file,digest in dict(saved['shared_asset_sha256'],**build['new_asset_sha256'],**build['protected_map_sha256']).items():assert sha(Path(file))==digest,file
    archive=WORK/'RejectedWindingPreview';archive.mkdir(parents=True,exist_ok=True)
    # Copies preserve the failed preview for diagnosis; no old approved result is modified.
    for p in WORK.glob('*.json'):
        if not (archive/p.name).exists():shutil.copy2(p,archive/p.name)
    for sub in ('Renders','Runs'):
        if (WORK/sub).exists() and not (archive/sub).exists():shutil.copytree(WORK/sub,archive/sub)
    shutil.copy2(MAP,archive/MAP.name)
    previous={r['asset_key']:r for r in repair['new_assets']}
    for row in previous.values():
        p=Path(row['file']);assert p.resolve().is_relative_to((ROOT/'Content/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011').resolve())
        shutil.copy2(p,archive/p.name)
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(refinement.TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    assert {a.get_actor_label():actor_state(a) for a in actors}==saved['actors']
    new_rows=[]
    for kind in ('Toilet','Washbasin'):
        assert sha(Path(previous[kind]['file']))==previous[kind]['sha256']
        mesh,row=refinement.clone_fixture(kind,True)
        assert row['asset']==previous[kind]['asset'] and row['source_sha256']==previous[kind]['source_sha256']
        assert row['sha256']!=previous[kind]['sha256']
        new_rows.append(row);build['new_asset_sha256'][row['file']]=row['sha256']
    # References and actor geometry bounds remain identical; saving is safe only
    # after every serialized actor state has been compared with this preview.
    assert {a.get_actor_label():actor_state(a) for a in actors}==saved['actors']
    assert sha(MAP)==REJECTED_SHA and levels.save_current_level()
    digest=sha(MAP);at=datetime.now(timezone.utc).isoformat()
    repair.update(new_assets=new_rows,map_sha256=digest,geometry_revision_utc=at,
                  winding_correction='New recipe triangles reversed for Unreal clockwise front faces; normals recomputed only on new pieces.',
                  rejected_preview_directory=str(archive))
    build.update(map_sha256=digest,status='PASS')
    applied=read(WORK/'Applied.json');applied['map_sha256']=digest
    write('BuildReport.json',build);write('ShapeOptimizationReport.json',repair);write('Applied.json',applied)
    write('WindingRepairApplied.json',dict(passed=True,map_sha256=digest,previous_map_sha256=REJECTED_SHA,revision_utc=at,new_asset_sha256={r['file']:r['sha256'] for r in new_rows},original_actor_states_unchanged=True))
    unreal.log('SANITARY_SHAPES_WINDING_REPAIR_PASS '+digest)

if __name__=='__main__':
    try:main()
    except Exception:write('WindingRepairFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
