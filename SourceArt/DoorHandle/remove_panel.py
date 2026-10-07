import bpy
from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\DoorHandle')
bpy.ops.wm.open_mainfile(filepath=str(p/'DoorHandle.blend'))
o=bpy.data.objects.get('Preview door panel')
if o:bpy.data.objects.remove(o,do_unlink=True)
bpy.context.scene.render.film_transparent=True
bpy.context.scene.render.filepath=str(p/'DoorHandle_NoPanel.png')
bpy.ops.wm.save_as_mainfile(filepath=str(p/'DoorHandle.blend'))
bpy.ops.render.render(write_still=True)
