import bpy
from mathutils import Vector
p=r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser/'
bpy.ops.wm.open_mainfile(filepath=p+'WaterDispenser_Fitted.blend')
s=bpy.context.scene;s.camera.location=(3,-.7,1.15);s.camera.rotation_euler=(Vector((0,0,.66))-s.camera.location).to_track_quat('-Z','Y').to_euler();s.render.engine='BLENDER_WORKBENCH';s.display.shading.color_type='MATERIAL';s.render.resolution_percentage=65;s.render.filepath=p+'Side_Fit_Check.png';bpy.ops.render.render(write_still=True)

