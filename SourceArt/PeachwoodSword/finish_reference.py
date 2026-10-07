import bpy, math, os
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
core=bpy.data.objects['Handle wood core']
v=[]; f=[]; n=64
for z in [-.101,.101]:
    v.extend([(.0155*math.cos(i*math.tau/n),.0125*math.sin(i*math.tau/n),z) for i in range(n)])
f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
me=bpy.data.meshes.new('Oval wrapped grip core'); me.from_pydata(v,[],f); me.update(); me.materials.append(bpy.data.materials['Dark brown woven grip']); core.data=me
for p in me.polygons:
    if len(p.vertices)==4:p.use_smooth=True
scene=bpy.context.scene; cam=scene.camera
def aim(p):cam.rotation_euler=(Vector(p)-cam.location).to_track_quat('-Z','Y').to_euler()
cam.location=(.8,-3.3,1.4); aim((.025,0,.56)); cam.data.ortho_scale=1.18
scene.render.resolution_x=1100; scene.render.resolution_y=1500
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
scene.render.filepath=os.path.join(out,'Reference_Preview.png'); bpy.ops.render.render(write_still=True)
cam.location=(.25,-.8,1.12); aim((.025,0,.915)); cam.data.ortho_scale=.38
scene.render.resolution_x=1400; scene.render.resolution_y=1200
scene.render.filepath=os.path.join(out,'Reference_Detail.png'); bpy.ops.render.render(write_still=True)
cam.location=(.8,-3.3,1.4); aim((.025,0,.56)); cam.data.ortho_scale=1.18
scene.render.resolution_x=1100; scene.render.resolution_y=1500
scene.render.filepath=os.path.join(out,'Reference_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result={'file':bpy.data.filepath,'grip_fixed':True}
