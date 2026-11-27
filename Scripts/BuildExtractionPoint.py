"""Assemble the existing extraction scene and verify its constant runtime state."""
import json,math,sys,time,traceback,shutil
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir());sys.path.insert(0,str(ROOT/'Scripts'))
REPORT=ROOT/'Saved/ExtractionBuildReport.json'
STATE={}
def write():REPORT.write_text(json.dumps(STATE,indent=2,default=str),encoding='utf-8')
def prop(obj,name,value):obj.set_editor_property(name,value)
def simple_material(name,color,roughness):
    p='/Game/Yastar/Materials/'+name
    m=unreal.load_asset(p) if unreal.EditorAssetLibrary.does_asset_exist(p) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,'/Game/Yastar/Materials',unreal.Material,unreal.MaterialFactoryNew())
    E=unreal.MaterialEditingLibrary;E.delete_all_material_expressions(m)
    c=E.create_material_expression(m,unreal.MaterialExpressionConstant3Vector);c.set_editor_property('constant',unreal.LinearColor(*color,1))
    E.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
    r=E.create_material_expression(m,unreal.MaterialExpressionConstant);r.set_editor_property('r',roughness);E.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
    E.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m);return m

def build_blueprint(mats,ns,H):
    path='/Game/Yastar/Blueprints/BP_GreenExtractionPoint'
    if unreal.EditorAssetLibrary.does_asset_exist(path):bp=unreal.load_asset(path)
    else:bp=unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(path,unreal.Actor)
    sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);lib=unreal.SubobjectDataBlueprintFunctionLibrary
    handles=sub.k2_gather_subobject_data_for_blueprint(bp)
    actorh=next(h for h in handles if lib.is_actor(lib.get_data(h)))
    templates={}
    for h in handles:
        d=lib.get_data(h)
        if lib.is_scene_component(d):templates[str(lib.get_variable_name(d))]=(h,lib.get_object_for_blueprint(d,bp))
    def add(name,cls,parent=None):
        if name in templates:return templates[name][1]
        h,reason=sub.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=templates[parent][0] if parent else actorh,new_class=cls,blueprint_context=bp,conform_transform_to_parent=False))
        assert lib.is_handle_valid(h),(name,str(reason));assert sub.rename_subobject(h,name)
        if parent:sub.attach_subobject(templates[parent][0],h)
        else:sub.make_new_scene_root(actorh,h,bp)
        obj=lib.get_object_for_blueprint(lib.get_data(h),bp);templates[name]=(h,obj);return obj
    add('ExtractionRoot',unreal.SceneComponent)
    for name,mesh,mat,loc,scale in [('EnergyBoundary','/Engine/BasicShapes/Cylinder',mats['body'],(0,0,H/2),(1.5,1.5,H/100)),('GroundRings','/Engine/BasicShapes/Plane',mats['ring'],(0,0,1),(1.95,1.95,1)),('EnergyThreads','/Engine/BasicShapes/Cylinder',mats['filaments'],(0,0,H/2),(1.497,1.497,H/100))]:
        c=add(name,unreal.StaticMeshComponent,'ExtractionRoot');c.set_static_mesh(unreal.load_asset(mesh));c.set_material(0,mat)
        prop(c,'relative_location',unreal.Vector(*loc));prop(c,'relative_scale3d',unreal.Vector(*scale));c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);prop(c,'cast_shadow',False)
    particles=add('AnomalyParticles',unreal.NiagaraComponent,'ExtractionRoot');particles.set_asset(ns)
    prop(particles,'auto_activate',True);prop(particles,'relative_location',unreal.Vector(0,0,0))
    light=add('LocalizedGreenLight',unreal.PointLightComponent,'ExtractionRoot')
    prop(light,'relative_location',unreal.Vector(0,0,45));prop(light,'intensity_units',unreal.LightUnits.LUMENS);prop(light,'intensity',22.0);prop(light,'attenuation_radius',225.0);prop(light,'light_color',unreal.Color(35,255,95,255));prop(light,'cast_shadows',False)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return path,unreal.EditorAssetLibrary.load_blueprint_class(path)

def main():
    import importlib,ExtractionMaterials,ExtractionNiagara
    importlib.reload(ExtractionMaterials);importlib.reload(ExtractionNiagara)
    from ExtractionMaterials import build_materials
    from ExtractionNiagara import build_particle_system
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.get_current_level().get_outermost().get_path_name()=='/Game/Yastar/Maps/L_GreenPortal'
    if not (ROOT/'Saved/ExtractionBeforeRebuild.umap').exists():
        shutil.copy2(ROOT/'Content/Yastar/Maps/L_GreenPortal.umap',ROOT/'Saved/ExtractionBeforeRebuild.umap')
    existing=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in existing}
    # A scaled existing mannequin is a visible 1.8m reference because this scene has no person.
    person=by.get('Preview - 180cm reference') or ae.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(180,15,0))
    person.set_actor_label('Preview - 180cm reference');sc=person.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh=unreal.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple');assert mesh
    sc.set_skeletal_mesh_asset(mesh)
    person.set_actor_scale3d(unreal.Vector(1,1,1));origin,extent=person.get_actor_bounds(False)
    measured=extent.z*2;assert measured>100,(origin,extent)
    factor=180.0/measured;person.set_actor_scale3d(unreal.Vector(factor,factor,factor))
    origin,extent=person.get_actor_bounds(False);loc=person.get_actor_location();person.set_actor_location(unreal.Vector(180,15,loc.z-(origin.z-extent.z)),False,False)
    origin,extent=person.get_actor_bounds(False)
    head=sc.get_socket_location('head')
    # Stay below the head centre, a conservative bound below the eye line.
    H=min(155.0,head.z-8.0) if head.z>140 else 153.0
    STATE['scale_reference']={'model':mesh.get_path_name(),'original_bounds_cm':measured,'scaled_height_cm':extent.z*2,'head_bone_z_cm':head.z,'maximum_vfx_height_cm':H,'fallback_reference':'180cm figure; below head centre'}
    mats=build_materials(height=H);diag={};ns=build_particle_system(mats['particle'],diag);STATE['niagara']=diag;write();assert diag.get('success'),diag
    bp_path,cls=build_blueprint(mats,ns,H)
    # Remove only actors made for earlier portal iterations in this isolated map.
    labels={'Portal - rising light','Portal - ground ring','Portal - green light','Green extraction point'}
    removed=[]
    for a in existing:
        label=a.get_actor_label()
        if label in labels or label.startswith('Portal - decorative particle ') or label.startswith('Portal - surface point '):removed.append(label);ae.destroy_actor(a)
    fx=ae.spawn_actor_from_class(cls,unreal.Vector(0,0,0));fx.set_actor_label('Green extraction point')
    for nc in fx.get_components_by_class(unreal.NiagaraComponent):nc.reinitialize_system()
    floor=by.get('Preview floor');assert floor
    floor.static_mesh_component.set_material(0,simple_material('M_GreenExtraction_PreviewFloor',(0.028,0.032,0.037),0.48))
    for a in list(ae.get_all_level_actors()):
        if a.get_actor_label() in ('Extraction neutral key','Extraction exposure'):ae.destroy_actor(a)
    key=ae.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,350),unreal.Rotator(pitch=-48,yaw=-35,roll=0));key.set_actor_label('Extraction neutral key')
    prop(key.get_component_by_class(unreal.DirectionalLightComponent),'intensity',1.4)
    pp=ae.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector());pp.set_actor_label('Extraction exposure');prop(pp,'unbound',True)
    settings=pp.get_editor_property('settings')
    for n,v in [('override_auto_exposure_method',True),('auto_exposure_method',unreal.AutoExposureMethod.AEM_MANUAL),('override_auto_exposure_bias',True),('auto_exposure_bias',0.0),('override_auto_exposure_apply_physical_camera_exposure',True),('auto_exposure_apply_physical_camera_exposure',False),('override_bloom_intensity',True),('bloom_intensity',0.35)]:prop(settings,n,v)
    prop(pp,'settings',settings)
    camera=by.get('Portal preview camera');assert camera
    camera.set_actor_location(unreal.Vector(410,-620,275),False,False);camera.set_actor_rotation(unreal.Rotator(pitch=-13.5,yaw=123,roll=0),False)
    cc=camera.get_component_by_class(unreal.CameraComponent);prop(cc,'field_of_view',43.0)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
    # Default game mode is isolated to this preview map.
    ws=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_world_settings()
    try:prop(ws,'default_game_mode',unreal.GameModeBase)
    except Exception:pass
    assert le.save_current_level()
    STATE.update(success=True,blueprint=bp_path,removed_previous_actor_count=len(removed),material_paths={k:v.get_path_name() for k,v in mats.items() if k in ('body','ring','filaments','particle')},constant_radius_cm=75.0,top_cap=False)
    write()
    state={'start':time.monotonic(),'next':time.monotonic()+45,'stage':0,'task':None,'camera':camera}
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    def finish():
        try:le.editor_request_end_play()
        except Exception:pass
        unreal.unregister_slate_post_tick_callback(state['handle']);unreal.EditorPythonScripting.set_keep_python_script_alive(False);write()
    def tick(_):
        try:
            now=time.monotonic()
            if state['task'] is not None:
                if not state['task'].is_task_done():return
                state['task']=None;state['stage']+=1;state['next']=now+5
                if state['stage']==1:le.editor_play_simulate()
                elif state['stage']==3:finish();return
            if now<state['next']:return
            if state['stage']==0:
                state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(ROOT/'Saved/Extraction_Editor.png'),camera,False,False)
            elif state['stage'] in (1,2):
                gw=unreal.EditorLevelLibrary.get_game_world()
                assert gw,'No simulation world'
                items=unreal.GameplayStatics.get_all_actors_of_class(gw,cls)
                assert len(items)==1,(len(items),'runtime extraction actors')
                comps=items[0].get_components_by_class(unreal.NiagaraComponent)
                active=[bool(c.is_active()) for c in comps]
                STATE.setdefault('runtime_samples',[]).append({'seconds':round(now-state['start'],2),'niagara_active':active,'actor_scale':str(items[0].get_actor_scale3d()),'component_count':len(items[0].get_components_by_class(unreal.SceneComponent))})
                assert active and all(active),'Niagara inactive'
                cams=unreal.GameplayStatics.get_all_actors_of_class(gw,unreal.CameraActor)
                livecam=cams[0] if cams else camera
                state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(ROOT/('Saved/Extraction_Runtime%s.png'%('A' if state['stage']==1 else 'B'))),livecam,False,False)
            if now-state['start']>240:raise RuntimeError('Runtime verification timeout')
        except Exception:
            STATE['runtime_error']=traceback.format_exc();unreal.log_error(STATE['runtime_error']);finish()
    state['handle']=unreal.register_slate_post_tick_callback(tick)

try:main()
except Exception:
    STATE['success']=False;STATE['error']=traceback.format_exc();write();unreal.log_error(STATE['error']);raise
