import bpy, bmesh, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
scene=bpy.context.scene
if bpy.context.screen and bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_cancel(restore_frame=False)
tassel=bpy.data.objects['TASSEL | 96 physical silk strands']
cl=next(m for m in tassel.modifiers if m.type=='CLOTH')
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1)
root=bpy.data.objects['SWORD_CONTROL | reference design']
if not scene.get('Tassel clearance fix'):
    prefixes=('Chinese knot','Knot lower tie','Polished redwood bead','Bound tassel crown','Tassel wound collar','TASSEL |')
    for o in bpy.data.objects:
        if o.name.startswith(prefixes):o.location.x+=.035; o.location.y-=.025
        elif o.name.startswith('Pommel suspension cord'):
            for sp in o.data.splines:
                for i,p in enumerate(sp.points):
                    t=i/max(1,len(sp.points)-1); p.co.x+=.035*t; p.co.y-=.025*t
    scene['Tassel clearance fix']='35 mm outboard and 25 mm forward; blade/guard collision; rebaked 160 frames'
collision_collection=bpy.data.collections.get('PHYSICS | sword colliders')
if collision_collection is None:
    collision_collection=bpy.data.collections.new('PHYSICS | sword colliders'); scene.collection.children.link(collision_collection)
colliders=[bpy.data.objects[n] for n in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face']]
for ob in colliders:
    if ob.name not in collision_collection.objects:collision_collection.objects.link(ob)
    bm=bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(ob.data); bm.free(); ob.data.update()
    if not any(m.type=='COLLISION' for m in ob.modifiers):ob.modifiers.new('Silk collision surface','COLLISION')
    ob.collision.thickness_outer=.002
    ob.collision.thickness_inner=.001
    ob.collision.cloth_friction=8
cl.settings.quality=12
cl.collision_settings.use_collision=True
cl.collision_settings.collection=collision_collection
cl.collision_settings.distance_min=.0015
cl.collision_settings.collision_quality=8
cl.point_cache.frame_start=1; cl.point_cache.frame_end=160
scene.frame_set(1)
deps=bpy.context.evaluated_depsgraph_get()
bvhs=[]
for ob in colliders:
    ev=ob.evaluated_get(deps); me=ev.to_mesh()
    matrix=root.matrix_world.inverted()@ev.matrix_world
    coords=[matrix@v.co for v in me.vertices]
    bvhs.append((ob.name,BVHTree.FromPolygons(coords,[list(p.vertices) for p in me.polygons],all_triangles=False)))
    ev.to_mesh_clear()
minimum=100; worst_frame=1; penetrations=0; samples={}
for frame in range(1,161):
    scene.frame_set(frame); deps=bpy.context.evaluated_depsgraph_get()
    ev=tassel.evaluated_get(deps); me=ev.to_mesh(); matrix=root.matrix_world.inverted()@ev.matrix_world
    frame_min=100
    for vert in me.vertices[:len(tassel.data.vertices)]:
        co=matrix@vert.co
        for name,bvh in bvhs:
            loc,normal,index,distance=bvh.find_nearest(co)
            signed=distance if (co-loc).dot(normal)>=0 else -distance
            frame_min=min(frame_min,signed)
            if signed<-.0004:penetrations+=1
    if frame_min<minimum:minimum=frame_min; worst_frame=frame
    if frame in [1,48,77,105,132,160]:samples[frame]={'tip_root_space':list(matrix@me.vertices[49].co),'minimum_clearance_m':frame_min}
    ev.to_mesh_clear()
    if frame%40==0:print('COLLISION_CHECK',frame,frame_min,flush=True)
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.bake_from_cache()
report={'frames_checked':160,'penetrating_vertex_samples':penetrations,'minimum_signed_clearance_m':minimum,'worst_frame':worst_frame,'baked':cl.point_cache.is_baked,'samples':samples}
with open(os.path.join(out,'collision_verification.json'),'w') as f:json.dump(report,f,indent=2)
assert penetrations==0,report
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
cam=scene.camera
scene.render.filepath=os.path.join(out,'Reference_Preview.png'); bpy.ops.render.render(write_still=True)
cam.location=(.25,-.8,1.10); cam.rotation_euler=(Vector((.04,0,.88))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=.46
scene.render.resolution_x=1200; scene.render.resolution_y=1300
scene.render.filepath=os.path.join(out,'Collision_Fix_Preview.png'); bpy.ops.render.render(write_still=True)
cam.location=(.8,-3.3,1.4); cam.rotation_euler=(Vector((.025,0,.56))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=1.18
scene.render.resolution_x=1100; scene.render.resolution_y=1500
scene.render.filepath=os.path.join(out,'Reference_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result=report
