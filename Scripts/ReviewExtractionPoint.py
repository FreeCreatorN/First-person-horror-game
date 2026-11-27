"""Fresh-editor visual and simulation verification for the extraction point."""
import json,sys,time,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir());sys.path.insert(0,str(ROOT/'Scripts'))
OUT=ROOT/'Saved/ExtractionFinalReview.json';data={'samples':[]}
def save():OUT.write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')
try:
    import TuneExtractionVisibility
    import ExtractionColorControls
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    fx=by['Green extraction point'];camera=by['Portal preview camera']
    cls=fx.get_class()
    data['blueprint_class']=cls.get_path_name()
    data['components']=[{'name':c.get_name(),'class':c.get_class().get_name(),'location':str(c.get_editor_property('relative_location')),'scale':str(c.get_editor_property('relative_scale3d')),'materials':[m.get_path_name() if m else None for m in c.get_materials()] if isinstance(c,unreal.StaticMeshComponent) else []} for c in fx.get_components_by_class(unreal.SceneComponent)]
    person=by['Preview - 180cm reference'];origin,extent=person.get_actor_bounds(False)
    head=person.get_component_by_class(unreal.SkeletalMeshComponent).get_socket_location('head')
    E=unreal.MaterialEditingLibrary
    data['parameters']={}
    for name,params in [('Body',['Height','BodyOpacity','BodyEmission','FlowSpeed','TopRipple']),('Ring',['RingEmission']),('Filaments',['FilamentIntensity']),('Particle',['ParticleIntensity'])]:
        mi=unreal.load_asset('/Game/Yastar/Materials/MI_GreenExtraction_'+name)
        data['parameters'][name]={p:E.get_material_instance_scalar_parameter_value(mi,p) for p in params}
    data['person_height_cm']=extent.z*2;data['head_bone_z_cm']=head.z
    data['body_maximum_height_cm']=data['parameters']['Body']['Height']
    assert data['body_maximum_height_cm']<head.z
    data['fixed_radius_cm']=75;data['xyz_world_position_offset']=False
    state={'start':time.monotonic(),'next':time.monotonic()+35,'task':None,'stage':0}
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    def finish():
        le.editor_request_end_play();unreal.unregister_slate_post_tick_callback(state['handle']);unreal.EditorPythonScripting.set_keep_python_script_alive(False);save()
    def tick(_):
        try:
            now=time.monotonic()
            if state['task'] is not None:
                if not state['task'].is_task_done():return
                state['task']=None;state['stage']+=1;state['next']=now+5
                if state['stage']==1:le.editor_play_simulate()
                elif state['stage']==3:data['success']=True;finish();return
            if now<state['next']:return
            if state['stage']==0:
                state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1440,810,str(ROOT/'Saved/Extraction_Final_Editor.png'),camera,False,False)
            elif state['stage'] in (1,2):
                gw=unreal.EditorLevelLibrary.get_game_world();assert gw
                fxs=unreal.GameplayStatics.get_all_actors_of_class(gw,cls);assert len(fxs)==1
                active=[c.is_active() for c in fxs[0].get_components_by_class(unreal.NiagaraComponent)];assert active and all(active)
                data['samples'].append({'simulation_seconds':unreal.GameplayStatics.get_time_seconds(gw),'niagara_active':active,'actor_scale':str(fxs[0].get_actor_scale3d()),'green_light_intensity':fxs[0].get_component_by_class(unreal.PointLightComponent).get_editor_property('intensity')})
                cam=unreal.GameplayStatics.get_all_actors_of_class(gw,unreal.CameraActor)[0]
                state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1440,810,str(ROOT/('Saved/Extraction_Final_Runtime%s.png'%('A' if state['stage']==1 else 'B'))),cam,False,False)
            if now-state['start']>240:raise RuntimeError('Review timeout')
        except Exception:data['error']=traceback.format_exc();data['success']=False;unreal.log_error(data['error']);finish()
    state['handle']=unreal.register_slate_post_tick_callback(tick)
except Exception:
    data['error']=traceback.format_exc();data['success']=False;save();unreal.log_error(data['error']);raise
