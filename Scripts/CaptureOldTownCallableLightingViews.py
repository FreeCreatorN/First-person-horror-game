"""Unsaved original-town on/off comparison using owned temporary cameras."""
import sys,os,json,time,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(R/'Scripts'))
import CaptureOldTownSoftGoodsViews as capture

OWN_CAMERAS=[]
CIRCUITS=[]
CAPTURE_STATES={}
INITIAL_STATES={}
LAST_INDEX=-1
SETUP_TIME=0.
SPECS={
 'CALL_Hotel_On':dict(location=[9130.,-1910.,580.],target=[9130.,-1700.,712.5],fov=62.,circuit='OTS_LightCircuit_HotelV4_F1_GalleryTube01',level=1.),
 'CALL_Hotel_Off':dict(location=[9130.,-1910.,580.],target=[9130.,-1700.,712.5],fov=62.,circuit='OTS_LightCircuit_HotelV4_F1_GalleryTube01',level=0.),
 'CALL_Street_On':dict(location=[1780.,-65.,285.],target=[1625.,-275.,400.],fov=52.,circuit='OTS_LightCircuit_P2Prop_StreetLamp_01',level=1.),
 'CALL_Street_Off':dict(location=[1780.,-65.,285.],target=[1625.,-275.,400.],fov=52.,circuit='OTS_LightCircuit_P2Prop_StreetLamp_01',level=0.),
}

old_tick=capture.on_tick
old_commit=capture._commit_cleanup

def on_tick(delta):
    global LAST_INDEX,SETUP_TIME
    try:
        s=capture._state
        if s['closing']:return
        if s['task'] is None and s['index']<len(s['cameras']):
            if LAST_INDEX!=s['index']:
                label=s['cameras'][s['index']].get_actor_label()
                spec=SPECS[label]
                unreal.OldTownLightCircuitEditorLibrary.restore_all_editor_previews()
                circuit=next(c for c in CIRCUITS if c.get_actor_label()==spec['circuit'])
                circuit.set_light_level(spec['level'])
                observed=json.loads(unreal.OldTownLightCircuitEditorLibrary.inspect_circuit(circuit))
                assert not observed['configuration_error'] and observed['mid']
                assert observed['level']==spec['level'] and observed['light_strength']==20.*spec['level']
                CAPTURE_STATES[label]=observed
                level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
                level.pilot_level_actor(s['cameras'][s['index']])
                assert level.get_pilot_level_actor()==s['cameras'][s['index']]
                LAST_INDEX=s['index'];SETUP_TIME=time.monotonic()
            if time.monotonic()-SETUP_TIME<2.:return
        old_tick(delta)
    except Exception:
        capture.fail(traceback.format_exc())

def physical_state(c):
    mesh=c.get_editor_property('target_lamp_mesh').static_mesh_component
    lights=[]
    for a in c.get_editor_property('controlled_lights'):
        lc=a.get_component_by_class(unreal.LightComponent)
        lights.append(dict(actor=a.get_path_name(),intensity=lc.get_editor_property('intensity'),visible=lc.get_editor_property('visible'),hidden_in_game=lc.get_editor_property('hidden_in_game')))
    return dict(material=mesh.get_material(2).get_path_name(),lights=lights)

def commit(success,message):
    unreal.OldTownLightCircuitEditorLibrary.restore_all_editor_previews()
    assert {c.get_actor_label():physical_state(c) for c in CIRCUITS}==INITIAL_STATES
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).eject_pilot_level_actor()
    old_commit(success,message)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels=[c.get_actor_label() for c in OWN_CAMERAS]
    for c in OWN_CAMERAS:
        assert actors.destroy_actor(c)
    remaining=[a.get_actor_label() for a in actors.get_all_level_actors() if a.get_actor_label() in labels]
    assert not remaining
    proof=dict(passed=True,temporary_camera_count=len(labels),temporary_camera_remaining=remaining,
        editor_preview_restored=True,circuit_state_at_capture=CAPTURE_STATES,map_save_requested=False)
    capture._write(capture._state['run_dir']/'LightingCaptureProof.json',proof)
    for path in capture._state['metadata_paths']:
        data=json.loads(path.read_text(encoding='utf8'))
        data['temporary_camera_cleanup_verified_zero']=True
        data['circuit_state_at_capture']=CAPTURE_STATES[data['camera']]
        capture._write(path,data)

def main():
    report=json.loads(capture.BUILD_REPORT.read_text(encoding='utf-8-sig'))
    s=capture._state
    s['run_id']=os.environ['OTS_CAPTURE_RUN_ID']
    s['run_dir']=capture.OUTPUT/'Runs'/s['run_id'];s['run_dir'].mkdir(parents=True,exist_ok=True)
    capture._commit_cleanup=commit
    capture.RENDERS.mkdir(parents=True,exist_ok=True)
    s['lighting_mode']='street_only';s['view_mode']='lit'
    s['source_build_report']=dict(file=str(capture.BUILD_REPORT.resolve()),sha256=capture._hash_file(capture.BUILD_REPORT))
    s['new_asset_sha256']=report['new_asset_sha256']
    assert all(capture._hash_file(Path(p))==h for p,h in s['new_asset_sha256'].items())
    s['map_sha256']=capture._hash_file(capture.MAP_FILE)
    assert s['map_sha256']==report['map_sha256']
    assert report['target_level']==capture.TARGET_LEVEL=='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(capture.TARGET_LEVEL)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    CIRCUITS.extend(a for a in actors.get_all_level_actors() if isinstance(a,unreal.OldTownLightCircuitActor))
    assert len(CIRCUITS)==16
    assert len({c.get_actor_label() for c in CIRCUITS})==16
    INITIAL_STATES.update({c.get_actor_label():physical_state(c) for c in CIRCUITS})
    assert list(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).get_viewport_config_keys())
    requested=os.environ['OTS_CAPTURE_CAMERAS'].split(',')
    for name in requested:
        spec=SPECS[name];pos=unreal.Vector(*spec['location'])
        rot=unreal.MathLibrary.find_look_at_rotation(pos,unreal.Vector(*spec['target']))
        camera=actors.spawn_actor_from_class(unreal.CameraActor,pos,rot,False)
        assert camera
        camera.set_actor_label(name)
        camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',spec['fov'])
        OWN_CAMERAS.append(camera)
    s['cameras']=OWN_CAMERAS
    actors.set_selected_level_actors([])
    capture.WARMUP_FRAMES=120
    capture.BETWEEN_CAMERA_FRAMES=80
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    s['tick_handle']=unreal.register_slate_post_tick_callback(on_tick)
    unreal.log('CALLABLE_LIGHT_CAPTURE_READY')

if __name__=='__main__':
    try:main()
    except Exception:
        capture.fail(traceback.format_exc())
        raise
