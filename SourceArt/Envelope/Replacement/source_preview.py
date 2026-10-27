import bpy
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\Envelope\Replacement')
bpy.ops.wm.open_mainfile(filepath=str(out/'EnvelopeSet.blend'))
s=bpy.context.scene
s.cycles.samples=12;s.render.resolution_percentage=65
s.render.filepath=str(out/'Source_Check.png')
bpy.ops.render.render(write_still=True)
