import bpy, os
from mathutils import Vector
out=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(out,'PeachwoodSword.blend'))
scene=bpy.context.scene
scene.frame_set(1)
guard=bpy.data.objects['Swept peachwood crossguard']
# Rounded, symmetrical ends with no pointed downward corner.
outline=[(-.074,.216),(-.077,.222),(-.075,.235),(-.070,.241),(-.045,.250),(-.024,.242),(.024,.242),(.045,.250),(.070,.241),(.075,.235),(.077,.222),(.074,.216),(.068,.215),(.043,.223),(-.043,.223),(-.068,.215)]
n=len(outline)
v=[(x,y,z) for y in [-.017,.017] for x,z in outline]
f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
me=bpy.data.meshes.new('Rounded guard solid'); me.from_pydata(v,[],f); me.update()
for m in guard.data.materials:me.materials.append(m)
guard.data=me
for mod in guard.modifiers:
    if mod.type=='BEVEL':mod.width=.0035; mod.segments=5
# Extend the upper grip into the guard, while keeping its lower end fixed.
grip=bpy.data.objects['Grip | 165 mm oval wood handle']
for vert in grip.data.vertices:
    if vert.co.z>0:vert.co.z+=.022
grip.name='Grip | continuous joint into guard'
for ob in bpy.data.objects:
    if ob.name.startswith('Brass narrow collar') and ob.location.z>.15:ob.location.z=.218
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.overlay.show_relationship_lines=False
            area.spaces.active.overlay.show_extras=False
scene['Guard revision']='Rounded guard ends; grip extends into guard; upper collar seated below guard.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_v2.blend'))
cam=scene.camera
cam.location=(.24,-.65,.85)
cam.rotation_euler=(Vector((0,0,.73))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale=.26
scene.render.resolution_x=1200; scene.render.resolution_y=1000
scene.render.filepath=os.path.join(out,'Guard_v2_Preview.png')
bpy.ops.render.render(write_still=True)
cloth=next(m for m in bpy.data.objects['TASSEL | 48 simulated silk strands'].modifiers if m.type=='CLOTH')
assert cloth.point_cache.is_baked
print('VERIFIED: grip upper end',max(v.co.z for v in grip.data.vertices)+grip.location.z,'guard center bottom',.223,'cloth baked',cloth.point_cache.is_baked)
