"""Read user's current saved town without applying an obsolete stage baseline."""
import sys,json,hashlib,shutil
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
from OldTownMainLightingCommon import capture_geometry_state,directional_record
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016';W.mkdir(parents=True,exist_ok=True)
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet';MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
MAIN=R/'Content/Yastar/Maps/L_Main.umap'
def main():
    before={str(p):native.sha(p) for p in (MAP,MAIN)}
    backup=R/'Saved/CodexBackups'/('UserOldTownBeforeVersion2_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False);out=backup/'L_OldTownSchoolStreet.umap';shutil.copy2(MAP,out)
    assert native.sha(out)==before[str(MAP)]
    native.write(W/'UserMapBackup.json',dict(passed=True,file=str(out),sha256=before[str(MAP)],source_file=str(MAP)))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());states={a.get_actor_label():stable_actor(a) for a in actors}
    assert len(states)==len(actors)
    meshes={};instances=Counter();cameras=[];scene_captures=[];dependencies=set();visible=0;static=0
    for a in actors:
        if isinstance(a,unreal.CameraActor):
            cameras.append(dict(label=a.get_actor_label(),name=a.get_name(),class_path=a.get_class().get_path_name(),folder=str(a.get_folder_path()),
                state=stable_actor(a),actor_properties=native.props(a,['hidden','is_editor_only_actor','auto_activate_for_player'])))
        for c in a.get_components_by_class(unreal.SceneCaptureComponent):
            scene_captures.append(dict(actor=a.get_actor_label(),component=c.get_name(),class_path=c.get_class().get_path_name(),
                properties=native.props(c,['capture_every_frame','capture_on_movement','lod_distance_factor','max_view_distance_override','texture_target'])))
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            static+=1;m=c.static_mesh
            if not m:continue
            p=m.get_path_name();instances[p]+=1;dependencies.add(p.split('.')[0])
            if c.get_editor_property('visible') and not c.get_editor_property('hidden_in_game'):visible+=1
            if p not in meshes:
                meshes[p]=dict(asset=p,file=str(native.asset_file(m)),sha256=native.sha(native.asset_file(m)),
                    nanite=native.value(m.get_editor_property('nanite_settings')),instances=0)
            for i in range(c.get_num_materials()):
                material=c.get_material(i)
                if material:dependencies.add(material.get_path_name().split('.')[0])
    for p,n in instances.items():meshes[p]['instances']=n
    geometry=capture_geometry_state(actors)
    lights=light_inventory(actors);dirs=[directional_record(a) for a in actors if a.get_components_by_class(unreal.DirectionalLightComponent)]
    registry=unreal.AssetRegistryHelpers.get_asset_registry();options=unreal.AssetRegistryDependencyOptions()
    for name in ('include_hard_package_references','include_soft_package_references'):options.set_editor_property(name,True)
    queue=list(dependencies|{TARGET})
    while queue:
        package=queue.pop()
        if package in dependencies and package not in set():pass
        for dep in registry.get_dependencies(unreal.Name(package),options):
            dep=str(dep)
            if dep.startswith('/Game/') and dep not in dependencies:dependencies.add(dep);queue.append(dep)
    files={}
    for p in dependencies:
        stem=R/('Content/'+p[6:])
        for ext in ('.uasset','.umap'):
            file=Path(str(stem)+ext)
            if file.is_file():files[str(file)]=native.sha(file)
    own={str(p.resolve()):native.sha(p) for p in (R/'Content/CodexGenerated/OldTown').rglob('*') if p.is_file()}
    native.write(W/'Input.json',dict(passed=True,target_level=TARGET,map_sha256=before[str(MAP)],main_sha256=before[str(MAIN)],
        actor_count=len(actors),scene_component_count=len(geometry),static_mesh_components=static,visible_mesh_components=visible,
        actors=states,exact_scene_components=geometry,light_inventory=lights,directional_lights=dirs,cameras=cameras,
        scene_capture_components=scene_captures,mesh_records=meshes,referenced_game_package_sha256=files,
        all_original_generated_file_sha256=own,backup=dict(file=str(out),sha256=native.sha(out)),
        user_changes_adopted_as_authorized_input=True,map_save_requested=False))
    # Read Main last; a new map load must not change either input on disk.
    assert le.load_level('/Game/Yastar/Maps/L_Main')
    main_dirs=[directional_record(a) for a in ae.get_all_level_actors() if a.get_components_by_class(unreal.DirectionalLightComponent)]
    native.write(W/'MainDirectionalInput.json',dict(passed=True,map_sha256=before[str(MAIN)],directional_lights=main_dirs,map_save_requested=False))
    assert all(native.sha(Path(p))==h for p,h in before.items())
    unreal.log('USER_OLDTOWN_V2_INPUT_PASS '+json.dumps(dict(actors=len(actors),cameras=len(cameras),static=static,visible=visible,meshes=len(meshes),directions=len(dirs))))
if __name__=='__main__':main()
