"""Truthful images of the revised saved animation, no manual pose override."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;OUT=HERE.parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Notebook.blend'))
s=bpy.context.scene;s.cycles.samples=10;s.render.resolution_x=900;s.render.resolution_y=720
camera=s.camera;camera.location=(.08,-.34,.52);camera.rotation_euler=(Vector((0,0,.025))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.405
for name,frame in [('Pickup',77),('Rollover',91),('Landing',103)]:
    s.frame_set(frame);s.render.filepath=str(HERE/f'Natural_{name}.png');bpy.ops.render.render(write_still=True)
if '--stills-only' not in sys.argv:
    s.cycles.samples=8;s.render.resolution_x=750;s.render.resolution_y=600
    folder=HERE/'PreviewFrames';folder.mkdir(exist_ok=True)
    frames=list(range(61,152,2))
    for i,frame in enumerate(frames):
        s.frame_set(frame);s.render.filepath=str(folder/f'{i:03d}.png');bpy.ops.render.render(write_still=True)
    (folder/'frames.json').write_text(json.dumps({'source_frames':frames,'fps':15,'source':'saved animation; no pose overrides'}),encoding='utf-8')
print('NATURAL_FLIP_PREVIEW_RENDERED',flush=True)
