"""Apply millimetre render repairs to the current user-saved map."""
import json,sys,shutil,traceback,math
from pathlib import Path
from copy import deepcopy
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from PolishOldTownDetails import actor_bounds
from OldTownSurfaceMaterials import make_offset_material,get_report,asset_hashes,PARAMETER
from OldTownWindowSurfaceRepair import apply_window
from AuditOldTownHotelV4 import audit,refresh
from ValidateEnterableStreet import validate_main_home
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
OLD=ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'Applied.json').exists(),'Repair already saved; inspect rather than reapply.'
    original=read(WORK/'InputSnapshot.json');build=read(OLD/'BuildReport.json');plan=build['hotel_v4']
    mapfile=ROOT/('Content/'+build['target_level'][6:]+'.umap');oldhash=sha(mapfile)
    assert oldhash==original['source_map_sha256']
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert {n:actor_state(a) for n,a in by.items()}==original['actors'],'User input changed.'
    before=WORK/'Before';before.mkdir(exist_ok=True)
    for p in (mapfile,OLD/'BuildReport.json',ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'):
        if not (before/p.name).exists():shutil.copy2(p,before/p.name)
    meshes=read(WORK/'MeshPreparation.json');assert meshes['passed']
    offsetplan=read(WORK/'OffsetPlanFinal.json');assert offsetplan['summary']['passed']
    offsets=offsetplan['offsets_cm'];window_reports=[]
    refresh(actors)
    plan['placed_windows']=[(lambda pair:(window_reports.append(pair[1]),pair[0])[1])(apply_window(by[r['actor']],r)) for r in plan['placed_windows']]
    swaps=[];materials=[];visual_ids=set()
    for a in actors:
        component_names=[c.get_name() for c in a.get_components_by_class(unreal.StaticMeshComponent)]
        for component_name in component_names:
            # Editor property notifications may reconstruct a Blueprint's SCS
            # components. Never keep references to siblings across such edits.
            c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==component_name)
            if not c.static_mesh or not c.get_editor_property('visible') or c.get_editor_property('hidden_in_game'):continue
            identifier=a.get_actor_label()+'::'+c.get_name();visual_ids.add(identifier)
            oldmesh=c.static_mesh.get_path_name()
            if oldmesh in meshes['mapping'] and meshes['mapping'][oldmesh]!=oldmesh:
                replacement=unreal.load_asset(meshes['mapping'][oldmesh]);assert replacement
                c.set_static_mesh(replacement);swaps.append(dict(id=identifier,original=oldmesh,asset=replacement.get_path_name()))
            delta=offsets.get(identifier)
            if not delta:continue
            rows=[]
            for slot in range(c.get_num_materials()):
                original_material=c.get_material(slot);assert original_material,identifier
                replacement=make_offset_material(original_material,delta)
                c.set_material(slot,replacement)
                value=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(replacement,unreal.Name(PARAMETER))
                assert max(abs(v-t) for v,t in zip((value.r,value.g,value.b),delta))<1e-5
                rows.append(dict(slot=slot,original=original_material.get_path_name(),asset=replacement.get_path_name()))
            if hasattr(c,'set_evaluate_world_position_offset'):c.set_evaluate_world_position_offset(True)
            elif not c.get_editor_property('evaluate_world_position_offset'):c.set_editor_property('evaluate_world_position_offset',True)
            c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==component_name)
            # The generated master declares its maximum WPO displacement;
            # renderer bounds expand from that without changing design bounds.
            if c.get_editor_property('world_position_offset_disable_distance')!=0:
                c.set_editor_property('world_position_offset_disable_distance',0)
            c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==component_name)
            if not c.get_editor_property('evaluate_world_position_offset_in_ray_tracing'):
                c.set_editor_property('evaluate_world_position_offset_in_ray_tracing',True)
            materials.append(dict(id=identifier,offset_cm=delta,materials=rows))
            if len(materials)%200==0:unreal.log('SURFACE_MATERIAL_PROGRESS %d/%d'%(len(materials),len(offsets)))
    if not set(offsets)<=visual_ids:
        write('MissingSurfaceDebug.json',dict(missing=sorted(set(offsets)-visual_ids),
            window_actor_states={a.get_actor_label():actor_state(a) for a in actors if a.get_actor_label().startswith('OTS_HotelV4_Window_')},
            visual_ids=sorted(visual_ids)))
    assert set(offsets)<=visual_ids,'Unknown/hidden surface IDs in plan: '+str(sorted(set(offsets)-visual_ids)[:30])
    # Place raised numerals close to their plaque instead of floating 8.75mm away.
    number_adjustments=[]
    for r in plan['placed_props']:
        if not (r['id'].startswith('Room') and r['id'].endswith('_Number')):continue
        a=by[r['actor']];pos=xyz(a.get_actor_location());pos[0]+=.775
        assert a.set_actor_location(unreal.Vector(*pos),False,True)
        r['position_cm']=pos
        number_adjustments.append(dict(actor=r['actor'],delta_cm=[.775,0,0],plate_gap_cm=.1))
        for raw in plan['props']:
            if raw['id']==r['id']:raw['position_cm']=pos
    for r in plan['placed_boxes']:
        c=by[r['actor']].get_component_by_class(unreal.StaticMeshComponent)
        r['material_asset']=c.get_material(0).get_path_name()
    for r in plan['placed_props']:
        c=by[r['actor']].get_component_by_class(unreal.StaticMeshComponent)
        r.update(asset=c.static_mesh.get_path_name(),world_bounds_cm=actor_bounds(by[r['actor']]))
        for key in ('world_min','world_max','bounds'):
            if key=='world_min':r[key]=r['world_bounds_cm'][0]
            elif key=='world_max':r[key]=r['world_bounds_cm'][1]
            elif key in r:r[key]=r['world_bounds_cm']
    for r in plan['placed_doors']+plan['placed_windows']:
        components={c.get_name():c for c in by[r['actor']].get_components_by_class(unreal.StaticMeshComponent)}
        for spec in r['components']:
            if spec['name'] in components:
                c=components[spec['name']];spec['asset']=c.static_mesh.get_path_name()
    # Close views complement the existing whole-building review cameras.
    cameras=[dict(camera='CAM_Surface_WindowInside',position=[9820.,-2660.,548.25],look_at=[10030.,-2660.,548.25],fov=72.,lighting_mode='temporary'),
        dict(camera='CAM_Surface_WindowOutside',position=[10275.,-2660.,548.25],look_at=[10030.,-2660.,548.25],fov=72.,lighting_mode='temporary'),
        dict(camera='CAM_Surface_RoomNumber',position=[9110.,-2612.,540.25],look_at=[9237.,-2612.,540.25],fov=68.,lighting_mode='temporary')]
    added=[]
    for r in cameras:
        assert r['camera'] not in by
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*r['position']),unreal.Vector(*r['look_at']))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*r['position']),rot,False);assert a
        a.set_actor_label(r['camera']);a.set_folder_path(unreal.Name('OldTownSchoolStreet/SurfaceReview'))
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',r['fov'])
        added.append(r['camera'])
    plan['review_cameras']+=cameras;plan['new_actor_labels']+=added
    for name in ('CAM_Openings_Window','CAM_OTS_MainHome','CAM_OTS_StreetDiagonal'):
        a=by[name];position=xyz(a.get_actor_location());forward=xyz(unreal.MathLibrary.get_forward_vector(a.get_actor_rotation()))
        plan['review_cameras'].append(dict(camera=name,position=position,look_at=[position[i]+forward[i]*500 for i in range(3)],
            fov=float(a.get_component_by_class(unreal.CameraComponent).get_editor_property('field_of_view')),lighting_mode='temporary'))
    actors=list(sub.get_all_level_actors());refresh(actors);current={a.get_actor_label():actor_state(a) for a in actors}
    assert len(actors)==original['actor_count']+len(added)
    changed=[n for n,s in original['actors'].items() if current[n]!=s]
    # Only visual mesh/materials, the specified non-colliding glass and number position may change.
    for n in changed:
        old=deepcopy(original['actors'][n]);new=deepcopy(current[n])
        if n in {x['actor'] for x in number_adjustments}:
            old['location']=new['location'];old['components'][0]['location']=new['components'][0]['location']
        for oc,nc in zip(old['components'],new['components']):
            assert oc['name']==nc['name']
            if 'mesh' in oc:
                oc['mesh']=nc['mesh'];oc['materials']=nc['materials']
                if n.startswith('OTS_HotelV4_Window_') and (oc['name'].endswith('Sash') or oc['name'].endswith('MeetingRail')):
                    assert 'NO_COLLISION' in oc['collision'];oc['location']=nc['location'];oc['scale']=nc['scale']
        assert old==new,'Unapproved nonvisual change: '+n
    created=set(plan['new_actor_labels'])
    baseline=dict(source_map_sha256=oldhash,preserved_actors={n:s for n,s in original['actors'].items() if n not in created},
        removed_actor_labels=[],shared_asset_sha256=original['shared_asset_sha256'],protected_map_sha256=original['protected_map_sha256'],main_home=original['main_home'],
        allowed_surface_overrides={n:current[n] for n in changed if n not in created})
    write('PreservationBaseline.json',baseline)
    plan['expected_actor_states']={n:current[n] for n in created}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,plan,baseline,actors);write('PreSaveAudit.json',result);assert result['passed'],result['errors'][:20]
    assert validate_main_home(actors)==original['main_home']
    matreport=get_report();write('MaterialRepair.json',matreport);assert matreport['passed']
    new_assets=dict(build['new_asset_sha256'],**asset_hashes())
    for r in meshes['reports']:
        if r.get('changed'):new_assets[r['file']]=r['sha256']
    for wr in window_reports:
        for r in wr['new_assets']:
            p=ROOT/('Content/'+r['asset'].split('.')[0][6:]+'.uasset');new_assets[str(p)]=sha(p)
    repair=dict(passed=True,source_map_sha256=oldhash,changed_actor_count=len(changed),changed_actor_labels=changed,
        shifted_components=len(materials),maximum_world_translation_cm=max(math.sqrt(sum(v*v for v in r['offset_cm'])) for r in materials),
        material_overrides=materials,mesh_swaps=swaps,mesh_preparation=str(WORK/'MeshPreparation.json'),window_repairs=window_reports,
        number_adjustments=number_adjustments,created_cameras=added,user_added_actors_preserved=['BP_ItemPickup','PointLight'])
    write('RepairReport.json',repair)
    assert sha(mapfile)==oldhash;assert levels.save_current_level()
    digest=sha(mapfile)
    build.update(status='PASS',source_map_sha256=oldhash,map_sha256=digest,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,
        protected_map_sha256=original['protected_map_sha256'],new_asset_sha256=new_assets,surface_repair=repair,
        hotel_openings_review_cameras=[r['camera'] for r in plan['review_cameras']])
    write('ArchitecturePlan.json',plan);write('BuildReport.json',build)
    write('Applied.json',dict(passed=True,map_sha256=digest,actor_count=len(actors)))
    write('InputRebaseReport.json',dict(passed=True,current_input_map_sha256=oldhash,historical_map_sha256=original.get('historical_map_sha256','382c208f1b5b239f6e0d4f052cc212a9d52d4b00672ce50d6ad59e52cb879bb1'),
        user_added_actors_preserved=['BP_ItemPickup','PointLight'],no_original_actors_removed=True))
    unreal.log('SURFACE_REPAIR_APPLY_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(traceback=traceback.format_exc()));raise
