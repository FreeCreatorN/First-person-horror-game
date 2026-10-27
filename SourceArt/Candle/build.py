"""Unlit ivory wax candle with continuous sculpted drips and a brass catch tray."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
export_col=bpy.data.collections.new('UE meshes - canonical origins');s.collection.children.link(export_col)
source_col=bpy.data.collections.new('SOURCE - individual components');s.collection.children.link(source_col)
display_col=bpy.data.collections.new('Candle - display assembly');s.collection.children.link(display_col)
components=[];rng=random.Random(318)
N=160;BASE=.0054;HEIGHT=.142

def material(name,color,rough,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    p.inputs['Emission Strength'].default_value=0
    return m,p

wax,p=material('M_Candle_Wax',(.71,.55,.32),.51)
p.inputs['Specular IOR Level'].default_value=.30;p.inputs['Subsurface Weight'].default_value=.12
ns=wax.node_tree.nodes;ls=wax.node_tree.links;co=ns.new('ShaderNodeTexCoord')
noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=82;noise.inputs['Detail'].default_value=3;ls.new(co.outputs['Object'],noise.inputs['Vector'])
ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.1;ramp.color_ramp.elements[0].color=(.57,.40,.20,1);ramp.color_ramp.elements[1].position=.9;ramp.color_ramp.elements[1].color=(.84,.70,.47,1)
ls.new(noise.outputs['Fac'],ramp.inputs[0]);ls.new(ramp.outputs[0],p.inputs['Base Color'])
fine=ns.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=4600;fine.inputs['Detail'].default_value=2;ls.new(co.outputs['Object'],fine.inputs['Vector'])
bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.11;bump.inputs['Distance'].default_value=.000015;ls.new(fine.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs[0],p.inputs['Normal'])
pool,p=material('M_Candle_CooledWaxPool',(.76,.61,.38),.33)
brass,p=material('M_Candle_AgedBrass',(.14,.086,.028),.43,1)
ns=brass.node_tree.nodes;ls=brass.node_tree.links;co=ns.new('ShaderNodeTexCoord');noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=180;noise.inputs['Detail'].default_value=4;ls.new(co.outputs['Object'],noise.inputs['Vector'])
ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.25;ramp.color_ramp.elements[0].color=(.043,.032,.018,1);ramp.color_ramp.elements[1].position=.78;ramp.color_ramp.elements[1].color=(.22,.139,.049,1)
ls.new(noise.outputs['Fac'],ramp.inputs[0]);ls.new(ramp.outputs[0],p.inputs['Base Color'])
rough=ns.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=.31;rough.inputs['To Max'].default_value=.57;ls.new(noise.outputs['Fac'],rough.inputs['Value']);ls.new(rough.outputs[0],p.inputs['Roughness'])
fine=ns.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=5200;fine.inputs['Detail'].default_value=2;ls.new(co.outputs['Object'],fine.inputs['Vector'])
bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.1;bump.inputs['Distance'].default_value=.000012;ls.new(fine.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs[0],p.inputs['Normal'])
wick_mat,p=material('M_Candle_CharredWick',(.009,.006,.003),.91)
fiber_mat,p=material('M_Candle_WickFiber',(.045,.027,.012),.9)

def mesh(name,vs,fs,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);o.data.materials.append(mat);components.append(o)
    for p in me.polygons:p.use_smooth=True
    return o
def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
def top(theta):return BASE+HEIGHT+.0011*math.sin(theta*3+.4)+.0010*math.sin(theta*7+.8)+.00055*math.cos(theta*11)
def angle_delta(a,b):return (a-b+math.pi)%math.tau-math.pi
drips=[(.18,.045,.065,.0017),(.90,.067,.060,.0022),(1.72,.023,.075,.0020),(2.49,.101,.054,.0024),(3.12,.040,.064,.0018),(3.65,.074,.060,.0023),(4.22,.093,.067,.0026),(4.93,.052,.070,.0021),(5.61,.135,.063,.0024),(6.02,.028,.070,.0017)]
def outer_radius(theta,z):
    u=(z-BASE)/HEIGHT
    r=.0225+.00032*math.sin(theta*4+.2)*math.sin(math.pi*u)+.00020*math.cos(theta*9+u*5)
    r+=.00065*math.exp(-max(0,z-BASE)/.003)
    r+=.00010*math.sin(u*110+theta*3)
    for a,length,width,amount in drips:
        end=BASE+HEIGHT-length
        shoulder=smooth((z-end)/.0045)
        bulb=math.exp(-((z-(end+.005))/.0036)**2)
        local_width=width*(.80+.55*bulb)
        streak=math.exp(-.5*(angle_delta(theta,a)/local_width)**2)
        r+=amount*shoulder*(.74+.26*bulb)*streak
    return r

# A single closed wax mesh; all streaks are part of its radial surface.
loops=[]
for j in range(73):
    t=j/72
    ring=[]
    for i in range(N):
        a=math.tau*i/N;z=BASE+(top(a)-BASE-.00045)*t;r=outer_radius(a,z)
        ring.append((r*math.cos(a),r*math.sin(a),z))
    loops.append(ring)
# Rounded irregular rim and the sloping cooled melt cavity.
for fraction,drop in [(.997,0),(.975,.00025),(.934,.00090),(.84,.0030),(.66,.0058),(.42,.0071),(.18,.00735),(.065,.00740)]:
    ring=[]
    for i in range(N):
        a=math.tau*i/N;r=(.0225+.0003*math.sin(a*4)) * fraction
        z=top(a)-drop if fraction>.90 else BASE+HEIGHT-drop+(top(a)-BASE-HEIGHT)*fraction**3
        ring.append((r*math.cos(a),r*math.sin(a),z))
    loops.append(ring)
vs=[v for ring in loops for v in ring];bottom=len(vs);vs.append((0,0,BASE));center=len(vs);vs.append((0,0,BASE+HEIGHT-.0074))
fs=[]
for j in range(len(loops)-1):
    for i in range(N):a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
for i in range(N):
    fs.append((bottom,(i+1)%N,i))
    a=(len(loops)-1)*N+i;b=(len(loops)-1)*N+(i+1)%N;fs.append((a,b,center))
body=mesh('Continuous ivory wax body and drips',vs,fs,wax);body.data.materials.append(pool)
for p in body.data.polygons:
    if p.center.z>BASE+HEIGHT-.008 and p.normal.z>.15:p.material_index=1

# A cooled spill at the foot, joined into the candle at its center.
def puddle_radius(a):return .030+.0020*math.sin(3*a+.4)+.0014*math.sin(7*a-.5)+.0008*math.cos(11*a)
vs=[]
for frac,zoff in [(1,.00545),(.985,.00590),(.91,.00655),(.55,.0067),(.20,.0065)]:
    for i in range(N):
        a=math.tau*i/N;r=puddle_radius(a)*frac;vs.append((r*math.cos(a),r*math.sin(a),zoff+.00010*math.sin(a*4)))
mid=len(vs);vs.append((0,0,.0064));under=len(vs);vs.append((0,0,.00525));fs=[]
for j in range(4):
    for i in range(N):a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
for i in range(N):fs.extend([(4*N+i,4*N+(i+1)%N,mid),(under,(i+1)%N,i)])
spill=mesh('Cooled wax spill on the dish',vs,fs,wax)

profile=[(0,.0020),(.025,.0020),(.036,.0019),(.039,.0005),(.0405,0),(.043,0),(.044,.0010),(.044,.0032),(.050,.0045),(.0545,.0068),(.056,.0083),(.0562,.0093),(.0557,.0100),(.0548,.0103),(.0540,.0098),(.0537,.0089),(.050,.0073),(.043,.0064),(.033,.0058),(.020,.00545),(0,.0054)]
def lathe(name,profile,mat,count=128):
    verts=[];rings=[]
    for r,z in profile:
        if r==0:rings.append([len(verts)]);verts.append((0,0,z))
        else:
            ring=[]
            for i in range(count):a=math.tau*i/count;ring.append(len(verts));verts.append((r*math.cos(a),r*math.sin(a),z))
            rings.append(ring)
    faces=[]
    for a,b in zip(rings,rings[1:]):
        for i in range(count):
            j=(i+1)%count
            if len(a)==1:faces.append((a[0],b[j],b[i]))
            elif len(b)==1:faces.append((a[i],a[j],b[0]))
            else:faces.append((a[i],a[j],b[j],b[i]))
    return mesh(name,verts,faces,mat)
tray=lathe('Spun aged brass candle tray with rolled lip',profile,brass)

def tube(name,points,radius,mat,steps=12):
    ps=[Vector(p) for p in points];vs=[]
    for i,p in enumerate(ps):
        tangent=(ps[min(i+1,len(ps)-1)]-ps[max(i-1,0)]).normalized()
        ref=Vector((1,0,0)) if abs(tangent.x)<.95 else Vector((0,1,0));u=tangent.cross(ref).normalized();v=tangent.cross(u).normalized()
        for j in range(steps):a=math.tau*j/steps;vs.append(tuple(p+(u*math.cos(a)+v*math.sin(a))*radius))
    fs=[]
    for i in range(len(ps)-1):
        for j in range(steps):a=i*steps+j;b=i*steps+(j+1)%steps;fs.append((a,b,b+steps,a+steps))
    fs.extend([tuple(reversed(range(steps))),tuple(range((len(ps)-1)*steps,len(ps)*steps))]);return mesh(name,vs,fs,mat)
pool_z=BASE+HEIGHT-.0074
wick_points=[(.0004-.0014*t*t,-.0006+.0003*math.sin(t*math.pi),pool_z-.0007+.0082*t-.0010*t**4) for t in [j/16 for j in range(17)]]
wick=tube('Curved charred cotton wick',wick_points,.00062,wick_mat,16)
for phase in (0,math.pi):
    points=[]
    for i in range(49):
        t=i/48;a=t*math.tau*2+phase;center=Vector((.0004-.0014*t*t,-.0006+.0003*math.sin(t*math.pi),pool_z-.0007+.0082*t-.0010*t**4))
        points.append(tuple(center+Vector((math.cos(a)*.00055,math.sin(a)*.00055,0))))
    tube('Visible twisted cotton fibers',points,.00014,fiber_mat,8)

for o in components:
    clone=o.copy();clone.data=o.data.copy();source_col.objects.link(clone)
bpy.ops.object.select_all(action='DESELECT')
for o in components:o.select_set(True)
bpy.context.view_layer.objects.active=body;bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_Candle'
s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
for layer in list(asset.data.uv_layers):asset.data.uv_layers.remove(layer)
asset.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.005);bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Final game triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
bm=bmesh.new();bm.from_mesh(asset.data);nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free();assert nonmanifold==0,nonmanifold

def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
colliders=[]
def cylindrical_hull(radius,lo,hi):
    name='UCX_SM_Candle_%02d'%len(colliders);points=[]
    for z in (lo,hi):
        for i in range(24):a=math.tau*i/24;points.append((radius*math.cos(a),radius*math.sin(a),z))
    colliders.append(hull(name,points))
cylindrical_hull(.0562,0,.0103)
cylindrical_hull(.0315,.0052,.008)
cylindrical_hull(.0254,.0054,.1495)
cylindrical_hull(.0011,pool_z,.1488)
for c in colliders:c.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_Candle.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
model={'parts':{'SM_Candle':{'filename':'SM_Candle.fbx','dimensions_cm':[d*100 for d in asset.dimensions],'triangles':len(asset.data.polygons),'collision_hulls':len(colliders),'uv_channels':1,'non_manifold_edges':nonmanifold,'material_slots':{m.name:'M_Candle' for m in asset.data.materials}}},
    'texture_sets':{'Candle':{'prefix':'T_Candle',**{ch:'Textures/T_Candle_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal','Metallic')}}},'materials':{'M_Candle':{'texture_set':'Candle'}},
    'assembly':{'candle_and_tray_combined':True,'wick_tip_blender_m':list(wick_points[-1]),'suggested_flame_position_ue_cm':[wick_points[-1][0]*100,-wick_points[-1][1]*100,(wick_points[-1][2]+.001)*100]},
    'wax_body_height_mm':HEIGHT*1000,'wax_nominal_diameter_mm':45,'tray_diameter_mm':112.4,'unlit':True,'emission_strength':0,'exported_lights':0,'exported_cameras':0,'drips_are_continuous_body_surface':True}
for c in colliders:bpy.data.objects.remove(c,do_unlink=True)
for c in list(asset.users_collection):c.objects.unlink(asset)
export_col.objects.link(asset);view=asset.copy();view.data=asset.data;view.name='VIEW_Candle';display_col.objects.link(view)
marker=bpy.data.objects.new('Flame placement - no light',None);source_col.objects.link(marker);marker.location=wick_points[-1];marker.empty_display_size=.005
export_col.hide_viewport=True;export_col.hide_render=True;source_col.hide_viewport=True;source_col.hide_render=True
studio=bpy.data.collections.new('Preview studio - excluded from exports');s.collection.children.link(studio)
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor,p=material('Preview slate',(.043,.054,.064),.82)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.00015));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,0,.071));bpy.ops.object.camera_add(location=(.25,-.34,.23));cam=bpy.context.object;cam.name='Camera_Candle';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.225;cam.data.clip_start=.0001;s.camera=cam;studio_obj(cam)
for name,pos,power,size,col in [('Key',(-.20,-.20,.35),7,.19,(1,.94,.86)),('Fill',(.28,-.05,.25),2.5,.23,(.82,.91,1)),('Rim',(.12,.22,.34),8,.17,(1,.92,.78))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.07,.085,.11,1)
s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1400;s.render.resolution_y=1600;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.25
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Candle_Preview.png');studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');view.select_set(True);bpy.context.view_layer.objects.active=view
(OUT/'model_report.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Candle.blend'));print(json.dumps(model,indent=2))
