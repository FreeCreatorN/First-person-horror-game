import bpy,bmesh,os,json
s=bpy.context.scene;o=bpy.data.objects['SM_TableLamp'];out=r'D:\UE\Project\HorrorGame\SourceArt\TableLamp'
# Remove the accidental discs closing the rolled fabric piping.
bm=bmesh.new();bm.from_mesh(o.data);bm.normal_update();idx=next(i for i,m in enumerate(o.data.materials) if m.name=='M_TableLamp_Linen')
remove=[f for f in bm.faces if f.material_index==idx and abs(f.normal.z)>.999 and any(abs(f.calc_center_median().z-z)<.00001 for z in [.312,.317,.520,.525])]
bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(o.data);bm.free()
active=o.data.uv_layers.active
for uv in list(o.data.uv_layers):
 if uv!=active:o.data.uv_layers.remove(uv)
o.data.uv_layers.active.name='UVMap'
colliders=[]
for i,(r1,r2,z,depth) in enumerate([(.115,.115,.034,.068),(.027,.027,.182,.235),(.18,.112,.419,.220)]):
 bpy.ops.mesh.primitive_cone_add(vertices=16,radius1=r1,radius2=r2,depth=depth,location=(0,0,z));c=bpy.context.object;c.name='UCX_SM_TableLamp_%02d'%i;c.hide_render=True;c.display_type='WIRE';colliders.append(c)
bpy.ops.object.select_all(action='DESELECT');o.select_set(True)
for c in colliders:c.select_set(True)
bpy.context.view_layer.objects.active=o
bpy.ops.export_scene.fbx(filepath=os.path.join(out,'SM_TableLamp.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
for c in colliders:c.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'TableLamp.blend'))
s.render.filepath=os.path.join(out,'TableLamp_Preview.png');bpy.ops.render.render(write_still=True)
report={'triangles':len(o.data.polygons),'uv_channels':len(o.data.uv_layers),'height_m':o.dimensions.z,'collision_hulls':len(colliders),'material_slots':[m.name for m in o.data.materials]}
with open(os.path.join(out,'model_report.json'),'w') as f:json.dump(report,f,indent=2)
print(report)
