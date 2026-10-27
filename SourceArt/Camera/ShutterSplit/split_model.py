"""Separate only the moving shutter cap; preserve the original UV atlas and normals."""
import bpy,bmesh,math,json,hashlib,re,time
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
report={'success':False,'parts':{},'renders':{}}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_report():
    (OUT/'split_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def geometry(obj,world=False):
    me=obj.data;bm=bmesh.new();bm.from_mesh(me)
    nm=sum(not e.is_manifold for e in bm.edges);loose=sum(not v.link_edges for v in bm.verts);bm.free()
    bpy.context.view_layer.update()
    me.calc_loop_triangles();points=[obj.matrix_world@v.co if world else v.co for v in me.vertices]
    lo=[min(v[i] for v in points) for i in range(3)];hi=[max(v[i] for v in points) for i in range(3)]
    assert nm==loose==0,(obj.name,nm,loose)
    return {'triangles':len(me.loop_triangles),'bounds_min_m':lo,'bounds_max_m':hi,'dimensions_cm':[(hi[i]-lo[i])*100 for i in range(3)],'non_manifold_edges':nm,'uv_channels':len(me.uv_layers)}
def uv_valid(me):
    assert len(me.uv_layers)==1
    uv=me.uv_layers.active.data
    for p in me.polygons:
        a,b,c=[uv[i].uv for i in p.loop_indices]
        assert abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))>2.e-13

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Camera.blend'))
s=bpy.context.scene;body=bpy.data.objects['SM_Camera'];view=bpy.data.objects['VIEW_Camera']
assert 'SM_Camera_ShutterButton' not in bpy.data.objects,'Shutter is already separated'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Before'/'Camera_before_split.blend'),copy=True)
old_model=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8-sig'))
old_validation=json.loads((ROOT/'validation_report.json').read_text(encoding='utf-8-sig'))
assert set(old_model['parts'])=={'SM_Camera'}
old_me=body.data;old_me.calc_loop_triangles();original_count=len(old_me.polygons)
assert original_count==old_model['parts']['SM_Camera']['triangles']==45168
source=bpy.data.collections['SOURCE - individual components']
moving=[o for o in source.objects if re.sub(r'\.\d{3}$','',o.name) in ('Shutter release','Cable release socket')]
assert len(moving)==2,[o.name for o in moving]
assert not any(o.parent for o in moving) and not body.parent
source_vertices=[o.matrix_basis@v.co for o in moving for v in o.data.vertices]
kd=KDTree(len(source_vertices))
for i,v in enumerate(source_vertices):kd.insert(v,i)
kd.balance()
is_moving={v.index:kd.find(body.matrix_basis@v.co)[2]<2.e-7 for v in old_me.vertices}
button_faces=[p.index for p in old_me.polygons if all(is_moving[i] for i in p.vertices)]
expected=sum(len(o.data.loop_triangles) or 0 for o in moving)
for o in moving:o.data.calc_loop_triangles()
expected=sum(len(o.data.loop_triangles) for o in moving)
assert len(button_faces)==expected and expected>100,(len(button_faces),expected)
button_face_set=set(button_faces)
body_faces=[p.index for p in old_me.polygons if p.index not in button_face_set]
pivot=Vector((.061,-.011,.0824));baked_materials=list(old_me.materials)
source_names=list(old_model['parts']['SM_Camera']['material_slots'])
assert len(source_names)==len(old_me.materials)
saved_normals=[n.vector.copy() for n in old_me.corner_normals]
canonical=bpy.data.collections['UE meshes - canonical origins'];display=bpy.data.collections['Camera - display assembly']
canonical.hide_viewport=False;canonical.hide_render=True
def subset(name,indices,offset):
    polys=[old_me.polygons[i] for i in indices]
    used=sorted({v for p in polys for v in p.vertices});remap={v:i for i,v in enumerate(used)}
    mats=sorted({p.material_index for p in polys});matmap={v:i for i,v in enumerate(mats)}
    me=bpy.data.meshes.new(name)
    me.from_pydata([tuple(old_me.vertices[i].co-offset) for i in used],[],[tuple(remap[i] for i in p.vertices) for p in polys]);me.update()
    for index in mats:me.materials.append(bpy.data.materials[source_names[index]])
    layer=me.uv_layers.new(name='UVMap');normals=[]
    for new_p,old_p in zip(me.polygons,polys):
        new_p.material_index=matmap[old_p.material_index];new_p.use_smooth=old_p.use_smooth
        for li,old_li in zip(new_p.loop_indices,old_p.loop_indices):
            layer.data[li].uv=old_me.uv_layers.active.data[old_li].uv
            normals.append(tuple(saved_normals[old_li]))
    me.normals_split_custom_set(normals);uv_valid(me)
    return me,mats
body_data,body_mats=subset('Camera body - shutter removed',body_faces,Vector((0,0,0)))
button_data,button_mats=subset('Independent shutter cap',button_faces,pivot)
body.data=body_data;view.data=body_data
button=bpy.data.objects.new('SM_Camera_ShutterButton',button_data);canonical.objects.link(button)
button_view=bpy.data.objects.new('VIEW_Camera_ShutterButton',button_data);display.objects.link(button_view);button_view.location=pivot
button_view['PressTravel_mm']=1.2;button_view['Role']='Moving shutter release cap and cable-release socket'
view['ShutterButtonIndependent']=True
assert len(body_data.polygons)+len(button_data.polygons)==original_count
def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
def body_collision():
    cs=[hull('UCX_SM_Camera_00',[(x,y,z) for x in (-.074,.078) for y in (-.029,.0316) for z in (-.00006,.0801)])]
    outline=[(-.040,.076),(-.034,.085),(-.019,.098),(.003,.098),(.019,.085),(.024,.076)]
    cs.append(hull('UCX_SM_Camera_01',[(x,y,z) for x,z in outline for y in (-.027,.019)]+[(x,y,.1011) for x in (-.020,.004) for y in (-.013,.013)]))
    for j,profile in enumerate([[(.0318,0),(.0318,.016)],[(.0315,.015),(.0288,.0523)]]):
        cs.append(hull('UCX_SM_Camera_%02d'%(j+2),[(-.008+r*math.cos(math.tau*i/32),-.025-t,.044+r*math.sin(math.tau*i/32)) for r,t in profile for i in range(32)]))
    return cs
def export(obj,mats,collisions):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    for c in collisions:c.select_set(True)
    path=ROOT/(obj.name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
    info=geometry(obj);info.update({'filename':path.name,'sha256':sha(path),'collision_hulls':len(collisions),'material_slots':{source_names[i]:old_model['parts']['SM_Camera']['material_slots'][source_names[i]] for i in mats}})
    report['parts'][obj.name]=info
    for c in collisions:bpy.data.objects.remove(c,do_unlink=True)
    for i,old_index in enumerate(mats):obj.material_slots[i].material=baked_materials[old_index]
export(body,body_mats,body_collision())
g=geometry(button);lo=g['bounds_min_m'];hi=g['bounds_max_m']
bc=[hull('UCX_SM_Camera_ShutterButton_00',[(.0037*math.cos(math.tau*i/24),.0037*math.sin(math.tau*i/24),z) for z in (lo[2],hi[2]) for i in range(24)])]
export(button,button_mats,bc)

# Read back both files. Exported coordinates are local for the moving button.
for name,spec in report['parts'].items():
    before=set(bpy.data.objects);before_mesh=set(bpy.data.meshes);before_mat=set(bpy.data.materials)
    bpy.ops.object.select_all(action='DESELECT');bpy.ops.import_scene.fbx(filepath=str(ROOT/spec['filename']),use_anim=False)
    added=set(bpy.data.objects)-before
    meshes=[o for o in added if o.type=='MESH' and not o.name.startswith('UCX_')]
    coll=[o for o in added if o.type=='MESH' and o.name.startswith('UCX_')]
    assert len(meshes)==1 and len(coll)==spec['collision_hulls']
    assert not any(o.type in ('LIGHT','CAMERA') for o in added)
    check=geometry(meshes[0],True);assert check['triangles']==spec['triangles'] and check['uv_channels']==1
    for key in ('bounds_min_m','bounds_max_m'):
        assert max(abs(a-b) for a,b in zip(check[key],spec[key]))<2.e-6,(name,key)
    slots={re.sub(r'\.\d{3}$','',m.name) for m in meshes[0].data.materials}
    assert slots==set(spec['material_slots']),(name,slots)
    uv_valid(meshes[0].data);spec['fbx_roundtrip']={'success':True,'triangles':check['triangles'],'collision_hulls':len(coll),'uv_channels':1}
    for o in added:bpy.data.objects.remove(o,do_unlink=True)
    for me in set(bpy.data.meshes)-before_mesh:
        if me.users==0:bpy.data.meshes.remove(me)
    for mat in set(bpy.data.materials)-before_mat:
        if mat.users==0:bpy.data.materials.remove(mat)
canonical.hide_viewport=True;canonical.hide_render=True
source.hide_viewport=True;source.hide_render=True
bpy.ops.object.select_all(action='DESELECT');button_view.select_set(True);bpy.context.view_layer.objects.active=button_view
report.update({'original_total_triangles':original_count,'combined_total_triangles':sum(v['triangles'] for v in report['parts'].values()),'pivot_blender_m':list(pivot),'socket_ue_cm':[6.1,1.1,8.24],'press_travel_cm':.12,'texture_files_sha256':{str(p):sha(p) for p in sorted((ROOT/'Textures').glob('T_Camera_*.png'))},'uv_atlas_reused_without_rebaking':True,'source_components_preserved':len(source.objects),'exported_cameras':0,'exported_lights':0})
assert len(report['texture_files_sha256'])==4

# Render current two-component assembly, with default released state restored.
camera=s.camera;camera_state=camera.matrix_world.copy();ortho=camera.data.ortho_scale;render_path=s.render.filepath
target=Vector((.045,-.005,.080));camera.location=target+Vector((.10,-.14,.15));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.075
old_res=(s.render.resolution_x,s.render.resolution_y);s.render.resolution_x=1200;s.render.resolution_y=1000;s.cycles.samples=32
for state,delta in [('Released',0.),('Pressed',-.0012)]:
    button_view.location=pivot+Vector((0,0,delta));s.render.filepath=str(OUT/('Camera_Shutter_'+state+'.png'))
    bpy.ops.render.render(write_still=True);p=Path(s.render.filepath)
    report['renders'][state]={'path':str(p),'sha256':sha(p),'button_world_z_m':button_view.location.z,'press_offset_m':delta}
button_view.location=pivot;camera.matrix_world=camera_state;camera.data.ortho_scale=ortho
s.render.resolution_x,s.render.resolution_y=old_res;s.render.filepath=render_path
assert abs(report['renders']['Released']['button_world_z_m']-report['renders']['Pressed']['button_world_z_m']-.0012)<1.e-7
old_model['parts']=report['parts'];old_model['assembly']['combined_single_mesh']=False
old_model['assembly'].update({'shutter_button_independent':True,'button_mesh':'SM_Camera_ShutterButton','button_pivot_blender_m':list(pivot),'button_socket_ue_cm':report['socket_ue_cm'],'button_press_travel_cm':.12})
(ROOT/'model_report.json').write_text(json.dumps(old_model,indent=2),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    for a in w.screen.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.region_3d.view_location=Vector((0,-.015,.046));a.spaces.active.region_3d.view_distance=.21
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Camera.blend'))
report['blend_sha256']=sha(ROOT/'Camera.blend');report['success']=True;write_report()
print('CAMERA_SHUTTER_SEPARATED '+json.dumps({'parts':{k:v['triangles'] for k,v in report['parts'].items()},'pivot':list(pivot),'travel_mm':1.2}),flush=True)
