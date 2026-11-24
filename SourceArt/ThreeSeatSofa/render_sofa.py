import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'ThreeSeatSofa.blend'))
S=bpy.data.scenes['ThreeSeatSofa'];bpy.context.window.scene=S
S.render.resolution_x=1800;S.render.resolution_y=1200;S.render.resolution_percentage=100
S.cycles.samples=40;S.cycles.use_denoising=True
for camera,output in [('01 Sofa hero','Sofa_Hero.png'),('02 Sofa rear','Sofa_Rear.png'),('03 Sofa front','Sofa_Front.png')]:
    S.camera=S.objects[camera];S.render.filepath=str(ROOT/output);bpy.ops.render.render(write_still=True);print('RENDERED',output,flush=True)
