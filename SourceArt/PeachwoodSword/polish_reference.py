import bpy, os
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
for o in bpy.data.objects:
    if o.name.startswith('Cross woven grip wrap'):
        for i in range(0,len(o.data.vertices),2):
            a,b=o.data.vertices[i:i+2]; mid=(a.co.z+b.co.z)/2; a.co.z=mid-.0076; b.co.z=mid+.0076
p=next(n for n in bpy.data.materials['Deep vermilion silk'].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Roughness'].default_value=.72; p.inputs['Sheen Weight'].default_value=.20; p.inputs['Specular IOR Level'].default_value=.22
scene=bpy.context.scene; cam=scene.camera
scene.render.filepath=os.path.join(out,'Reference_Preview.png'); bpy.ops.render.render(write_still=True)
cam.location=(.25,-.8,1.12); cam.rotation_euler=(Vector((.025,0,.915))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=.38
scene.render.resolution_x=1400; scene.render.resolution_y=1200
scene.render.filepath=os.path.join(out,'Reference_Detail.png'); bpy.ops.render.render(write_still=True)
cam.location=(.8,-3.3,1.4); cam.rotation_euler=(Vector((.025,0,.56))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=1.18
scene.render.resolution_x=1100; scene.render.resolution_y=1500
scene.render.filepath=os.path.join(out,'Reference_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result={'saved':bpy.data.filepath}
