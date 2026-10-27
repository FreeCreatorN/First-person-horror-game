"""Targeted revision on fresh original map; save this level only."""
import sys,traceback,re,shutil
from datetime import datetime,timezone
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelRevisionCommon import *
import OldTownDoorReuseCommon as reuse
from HotelRevisionHandles import configure_back_handles
from OldTownMainLightingCommon import compare_world_transform
from ApplyOldTownDoorReuse import actor_fields

PREFIX='OTS_HotelV4_'
FRONT=['Door_SouthFrontExit','Door_NorthFrontExit','Door_ServiceEntry']
REMOVE=FRONT+['Door_'+side+'FrontExit_'+part for side in ('South','North') for part in ('FixedHinges','MovingHinges')]+['ExitThreshold_0','ExitThreshold_64','ServiceEntryThreshold']
FURNITURE=['CleanLinenShelf','DirtyLinenShelf','ChangingShelf','EquipmentShelf']
REMOVE+= [n+'_DoorTrim' for n in FURNITURE]

def build_plan(by):
    patches=[]
    for suffix,y,neighbor in [('South',-3200.,'01'),('North',3200.,'14'),('Service',2600.,'21')]:
        patches.append(dict(label=PREFIX+'RevisionFrontWall_'+suffix,lo=[9000.,y-74.,11.],hi=[9020.,y+74.,235.],
            material_source=PREFIX+'F0_StreetWall_'+neighbor,role='front_wall'))
    for name,lo,hi in [('SouthOuter',-3380.,-3360.),('SouthInner',-3040.,-3020.),('NorthInner',3020.,3040.),('NorthOuter',3360.,3380.)]:
        patches.append(dict(label=PREFIX+'RevisionStairLining_'+name,lo=[9260.,lo,11.],hi=[10020.,hi,1480.],
            material_source=PREFIX+'F0_StreetWall_01',role='stair_wall'))
    for side,lo,hi in [('South',-3360.,-3040.),('North',3040.,3360.)]:
        for f,z in enumerate([11.,378.25,745.5]):
            mid=z+183.625
            patches.append(dict(label=PREFIX+'Revision'+side+'_F%d_LandingExtension'%f,lo=[9968.,lo,mid-20.],hi=[10020.,hi,mid],
                material_source=PREFIX+side+'_F%d_HalfLanding'%f,role='landing_extension'))
    for row in patches:own(by[row['material_source']])
    return dict(removed=[PREFIX+n for n in REMOVE],furniture=[PREFIX+n for n in FURNITURE],additions=patches)

def box(ae,row,by):
    lo,hi=row['lo'],row['hi'];center=[(a+b)/2 for a,b in zip(lo,hi)]
    a=ae.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),unreal.Rotator(0,0,0),False);assert a
    a.set_actor_label(row['label']);a.set_folder_path('CodexGenerated/Hotel/Revision_20261019')
    a.set_editor_property('tags',[unreal.Name('HotelRedesign_20261008_V4'),unreal.Name('HotelRevision_20261019')])
    c=a.static_mesh_component;c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    c.set_material(0,by[row['material_source']].static_mesh_component.get_material(0))
    c.set_mobility(unreal.ComponentMobility.STATIC)
    c.set_relative_scale3d(unreal.Vector(*[(b-a)/100 for a,b in zip(lo,hi)]))
    c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    return a

def attachment_rows(actors,doors):
    result=[]
    for a in actors:
        if a in doors:continue
        for c in a.get_components_by_class(unreal.SceneComponent):
            p=c.get_attach_parent()
            if p and p.get_owner() in doors:
                own(a)
                result.append(dict(actor=a,component=c,door=p.get_owner().get_actor_label(),parent=p.get_name(),socket=c.get_attach_socket_name(),
                    raw={k:c.get_editor_property(k) for k in ('relative_location','relative_rotation','relative_scale3d')},world=native.value(c.get_world_transform())))
    return result

def top_properties(actor):
    """Capture all readable actor properties, including any user-added variables."""
    result={}
    for name in dir(actor):
        if name.startswith('_'):continue
        try:result[name]=actor.get_editor_property(name)
        except Exception:pass
    return result

def replace(ae,old,cls,linked):
    old_name=old.get_name();old_path=old.get_path_name();label=old.get_actor_label();folder=old.get_folder_path();tags=list(old.tags)
    fields=actor_fields(old);raw=top_properties(old)
    assert old.rename('OTS_RetiredHotelRevision_'+old_name)
    old.set_actor_label('OTS_RetiredHotelRevision_'+label)
    a=ae.spawn_actor_from_class(cls,old.get_actor_location(),old.get_actor_rotation(),False);assert a
    assert a.rename(old_name) and a.get_path_name()==old_path
    a.set_actor_label(label);a.set_folder_path(folder);a.set_editor_property('tags',tags)
    for key in fields:
        current=old.get_editor_property(key)
        if native.value(a.get_editor_property(key))!=native.value(current):a.set_editor_property(key,current,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    proof=reuse.configure_door(old,a)
    cs=components(a)
    # Copy additional top-level scalar/struct instance overrides only when they
    # differ. Component/actor identity references are handled explicitly.
    top_failures=[]
    excluded={'actor_guid','actor_instance_guid','actor_label','folder_path','tags','root_component','blueprint_created_components','instance_components','creation_time'}
    for key,value in raw.items():
        if key in excluded or isinstance(value,unreal.ActorComponent):continue
        try:
            v=reuse._remap_raw(value,old,a,cs)
            if native.value(v)!=native.value(a.get_editor_property(key)):
                a.set_editor_property(key,v,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        except Exception as e:top_failures.append(dict(property=key,error=str(e)))
    for row in linked:
        c=row['component'];parent=cs[row['parent']];rule=unreal.AttachmentRule.KEEP_RELATIVE
        c.attach_to_component(parent,row['socket'],rule,rule,rule,False)
        assert c.get_attach_parent()==parent
        for k,v in row['raw'].items():
            if native.value(c.get_editor_property(k))!=native.value(v):c.set_editor_property(k,v,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        c.set_absolute(c.get_editor_property('absolute_location'),c.get_editor_property('absolute_rotation'),c.get_editor_property('absolute_scale'))
        compare_world_transform(row['world'],native.value(c.get_world_transform()))
    assert actor_fields(a)==fields and a.get_folder_path()==folder and list(a.tags)==tags
    proof.update(label=label,original_actor_path=old_path,actor_fields=fields,folder=str(folder),tags=[str(t) for t in tags],blueprint=a.get_class().get_path_name().split('.')[0],top_setter_failures=top_failures)
    assert ae.destroy_actor(old)
    rear=configure_back_handles(a)
    # All original scene components must remain exact after configuring new ones.
    current=reuse.door_snapshot(a)
    for name,source in proof['current_snapshot']['components'].items():
        if name.startswith('Rear'):continue
        assert current['components'][name]==source,(label,name)
    proof['rear']=rear
    return a,proof

def main():
    assert not (W/'Applied.json').exists()
    assets=read('Assets.json');inspection=read('Inspection.json');assert assets['passed']
    assert read('FrontRemovalPreflight.json')['passed']
    assert read('BlueprintGraphPreservation.json')['passed']
    assert native.sha(MAP)==assets['source_map_sha256']==inspection['source_map_sha256'],'Map changed since inspection'
    for p,h in assets['new_asset_sha256'].items():assert native.sha(Path(p))==h
    beforefiles=files()
    backup=R/'Saved/CodexBackups'/('HotelRevisionBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False);b=backup/MAP.name;shutil.copy2(MAP,b);assert native.sha(b)==inspection['source_map_sha256']
    write('Backup.json',dict(source=str(MAP),file=str(b),sha256=native.sha(b)))
    le,ae,world,actors,by=load();plan=build_plan(by)
    removed=set(plan['removed']);furniture=set(plan['furniture'])
    for n in removed|furniture:own(by[n])
    doors={r['label']:by[r['label']] for r in read('Doors.json')['doors'] if r['label'] not in removed}
    assert len(doors)==93
    for a in doors.values():own(a)
    attached=attachment_rows(actors,set(doors.values()))
    # Reference preflight uses the complete fresh Native export, not labels.
    before=read('BeforeScene.json');assert len(actors)==before['actor_count']
    source_names={by[n].get_name():n for n in removed|set(doors)}
    pattern=re.compile(r'PersistentLevel\.('+'|'.join(sorted(map(re.escape,source_names),key=len,reverse=True))+r')(?![A-Za-z0-9_])')
    linked_labels={r['actor'].get_actor_label() for r in attached};refs=[]
    for label,rec in before['full_existing_actor_native'].items():
        if label in removed|set(doors):continue
        for line in text(rec['file']).splitlines():
            m=pattern.search(line)
            if m and not(label in linked_labels and source_names[m.group(1)] in doors and line.strip().startswith('AttachParent=')):
                refs.append(dict(actor=label,line=line))
    write('ReferencePreflight.json',dict(passed=not refs,unexpected=refs,attachment_count=len(attached)))
    assert not refs,refs
    proof=[]
    for label,old in doors.items():
        source=old.get_class().get_path_name().split('.')[0];target=assets['blueprints'][source]
        cls=unreal.EditorAssetLibrary.load_blueprint_class(target);assert cls
        a,p=replace(ae,old,cls,[r for r in attached if r['door']==label]);by[label]=a;proof.append(p)
    for label in removed:assert ae.destroy_actor(by.pop(label))
    for suffix,row in assets['furniture'].items():
        a=by[PREFIX+suffix];c=a.static_mesh_component;pos=native.value(a.get_actor_location())
        c.set_static_mesh(unreal.load_asset(row['asset']));c.set_editor_property('override_materials',[],notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        a.set_actor_scale3d(unreal.Vector(1,1,1));a.set_actor_location(unreal.Vector(pos[0],pos[1],11.),False,True)
        c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    for row in plan['additions']:by[row['label']]=box(ae,row,by)
    changed=set(doors)|removed|furniture
    # Other Actors, including user edits and all 120 remaining external hinges,
    # are exact before the only map save.
    current=[a for a in ae.get_all_level_actors() if a.get_actor_label() not in changed and a.get_actor_label() not in {r['label'] for r in plan['additions']}]
    base.W=W;base.TAG='HotelRevision_NoExistingActorExclusion'
    expected=filtered(before,changed);actual=snapshot(current,'PreSaveOthers',world)
    write('ExpectedOthers.json',expected);write('PreSaveOthers.json',actual);base.compare_snapshot(expected,actual)
    # Fail before saving if the GUI saved original old-town during this run.
    assert native.sha(MAP)==inspection['source_map_sha256'],'Original map was changed externally; helper does not overwrite it'
    assert le.save_current_level()
    now=files();outside=[p for p,h in beforefiles.items() if now.get(p)!=h and Path(p)!=MAP]
    assert all(native.sha(Path(p))==h for p,h in assets['new_asset_sha256'].items())
    write('Applied.json',dict(passed=True,source_map_sha256=inspection['source_map_sha256'],map_sha256=native.sha(MAP),plan=plan,doors=proof,
        actor_count=len(ae.get_all_level_actors()),new_asset_sha256=assets['new_asset_sha256'],other_actors_exact=True,
        outside_file_changes_observed=outside,explicit_saved_level=TARGET,existing_assets_saved=[]))
    unreal.log('HOTEL_REVISION_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception as error:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc(),proof=getattr(error,'proof',None)));raise
