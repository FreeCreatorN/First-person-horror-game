from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\Clipboard')
exec(compile((p/'build.py').read_text(encoding='utf-8-sig').split('assets={};parts={}')[0],str(p/'build.py'),'exec'))
for group,objects in groups.items():
 for o in objects:
  ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();bm=bmesh.new();bm.from_mesh(me)
  count=sum(not e.is_manifold for e in bm.edges)
  if count:print('BAD_COMPONENT',group,o.name,count,flush=True)
  bm.free();ev.to_mesh_clear()
