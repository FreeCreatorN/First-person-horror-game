import sys,importlib
from pathlib import Path
import unreal
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).get_current_level().get_outermost().get_path_name()=='/Game/Yastar/Maps/L_GreenPortal'
r=Path(unreal.Paths.project_dir());sys.path.insert(0,str(r/'Scripts'))
import ExtractionMaterials;importlib.reload(ExtractionMaterials)
E=unreal.MaterialEditingLibrary
m=unreal.load_asset('/Game/Yastar/Materials/M_GreenPortal_Beam')
nodes=[o for o in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if o.get_path_name().startswith(m.get_path_name()+':')]
fresnel=next((o for o in unreal.ObjectIterator(unreal.MaterialExpressionFresnel) if o.get_path_name().startswith(m.get_path_name()+':')),None)
if fresnel is None:fresnel=E.create_material_expression(m,unreal.MaterialExpressionFresnel,-1000,0)
for n in nodes:
    inputs=list(n.get_editor_property('inputs'))
    if not any(str(i.get_editor_property('input_name'))=='Facing' for i in inputs):
        ci=unreal.CustomInput();ci.set_editor_property('input_name','Facing');inputs.append(ci);n.set_editor_property('inputs',inputs)
    E.connect_material_expressions(fresnel,'',n,'Facing');n.set_editor_property('code',ExtractionMaterials.BODY_CODE)
E.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m)
for name,values in [('Body',{'BodyOpacity':0.055,'BodyEmission':3.0}),('Ring',{'RingEmission':2.4}),('Filaments',{'FilamentIntensity':3.0}),('Particle',{'ParticleIntensity':4.0})]:
    mi=unreal.load_asset('/Game/Yastar/Materials/MI_GreenExtraction_'+name)
    for k,v in values.items():E.set_material_instance_scalar_parameter_value(mi,k,v)
    E.update_material_instance(mi);unreal.EditorAssetLibrary.save_loaded_asset(mi)
ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
old=next((a for a in ae.get_all_level_actors() if a.get_actor_label()=='Extraction neutral fill'),None)
if not old:old=ae.spawn_actor_from_class(unreal.PointLight,unreal.Vector(170,-150,180));old.set_actor_label('Extraction neutral fill')
c=old.get_component_by_class(unreal.PointLightComponent)
c.set_editor_property('intensity_units',unreal.LightUnits.LUMENS);c.set_editor_property('intensity',240.0);c.set_editor_property('attenuation_radius',330.0);c.set_editor_property('cast_shadows',False)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
