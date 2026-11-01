"""Small actual-render animation preview from the saved skinned source."""
import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Notebook.blend'))
s=bpy.context.scene;s.render.resolution_x=750;s.render.resolution_y=600;s.cycles.samples=8
camera=s.camera;camera.location=(.08,-.34,.52);camera.rotation_euler=(Vector((0,0,.025))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.405
folder=OUT/'PreviewFrames';folder.mkdir(exist_ok=True)
frames=list(range(1,142,3))
for index,frame in enumerate(frames):
    s.frame_set(frame);s.render.filepath=str(folder/f'{index:03d}.png');bpy.ops.render.render(write_still=True)
(OUT/'PreviewFrames'/'frames.json').write_text(json.dumps({'source_frames':frames,'fps':10,'last_source_frame':frames[-1]}),encoding='utf-8')
print('NOTEBOOK_PREVIEW_FRAMES_READY',len(frames),flush=True)
