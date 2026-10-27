"""Clear A60 bulb: closed glass wall, E27 helical cap and suspended coil filament."""
import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
export_col=bpy.data.collections.new('UE meshes - canonical origins');s.collection.children.link(export_col)
source_col=bpy.data.collections.new('SOURCE - individual components');s.collection.children.link(source_col)
display_col=bpy.data.collections.new('LightBulb - display assembly');s.collection.children.link(display_col)
components=[]

def material(name,color,rough,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Emission Strength'].default_value=0
    return m,p
glass,p=material('M_Bulb_Glass',(.965,.985,1.0),.07)
p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.45;p.inputs['Alpha'].default_value=1
glass['ue_material']='M_LightBulb_Glass'
metal,p=material('M_Bulb_NickelCap',(.32,.30,.25),.31,1)
ns=metal.node_tree.nodes;ls=metal.node_tree.links;co=ns.new('ShaderNodeTexCoord');noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1200;noise.inputs['Detail'].default_value=2;ls.new(co.outputs['Object'],noise.inputs['Vector'])
rr=ns.new('ShaderNodeMapRange');rr.inputs['To Min'].default_value=.24;rr.inputs['To Max'].default_value=.37;ls.new(noise.outputs['Fac'],rr.inputs['Value']);ls.new(rr.outputs[0],p.inputs['Roughness'])
insulator,p=material('M_Bulb_BlackInsulator',(.009,.012,.016),.48)
contact,p=material('M_Bulb_ContactButton',(.23,.15,.07),.33,1)
wire,p=material('M_Bulb_NickelLeadWires',(.19,.20,.21),.40,1)
filament,p=material('M_Bulb_Filament',(.24,.20,.13),.54,.35)
p.inputs['Emission Color'].default_value=(1.0,.72,.36,1);p.inputs['Emission Strength'].default_value=0
filament['ue_material']='M_LightBulb_Filament';filament['GlowStrength']=0.0

def mesh(name,vs,fs,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat);components.append(o)
    for p in me.polygons:p.use_smooth=True
    return o
def catmull(points,steps=6):
    pts=[Vector(p) for p in points];result=[]
    for i in range(len(pts)-1):
        p0=pts[i-1] if i else pts[0]*2-pts[1];p1=pts[i];p2=pts[i+1];p3=pts[i+2] if i+2<len(pts) else pts[-1]*2-pts[-2]
        for j in range(steps):
            t=j/steps;result.append(tuple(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)))
    result.append(tuple(pts[-1]));return result
def lathe(name,profile,mat,count=96,close_profile=False):
    verts=[];rings=[]
    for r,z in profile:
        if r<1e-8:rings.append([len(verts)]);verts.append((0,0,z))
        else:
            ring=[]
            for i in range(count):a=math.tau*i/count;ring.append(len(verts));verts.append((r*math.cos(a),r*math.sin(a),z))
            rings.append(ring)
    faces=[]
    pairs=list(zip(rings,rings[1:]))+([(rings[-1],rings[0])] if close_profile else [])
    for a,b in pairs:
        if len(a)==len(b)==1:continue
        for i in range(count):
            j=(i+1)%count
            if len(a)==1:faces.append((a[0],b[j],b[i]))
            elif len(b)==1:faces.append((a[i],a[j],b[0]))
            else:faces.append((a[i],a[j],b[j],b[i]))
    return mesh(name,verts,faces,mat)

# Wall thickness follows the profile normal, including the glass dome.
outer=catmull([(.01225,.024),(.0124,.029),(.0138,.035),(.018,.043),(.024,.052),(.0286,.063),(.030,.073),(.0285,.084),(.024,.093),(.017,.100),(.0085,.104),(0,.105)],6)
inner=[]
for i,(r,z) in enumerate(outer):
    a=Vector(outer[max(0,i-1)]);b=Vector(outer[min(len(outer)-1,i+1)]);t=(b-a).normalized();thick=.00055
    inner.append((max(0,r-t.y*thick),z+t.x*thick))
inner[-1]=(0,.10445)
shell=lathe('Clear glass envelope with 0.55 mm wall',outer+list(reversed(inner)),glass,96,True)

# The screw is a continuous helix in the metal surface, not stacked tori.
N=128;rows=[]
def ring(r,z):return [(r*math.cos(math.tau*i/N),r*math.sin(math.tau*i/N),z) for i in range(N)]
rows.append(ring(.0119,.0040));rows.append(ring(.0121,.0046))
for j in range(97):
    z=.0047+(.0228-.0047)*j/96;fade=min(1,(z-.0046)/.0009,(.0234-z)/.0009);fade=max(0,fade)
    row=[]
    for i in range(N):
        a=math.tau*i/N;phase=math.tau*(z-.0047)/.00363-a;r=.0121+.0007*(1+math.cos(phase))*fade
        row.append((r*math.cos(a),r*math.sin(a),z))
    rows.append(row)
for r,z in [(.0124,.0235),(.0130,.0243),(.01325,.0253),(.01285,.0260),(.01165,.0260),(.01155,.0248),(.01135,.0060),(.0082,.0040)]:rows.append(ring(r,z))
vs=[v for row in rows for v in row];fs=[]
for j in range(len(rows)):
    k=(j+1)%len(rows)
    for i in range(N):a=j*N+i;b=j*N+(i+1)%N;c=k*N+(i+1)%N;d=k*N+i;fs.append((a,b,c,d))
cap=mesh('True helical E27 metal screw cap',vs,fs,metal)
lathe('Moulded black insulating contact separator',[(0,.00065),(.0031,.00065),(.0068,.0014),(.0093,.0029),(.0095,.0043),(.0084,.0057),(0,.0057)],insulator,80)
lathe('Bottom electrical contact button',[(0,0),(.0025,0),(.0032,.0002),(.0036,.0007),(.0032,.00115),(0,.00115)],contact,64)

# The glass pinch stem and its internal support wires are fully modelled.
stem_profile=catmull([(0,.0235),(.0060,.0235),(.0063,.0265),(.0043,.0305),(.0030,.039),(.0021,.048),(.0016,.0518),(0,.0524)],5)
stem_profile=[(max(0,r),z) for r,z in stem_profile]
lathe('Internal sealed glass support stem',stem_profile,glass,64)

def tube(name,points,radius,mat,segments=8):
    ps=[Vector(p) for p in points];vs=[]
    for i,p in enumerate(ps):
        t=(ps[min(i+1,len(ps)-1)]-ps[max(0,i-1)]).normalized();ref=Vector((1,0,0)) if abs(t.x)<.95 else Vector((0,1,0))
        u=t.cross(ref).normalized();v=t.cross(u).normalized()
        for j in range(segments):a=math.tau*j/segments;vs.append(tuple(p+radius*(u*math.cos(a)+v*math.sin(a))))
    fs=[]
    for i in range(len(ps)-1):
        for j in range(segments):a=i*segments+j;b=i*segments+(j+1)%segments;fs.append((a,b,b+segments,a+segments))
    fs.extend([tuple(reversed(range(segments))),tuple(range((len(ps)-1)*segments,len(ps)*segments))]);o=mesh(name,vs,fs,mat)
    for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
    return o
turns=40
def coil_point(t):
    a=math.tau*turns*t
    return (-.014+.028*t,-.0015+.00045*math.cos(a),.077+.0020*math.sin(math.pi*t)+.00045*math.sin(a))
coil=tube('Suspended coiled tungsten filament',[coil_point(i/400) for i in range(401)],.00010,filament,6)
for sign in (-1,1):
    end=coil_point(0 if sign==-1 else 1)
    pts=catmull([(sign*.0022,0,.026),(sign*.0022,0,.043),(sign*.0042,-.0002,.052),(sign*.0100,-.0008,.061),(sign*.0146,-.00105,.070),end],7)
    tube('Nickel lead-in wire '+str(sign),pts,.00032,wire,10)
for t in (.25,.50,.75):
    end=coil_point(t);start=(.0004 if t>.5 else -.0004,.001,.049)
    bend=((start[0]+end[0])*.45,.0015,.067)
    tube('Filament support '+str(t),catmull([start,bend,end],10),.00013,wire,8)

for o in components:
    copy=o.copy();copy.data=o.data.copy();source_col.objects.link(copy)
bpy.ops.object.select_all(action='DESELECT')
for o in components:o.select_set(True)
bpy.context.view_layer.objects.active=shell;bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_LightBulb'
s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.004);bpy.ops.object.mode_set(mode='OBJECT')
tr=asset.modifiers.new('Game triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tr.name)
bm=bmesh.new();bm.from_mesh(asset.data);nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free();assert nonmanifold==0,nonmanifold

def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
cs=[]
cs.append(hull('UCX_SM_LightBulb_00',[(r*math.cos(math.tau*i/32),r*math.sin(math.tau*i/32),z) for r,z in outer for i in range(32)]))
cs.append(hull('UCX_SM_LightBulb_01',[(.0135*math.cos(math.tau*i/24),.0135*math.sin(math.tau*i/24),z) for z in (0,.026) for i in range(24)]))
for o in cs:o.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_LightBulb.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
mapping={m.name:('M_LightBulb_Glass' if m==glass else 'M_LightBulb_Filament' if m==filament else 'M_LightBulb_Opaque') for m in asset.data.materials}
report={'parts':{'SM_LightBulb':{'filename':'SM_LightBulb.fbx','dimensions_cm':[v*100 for v in asset.dimensions],'triangles':len(asset.data.polygons),'collision_hulls':len(cs),'uv_channels':1,'non_manifold_edges':nonmanifold,'material_slots':mapping}},
    'texture_sets':{'Opaque':{'prefix':'T_LightBulb',**{ch:'Textures/T_LightBulb_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal','Metallic')}}},
    'materials':{'M_LightBulb_Opaque':{'shader_type':'opaque_atlas','texture_set':'Opaque'},'M_LightBulb_Glass':{'shader_type':'glass','opacity':.10,'roughness':.08,'ior':1.45,'tint':[.94,.98,1]},'M_LightBulb_Filament':{'shader_type':'filament','base_color':[.24,.20,.13],'emissive_color':[1,.72,.36],'glow_strength':0}},
    'glass_wall_thickness_mm':.55,'nominal_height_mm':105,'nominal_diameter_mm':60,'cap_type':'E27 style','thread_is_continuous_helix':True,'thread_pitch_mm':3.63,
    'assembly':{'combined_single_mesh':True,'filament_center_blender_m':list(coil_point(.5)),'filament_glow_default':0,'light_actors_included':False},'exported_lights':0,'exported_cameras':0,
    'reference_url':'https://www.signify.com/global/prof/conventional-lamps-and-tubes/incandescent-lamps/gls-specialties/philips-standard-extra-low-voltage-a60/920021020517_EU/product'}
for o in cs:bpy.data.objects.remove(o,do_unlink=True)
for c in list(asset.users_collection):c.objects.unlink(asset)
export_col.objects.link(asset);view=asset.copy();view.data=asset.data;view.name='VIEW_LightBulb';display_col.objects.link(view)
export_col.hide_viewport=True;export_col.hide_render=True;source_col.hide_viewport=True;source_col.hide_render=True

studio=bpy.data.collections.new('Preview studio - excluded from exports');s.collection.children.link(studio)
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor,p=material('Preview dark slate',(.026,.034,.045),.77)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.00015));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,0,.056));bpy.ops.object.camera_add(location=target+Vector((.16,-.22,.10)));cam=bpy.context.object;cam.name='Camera_LightBulb';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.148;cam.data.clip_start=.0001;s.camera=cam;studio_obj(cam)
for name,pos,power,width,height,col in [('Left reflection',(-.18,-.07,.17),2.7,.018,.18,(1,.96,.9)),('Right reflection',(.20,.06,.16),2,.014,.17,(.84,.92,1)),('Back rim',(-.08,.20,.18),2.5,.07,.08,(1,.95,.87))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.shape='RECTANGLE';o.data.size=width;o.data.size_y=height;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;bg=next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.07,.09,.13,1);bg.inputs[1].default_value=.4
s.render.engine='CYCLES';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.transmission_bounces=8;s.cycles.glossy_bounces=8;s.cycles.max_bounces=12
s.render.resolution_x=1400;s.render.resolution_y=1600;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.1;s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'LightBulb_Preview.png');studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');view.select_set(True);bpy.context.view_layer.objects.active=view
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'LightBulb.blend'));print(json.dumps(report,indent=2))
