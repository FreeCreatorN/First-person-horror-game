"""Stage-owned capture helpers; temporary review poses, never map saves."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'Scripts'
W=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=S/'CaptureOldTownHotelViews.py';text=source.read_text(encoding='utf-8-sig')
def replace_once(a,b):
    global text
    assert text.count(a)==1,a
    text=text.replace(a,b)
replace_once('WIDTH, HEIGHT = 1280, 720','WIDTH, HEIGHT = 1920, 1080')
replace_once('    _state["cameras"] = [by_label[label] for label in labels]',
'''    _state["review_original_cameras"] = []
    for label, settings in report.get("review_camera_overrides", {}).items():
        if label not in by_label:
            continue
        camera = by_label[label]
        cc = camera.get_component_by_class(unreal.CameraComponent)
        _state["review_original_cameras"].append((camera, camera.get_actor_transform(), cc.get_editor_property("field_of_view")))
        location = unreal.Vector(*settings["location_cm"])
        rotation = unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(*settings["target_cm"]))
        camera.set_actor_location(location, False, True)
        camera.set_actor_rotation(rotation, True)
        cc.set_editor_property("field_of_view", settings["fov_degrees"])
    _state["cameras"] = [by_label[label] for label in labels]''')
replace_once('    lighting = _destroy_owned_temporary_lights()',
'''    for camera, transform, fov in _state.get("review_original_cameras", []):
        camera.set_actor_transform(transform, False, True)
        camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", fov)
        assert camera.get_actor_transform().translation == transform.translation
    _state["review_cameras_restored"] = True
    lighting = _destroy_owned_temporary_lights()''')
replace_once('                "camera_rotation_degrees": [rotation.pitch, rotation.yaw, rotation.roll],',
'''                "camera_rotation_degrees": [rotation.pitch, rotation.yaw, rotation.roll],
                "camera_fov_degrees": camera.get_component_by_class(unreal.CameraComponent).get_editor_property("field_of_view"),
                "camera_pose_scope": "temporary inspection override; original restored at cleanup; saved map unchanged",''')
target=S/'CaptureOldTownRealismRefinementViews.py';target.write_text(text,encoding='utf-8')
pssource=S/'CaptureOldTownHotelViews.ps1';pstext=pssource.read_text(encoding='utf-8-sig')
assert pstext.count("Scripts\\CaptureOldTownHotelViews.py")==1
pstext=pstext.replace("Scripts\\CaptureOldTownHotelViews.py","Scripts\\CaptureOldTownRealismRefinementViews.py")
pstext=pstext.replace("$hotelProject = 'D:\\UE\\Project\\HorrorGame'",'''$hotelProject = 'D:\\UE\\Project\\HorrorGame'
$refinementLiveEditors=@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue | Where-Object { -not $_.HasExited })
if ($refinementLiveEditors.Count -ne 0) { throw 'An actual editor is running; no capture helper launched.' }''')
pstarget=S/'CaptureOldTownRealismRefinementViews.ps1';pstarget.write_text(pstext,encoding='utf-8-sig')
build=json.loads((W/'BuildReport.json').read_text())
build['hotel_openings_review_cameras']+=['CAM_V4_TopGallery','CAM_StreetAccess_NightStreet']
assert len(set(build['hotel_openings_review_cameras']))==14
build['review_camera_overrides']={
 'CAM_StreetAccess_Lamp':dict(location_cm=[1700.,160.,300.],target_cm=[1575.,272.68,375.14],fov_degrees=55.),
 'CAM_V4_TopGallery':dict(location_cm=[9130.,-1860.,1260.],target_cm=[9130.,-1700.,1467.],fov_degrees=55.)}
(W/'BuildReport.json').write_text(json.dumps(build,ensure_ascii=False,indent=2),encoding='utf-8')
(W/'CaptureSetup.json').write_text(json.dumps(dict(passed=True,
 original_capture_script=dict(file=str(source),sha256=sha(source)),original_capture_wrapper=dict(file=str(pssource),sha256=sha(pssource)),
 stage_capture_script=dict(file=str(target),sha256=sha(target)),stage_capture_wrapper=dict(file=str(pstarget),sha256=sha(pstarget)),
 temporary_review_camera_overrides=build['review_camera_overrides'],saved_camera_changes=False,resolution=[1920,1080]),ensure_ascii=False,indent=2),encoding='utf-8')
print('STAGE_CAPTURE_HELPERS_READY')
