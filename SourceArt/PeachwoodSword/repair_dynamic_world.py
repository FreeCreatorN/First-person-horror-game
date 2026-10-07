import bpy, bmesh, os, json
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
scene=bpy.context.scene; world=scene.rigidbody_world
root=bpy.data.objects['SWORD_CONTROL | reference design']
pendant=bpy.data.objects['SUSPENSION | hanging knot body']
tassel=bpy.data.objects['TASSEL | 96 physical silk strands']
cloth=next(m for m in tassel.modifiers if m.type=='CLOTH')
for cache in [world.point_cache,cloth.point_cache]:
    if cache.is_baked:
        with bpy.context.temp_override(point_cache=cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1)
if not scene.get('Raised dynamic demo'):
    root.location.z+=.55
    for ob in bpy.data.collections['PHYSICS | articulated suspension'].objects:
        if ob.parent is None:ob.location.z+=.55
    scene.camera.location.z+=.55
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location.z+=.55
    scene['Raised dynamic demo']=True
    bpy.context.view_layer.update()
for ob in bpy.data.collections['PHYSICS | articulated suspension'].objects:
    if ob.rigid_body and ob.name not in world.collection.objects:world.collection.objects.link(ob)
    if ob.rigid_body_constraint and ob.name not in world.constraints.objects:world.constraints.objects.link(ob)
# The ornament contact hull encloses the actual knot, bead, and tassel crown.
deps=bpy.context.evaluated_depsgraph_get(); verts=[]
for ob in pendant.children:
    if ob==tassel:continue
    ev=ob.evaluated_get(deps); me=ev.to_mesh()
    if me:
        trans=pendant.matrix_world.inverted()@ev.matrix_world
        verts.extend(trans@v.co for v in list(me.vertices)[::max(1,len(me.vertices)//180)])
        ev.to_mesh_clear()
bm=bmesh.new()
for p in verts:bm.verts.new(p)
bm.verts.ensure_lookup_table()
res=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
unused=res.get('geom_interior',[])+res.get('geom_unused',[])
unused=[v for v in unused if isinstance(v,bmesh.types.BMVert) and v.is_valid]
if unused:bmesh.ops.delete(bm,geom=list(set(unused)),context='VERTS')
me=bpy.data.meshes.new('Knot and bead collision hull'); bm.to_mesh(me); bm.free()
pendant.data=me; pendant.rigid_body.collision_shape='CONVEX_HULL'
pendant.rigid_body.collision_margin=.0008
world.substeps_per_frame=20; world.solver_iterations=100
cloth.show_viewport=False
rows=[]; max_gap=0
links=sorted([o for o in bpy.data.objects if o.name.startswith('SUSPENSION | cord link')],key=lambda o:o.name)
for frame in range(1,161):
    scene.frame_set(frame); dg=bpy.context.evaluated_depsgraph_get()
    ev=pendant.evaluated_get(dg)
    # The joint transforms store their pivot in world space at frame 1.
    if frame in [1,40,80,120,160]:rows.append({'frame':frame,'world':list(ev.matrix_world.translation),'sword_space':list(root.matrix_world.inverted()@ev.matrix_world.translation)})
    if frame%40==0:print('RIGID_STEP',frame,list(ev.matrix_world.translation),flush=True)
with bpy.context.temp_override(point_cache=world.point_cache):bpy.ops.ptcache.bake_from_cache()
assert (Vector(rows[0]['world'])-Vector(rows[2]['world'])).length>.1,rows
cloth.show_viewport=True
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
with open(os.path.join(out,'rigid_suspension_verification.json'),'w') as f:json.dump({'samples':rows,'baked':world.point_cache.is_baked,'body_count':len(world.collection.objects),'constraint_count':len(world.constraints.objects)},f,indent=2)
print('RIGID_VERIFIED',json.dumps(rows),flush=True)

