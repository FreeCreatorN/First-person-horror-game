import bpy,json
from pathlib import Path
out=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(out/'Camera.blend'))
obj=bpy.data.objects['SM_Camera'];names=list(json.loads((out/'model_report.json').read_text())['parts']['SM_Camera']['material_slots'])
for i,name in enumerate(names):obj.material_slots[i].material=bpy.data.materials[name]
obj.data.normals_split_custom_set([(0.,0.,0.)]*len(obj.data.loops))
bpy.context.scene.cycles.samples=16
bpy.context.scene.render.filepath=str(out/'Camera_NormalCheck.png')
bpy.ops.render.render(write_still=True)
