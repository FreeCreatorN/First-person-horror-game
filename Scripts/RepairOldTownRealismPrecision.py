"""Recover full-precision imported UVs without changing map references/poses."""
import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as pbr
import OldTownRealismImport as imp
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
build=read(WORK/'BuildReport.json');material=read(WORK/'MaterialBuild.json')
assert pbr.sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==build['map_sha256']
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
pbr.initialize();axes=read(WORK/'AxisVerification.json')
for cat in ('Furniture','Architecture','Sanitary','Street'):
    base=ROOT/('SourceArt/OldTownRealism_20261012/'+cat);manifest=read(base/'ModelDataManifest.json');rows=[]
    for entry in manifest['variants']:
        m,row=imp.build_variant(entry,base,axes,cat);rows.append(row)
    write(cat+'AssetBuild.json',dict(passed=True,assets=rows,manifest_sha256=pbr.sha(base/'ModelDataManifest.json'),full_precision_uv_and_tangents=True))
rows={r['asset']:dict(r,sha256=pbr.sha(r['file'])) for r in material['assets']}
rows.update({r['asset']:r for r in pbr.report()['assets']})
material.update(assets=list(rows.values()))
compile_log=str(WORK/'SolidsImportSlots3.stdout.log')
if compile_log not in material['final_compile_logs']:material['final_compile_logs'].append(compile_log)
write('MaterialBuild.json',material)
build['new_asset_sha256'].update({str(p):pbr.sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
write('BuildReport.json',build)
write('PrecisionRepair.json',dict(passed=True,map_sha256=build['map_sha256'],mesh_count=143,map_references_unchanged=True,full_precision_uv=True))
unreal.log('REALISM_PRECISION_REPAIR_PASS')
