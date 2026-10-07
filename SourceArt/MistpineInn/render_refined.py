import bpy,os
s=bpy.context.scene;s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior'];s.render.filepath=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn\Refined_Exterior.png';bpy.ops.render.render(write_still=True)
print(s.render.filepath)
