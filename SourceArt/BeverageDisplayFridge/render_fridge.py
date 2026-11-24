import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'BeverageDisplayFridge.blend'))
s=bpy.context.scene
assert s.name=='BeverageDisplayFridge'
s.render.resolution_x=1100;s.render.resolution_y=1400;s.render.resolution_percentage=100
s.cycles.samples=28;s.cycles.device='CPU'
for tag,frame,cam in [('Front',1,'01 Beverage fridge front45'),('Open',70,'02 Beverage fridge open')]:
    s.frame_set(frame);s.camera=bpy.data.objects[cam]
    s.render.filepath=str(ROOT/('BeverageDisplayFridge_'+tag+'.png'))
    bpy.ops.render.render(write_still=True)
    print('RENDERED',tag,flush=True)
