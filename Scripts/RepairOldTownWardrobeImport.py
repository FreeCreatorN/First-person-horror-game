"""Preserve the wardrobe's source UV seams during legacy import; no map edits."""
import json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as pbr
import OldTownRealismImport as imp
import InspectOldTownRealismInput as native
from AuditOldTownRealismAppearance import physical_uv_errors
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
build=read(WORK/'BuildReport.json');digest=build['map_sha256']
assert pbr.sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==digest
pbr.initialize()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
base=ROOT/'SourceArt/OldTownRealism_20261012/Furniture'
entry=next(v for v in read(base/'ModelDataManifest.json')['variants'] if v['kind']=='WardrobeDoors')
entry['native_no_degenerate_merge']=True
entry['native_uv_chart_separation']=True
mesh,row=imp.build_variant(entry,base,read(WORK/'AxisVerification.json'),'Furniture')
native.WORK=WORK/'WardrobeImportNative';native.WORK.mkdir(exist_ok=True)
record=native.mesh_record(mesh);geometry=read(Path(record['geometry_file']))
uv=physical_uv_errors(geometry,entry['world_dimensions_cm'])
write('WardrobeImportRepair.json',dict(passed=uv['passed'],map_sha256=digest,uv=uv,mesh=record,source_triangles=entry['triangles']))
assert uv['passed'],uv
furniture=read(WORK/'FurnitureAssetBuild.json')
furniture['assets']=[row if r['key']==entry['key'] else r for r in furniture['assets']]
write('FurnitureAssetBuild.json',furniture)
material=read(WORK/'MaterialBuild.json')
rows={r['asset']:dict(r,sha256=pbr.sha(r['file'])) for r in material['assets']}
rows.update({r['asset']:r for r in pbr.report()['assets']})
material['assets']=list(rows.values());material['final_compile_logs'].append(str(WORK/'WardrobeImportRepair2.stdout.log'))
write('MaterialBuild.json',material)
build['new_asset_sha256'].update({str(p):pbr.sha(p) for p in (ROOT/'Content/CodexGenerated/OldTown/Realism_20261012').rglob('*.uasset')})
write('BuildReport.json',build)
assert pbr.sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==digest
unreal.log('WARDROBE_NATIVE_IMPORT_REPAIR_PASS')
