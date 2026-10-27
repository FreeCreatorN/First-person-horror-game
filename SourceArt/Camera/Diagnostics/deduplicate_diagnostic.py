import bpy, bmesh, json
from pathlib import Path
from collections import Counter
out=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(out.parent/'Camera.blend'))
obj=bpy.data.objects['SM_Camera']
names=list(json.loads((out.parent/'model_report.json').read_text())['parts']['SM_Camera']['material_slots'])
for i,name in enumerate(names):obj.material_slots[i].material=bpy.data.materials[name]
mesh=obj.data
bm=bmesh.new();bm.from_mesh(mesh)
seen={};dupes=[]
for f in bm.faces:
    key=(f.material_index,tuple(sorted(tuple(round(float(a),9) for a in v.co) for v in f.verts)))
    if key in seen:dupes.append(f)
    else:seen[key]=f
report={'before':len(bm.faces),'duplicate_faces':len(dupes),'unique_faces':len(seen),'source_component_objects':len(bpy.data.collections['SOURCE - individual components'].objects)}
bmesh.ops.delete(bm,geom=dupes,context='FACES_ONLY')
loose=[v for v in bm.verts if not v.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
bm.to_mesh(mesh);bm.free();mesh.update()
report['after']=len(mesh.polygons)
(out/'dedup_report.json').write_text(json.dumps(report,indent=2))
scene=bpy.context.scene;scene.cycles.samples=16
scene.render.resolution_percentage=60
scene.render.filepath=str(out/'Camera_Deduplicated_Source.png')
bpy.ops.render.render(write_still=True)
print('CAMERA_DEDUP',json.dumps(report),flush=True)
