import bpy
from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\Clipboard')
bpy.ops.wm.open_mainfile(filepath=str(p/'Clipboard.blend'))
s=bpy.context.scene;s.cycles.samples=12;s.render.resolution_percentage=65;s.render.filepath=str(p/'Source_Check.png')
bpy.ops.render.render(write_still=True)
