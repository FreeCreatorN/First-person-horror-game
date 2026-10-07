"""Asset-only probe, no project map is loaded or saved."""
import unreal,sys,json,traceback,hashlib
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(root/'Scripts'))
from BuildOldTownOpeningBlueprints import create_blueprint
specs=[{'name':'OpeningRoot','parent':None,'class':'SceneComponent','mobility':'STATIC'},
 {'name':'FixedFrame','parent':'OpeningRoot','class':'StaticMeshComponent','asset':'/Engine/BasicShapes/Cube.Cube','collision':'NO_COLLISION','mobility':'STATIC','relative_location':[-200,0,115],'relative_scale':[.04,.04,2.30]},
 {'name':'DoorHinge','parent':'OpeningRoot','class':'SceneComponent','mobility':'MOVABLE','relative_location':[-66,20,0],'relative_rotation':[0,90,0]},
 {'name':'DoorLeaf','parent':'DoorHinge','class':'StaticMeshComponent','asset':'/Engine/BasicShapes/Cube.Cube','collision':'NO_COLLISION','relative_location':[66,0,115],'relative_scale':[1.32,.04,2.30]},
 {'name':'LeafCollision','parent':'DoorHinge','class':'StaticMeshComponent','asset':'/Engine/BasicShapes/Cube.Cube','collision':'QUERY_AND_PHYSICS','hidden':True,'relative_location':[66,0,115],'relative_scale':[1.32,.04,2.30]}]
for row in specs:
 row.setdefault('mobility','MOVABLE');row.setdefault('collision','NO_COLLISION');row.setdefault('asset',None)
 row.setdefault('relative_location',[0,0,0]);row.setdefault('relative_rotation',[0,0,0]);row.setdefault('relative_scale',[1,1,1])
out=root/'Saved/CodexOutputs/HotelOpenings_20261004/BlueprintProbe.json'
target=root/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
before=hashlib.sha256(target.read_bytes()).hexdigest()
result={'passed':False,'checks':[],'failures':[],'component_rows':[]};a=None
try:
 bp,cls=create_blueprint('/Game/CodexGenerated/OldTown/Blueprints/Openings/BP_OpeningProbe',specs)
 sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
 a=sub.spawn_actor_from_class(cls,unreal.Vector(0,0,0),unreal.Rotator(pitch=0,yaw=0,roll=0),False)
 a.set_actor_label('OpeningBlueprintProbeOnly')
 for c in a.get_components_by_class(unreal.SceneComponent):
  r=c.get_editor_property('relative_rotation');p=c.get_attach_parent();v=c.get_editor_property('relative_location')
  row={'name':c.get_name(),'parent':p.get_name() if p else None,'location':[v.x,v.y,v.z],'rotation':[r.pitch,r.yaw,r.roll],'mobility':str(c.mobility)}
  if isinstance(c,unreal.PrimitiveComponent):
   row.update(collision=str(c.get_collision_enabled()),visible=c.get_editor_property('visible'),hidden_in_game=c.get_editor_property('hidden_in_game'))
  result['component_rows'].append(row)
 rows=result['component_rows']
 assert {r['name'] for r in rows}=={r['name'] for r in specs},rows
 assert next(r for r in rows if r['name']=='OpeningRoot')['parent'] is None,rows
 assert next(r for r in rows if r['name']=='DoorLeaf')['parent']=='DoorHinge',rows
 assert next(r for r in rows if r['name']=='DoorHinge')['rotation']==[0,90,0],rows
 assert next(r for r in rows if r['name']=='LeafCollision')['visible'] is False,rows
 assert next(r for r in rows if r['name']=='LeafCollision')['hidden_in_game'] is True,rows
 from AuditOldTownOpeningComponents import audit_scene,audit_physics
 from ValidateEnterableStreet import refresh_world_collision
 refresh_world_collision([a])
 fixture={'actor':a.get_actor_label(),'portal_id':'Probe::Front_0','components':specs,'world_center':[0,0,0],
          'opening_width':140.,'opening_height':230.,'axes':{'across':[1,0,0],'inward':[0,1,0]},
          'closed_hinges':{'DoorHinge':[0,0,0]},'open_hinges':{'DoorHinge':[0,90,0]}}
 report={'opening_components':{'doors':[fixture],'windows':[]}}
 resolved=audit_scene(result,[a],report)
 world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
 audit_physics(world,[fixture],resolved,result)
 assert not result['failures'],result['failures']
 assert hashlib.sha256(target.read_bytes()).hexdigest()==before,'Target map changed during asset-only probe'
 result['passed']=True
except Exception:
 result['traceback']=traceback.format_exc()
 raise
finally:
 if a is not None:unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a)
 out.write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('OPENING_BLUEPRINT_PROBE_PASS')
