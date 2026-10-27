"""Reproduce UE T3D export marks and prove complete unchanged brush geometry."""
import sys,traceback,hashlib
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import ApplyOldTownFunctionalLighting as task
W=task.W
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
before=task.native.sha(task.MAP);created=[]
def exp(obj,name,model=False):
    p=W/'ExportMarkProbe'/name
    if not model:return task.native.native_text_export(obj,p)[0]
    t=unreal.AssetExportTask()
    for k,v in dict(object=obj,exporter=unreal.ModelExporterT3D(),filename=str(p),automated=True,prompt=False,replace_identical=True).items():t.set_editor_property(k,v)
    assert unreal.Exporter.run_asset_export_task(t)
    raw=p.read_bytes();return raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
try:
    assert le.load_level(task.TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==7952
    pp=by['PostProcessVolume']
    # ABrush.Brush is protected in Python; resolve the existing subobject named
    # in the native Actor export rather than trying to alter its access flags.
    model=unreal.load_object(None,pp.get_path_name()+'.Model_1');assert model
    task.reset_export_marks()
    initial=exp(pp,'Initial.t3d');repeated=exp(pp,'RepeatedWithoutReset.t3d')
    direct_before=exp(model,'ModelBefore.t3d',True)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rows=task.recipes(by)
    for row in (rows[0],rows[-1]):created.append(task.bind_light(row,by,ae,world))
    direct_after=exp(model,'ModelAfterLightCreation.t3d',True)
    task.reset_export_marks();restored=exp(pp,'AfterReset.t3d')
    task.reset_export_marks();restored_again=exp(pp,'AfterSecondReset.t3d')
    assert initial.count('Begin Polygon')==6 and repeated.count('Begin Polygon')==0
    assert direct_before==direct_after and direct_before.count('Begin Polygon')==6
    assert initial==restored==restored_again
    assert all(ae.destroy_actor(a) for a in created);created=[]
    assert len(ae.get_all_level_actors())==7952 and task.native.sha(task.MAP)==before
    task.write('ExportMarkProbe.json',dict(passed=True,no_map_save=True,map_sha256=before,
        missing_brush_reproduced_on_repeat=True,full_brush_restored_after_native_mark_reset=True,
        direct_model_and_all_six_polygons_unchanged_after_light_creation=True,
        actor_text_sha256=hashlib.sha256(initial.encode()).hexdigest(),model_text_sha256=hashlib.sha256(direct_before.encode()).hexdigest(),
        method='OBJ COMPONENTS Default__Object resets native exporter TagImp/TagExp only; full Actor text and independent ModelExporterT3D geometry compared without omission or normalization.'))
    unreal.log('FUNCTIONAL_LIGHT_EXPORT_MARK_PROBE_PASS')
except Exception:
    task.write('ExportMarkProbe.json',dict(passed=False,no_map_save=True,map_sha256=task.native.sha(task.MAP),traceback=traceback.format_exc()));raise
finally:
    for actor in created:ae.destroy_actor(actor)
