"""Compile final owned surface roles and bind new package files before audits."""
import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as pbr
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def read(n):return json.loads((WORK/n).read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
build=read('BuildReport.json');old=read('MaterialBuild.json')
assert pbr.sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==build['map_sha256']
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
pbr.initialize()
for r in old['assets']:
    if r['kind']=='master':pbr.master(r['role'],r['projection'])
rows={r['asset']:dict(r,sha256=pbr.sha(r['file'])) for r in old['assets']}
rows.update({r['asset']:r for r in pbr.report()['assets']})
logs=list(old.get('final_compile_logs',[]));current_log=str(WORK/'MaterialAppearance.stdout.log')
if current_log not in logs:logs.append(current_log)
write('MaterialBuild.json',dict(passed=True,assets=list(rows.values()),physical_uv_cm_per_unit=100.,source_license='https://polyhaven.com/license',final_compile_logs=logs))
build['new_asset_sha256'].update({str(p):pbr.sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
build['hotel_openings_review_cameras']=list(dict.fromkeys(build['hotel_openings_review_cameras']+['CAM_Cleanup_MainStreet','CAM_StreetAccess_Lamp','CAM_Enterable_Bedroom','CAM_OTS_Alley']))
build['realism_scope']='whole_map'
write('BuildReport.json',build)
unreal.log('REALISM_MATERIAL_FINALIZE_PASS')
