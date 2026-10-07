import bpy, math, json
from pathlib import Path
from mathutils.bvhtree import BVHTree
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\Switch')
s=bpy.context.scene
base=bpy.data.objects['SM_Switch_Base'];button=bpy.data.objects['SM_Switch_Rocker']
def tree(o, exclude_steel=False):
    verts=[o.matrix_world@v.co for v in o.data.vertices]
    faces=[list(p.vertices) for p in o.data.polygons if not (exclude_steel and o.data.materials[p.material_index].name=='M_Switch_Steel')]
    return BVHTree.FromPolygons(verts,faces,all_triangles=True,epsilon=0)
base_tree=tree(base)
checks=[]
for angle in [-4,-3,-2,-1,0,1,2,3,4]:
    button.rotation_euler.x=math.radians(angle);bpy.context.view_layer.update()
    contacts=len(base_tree.overlap(tree(button,True)))
    checks.append({'angle_degrees':angle,'rocker_shell_base_intersections':contacts})
assert all(x['rocker_shell_base_intersections']==0 for x in checks),checks
report={'motion_samples':checks,'roundtrip':{},'success':False}
s.frame_set(1);s.render.filepath=str(OUT/'Switch_Preview.png');bpy.ops.render.render(write_still=True)
s.frame_set(30);s.render.filepath=str(OUT/'Switch_Pressed.png');bpy.ops.render.render(write_still=True)
for name,expected in [('SM_Switch_Base',5),('SM_Switch_Rocker',1)]:
    temp=bpy.data.scenes.new('FBX verification');bpy.context.window.scene=temp
    bpy.ops.import_scene.fbx(filepath=str(OUT/(name+'.fbx')))
    objects=list(temp.objects);meshes=[o for o in objects if o.type=='MESH' and not o.name.startswith('UCX_')]
    cols=[o for o in objects if o.name.startswith('UCX_')]
    assert len(meshes)==1 and len(cols)==expected,(name,[o.name for o in objects])
    assert not any(o.type in {'LIGHT','CAMERA'} for o in objects)
    asset=meshes[0]
    assert asset.location.length<1e-6, list(asset.location)
    report['roundtrip'][name]={'collision_hulls':len(cols),'dimensions_cm':[round(v*100,5) for v in asset.dimensions],'origin':list(asset.location),'uv_channels':len(asset.data.uv_layers),'lights':0}
    bpy.context.window.scene=s
    for o in objects:bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.scenes.remove(temp)
report['success']=True
(OUT/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SWITCH_VALIDATION '+json.dumps(report))
