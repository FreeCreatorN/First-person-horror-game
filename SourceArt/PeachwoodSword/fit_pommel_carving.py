import bpy,os,json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
s=bpy.context.scene
if bpy.context.screen and bpy.context.screen.is_animation_playing:bpy.ops.screen.animation_cancel(restore_frame=False)
saved_frame=s.frame_current;s.frame_set(1)
root=bpy.data.objects['SWORD_CONTROL | reference design'];target=bpy.data.objects['Round cloud-carved pommel']
dg=bpy.context.evaluated_depsgraph_get();ev=target.evaluated_get(dg);me=ev.to_mesh()
world_to_root=root.matrix_world.inverted();target_matrix=world_to_root@ev.matrix_world
bvh=BVHTree.FromPolygons([target_matrix@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]);ev.to_mesh_clear()
center=world_to_root@target.matrix_world.translation
changed=[];count=0;max_depth=0
for ob in list(bpy.data.objects):
 if ob.type!='CURVE' or not ob.name.startswith(('Pommel carved border','Cloud scroll recessed line','Cloud scroll raised edge')):continue
 matrix=world_to_root@ob.matrix_world
 points=[matrix@Vector(p.co[:3]) for sp in ob.data.splines for p in sp.points]
 if not points or not all(abs(p.z-center.z)<.036 and abs(p.x-center.x)<.034 for p in points):continue
 inverse=matrix.inverted();is_dark=ob.name.startswith('Cloud scroll recessed')
 ob.data.bevel_depth=.00048 if is_dark else .00058
 for sp in ob.data.splines:
  for p in sp.points:
   co=matrix@Vector(p.co[:3]);side=1 if co.y>center.y else -1
   start=Vector((co.x,center.y+side*.1,co.z));direction=Vector((0,-side,0))
   hit,normal,idx,distance=bvh.ray_cast(start,direction,.2)
   assert idx is not None,(ob.name,list(co))
   # Embed each round carving stroke into the actual faceted wood surface.
   inset=.00031 if is_dark else .00025
   fitted=hit-normal*inset;local=inverse@fitted;p.co=(*local,1)
   max_depth=max(max_depth,(co-fitted).length);count+=1
 changed.append(ob.name)
assert len(changed)==14,changed
report={'objects_fitted':len(changed),'curve_points_projected':count,'largest_correction_m':max_depth,'maximum_relief_above_surface_m':.00033}
s['Pommel carving']='Both faces conformed to the actual curved wood mesh. Stroke centers embedded; relief approximately 0.33 mm.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
cam=s.camera;old_matrix=cam.matrix_world.copy();old_scale=cam.data.ortho_scale;old_res=(s.render.resolution_x,s.render.resolution_y);old_path=s.render.filepath
aim=target.matrix_world.translation
cam.location=aim+Vector((.17,-.24,.025));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.105
s.render.resolution_x=1100;s.render.resolution_y=1000;s.render.filepath=os.path.join(out,'Pommel_Carving_Fitted.png')
bpy.ops.render.render(write_still=True)
cam.matrix_world=old_matrix;cam.data.ortho_scale=old_scale;s.render.resolution_x,s.render.resolution_y=old_res;s.render.filepath=old_path
s.frame_set(saved_frame)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result=report
