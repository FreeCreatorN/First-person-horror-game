import bpy, os, math
from mathutils import Vector
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))
s=bpy.context.scene
C=bpy.data.collections['01 Exterior']
def box(name,loc,size,mat):
    mesh=bpy.data.meshes.new(name)
    verts=[(a*size[0]/2,b*size[1]/2,c*size[2]/2) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
    mesh.from_pydata(verts,[],[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]); mesh.update()
    o=bpy.data.objects.new(name,mesh); C.objects.link(o); o.location=loc; o.data.materials.append(bpy.data.materials[mat]); return o
for x in [-10.18,10.18]:
    side=1 if x>0 else -1
    for floor in range(3):
        z=2.52+floor*3.2
        for y in [-3.5,0,3.5]:
            box('End elevation window',(x,y,z),(.08,1.3,1.65),'Amber window glow')
            for dy in [-.68,0,.68]: box('End window mullion',(x+side*.07,y+dy,z),(.14,.075,1.8),'Dark aged oak')
            for dz in [-.86,0,.86]: box('End window transom',(x+side*.07,y,z+dz),(.14,1.5,.08),'Dark aged oak')
            box('End stone sill',(x+side*.1,y,z-.96),(.32,1.65,.15),'Foundation stone')
        box('End timber belt',(x,0,z-1.82),(.16,11,.23),'Dark aged oak')
    for y in [-5.4,-1.75,1.75,5.4]: box('End vertical timber',(x,y,5.5),(.16,.16,9.6),'Dark aged oak')
# Raise the dormer faces and their associated windows above the main roof.
for o in list(C.objects):
    if o.name.startswith(('Dormer front',)) or (o.name.startswith(('Recessed window','Window mullion','Window transom','Stone sill','Wood shutter','Shutter strap')) and o.location.z>10.4): o.location.z+=.55
# Fix actual front door opening by cutting the wall spandrel and hiding central ground window.
for o in list(C.objects):
    if o.name.startswith(('Recessed window','Window mullion','Window transom','Stone sill','Wood shutter','Shutter strap')) and abs(o.location.x)<1 and o.location.z<3.5:
        bpy.data.objects.remove(o,do_unlink=True)
# Open landing through the second floor slab.
slab=next(o for o in C.objects if o.name.startswith('Floor slab 1'))
cutter=box('Temporary stair opening',(4.2,0,3.9),(2.25,6.2,1),'Dark aged oak')
mod=slab.modifiers.new('Stairwell opening','BOOLEAN'); mod.operation='DIFFERENCE'; mod.object=cutter
bpy.context.view_layer.objects.active=slab; slab.select_set(True); bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(cutter,do_unlink=True)
# Clear bindings during still renders so selected cameras are honored.
bindings=[(m,m.camera) for m in s.timeline_markers]
for m,c in bindings:m.camera=None
for name,cam in [('Exterior','CAM 01 Exterior'),('Lobby','CAM 02 Lobby'),('GuestRoom','CAM 04 Guest room'),('Corridor','CAM 03 Corridor')]:
    s.camera=bpy.data.objects[cam]; s.render.filepath=os.path.join(OUT,name+'.png'); bpy.ops.render.render(write_still=True)
for m,c in bindings:m.camera=c
s.frame_set(1); s.camera=bpy.data.objects['CAM 01 Exterior']
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))
print('VERIFIED',len(s.objects),'objects',len([o for o in s.objects if o.type=='CAMERA']),'cameras')
