"""Closed photo card: flush photo material, full image UV, bevelled edge and curled corner."""
import bpy,bmesh,math,json,hashlib,re
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
(OUT/'Textures').mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def collection(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
canonical=collection('UE meshes - canonical origins');display=collection('PhotoPaper - display assembly')
def material(name,color,rough):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=0;p.inputs['Emission Strength'].default_value=0
    return m,p
frame,_=material('M_PhotoPaper_Frame',(.82,.80,.75),.66)
photo,p=material('M_PhotoPaper_Image',(.06,.065,.07),.23)
back,_=material('M_PhotoPaper_Back',(.73,.72,.67),.80)
image=bpy.data.images.new('T_PhotoPaper_Blank',width=128,height=128,alpha=False)
image.colorspace_settings.name='sRGB';image.pixels=[.06,.065,.07,1.]*(128*128)
image.filepath_raw=str(OUT/'Textures'/'T_PhotoPaper_Blank.png');image.file_format='PNG';image.save()
disk=bpy.data.images.load(str(OUT/'Textures'/'T_PhotoPaper_Blank.png'),check_existing=False)
tex=photo.node_tree.nodes.new('ShaderNodeTexImage');tex.image=disk;tex.label='PhotoTexture - replaceable photo'
photo.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color'])
def rr(w,h,r,cy=0):
    pts=[]
    for cx,yy,a0 in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for j in range(9):
            a=math.radians(a0+j*90/8);pts.append((cx+r*math.cos(a),cy+yy+r*math.sin(a)))
    return pts
def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def lift(x,y):return .00065*smooth((x-.031)/.013)*smooth((-.040-y)/.014)
inner=rr(.078,.078,.00025,.010);outer=rr(.088-.00006,.108-.00006,.0012-.00003)
n=len(inner);vs=[];faces=[];slots=[];thickness=.00035
for row in range(4):
    t=row/3
    for a,b in zip(inner,outer):
        x=a[0]*(1-t)+b[0]*t;y=a[1]*(1-t)+b[1]*t;vs.append((x,y,thickness+lift(x,y)))
for row in range(3):
    for i in range(n):
        j=(i+1)%n;faces.append((row*n+i,(row+1)*n+i,(row+1)*n+j,row*n+j));slots.append(0)
center=len(vs);vs.append((0,.010,thickness))
for i in range(n):faces.append((center,i,(i+1)%n));slots.append(1)
front_faces=list(faces);front_count=len(vs)
vs += [(x,y,z-thickness) for x,y,z in vs[:]]
for f in front_faces:faces.append(tuple(i+front_count for i in reversed(f)));slots.append(2)
side_upper=[];side_lower=[]
for z,ids in [(thickness-.000035,side_upper),(.000035,side_lower)]:
    for x,y in rr(.088,.108,.0012):ids.append(len(vs));vs.append((x,y,z+lift(x,y)))
top_outer=[3*n+i for i in range(n)];bottom_outer=[front_count+3*n+i for i in range(n)]
for aa,bb in [(top_outer,side_upper),(side_upper,side_lower),(side_lower,bottom_outer)]:
    for i in range(n):
        j=(i+1)%n;faces.append((aa[i],bb[i],bb[j],aa[j]));slots.append(0)
me=bpy.data.meshes.new('PhotoPaper continuous front-border-back volume');me.from_pydata(vs,[],faces);me.update()
for mat in (frame,photo,back):me.materials.append(mat)
for poly,slot in zip(me.polygons,slots):poly.material_index=slot;poly.use_smooth=True
uv=me.uv_layers.new(name='UVMap')
edge_uv={v:(i/n,layer/3) for layer,ring in enumerate((top_outer,side_upper,side_lower,bottom_outer)) for i,v in enumerate(ring)}
for poly in me.polygons:
    for li in poly.loop_indices:
        vid=me.loops[li].vertex_index;x,y,z=me.vertices[vid].co
        if poly.index>=2*len(front_faces):
            uu,vv=edge_uv[vid]
            if (poly.index-2*len(front_faces))%n==n-1 and uu==0:uu=1.
            coord=(uu,vv)
        elif poly.material_index==1:coord=((x+.039)/.078,(y+.029)/.078)
        elif poly.material_index==2:coord=(.5-x/.088,.5+y/.108)
        else:coord=(.5+x/.088,.5+y/.108)
        uv.data[li].uv=coord
obj=bpy.data.objects.new('SM_PhotoPaper',me);canonical.objects.link(obj)
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
tr=obj.modifiers.new('Game ready triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tr.name)
def geometry(o):
    o.data.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(o.data)
    nm=sum(not e.is_manifold for e in bm.edges);loose=sum(not v.link_edges for v in bm.verts);bm.free()
    bpy.context.view_layer.update();points=[o.matrix_world@v.co for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    assert nm==loose==0,(nm,loose)
    return {'triangles':len(o.data.loop_triangles),'bounds_min_m':lo,'bounds_max_m':hi,'dimensions_m':[hi[i]-lo[i] for i in range(3)],'non_manifold_edges':nm,'loose_vertices':loose}
g=geometry(obj);uv_data=obj.data.uv_layers.active.data
photo_uv=[]
for poly in obj.data.polygons:
    a,b,c=[uv_data[i].uv for i in poly.loop_indices]
    assert abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))>2.e-13
    if poly.material_index==1:
        assert poly.normal.z>.99
        photo_uv.extend([uv_data[i].uv.copy() for i in poly.loop_indices])
photo_info={'min':[min(v[i] for v in photo_uv) for i in range(2)],'max':[max(v[i] for v in photo_uv) for i in range(2)],'slot_index':1,'source_slot_name':'M_PhotoPaper_Image','photo_size_m':[.078,.078],'front_normal':'+Z','image_top_direction':'+Y'}
assert max(abs(x) for x in photo_info['min'])<1.e-6 and max(abs(x-1) for x in photo_info['max'])<1.e-6
bm=bmesh.new()
for v in obj.data.vertices:bm.verts.new(v.co)
bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
unused=[v for v in bm.verts if not v.link_faces]
if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));cm=bpy.data.meshes.new('Photo card convex collision');bm.to_mesh(cm);bm.free()
collision=bpy.data.objects.new('UCX_SM_PhotoPaper_00',cm);s.collection.objects.link(collision);collision.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_PhotoPaper.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
bpy.data.objects.remove(collision,do_unlink=True)
model={'parts':{'SM_PhotoPaper':{'filename':'SM_PhotoPaper.fbx','dimensions_cm':[v*100 for v in g['dimensions_m']],'bounds_min_m':g['bounds_min_m'],'bounds_max_m':g['bounds_max_m'],'triangles':g['triangles'],'collision_hulls':1,'uv_channels':1,'non_manifold_edges':0,'material_slots':{'M_PhotoPaper_Frame':'M_PhotoPaper_Frame','M_PhotoPaper_Image':'MI_PhotoPaper_Image','M_PhotoPaper_Back':'M_PhotoPaper_Back'}}},'materials':{'M_PhotoPaper_Frame':{'base_color':[.82,.80,.75],'roughness':.66},'M_PhotoPaper_Image':{'texture_parameter':'PhotoTexture','roughness':.23},'M_PhotoPaper_Back':{'base_color':[.73,.72,.67],'roughness':.80}},'texture':{'name':'T_PhotoPaper_Blank','filename':'Textures/T_PhotoPaper_Blank.png','sha256':sha(OUT/'Textures'/'T_PhotoPaper_Blank.png')},'photo_uv':photo_info,'thickness_mm':.35,'corner_lift_mm':.65,'borders_mm':{'left':5,'right':5,'top':5,'bottom':25},'exported_cameras':0,'exported_lights':0}
(OUT/'model_report.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
validation={'success':False,'geometry':{'SM_PhotoPaper':g},'uv':{'SM_PhotoPaper':{'layers':['UVMap'],'zero_area_triangles':0}},'photo_uv':photo_info,'fbx_roundtrip':{},'renders':{}}
before=set(bpy.data.objects);before_mat=set(bpy.data.materials);before_mesh=set(bpy.data.meshes)
bpy.ops.object.select_all(action='DESELECT');bpy.ops.import_scene.fbx(filepath=str(OUT/'SM_PhotoPaper.fbx'),use_anim=False)
added=set(bpy.data.objects)-before;meshes=[o for o in added if o.type=='MESH' and not o.name.startswith('UCX_')];cs=[o for o in added if o.type=='MESH' and o.name.startswith('UCX_')]
assert len(meshes)==len(cs)==1 and not any(o.type in ('LIGHT','CAMERA') for o in added)
actual=geometry(meshes[0]);assert actual['triangles']==g['triangles']
for key in ('bounds_min_m','bounds_max_m'):assert max(abs(a-b) for a,b in zip(actual[key],g[key]))<1.e-6
names=[re.sub(r'\.\d{3}$','',m.name) for m in meshes[0].data.materials];assert names==list(model['parts']['SM_PhotoPaper']['material_slots'])
validation['fbx_roundtrip']['SM_PhotoPaper']={'success':True,'source':str(OUT/'SM_PhotoPaper.fbx'),'sha256':sha(OUT/'SM_PhotoPaper.fbx'),'ucx_count':1,'uv_layers':len(meshes[0].data.uv_layers),'geometry':actual,'material_slots':names}
for o in added:bpy.data.objects.remove(o,do_unlink=True)
for m in set(bpy.data.meshes)-before_mesh:
    if m.users==0:bpy.data.meshes.remove(m)
for m in set(bpy.data.materials)-before_mat:
    if m.users==0:bpy.data.materials.remove(m)
view=bpy.data.objects.new('VIEW_PhotoPaper',obj.data);display.objects.link(view)
canonical.hide_viewport=True;canonical.hide_render=True
studio=collection('Preview studio - excluded from exports')
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor,_=material('Preview charcoal',(.032,.038,.046),.83)
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.00008));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,.005,.0003));bpy.ops.object.camera_add(location=target+Vector((.13,-.17,.23)));camera=bpy.context.object;camera.name='Camera_PhotoPaper';camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=.155;camera.data.clip_start=.00001;s.camera=camera;studio_obj(camera)
for name,loc,power,size,color in [('Key',(-.12,-.1,.26),2.8,.16,(1,.97,.92)),('Fill',(.18,.05,.20),1.7,.14,(.89,.95,1)),('Rim',(-.03,.18,.21),2.2,.10,(1,.98,.93))]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=color;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;bg=next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.12,.15,.19,1);bg.inputs[1].default_value=.3
s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1400;s.render.resolution_y=1200;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.4;s.render.image_settings.file_format='PNG';studio.hide_viewport=True
def render(name):
    path=OUT/name;s.render.filepath=str(path);bpy.ops.render.render(write_still=True);assert path.is_file()
    validation['renders'][name]={'path':str(path),'sha256':sha(path),'engine':'CYCLES','samples':s.cycles.samples}
render('PhotoPaper_Preview.png')
view.rotation_euler.y=math.pi;view.location.z=g['bounds_max_m'][2]+.00002
render('PhotoPaper_Back.png')
view.rotation_euler.y=0;view.location.z=0
camera_state=camera.matrix_world.copy();ortho=camera.data.ortho_scale
target=Vector((.025,-.043,.0003));camera.location=target+Vector((.05,-.09,.045));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.070
render('PhotoPaper_Edge.png')
camera.matrix_world=camera_state;camera.data.ortho_scale=ortho;s.render.filepath=str(OUT/'PhotoPaper_Preview.png')
bpy.ops.object.select_all(action='DESELECT');view.select_set(True);bpy.context.view_layer.objects.active=view
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PhotoPaper.blend'))
validation['blend_file']=str(OUT/'PhotoPaper.blend');validation['success']=True
(OUT/'validation_report.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
print('PHOTOPAPER_SOURCE_READY '+json.dumps({'triangles':g['triangles'],'dimensions_cm':model['parts']['SM_PhotoPaper']['dimensions_cm'],'photo_uv':photo_info}),flush=True)
