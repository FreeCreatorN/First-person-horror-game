import bpy, json
o=bpy.data.objects['TASSEL | 96 physical silk strands']
c=next(m for m in o.modifiers if m.type=='CLOTH')
assert c.point_cache.is_baked
positions=[]
for f in [1,77]:
    bpy.context.scene.frame_set(f)
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh(); positions.append(list(me.vertices[49].co)); ev.to_mesh_clear()
assert abs(positions[0][0]-positions[1][0])>.025
print('VERIFIED_SAVED_REFERENCE',json.dumps({'baked':True,'positions':positions,'objects':len(bpy.data.objects)}))
