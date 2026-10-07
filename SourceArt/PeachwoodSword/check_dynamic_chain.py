import bpy, json
from mathutils import Vector
s=bpy.context.scene; root=bpy.data.objects['SWORD_CONTROL | reference design']; pendant=bpy.data.objects['SUSPENSION | hanging knot body']
rows=[]
for f in [1,40,80,120,160]:
    s.frame_set(f); dg=bpy.context.evaluated_depsgraph_get()
    ob=pendant.evaluated_get(dg)
    rows.append({'frame':f,'world':list(ob.matrix_world.translation),'sword_space':list(root.matrix_world.inverted()@ob.matrix_world.translation),'tassel_origin':list(bpy.data.objects['TASSEL | 96 physical silk strands'].evaluated_get(dg).matrix_world.translation)})
s.frame_set(1)
result=rows
print(json.dumps(rows))
