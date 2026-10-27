"""Read current saved doors, switch bindings and project-wide asset references."""
import sys,json,re,traceback
from pathlib import Path
from collections import Counter
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor
from OldTownMainLightingCommon import capture_geometry_state
W=R/'Saved/CodexOutputs/OldTownDoorReuse_20261017';W.mkdir(parents=True,exist_ok=True)
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
SWITCH='/Game/Yastar/Blueprints/BP_LightSwitch'
OWN_BP='/Game/CodexGenerated/OldTown/Blueprints/Openings/'
def write(name,obj):native.write(W/name,obj)
def files():return {str(p):native.sha(p) for base in (R/'Content',R/'Config') for p in base.rglob('*') if p.is_file()}
def export(obj,name):
    text,proof=native.native_text_export(obj,W/'Native'/name);assert proof['passed'];return text,proof
def main():
    before=files();write('ReadOnlyProtectedBefore.json',dict(file_sha256=before))
    bp=unreal.load_asset(SWITCH);assert isinstance(bp,unreal.Blueprint)
    text,proof=export(bp,'BP_LightSwitch.t3d')
    variables=sorted(set(re.findall(r'VarName="([^"]+)"',text)))
    cls=bp.generated_class();cdo=unreal.get_default_object(cls)
    switch=dict(asset=SWITCH,native=proof,variable_names=variables,cdo_variables=native.props(cdo,variables),cdo_properties=native.reflect_editor_properties(cdo))
    _,switch['cdo_native']=export(cdo,'BP_LightSwitch_CDO.t3d')
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(by)==len(actors),'Duplicate labels need review before replacement'
    doors=[];pieces=[];switches=[]
    for actor in actors:
        label=actor.get_actor_label();cp=actor.get_class().get_path_name()
        if cp.startswith(SWITCH+'.'):
            _,p=export(actor,'Switch_'+actor.get_name()+'.t3d')
            switches.append(dict(label=label,name=actor.get_name(),path=actor.get_path_name(),variables=native.props(actor,variables),properties=native.reflect_editor_properties(actor),native=p))
        if not re.search(r'door|swing|slider|门',label+' '+cp,re.I):continue
        row=dict(label=label,name=actor.get_name(),path=actor.get_path_name(),class_path=cp,tags=[str(t) for t in actor.tags],folder=str(actor.get_folder_path()),state=stable_actor(actor),components=capture_geometry_state([actor]))
        if cp.startswith(OWN_BP) and re.search(r'door|swing|slider',cp,re.I):
            _,row['native']=export(actor,'Door_'+actor.get_name()+'.t3d');doors.append(row)
        else:pieces.append(row)
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,include_searchable_names=True,include_soft_management_references=True,include_hard_management_references=True)
    records=[]
    for asset in registry.get_assets_by_path('/Game',True,False):
        package=str(asset.package_name)
        records.append(dict(package=package,asset_name=str(asset.asset_name),class_path=str(asset.asset_class_path),dependencies=sorted(str(n) for n in registry.get_dependencies(package,options)),referencers=sorted(str(n) for n in registry.get_referencers(package,options))))
    write('AssetReferences.json',dict(passed=True,project_asset_count=len(records),includes_hard_soft_and_management=True,assets=records))
    door_bp={}
    for row in doors:
        path=row['class_path'].split('.')[0]
        if path in door_bp:continue
        obj=unreal.load_asset(path);bptext,p=export(obj,Path(path).name+'.t3d')
        vnames=sorted(set(re.findall(r'VarName="([^"]+)"',bptext)))
        defaults=unreal.get_default_object(obj.generated_class())
        door_bp[path]=dict(native=p,variables=vnames,defaults=native.props(defaults,vnames),parent_class_export=re.findall(r'ParentClass=(.*)',bptext))
    after=files();changed={p:[before.get(p),after.get(p)] for p in set(before)|set(after) if before.get(p)!=after.get(p)}
    write('SwitchDiagnosisInput.json',dict(passed=not changed,blueprint=switch,instances=switches,map_sha256=native.sha(MAP),saved_disk_only=True,user_editor_unsaved_memory_not_inspected=True,no_save_or_explicit_compile_called=True))
    write('DoorInventory.json',dict(passed=not changed,target_level=TARGET,map_sha256=native.sha(MAP),actor_count=len(actors),owned_door_assemblies=doors,other_door_named_actors=pieces,door_blueprints=door_bp,assembly_class_counts=dict(Counter(d['class_path'] for d in doors)),no_save_or_explicit_compile_called=True,changed_content_or_config_files=changed))
    assert not changed,changed
    unreal.log('OLD_TOWN_DOOR_READ_ONLY_PASS '+json.dumps(dict(actors=len(actors),assemblies=len(doors),other_door_named=len(pieces),switches=len(switches),assets=len(records))))
if __name__=='__main__':
    try:main()
    except Exception:write('ReadOnlyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
