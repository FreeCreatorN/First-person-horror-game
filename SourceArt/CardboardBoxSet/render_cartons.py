import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CardboardBoxSet.blend'));s=bpy.context.scene
s.render.resolution_x=1800;s.render.resolution_y=1150;s.cycles.device='CPU';s.cycles.samples=28
for filename,camera in [('CardboardBoxSet_Overview.png','01 Carton set overview'),('CardboardBoxSet_Open.png','02 Open carton closeup'),('CardboardBoxSet_Handle.png','03 Storage handle closeup')]:
    s.camera=bpy.data.objects[camera];s.render.filepath=str(ROOT/filename);bpy.ops.render.render(write_still=True);print('RENDERED',filename,flush=True)
