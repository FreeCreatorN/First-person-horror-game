import bpy, math, os, json
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
scene=bpy.context.scene
if bpy.context.screen and bpy.context.screen.is_animation_playing:bpy.ops.screen.animation_cancel(restore_frame=False)
root=bpy.data.objects['SWORD_CONTROL | reference design']
tassel=bpy.data.objects['TASSEL | 96 physical silk strands']
cloth=next(m for m in tassel.modifiers if m.type=='CLOTH')
with bpy.context.temp_override(point_cache=cloth.point_cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1); bpy.context.view_layer.update()
assert bpy.data.objects.get('SUSPENSION | hanging knot body') is None, 'Suspension already created'
red=bpy.data.materials['Deep vermilion silk']
physics=bpy.data.collections.new('PHYSICS | articulated suspension'); scene.collection.children.link(physics)
visual=bpy.data.collections.new('CORD | physical braided links'); scene.collection.children.link(visual)
def move_collection(o,c):
    for old in list(o.users_collection):old.objects.unlink(o)
    c.objects.link(o)
def body(name,loc,radius,length,mass,rotation=None,passive=False):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=loc)
    ob=bpy.context.object; ob.name=name; ob.scale=(radius,radius,max(radius,length/2))
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if rotation is not None:ob.rotation_euler=rotation
    bpy.ops.rigidbody.object_add(); ob.rigid_body.type='PASSIVE' if passive else 'ACTIVE'
    ob.rigid_body.collision_shape='CAPSULE' if length>radius*2 else 'SPHERE'
    ob.rigid_body.mass=mass; ob.rigid_body.use_margin=True; ob.rigid_body.collision_margin=.0004
    ob.rigid_body.friction=.4; ob.rigid_body.restitution=0
    ob.rigid_body.linear_damping=.1; ob.rigid_body.angular_damping=.3
    ob.rigid_body.use_deactivation=False
    ob.display_type='WIRE'; ob.hide_render=True; move_collection(ob,physics)
    return ob
def keep_parent(ob,parent):
    matrix=ob.matrix_world.copy(); ob.parent=parent; ob.matrix_parent_inverse=parent.matrix_world.inverted(); ob.matrix_world=matrix
def joint(name,a,b,loc):
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=loc); ob=bpy.context.object; ob.name=name; ob.empty_display_size=.004
    bpy.ops.rigidbody.constraint_add(); c=ob.rigid_body_constraint; c.type='POINT'; c.object1=a; c.object2=b; c.disable_collisions=True
    move_collection(ob,physics)
def cord_curve(name,coords,radius,parent):
    cu=bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.bevel_depth=radius; cu.bevel_resolution=3
    sp=cu.splines.new('POLY'); sp.points.add(len(coords)-1)
    for p,co in zip(sp.points,coords):p.co=(*co,1)
    ob=bpy.data.objects.new(name,cu); visual.objects.link(ob); ob.data.materials.append(red); ob.parent=parent
    return ob
old=bpy.data.objects['Pommel suspension cord']
points=[old.matrix_world@Vector(p.co[:3]) for p in old.data.splines[0].points]
# Sample the existing curved cord into 18 short, freely jointed links.
nodes=[]
for i in range(19):
    u=i/18*(len(points)-1); lo=int(u); hi=min(lo+1,len(points)-1); nodes.append(points[lo].lerp(points[hi],u-lo))
anchor=body('SUSPENSION | fixed pommel attachment',nodes[0],.0015,.003,1,passive=True)
anchor.rigid_body.kinematic=True; keep_parent(anchor,root)
for j in range(20):anchor.rigid_body.collision_collections[j]=(j==1)
links=[]
for i,(a,b) in enumerate(zip(nodes,nodes[1:])):
    length=(b-a).length; rotation=(b-a).to_track_quat('Z','Y').to_euler()
    link=body('SUSPENSION | cord link %02d'%i,(a+b)/2,.0017,length,.0012,rotation)
    # Links embedded in the drilled attachment are exempt from sword contact.
    if i<3:
        for j in range(20):link.rigid_body.collision_collections[j]=(j==1)
    links.append(link); joint('Cord ball joint %02d'%i,anchor if i==0 else links[i-1],link,a)
    cord_curve('Braided rope core %02d'%i,[(0,0,-length/2-.0004),(0,0,length/2+.0004)],.00155,link)
    for k in range(3):
        coords=[]
        for j in range(33):
            t=j/32; angle=t*math.tau*2+k*math.tau/3
            coords.append((.0012*math.cos(angle),.0012*math.sin(angle),(t-.5)*length))
        cord_curve('Braided rope thread %02d %d'%(i,k),coords,.00052,link)
ornament_names=('Chinese knot','Knot lower tie','Polished redwood bead','Bound tassel crown','Tassel wound collar')
ornaments=[o for o in bpy.data.objects if o.name.startswith(ornament_names)]
center=root.matrix_world@Vector((.115,-.030,.139+.2275))
pendant=body('SUSPENSION | hanging knot body',center,.016,.100,.023)
pendant.rigid_body.collision_shape='CAPSULE'
joint('Cord to weighted knot',links[-1],pendant,nodes[-1])
for ob in ornaments+[tassel]:keep_parent(ob,pendant)
for ob in list(bpy.data.objects):
    if ob.name.startswith('Pommel suspension cord'):bpy.data.objects.remove(ob,do_unlink=True)
# Sword surfaces participate in both rigid-body contact and cloth contact.
for name in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel']:
    ob=bpy.data.objects[name]; bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active=ob
    if ob.rigid_body is None:bpy.ops.rigidbody.object_add()
    ob.rigid_body.type='PASSIVE'; ob.rigid_body.kinematic=True; ob.rigid_body.collision_shape='MESH'
    ob.rigid_body.use_margin=True; ob.rigid_body.collision_margin=.001
world=scene.rigidbody_world; world.substeps_per_frame=12; world.solver_iterations=80
world.point_cache.frame_start=1; world.point_cache.frame_end=160
cloth.settings.quality=16; cloth.collision_settings.collision_quality=12
# Pass one: bake the articulated rope and weighted ornament.
cloth.show_viewport=False
for f in range(1,161):scene.frame_set(f)
with bpy.context.temp_override(point_cache=world.point_cache):bpy.ops.ptcache.bake_from_cache()
cloth.show_viewport=True
scene.frame_set(1)
scene['Suspension physics']='18 rigid articulated rope links, weighted knot/bead assembly, fixed pommel anchor only; cloth tassel follows moving ornament. Rigid bodies baked before cloth.'
scene['Animation demo']='One full end-over-end turn around the sword center; fully moving suspension and silk tassel.'
bpy.ops.object.select_all(action='DESELECT'); root.select_set(True); bpy.context.view_layer.objects.active=root
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result={'rope_links':len(links),'rigid_body_cache':world.point_cache.is_baked,'next':'cloth bake and collision check'}
