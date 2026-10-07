import bpy, os, json
o=bpy.data.objects['TASSEL | 48 simulated silk strands']
c=next(m for m in o.modifiers if m.type=='CLOTH')
r={'saved_cache_baked':c.point_cache.is_baked,'vertices':len(o.data.vertices),'frames':{}}
for f in [1,75,130]:
    bpy.context.scene.frame_set(f)
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh(); r['frames'][f]=list(me.vertices[37].co); ev.to_mesh_clear()
print('SAVED_FILE_VERIFICATION',json.dumps(r))
assert c.point_cache.is_baked
assert abs(r['frames'][75][0]-r['frames'][1][0])>.05
