"""Create private size-shared door BPs and test each old variant without saving the map."""
import sys,json,hashlib,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import BuildOldTownOpeningBlueprints as builder
from OldTownMainLightingCommon import capture_geometry_state
import OldTownDoorReuseCommon as common
W=R/'Saved/CodexOutputs/OldTownDoorReuse_20261017'
ASSET='/Game/CodexGenerated/OldTown/DoorReuse_20261017/Blueprints'
FOLDER=R/('Content/'+ASSET.removeprefix('/Game/'))
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def verify(baseline):
    cur=files();changed=[p for p,h in baseline.items() if cur.get(p)!=h]
    added=set(cur)-set(baseline)
    assert not changed and all(Path(p).is_relative_to(FOLDER) for p in added),dict(changed=changed,unexpected=list(added))
    return dict(passed=True,checked_existing_files=len(baseline),new_asset_sha256={p:cur[p] for p in sorted(added)})
def main():
    plan=read('DoorReuseDesign.json');assert plan['passed'] and native.sha(MAP)==plan['source_map_sha256']
    assert not (W/'ReusableBlueprints.json').exists(),'Completed BP creation is immutable'
    assert not FOLDER.exists(),'New asset directory must start empty'
    baseline=files();write('ProtectedBefore.json',dict(file_sha256=baseline))
    backup=R/'Saved/CodexBackups'/('OriginalTownBeforeDoorReuse_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False);shutil.copy2(MAP,backup/MAP.name)
    assert native.sha(backup/MAP.name)==plan['source_map_sha256']
    write('Backup.json',dict(passed=True,file=str(backup/MAP.name),sha256=native.sha(MAP),created_before_content_writes=True))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET);actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(actors)==7986
    builder.ROOT=ASSET+'/'
    groups=[];proofs=[]
    for group in plan['groups']:
        sources={name:common.component_map(by[row['label']])[name] for row in group['instances'] for name in row['source_component_names']}
        representative=by[group['instances'][0]['label']];rep=common.component_map(representative)
        todo={row['name']:row for row in group['component_union']};ordered=[]
        while todo:
            ready=[n for n,r in todo.items() if r['parent'] is None or r['parent'] in {s['name'] for s in ordered}]
            assert ready,'Component parenting cycle'
            for name in sorted(ready):
                row=todo.pop(name);source=rep.get(name,sources[name]);is_root=row['parent'] is None
                local=source.get_editor_property('relative_location');rot=source.get_editor_property('relative_rotation');scale=source.get_editor_property('relative_scale3d')
                spec=dict(name=name,parent=row['parent'],mobility='STATIC' if source.get_editor_property('mobility')==unreal.ComponentMobility.STATIC else 'MOVABLE',
                    relative_location=[0,0,0] if is_root else native.value(local),relative_rotation=[0,0,0] if is_root else native.value(rot),relative_scale=[1,1,1] if is_root else native.value(scale),collision='NO_COLLISION')
                spec['class']=row['class_path'].rsplit('.',1)[1]
                if isinstance(source,unreal.StaticMeshComponent):
                    assert source.static_mesh
                    spec['asset']=source.static_mesh.get_path_name()
                    spec['material']=source.get_material(0).get_path_name() if source.get_material(0) else None
                ordered.append(spec)
        path=ASSET+'/'+group['new_blueprint_name_suggestion']
        bp,cls=builder.create_blueprint(path,ordered)
        templates=builder._templates(unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem),bp)
        for name,(_,component) in templates.items():
            if isinstance(component,unreal.StaticMeshComponent):
                if name not in rep:
                    component.set_static_mesh(None);component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    component.set_editor_property('visible',False);component.set_editor_property('hidden_in_game',True)
                else:
                    source=rep[name]
                    component.set_editor_property('override_materials',source.get_editor_property('override_materials'))
                    component.set_editor_property('body_instance',source.get_editor_property('body_instance'))
                    for prop in ('cast_shadow','generate_overlap_events','receives_decals','evaluate_world_position_offset','visible','hidden_in_game'):
                        component.set_editor_property(prop,source.get_editor_property(prop))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
        cls=unreal.EditorAssetLibrary.load_blueprint_class(path)
        seen=set()
        for row in group['instances']:
            if row['original_class_path'] in seen:continue
            seen.add(row['original_class_path']);source=by[row['label']]
            target=ae.spawn_actor_from_class(cls,source.get_actor_location(),source.get_actor_rotation(),False);assert target
            try:
                target.set_actor_label('OTS_TemporaryDoorReuseProbe')
                proof=common.configure_door(source,target)
                assert proof['passed'],proof
                proofs.append(dict(source_label=row['label'],source_class=row['original_class_path'],target_class=cls.get_path_name(),proof=proof))
            finally:assert ae.destroy_actor(target)
        groups.append(dict(blueprint=path,class_path=cls.get_path_name(),clear_dimensions_cm=group['clear_dimensions_cm'],labels=[r['label'] for r in group['instances']],component_union=group['component_union']))
    assert len(proofs)==15 and len({p['source_label'] for p in proofs})==15
    assert len(ae.get_all_level_actors())==7986 and native.sha(MAP)==plan['source_map_sha256']
    protected=verify(baseline);assert len(protected['new_asset_sha256'])==10
    write('ReusableBlueprints.json',dict(passed=True,source_map_sha256=plan['source_map_sha256'],groups=groups,variant_probes=proofs,new_asset_sha256=protected['new_asset_sha256'],no_map_save=True,existing_file_protection=protected))
    unreal.log('OLD_TOWN_SHARED_DOOR_BLUEPRINTS_PROBE_PASS')
if __name__=='__main__':
    try:main()
    except Exception as error:
        write('BlueprintProbeFailure.json',dict(passed=False,traceback=traceback.format_exc(),proof=getattr(error,'proof',None)))
        raise
