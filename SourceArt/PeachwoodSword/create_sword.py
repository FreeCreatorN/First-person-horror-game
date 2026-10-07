import bpy, math, os, json
from mathutils import Vector
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection': bpy.data.collections.remove(c)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.render.resolution_x=1200
scene.render.resolution_y=1400
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.22,.22,.22)
scene.frame_end=160
scene.render.fps=30
def mat(name,col,metal=0,rough=.45):
    m=bpy.data.materials.new(name); m.diffuse_color=(*col,1); m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'); p.inputs['Base Color'].default_value=(*col,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return m
wood=mat('Peach wood | longitudinal grain',(.34,.105,.045))
n=wood.node_tree.nodes; l=wood.node_tree.links; p=next(q for q in n if q.type=='BSDF_PRINCIPLED')
tex=n.new('ShaderNodeTexCoord'); mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(9,9,.45); l.new(tex.outputs['Generated'],mapping.inputs[0])
noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=5; noise.inputs['Detail'].default_value=3; l.new(mapping.outputs[0],noise.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.22; ramp.color_ramp.elements[0].color=(.065,.013,.006,1); ramp.color_ramp.elements[1].position=.8; ramp.color_ramp.elements[1].color=(.49,.19,.066,1); l.new(noise.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],p.inputs['Base Color'])
bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.16; bump.inputs['Distance'].default_value=.0004; l.new(noise.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs[0],p.inputs['Normal'])
dark=mat('Burnished dark wood',(.052,.012,.007)); gold=mat('Muted brass bindings',(.39,.21,.06),.65,.3)
red=mat('Deep vermilion silk',(.36,.008,.019),0,.38); next(q for q in red.node_tree.nodes if q.type=='BSDF_PRINCIPLED').inputs['Sheen Weight'].default_value=.55
grey=mat('Scale mannequin clay',(.13,.19,.21)); floor=mat('Studio charcoal',(.019,.028,.032))
bpy.ops.object.empty_add(); root=bpy.context.object; root.name='SWORD_CONTROL | animated grip'; root.location=(0,0,.52)
def mesh(name,verts,faces,material,parent=root):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update(); ob=bpy.data.objects.new(name,me); scene.collection.objects.link(ob); ob.data.materials.append(material)
    if parent: ob.parent=parent
    return ob
def bevel(ob,width=.002):
    m=ob.modifiers.new('Soft carved edges','BEVEL'); m.width=width; m.segments=3
    ob.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
def cube(name,loc,scale,material,parent=root):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material); o.parent=parent; bevel(o); return o
def sphere(name,loc,scale,material,parent=root):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(material); o.parent=parent
    for p in o.data.polygons:p.use_smooth=True
    return o
def curve(name,coords,radius,material,parent=root):
    cu=bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.bevel_depth=radius; cu.bevel_resolution=3
    sp=cu.splines.new('POLY'); sp.points.add(len(coords)-1)
    for p,co in zip(sp.points,coords): p.co=(*co,1)
    o=bpy.data.objects.new(name,cu); scene.collection.objects.link(o); o.data.materials.append(material); o.parent=parent; return o
# Diamond cross section: 70 cm blade, 24 cm hilt assembly.
verts=[]
for z,w,t in [(.24,.028,.009),(.29,.031,.009),(.78,.025,.0065),(.87,.018,.0045),(.94,.0006,.0008)]:
    verts.extend([(-w,0,z),(0,-t,z),(w,0,z),(0,t,z)])
faces=[(3,2,1,0)]
for i in range(4):
    for j in range(4):faces.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
faces.append((16,17,18,19))
blade=mesh('Blade | solid peach wood 700 mm',verts,faces,wood); bevel(blade,.0007)
cube('Grip | 165 mm oval wood handle',(0,0,.125),(.032,.025,.165),wood)
cube('Pommel carved block',(0,0,.023),(.049,.034,.046),wood)
for z in [.047,.202]:cube('Brass narrow collar',(0,0,z),(.036,.029,.007),gold)
# Swept traditional wooden guard.
outline=[(-.077,.209),(-.075,.238),(-.045,.251),(-.024,.242),(.024,.242),(.045,.251),(.075,.238),(.077,.209),(.045,.222),(-.045,.222)]
v=[(x,y,z) for y in [-.017,.017] for x,z in outline]; N=len(outline)
f=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
guard=mesh('Swept peachwood crossguard',v,f,wood); bevel(guard,.003)
cube('Guard center dark plaque',(0,-.018,.232),(.039,.004,.031),dark)
# Seven-star motif on both faces, with fine scorched connecting lines.
stars=[(-.010,.36),(.009,.408),(-.007,.46),(.01,.505),(-.009,.563),(.006,.62),(0,.674)]
for side in [-1,1]:
    curve('Seven star etched path',[(x,side*(.009-abs(x)*.27+.0004),z) for x,z in stars],.0006,dark)
    for x,z in stars:sphere('Seven star brass pin',(x,side*(.009-abs(x)*.27+.0006),z),(.0019,.0008,.0019),gold)
for z in [.074+i*.014 for i in range(8)]:
    curve('Grip carved ring',[(.0165*math.cos(a*math.tau/48),.013*math.sin(a*math.tau/48),z) for a in range(49)],.00065,dark)
# Pommel loop and decorative Chinese knot.
curve('Red suspension loop',[(.011*math.sin(i*math.tau/64),-.007,.004-.036*(1-math.cos(i*math.tau/64))) for i in range(65)],.0025,red)
for sign in [-1,1]:
    curve('Interlaced knot',[(sign*.013*math.sin(i*math.tau/96),-.007+.003*math.sin(2*i*math.tau/96),-.079+.018*math.cos(i*math.tau/96)) for i in range(97)],.0032,red)
sphere('Tassel head', (0,-.007,-.103),(.012,.012,.018),red)
for z in [-.095,-.109]:curve('Tassel gold thread',[(.012*math.cos(i*math.tau/64),-.007+.012*math.sin(i*math.tau/64),z) for i in range(65)],.0009,gold)
# Each silk strand is a narrow cloth ribbon; top two rows are pinned.
v=[]; f=[]; pins=[]
for k in range(48):
    a=k*math.tau/48; radial=.0085+(k%3)*.001
    length=.255+.015*math.sin(k*2.4); base=len(v)
    for row in range(19):
        t=row/18; rr=radial+t*.006; cx=rr*math.cos(a); cy=-.007+rr*math.sin(a)
        for s in [-1,1]:v.append((cx+s*.0009*math.cos(a+.7),cy+s*.0009*math.sin(a+.7),-.113-length*t))
        if row<2:pins.extend([base+2*row,base+2*row+1])
        if row<18:f.append((base+2*row,base+2*row+1,base+2*row+3,base+2*row+2))
tassel=mesh('TASSEL | 48 simulated silk strands',v,f,red)
vg=tassel.vertex_groups.new(name='Pinned attachment'); vg.add(pins,1,'REPLACE')
cl=tassel.modifiers.new('Silk cloth physics | pinned roots','CLOTH'); st=cl.settings
st.quality=8; st.mass=.035; st.vertex_group_mass=vg.name; st.tension_stiffness=18; st.compression_stiffness=18; st.shear_stiffness=8; st.bending_stiffness=.08; st.air_damping=3
cl.collision_settings.use_self_collision=False
cl.point_cache.frame_start=1; cl.point_cache.frame_end=160
sol=tassel.modifiers.new('Silk thickness','SOLIDIFY'); sol.thickness=.00035
for frame,ang in [(1,0),(25,0),(48,-22),(75,25),(103,-15),(130,7),(160,0)]:
    root.rotation_euler[1]=math.radians(ang); root.keyframe_insert(data_path='rotation_euler',frame=frame)
# Adult 1.8 m proportion reference, separate collection.
ref=bpy.data.collections.new('REFERENCE | 1.80 m adult male'); scene.collection.children.link(ref)
def reference(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    ref.objects.link(o); return o
def limb(name,a,b,r):
    mid=(Vector(a)+Vector(b))/2
    o=sphere(name,mid,(r,r,(Vector(b)-Vector(a)).length/2+r),grey,None)
    o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler(); reference(o)
x=.65
reference(sphere('Head | crown at 1.80 m',(x,0,1.685),(.079,.087,.115),grey,None))
reference(sphere('Thorax',(x,0,1.37),(.205,.105,.235),grey,None)); reference(sphere('Pelvis',(x,0,1.02),(.145,.103,.13),grey,None))
limb('Neck',(x,0,1.51),(x,0,1.60),.055)
for s in [-1,1]:
    limb('Upper leg',(x+s*.085,0,1.00),(x+s*.10,0,.56),.073); limb('Lower leg',(x+s*.10,0,.56),(x+s*.11,0,.12),.05)
    reference(sphere('Foot',(x+s*.11,-.052,.06),(.055,.115,.06),grey,None))
    limb('Upper arm',(x+s*.22,0,1.47),(x+s*.285,0,1.17),.052); limb('Forearm',(x+s*.285,0,1.17),(x+s*.30,-.01,.92),.039)
    reference(sphere('Hand',(x+s*.30,-.01,.855),(.04,.03,.08),grey,None))
cube('Studio floor',(0,0,-.025),(200,200,.04),floor,None)
def aim(o,point):o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(1.45,-3.7,1.9)); cam=bpy.context.object; cam.name='Camera | sword portrait'; aim(cam,(0,0,.86)); cam.data.type='ORTHO'; cam.data.ortho_scale=1.6; scene.camera=cam
for name,loc,power,size in [('Key',(-2,-3,3),450,2),('Rim',(1,1,2.4),600,1.7),('Fill',(2,-1,1),130,1.5)]:
    bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; aim(o,(0,0,.8))
scene.frame_set(1)
for o in ref.objects:o.hide_render=True
bpy.ops.object.select_all(action='DESELECT'); root.select_set(True); bpy.context.view_layer.objects.active=root
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=2.5; area.spaces.active.region_3d.view_location=(.25,0,.9)
            area.spaces.active.clip_end=300
scene['README']='Metric: sword 0.94m, adult reference 1.80m. Play frames 1-160 from frame 1. Root control has a swing demo. Tassel uses real pinned cloth. Blender physics is not exported to Unreal automatically.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'PeachwoodSword.blend'))
# Bake and measure real deformation before delivering.
positions={}
for frame in range(1,161):
    scene.frame_set(frame)
    if frame in [1,75,130]:
        dg=bpy.context.evaluated_depsgraph_get(); ev=tassel.evaluated_get(dg); me=ev.to_mesh(); positions[frame]=list(me.vertices[37].co); ev.to_mesh_clear()
    if frame%40==0:print('SIMULATION',frame,flush=True)
with bpy.context.temp_override(point_cache=cl.point_cache): bpy.ops.ptcache.bake_from_cache()
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'PeachwoodSword.blend'))
with open(os.path.join(OUT,'verification.json'),'w') as file:json.dump({'strand_tip_local_positions':positions,'sword_length_m':.94,'reference_height_m':1.8,'cache_baked':cl.point_cache.is_baked},file,indent=2)
scene.render.filepath=os.path.join(OUT,'Sword_Preview.png'); bpy.ops.render.render(write_still=True)
for o in ref.objects:o.hide_render=False
cam.location=(2.3,-5,2.5); aim(cam,(.34,0,.9)); cam.data.ortho_scale=2.14
scene.render.filepath=os.path.join(OUT,'Scale_Preview.png'); bpy.ops.render.render(write_still=True)
print('DONE',flush=True)

