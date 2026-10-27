"""Preflight independent materials and furniture assets without editing a map."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as pbr
import OldTownRealismImport as imp
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.Enable 0')
    pbr.initialize()
    for role in pbr.SPEC:
        for mode in ('World','UV'):pbr.master(role,mode)
    write('MaterialBuild.json',pbr.report())
    base=ROOT/'SourceArt/OldTownRealism_20261012/Furniture'
    axes=imp.axis_probe(base/'AxisProbe.fbx');write('AxisVerification.json',axes)
    write('NativeTransformAPI.json',dict(transform_mesh=str(unreal.GeometryScript_MeshTransforms.transform_mesh.__doc__),Transform=str(unreal.Transform.__doc__)))
    manifest=json.loads((base/'ModelDataManifest.json').read_text(encoding='utf-8'))
    assert manifest['status']=='COMPLETE' and manifest['actor_count']==680
    reports=[]
    for entry in manifest['variants']:
        mesh,row=imp.build_variant(entry,base,axes);reports.append(row)
        write('FurnitureAssetProgress.json',dict(passed=True,completed=len(reports),expected=len(manifest['variants']),assets=reports))
    write('FurnitureAssetBuild.json',dict(passed=True,assets=reports,actors=680,axis_verification=axes,manifest_sha256=pbr.sha(base/'ModelDataManifest.json')))
    write('MaterialBuild.json',pbr.report())
    unreal.log('REALISM_ASSET_PREPARE_PASS '+str(len(reports)))
try:main()
except Exception:
    write('AssetFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
