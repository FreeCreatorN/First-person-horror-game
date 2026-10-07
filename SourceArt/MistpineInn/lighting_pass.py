import bpy,os
from mathutils import Vector
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))
s=bpy.context.scene
for o in s.objects:
    if o.name.startswith('Corridor carpet'): o.location.z=4.03
d=bpy.data.lights.new('Guest room soft warm bounce','AREA'); d.energy=160; d.color=(1,.71,.43); d.shape='DISK'; d.size=2.5
o=bpy.data.objects.new(d.name,d); bpy.data.collections['03 Guest corridor and rooms'].objects.link(o); o.location=(6,-3.8,6.65)
bindings=[(m,m.camera) for m in s.timeline_markers]
for m,c in bindings:m.camera=None
for name,cam in [('GuestRoom','CAM 04 Guest room'),('Corridor','CAM 03 Corridor')]:
    s.camera=bpy.data.objects[cam]; s.render.filepath=os.path.join(OUT,name+'.png'); bpy.ops.render.render(write_still=True)
for m,c in bindings:m.camera=c
s.frame_set(1); s.camera=bpy.data.objects['CAM 01 Exterior']; bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))
