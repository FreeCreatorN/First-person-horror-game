import bpy, bmesh, json
from pathlib import Path
from mathutils import Vector
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\Flashlight')
s=bpy.context.scene;asset=bpy.data.objects['SM_Flashlight'];report={'success':False}
bm=bmesh.new();bm.from_mesh(asset.data)
report['non_manifold_edges']=sum(not e.is_manifold for e in bm.edges);bm.free()
assert report['non_manifold_edges']==0,report
assert len(asset.data.uv_layers)>=1
for name in ['M_Flashlight_Lens','M_Flashlight_LED']:
    node=bpy.data.materials[name].node_tree.nodes['LightStrength']
    assert abs(node.outputs[0].default_value-.35)<1e-5
s.render.filepath=str(OUT/'Flashlight_Preview.png');bpy.ops.render.render(write_still=True)
cam=s.camera;cam.location=(.32,-.085,.065);target=Vector((.087,0,0))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.105
s.render.resolution_x=1000;s.render.resolution_y=1000
s.render.filepath=str(OUT/'Flashlight_Lens_Closeup.png');bpy.ops.render.render(write_still=True)
for name in ['M_Flashlight_Lens','M_Flashlight_LED']:bpy.data.materials[name].node_tree.nodes['LightStrength'].outputs[0].default_value=0
s.render.filepath=str(OUT/'Flashlight_Lens_Off.png');bpy.ops.render.render(write_still=True)
temp=bpy.data.scenes.new('FBX verification');bpy.context.window.scene=temp
bpy.ops.import_scene.fbx(filepath=str(OUT/'SM_Flashlight.fbx'))
objs=list(temp.objects);meshes=[o for o in objs if o.type=='MESH' and not o.name.startswith('UCX_')];cols=[o for o in objs if o.name.startswith('UCX_')]
assert len(meshes)==1 and len(cols)==3,[o.name for o in objs]
assert not any(o.type in {'LIGHT','CAMERA'} for o in objs)
m=meshes[0];assert m.location.length<1e-6
report['fbx']={'origin':list(m.location),'dimensions_cm':[v*100 for v in m.dimensions],'collision_hulls':len(cols),'light_objects':0,'materials':[mat.name for mat in m.data.materials]}
report['material_control']={'LightStrength':.35,'off_value':0,'LightColor':[.86,.93,1],'Lens_Opacity':.14}
report['success']=True
(OUT/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('FLASHLIGHT_VALIDATION '+json.dumps(report))
