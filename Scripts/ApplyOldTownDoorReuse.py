"""Replace only the 124 proven assistant-made door assemblies; preserve all other Actors."""
import sys,json,re,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
import OldTownDoorReuseCommon as common
from OldTownMainLightingCommon import capture_geometry_state,compare_world_transform
W=R/'Saved/CodexOutputs/OldTownDoorReuse_20261017'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet';MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
base.W=W;base.TAG='OTS_DoorReuseNoExistingActorExclusion_20261017'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def reset_marks(world):unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
def snapshot(actors,phase,world):
    reset_marks(world);value=base.snapshot(actors,phase)
    pp=value['full_existing_actor_native'].get('PostProcessVolume')
    if pp:assert native_text(pp['file']).count('Begin Polygon')==6
    return value
def native_text(path):
    raw=Path(path).read_bytes();return raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
def verify_old_files(baseline,allow_map=False,allow_cleanup=False):
    removed={}
    if allow_cleanup:
        result=read('OfflineCleanupResult.json');approval=read('OfflineCleanupApproved.json')
        assert result['passed'] and approval['passed'] and native.sha(W/'OfflineCleanupApproved.json')==result['approval_sha256']
        manifest=read(result['manifest_file']);assert native.sha(Path(result['manifest_file']))==result['manifest_sha256']
        assert result['map_sha256']==approval['map_sha256']==manifest['map_sha256']==read('AppliedDoorReuse.json')['map_sha256']==native.sha(MAP)
        approved={r['file']:r['current_sha256'] for r in approval['candidate_files']}
        assert len(approved)==len(manifest['files'])==result['isolated_count']
        assert {r['original_path'] for r in manifest['files']}==set(approved)
        current={str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
        assert current==approval['protected_file_sha256']
        for row in manifest['files']:
            p=row['original_path'];assert p in approved and approved[p]==row['sha256']==baseline[p]
            assert not Path(p).exists() and native.sha(Path(row['isolated_path']))==row['sha256']
            removed[p]=row['sha256']
    changed=[p for p,h in baseline.items() if p not in removed and not (allow_map and Path(p)==MAP) and native.sha(Path(p))!=h]
    assert not changed,changed
    return dict(passed=True,checked_existing_files=len(baseline)-len(removed)-(1 if allow_map else 0),changed_protected_files=changed,verified_owned_resources_isolated=len(removed))
def actor_fields(actor):return native.props(actor,['hidden','actor_enable_collision','is_editor_only_actor','replicates','net_dormancy','always_relevant','net_cull_distance_squared','net_update_frequency','net_priority','can_be_damaged','initial_life_span','custom_time_dilation','spawn_collision_handling_method','auto_destroy_when_finished','enable_auto_lod_generation','hlod_layer'])
def apply():
    assert not (W/'AppliedDoorReuse.json').exists(),'Stage already applied'
    plan=read('ReusableBlueprints.json');assert plan['passed'] and native.sha(MAP)==plan['source_map_sha256']
    for p,h in plan['new_asset_sha256'].items():assert native.sha(Path(p))==h
    baseline=read('ProtectedBefore.json')['file_sha256'];verify_old_files(baseline)
    backup=read('Backup.json');assert native.sha(Path(backup['file']))==plan['source_map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET);world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==len(by)==7986
    labels={n for g in plan['groups'] for n in g['labels']};assert len(labels)==124
    source_doors={by[n] for n in labels}
    attachments=[]
    for actor in actors:
        if actor in source_doors:continue
        for comp in actor.get_components_by_class(unreal.SceneComponent):
            parent=comp.get_attach_parent()
            if parent and parent.get_owner() in source_doors:
                assert actor.get_actor_label().startswith('OTS_'),'Non-assistant attached object needs separate inspection'
                attachments.append(dict(actor=actor,component=comp,door=parent.get_owner().get_actor_label(),parent_name=parent.get_name(),socket=comp.get_attach_socket_name(),raw_local={k:comp.get_editor_property(k) for k in ('relative_location','relative_rotation','relative_scale3d')},world=comp.get_world_transform()))
    before=snapshot(actors,'BeforeReuse',world);write('BeforeReuseSnapshot.json',before)
    assert len(before['full_existing_actor_native'])==7986
    source_names={by[n].get_name() for n in labels};pattern=re.compile(r'PersistentLevel\.('+'|'.join(sorted((re.escape(n) for n in source_names),key=len,reverse=True))+r')(?![A-Za-z0-9_])')
    attachment_labels={r['actor'].get_actor_label() for r in attachments}
    hard_refs=[]
    for label,rec in before['full_existing_actor_native'].items():
        if label in labels:continue
        for line in native_text(rec['file']).splitlines():
            if pattern.search(line) and not (label in attachment_labels and line.strip().startswith('AttachParent=')):
                hard_refs.append(dict(actor=label,line=line))
    write('DoorReferencePreflight.json',dict(passed=not hard_refs,attachment_count=len(attachments),unexpected_hard_references=hard_refs))
    assert not hard_refs,hard_refs
    proofs=[];new_by={}
    for group in plan['groups']:
        cls=unreal.EditorAssetLibrary.load_blueprint_class(group['blueprint']);assert cls
        for label in group['labels']:
            old=by[label];old_name=old.get_name();old_path=old.get_path_name();folder=old.get_folder_path();tags=list(old.tags);fields=actor_fields(old)
            linked=[r for r in attachments if r['door']==label]
            # Keep local attachment properties verbatim; the replacement parent
            # will have the same full path and transform after FName restoration.
            assert old.rename('OTS_RetiredDoorReuse_'+old_name)
            old.set_actor_label('OTS_RetiredDoorReuse_'+label)
            new=ae.spawn_actor_from_class(cls,old.get_actor_location(),old.get_actor_rotation(),False);assert new
            assert new.rename(old_name) and new.get_path_name()==old_path
            new.set_actor_label(label);new.set_folder_path(folder);new.set_editor_property('tags',tags)
            assert new.get_folder_path()==folder and list(new.tags)==tags
            for key in fields:
                current=old.get_editor_property(key)
                if native.value(new.get_editor_property(key))!=native.value(current):new.set_editor_property(key,current)
            assert actor_fields(new)==fields
            proof=common.configure_door(old,new);assert proof['passed']
            proof.update(label=label,original_actor_path=old_path,actor_name_preserved=True,blueprint=group['blueprint'],class_path=new.get_class().get_path_name(),actor_fields=fields,folder_path=str(folder),tags=[str(t) for t in tags])
            components=common.component_map(new)
            for row in linked:
                comp=row['component'];parent=components[row['parent_name']]
                assert unreal.SystemLibrary.is_valid(comp) and unreal.SystemLibrary.is_valid(parent)
                assert common.component_map(comp.get_owner()).get(comp.get_name())==comp
                result=comp.attach_to_component(parent,row['socket'],unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
                assert comp.get_attach_parent()==parent and comp.get_attach_socket_name()==row['socket'],dict(component=comp.get_path_name(),parent=parent.get_path_name(),api_return=result)
                for key,v in row['raw_local'].items():comp.set_editor_property(key,v,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                compare_world_transform(native.value(row['world']),native.value(comp.get_world_transform()))
            assert ae.destroy_actor(old);proofs.append(proof);new_by[label]=new
    assert len(ae.get_all_level_actors())==7986
    other=[a for a in ae.get_all_level_actors() if a.get_actor_label() not in labels]
    actual=snapshot(other,'BeforeReuseSave',world)
    assert len(other)==len(actual['full_existing_actor_native'])==7862
    expected={k:({n:v for n,v in value.items() if n not in labels} if k in ('actors','actor_properties','full_existing_actor_native') else value) for k,value in before.items()}
    expected['actor_count']=len(other)
    expected['exact_scene_components']={k:v for k,v in before['exact_scene_components'].items() if k.split('::')[0] not in labels}
    base.compare_snapshot(expected,actual)
    verify_old_files(baseline)
    assert le.save_current_level()
    verify_old_files(baseline,True)
    assert all(native.sha(Path(p))==h for p,h in plan['new_asset_sha256'].items())
    write('ExpectedOtherActors.json',expected)
    write('AppliedDoorReuse.json',dict(passed=True,target_level=TARGET,source_map_sha256=plan['source_map_sha256'],map_sha256=native.sha(MAP),actor_count=7986,door_count=124,blueprint_count=10,groups=plan['groups'],door_proofs=proofs,attachments=[dict(actor=r['actor'].get_actor_label(),component=r['component'].get_name(),door=r['door'],parent_name=r['parent_name']) for r in attachments],new_asset_sha256=plan['new_asset_sha256'],existing_asset_protection=verify_old_files(baseline,True)))
    unreal.log('OLD_TOWN_DOOR_REUSE_APPLY_PASS')
def audit(after_cleanup=False):
    applied=read('AppliedDoorReuse.json');assert native.sha(MAP)==applied['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET);world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==len(by)==7986
    labels={p['label'] for p in applied['door_proofs']}
    phase='ReadbackAfterCleanupOtherActors' if after_cleanup else 'ReadbackOtherActors'
    actual=snapshot([a for a in actors if a.get_actor_label() not in labels],phase,world)
    assert len(actual['full_existing_actor_native'])==7862
    write(phase+'.json',actual);base.compare_snapshot(read('ExpectedOtherActors.json'),actual)
    rows=[]
    for p in applied['door_proofs']:
        actor=by[p['label']];assert actor.get_class().get_path_name()==p['class_path'] and actor.get_path_name()==p['original_actor_path'] and actor_fields(actor)==p['actor_fields']
        assert str(actor.get_folder_path())==p['folder_path'] and [str(t) for t in actor.tags]==p['tags']
        proof=common.verify_configured_door(p['source_snapshot'],actor);assert proof['passed'];rows.append(dict(label=p['label'],passed=True,proof=proof))
    protected=verify_old_files(read('ProtectedBefore.json')['file_sha256'],True,after_cleanup)
    assert all(native.sha(Path(p))==h for p,h in applied['new_asset_sha256'].items())
    write('DoorReuseAfterCleanupReadback.json' if after_cleanup else 'DoorReuseReadback.json',dict(passed=True,map_sha256=native.sha(MAP),actor_count=7986,door_count=124,shared_blueprints=10,doors=rows,all_other_actors_native_unchanged=True,protected=protected,after_cleanup=after_cleanup))
    unreal.log('OLD_TOWN_DOOR_REUSE_READBACK_PASS')
if __name__=='__main__':
    try:apply()
    except Exception as error:
        write('ApplyDoorFailure.json',dict(passed=False,traceback=traceback.format_exc(),proof=getattr(error,'proof',None)))
        raise
