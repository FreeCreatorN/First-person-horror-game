import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'SnackIceCreamSet.blend'));s=bpy.context.scene
s.render.resolution_x=2000;s.render.resolution_y=1500;s.cycles.samples=32;s.cycles.device='CPU'
for filename,cam in [('Goods_Overview.png','01 Goods overview'),('Goods_IceCream.png','02 Ice cream details'),('Goods_Snacks.png','03 Snack details')]:
    s.camera=bpy.data.objects[cam];s.render.filepath=str(ROOT/filename);bpy.ops.render.render(write_still=True);print('RENDERED',filename,flush=True)
