import bpy,bmesh
from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\Clipboard')
bpy.ops.wm.open_mainfile(filepath=str(p/'Clipboard.blend'))
c=bpy.data.collections['SOURCE - individual components'];c.hide_viewport=False
bpy.context.view_layer.update()
for o in c.objects:
 ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles()
 bad=sum(t.area<1e-14 for t in me.loop_triangles)
 if bad:print('DEGENERATE_COMPONENT',o.name,bad,len(me.loop_triangles),flush=True)
 ev.to_mesh_clear()
