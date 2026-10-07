import bpy,os
s=bpy.context.scene;s.frame_set(215);s.render.resolution_x=900;s.render.resolution_y=900;s.cycles.samples=20;s.render.filepath=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword\Slash_Preview.png'
bpy.ops.render.render(write_still=True)
s.frame_set(1)
result={'preview':s.render.filepath}
