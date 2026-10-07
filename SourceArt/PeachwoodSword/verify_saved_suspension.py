import bpy,json
s=bpy.context.scene;t=bpy.data.objects['TASSEL | 96 physical silk strands'];cl=next(m for m in t.modifiers if m.type=='CLOTH')
assert cl.point_cache.is_baked
assert s.frame_end==637
assert not s.rigidbody_world.enabled
positions=[]
for f in [1,319,637]:
 s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
 knot=bpy.data.objects['SUSPENSION | hanging knot body'].evaluated_get(dg)
 positions.append(list(knot.matrix_world.translation))
assert positions[1][2]<positions[0][2]-.6
print('SAVED_SUSPENSION_VALID',json.dumps({'cloth_baked':True,'frames':637,'knot_positions':positions}))
