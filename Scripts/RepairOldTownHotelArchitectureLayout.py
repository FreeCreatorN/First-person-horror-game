"""Finish visually reviewed counter/service placement and source provenance."""
import json
import shutil
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from ApplyOldTownHotelArchitecture import read,write,import_fixtures,sha,WORK
from AuditOldTownHotelArchitecture import audit
from ValidateEnterableStreet import refresh_world_collision

build=read(WORK/'BuildReport.json')
plan=read(WORK/'ArchitecturePlan.json')
hotel=build['hotel_architecture']
mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
assert sha(mapfile)==build['map_sha256']
assert plan['validation']['passed']
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/Yastar/Maps/L_Main')
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
before=WORK/'BeforeLayoutRepair'
before.mkdir(exist_ok=True)
for p in (mapfile,WORK/'BuildReport.json',WORK/'ArchitectureAudit.json'):
    if not (before/p.name).exists():shutil.copy2(p,before/p.name)
mats={k:unreal.load_asset(v) for k,v in hotel['material_paths'].items()}
# Frosted shower panels transmit light and let the fixtures remain legible.
glass=mats['glass']
glass.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
glass.set_editor_property('two_sided',True)
edit=unreal.MaterialEditingLibrary
opacity=edit.create_material_expression(glass,unreal.MaterialExpressionConstant,-300,280)
opacity.set_editor_property('r',.16)
assert edit.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY)
edit.recompile_material(glass)
assert unreal.EditorAssetLibrary.save_loaded_asset(glass,False)
fixtures,imported=import_fixtures(world,mats)
write('LayoutRepairStage.json',{'stage':'assets_imported'})
assert level.load_level(build['target_level'])
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors=list(sub.get_all_level_actors())
by={a.get_actor_label():a for a in actors}
for row in hotel['placed_doors']:
    spec=next(c for c in row['components'] if c['name']=='DoorHinge')
    hinge=next(c for c in by[row['actor']].get_components_by_class(unreal.SceneComponent) if c.get_name()=='DoorHinge')
    r=spec['relative_rotation']
    hinge.set_editor_property('relative_rotation',unreal.Rotator(pitch=r[0],yaw=r[1],roll=r[2]))
updates=[]
new_boxes={r['id']:r for r in plan['boxes']}
for row in hotel['placed_boxes']:
    source=new_boxes[row['id']]
    if row['world_min']==source['world_min'] and row['world_max']==source['world_max']:continue
    a=by[row['actor']]
    lo,hi=source['world_min'],source['world_max']
    a.set_actor_location(unreal.Vector(*[(lo[i]+hi[i])/2 for i in range(3)]),False,False)
    a.set_actor_scale3d(unreal.Vector(*[(hi[i]-lo[i])/100 for i in range(3)]))
    row.update(source)
    updates.append(a.get_actor_label())
new_props={r['id']:r for r in plan['props']}
for row in hotel['placed_props']:
    source=new_props[row['id']]
    if row['position_cm']==source['position_cm'] and row['yaw']==source['yaw']:continue
    assert not row['colliders'],'Collider update requires explicit handling'
    a=by[row['actor']]
    a.set_actor_location(unreal.Vector(*source['position_cm']),False,False)
    a.set_actor_rotation(unreal.Rotator(pitch=0,yaw=source['yaw'],roll=0),False)
    row.update(source)
    updates.append(a.get_actor_label())
for row in plan['review_cameras']:
    a=by[row['camera']]
    a.set_actor_location(unreal.Vector(*row['position']),False,False)
    a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*row['position']),unreal.Vector(*row['look_at'])),False)
    a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',row['fov'])
by['OTS_HotelArch_ReceptionLetters'].set_actor_location(unreal.Vector(10016,-195,255),False,False)
for key in ('boxes','props','routes','review_cameras','validation'):
    hotel[key]=plan[key]
hotel['imported_assets']=imported
profiles=[(c,str(c.get_collision_profile_name())) for a in actors for c in a.get_components_by_class(unreal.PrimitiveComponent)]
write('LayoutRepairStage.json',{'stage':'refreshing_collision'})
refresh_world_collision(actors)
for c,profile in profiles:
    if profile!='Custom' and str(c.get_collision_profile_name())!=profile:c.set_collision_profile_name(profile)
write('LayoutRepairStage.json',{'stage':'auditing'})
report=audit(world,actors,build)
write('LayoutRepairAudit.json',report)
assert report['passed'],report['errors'][:10]
assert level.save_current_level()
old=build['map_sha256']
build['map_sha256']=sha(mapfile)
write('BuildReport.json',build)
write('LayoutRepair.json',dict(passed=True,source_map_sha256=old,map_sha256=build['map_sha256'],changed_actors=updates,
    changes='Clear reception from lift shaft, fix source provenance, service furniture, camera framing and frosted shower glass.'))
unreal.log('HOTEL_LAYOUT_REPAIR_PASS '+build['map_sha256'])
