import bpy, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
scene=bpy.context.scene; root=bpy.data.objects['SWORD_CONTROL | reference design']
tassel=bpy.data.objects['TASSEL | 96 physical silk strands']; cl=next(m for m in tassel.modifiers if m.type=='CLOTH')
if cl.point_cache.is_baked:
    with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1)
dg=bpy.context.evaluated_depsgraph_get()
colliders=[bpy.data.objects[n] for n in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel','Polished redwood bead']]
local_bvh=[]
for ob in colliders:
    ev=ob.evaluated_get(dg); me=ev.to_mesh()
    local_bvh.append((ob,BVHTree.FromPolygons([v.co.copy() for v in me.vertices],[list(p.vertices) for p in me.polygons])))
    ev.to_mesh_clear()
joints=[]
for ob in scene.rigidbody_world.constraints.objects:
    c=ob.rigid_body_constraint
    if c and c.object1 and c.object2:
        a=c.object1; b=c.object2; p=ob.matrix_world.translation
        joints.append((a,b,a.evaluated_get(dg).matrix_world.inverted()@p,b.evaluated_get(dg).matrix_world.inverted()@p))
rows=[]; minimum=100; min_z=100; max_joint_gap=0; inside=0; max_pin_error=0
pin_indices=[v.index for v in tassel.data.vertices if any(g.group==0 and g.weight>.99 for g in v.groups)]
for frame in range(1,scene.frame_end+1):
    scene.frame_set(frame); dg=bpy.context.evaluated_depsgraph_get()
    for a,b,pa,pb in joints:
        gap=(a.evaluated_get(dg).matrix_world@pa-b.evaluated_get(dg).matrix_world@pb).length
        max_joint_gap=max(max_joint_gap,gap)
    ev=tassel.evaluated_get(dg); me=ev.to_mesh(); matrix=ev.matrix_world
    transforms=[(ob.evaluated_get(dg).matrix_world.inverted(),bvh) for ob,bvh in local_bvh]
    frame_min=100
    for vertex in me.vertices[:len(tassel.data.vertices)]:
        p=matrix@vertex.co; min_z=min(min_z,p.z)
        for inv,bvh in transforms:
            co=inv@p; pos,normal,index,dist=bvh.find_nearest(co)
            if index is None:continue
            signed=dist if (co-pos).dot(normal)>=0 else -dist
            frame_min=min(frame_min,signed)
            if signed<-.0005:inside+=1
    for idx in pin_indices:
        max_pin_error=max(max_pin_error,(matrix@me.vertices[idx].co-matrix@tassel.data.vertices[idx].co).length)
    minimum=min(minimum,frame_min)
    if frame in [1,160,319,478,637]:
        knot=bpy.data.objects['SUSPENSION | hanging knot body'].evaluated_get(dg)
        rows.append({'frame':frame,'knot_world':list(knot.matrix_world.translation),'silk_tip_world':list(matrix@me.vertices[49].co),'clearance':frame_min})
    ev.to_mesh_clear()
    if frame%40==0:print('FULL_PHYSICS',frame,'clearance',frame_min,'inside',inside,'joint_gap',max_joint_gap,flush=True)
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.bake_from_cache()
report={'frames':scene.frame_end,'rope_motion_baked':bpy.data.objects['SUSPENSION | hanging knot body'].animation_data.action is not None,'cloth_baked':cl.point_cache.is_baked,'penetrating_vertex_samples':inside,'minimum_local_clearance':minimum,'maximum_joint_gap_m':max_joint_gap,'maximum_pin_error_m':max_pin_error,'lowest_silk_world_z':min_z,'samples':rows}
with open(os.path.join(out,'full_suspension_verification.json'),'w') as f:json.dump(report,f,indent=2)
assert max_joint_gap<.006,report
assert max_pin_error<.003,report
assert inside==0,report
assert min_z>0,report
scene.frame_set(1)
scene['Suspension physics']='Only the pommel anchor is fixed. An 18-segment length-constrained particle rope suspends the weighted knot/bead/crown assembly; 96 cloth silk strands follow it. Rope actions and cloth cache baked for 637 frames at 120 fps.'
scene['README']='1.015 m sword with 1.8 m reference. Full end-over-end turn about the sword midpoint. Only pommel anchor is fixed. Rope uses a custom particle solver baked to actions; silk uses Blender cloth. Re-run solve_suspension_rope.py followed by bake_full_suspension.py for this demo. Bullet world is disabled.'
cam=scene.camera;cam.data.ortho_scale=1.9
cam.rotation_euler=(Vector((.025,0,1.00))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
scene.render.resolution_x=1100; scene.render.resolution_y=1300
scene.render.filepath=os.path.join(out,'Dynamic_Suspension_Upright.png'); bpy.ops.render.render(write_still=True)
scene.frame_set(319)
scene.render.filepath=os.path.join(out,'Dynamic_Suspension_Inverted.png'); bpy.ops.render.render(write_still=True)
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
print('FINISHED',json.dumps(report),flush=True)

