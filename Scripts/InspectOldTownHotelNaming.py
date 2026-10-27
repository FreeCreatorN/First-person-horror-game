"""Read-only fresh map, source assets, and opening assemblies for Hotel naming."""
import sys,json,re,traceback
from pathlib import Path
from collections import Counter
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor
from OldTownMainLightingCommon import capture_geometry_state
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';W.mkdir(parents=True,exist_ok=True)
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet';MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def write(n,x):native.write(W/n,x)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def main():
    assert not (W/'Inventory.json').exists(),'Fresh inventory must not overwrite accepted input'
    before=files();write('ProtectedBefore.json',dict(file_sha256=before))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());labels=[a.get_actor_label() for a in actors];assert len(set(labels))==len(labels)
    state={a.get_actor_label():stable_actor(a) for a in actors}
    geometry=capture_geometry_state(actors)
    windows=[];doors=[];bp_records={}
    for actor in actors:
        cp=actor.get_class().get_path_name();package=cp.split('.')[0]
        if not package.startswith('/Game/CodexGenerated/OldTown/'):continue
        if not re.search(r'window|door|reusabledoor|swing|slider',package,re.I):continue
        row=dict(label=actor.get_actor_label(),name=actor.get_name(),path=actor.get_path_name(),class_path=cp,state=state[actor.get_actor_label()],components={k:v for k,v in geometry.items() if k.startswith(actor.get_actor_label()+'::')})
        (windows if re.search('window',package,re.I) else doors).append(row)
        if package not in bp_records:
            bp=unreal.load_asset(package);assert isinstance(bp,unreal.Blueprint)
            text,proof=native.native_text_export(bp,W/'Native'/(Path(package).name+'.t3d'));assert proof['passed']
            bp_records[package]=dict(native=proof,variables=sorted(set(re.findall(r'VarName="([^"]+)"',text))),parent_class_export=re.findall(r'ParentClass=(.*)',text))
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True);registry.scan_paths_synchronous(['/Game'],True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,include_searchable_names=True,include_soft_management_references=True,include_hard_management_references=True)
    refs=[]
    for a in registry.get_assets_by_path('/Game',True,False):
        p=str(a.package_name)
        refs.append(dict(package=p,asset_name=str(a.asset_name),class_path=str(a.asset_class_path),dependencies=sorted(str(n) for n in (registry.get_dependencies(p,options) or [])),referencers=sorted(str(n) for n in (registry.get_referencers(p,options) or []))))
    after=files();assert before==after,'Content/Config changed during read-only inspection'
    write('AssetReferences.json',dict(passed=True,map_sha256=native.sha(MAP),includes_hard_soft_and_management=True,forced_disk_rescan=True,assets=refs,file_sha256=before))
    write('SceneSnapshot.json',dict(actors=state,exact_scene_components=geometry,actor_count=len(actors)))
    write('Inventory.json',dict(passed=True,target_level=TARGET,map_sha256=native.sha(MAP),actor_count=len(actors),window_assemblies=windows,door_assemblies=doors,blueprints=bp_records,window_class_counts=dict(Counter(r['class_path'] for r in windows)),door_class_counts=dict(Counter(r['class_path'] for r in doors)),no_save_or_explicit_compile_called=True,existing_content_config_unchanged=True))
    unreal.log('HOTEL_NAMING_READ_ONLY_PASS '+str(dict(actors=len(actors),windows=len(windows),doors=len(doors),assets=len(refs))))
if __name__=='__main__':
    try:main()
    except Exception:write('InspectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
