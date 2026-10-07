import bpy, math, random, os, json
from mathutils import Vector
random.seed(18)
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection': bpy.data.collections.remove(c)
def collection(name):
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c
C=collection('01 Exterior')
def put(o,name):
    o.name=name
    for c in list(o.users_collection): c.objects.unlink(o)
    C.objects.link(o); return o
def mat(name,color,rough=.6,noise=0,metal=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    n=m.node_tree.nodes; p=next(nod for nod in n if nod.type=='BSDF_PRINCIPLED'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal
    if noise:
        t=n.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value=noise
        r=n.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].color=(*(v*.35 for v in color),1); r.color_ramp.elements[1].color=(*color,1)
        m.node_tree.links.new(t.outputs['Fac'],r.inputs[0]); m.node_tree.links.new(r.outputs[0],p.inputs['Base Color'])
        b=n.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.28; b.inputs['Distance'].default_value=.08; m.node_tree.links.new(t.outputs['Fac'],b.inputs['Height']); m.node_tree.links.new(b.outputs[0],p.inputs['Normal'])
    return m
plaster=mat('Weathered warm plaster',(.48,.43,.33),noise=5)
wood=mat('Dark aged oak',(.12,.065,.028),noise=7)
trim=mat('Carved walnut',(.23,.12,.05),noise=4)
stone=mat('Foundation stone',(.22,.25,.25),noise=12)
slate=mat('Blue slate',(.085,.13,.16),noise=18)
brass=mat('Aged brass',(.48,.29,.08),.3,3,.7)
red=mat('Burgundy carpet',(.19,.025,.028),noise=35)
wallpaper=mat('Faded olive wallpaper',(.29,.27,.15),noise=9)
linen=mat('Ivory linen',(.65,.57,.42),noise=35)
glass=mat('Amber window glow',(.75,.36,.08),.25)
p=next(nod for nod in glass.node_tree.nodes if nod.type=='BSDF_PRINCIPLED'); p.inputs['Emission Color'].default_value=(1,.48,.13,1); p.inputs['Emission Strength'].default_value=.65
def box(name,loc,scale,m,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=put(bpy.context.object,name); o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if m:o.data.materials.append(m)
    if bevel: mod=o.modifiers.new('Soft worn edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('Normals','WEIGHTED_NORMAL')
    return o
def beam(name,a,b,width,m):
    a,b=Vector(a),Vector(b); o=box(name,(a+b)/2,(width,width,(b-a).length),m); o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler(); return o
def text(name,body,loc,size,m,rot=(math.pi/2,0,0)):
    bpy.ops.object.text_add(location=loc,rotation=rot); o=put(bpy.context.object,name); o.data.body=body; o.data.align_x='CENTER'; o.data.size=size; o.data.extrude=.008; o.data.materials.append(m); return o
def light(name,loc,power,color=(1,.61,.28),size=1):
    d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.color=color; d.shape='DISK'; d.size=size; o=bpy.data.objects.new(name,d); C.objects.link(o); o.location=loc; return o
def camera(name,loc,target,lens=35):
    d=bpy.data.cameras.new(name); o=bpy.data.objects.new(name,d); C.objects.link(o); o.location=loc; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); d.lens=lens; d.clip_end=300; return o
def roof(cx,cy,z,w,depth,rise):
    for side in [-1,1]:
        o=box('Slate roof pitch',(cx,cy+side*depth/4,z+rise/2),(w,math.hypot(depth/2,rise),.16),slate); o.rotation_euler.x=-side*math.atan2(rise,depth/2)
        for x in [cx-w/2,cx+w/2]: beam('Roof bargeboard',(x,cy,z+rise),(x,cy+side*depth/2,z),.18,wood)
    beam('Ridge cap',(cx-w/2,cy,z+rise+.06),(cx+w/2,cy,z+rise+.06),.18,slate)
def window(x,y,z,w=1.15,h=1.65):
    box('Recessed window',(x,y,z),(w,.1,h),glass)
    for dx in [-w/2,0,w/2]: box('Window mullion',(x+dx,y-.09,z),(.075,.13,h+.17),wood)
    for dz in [-h/2,0,h/2]: box('Window transom',(x,y-.09,z+dz),(w+.17,.14,.075),wood)
    box('Stone sill',(x,y-.13,z-h/2-.1),(w+.3,.35,.13),stone)
    for dx in [-w*.72,w*.72]:
        box('Wood shutter',(x+dx,y,z),(.34,.12,h),wood)
        for dz in [-.5,.5]: box('Shutter strap',(x+dx,y-.08,z+dz),(.32,.035,.06),brass)
# Full scale shell: front faces -Y, 20m wide x 11m deep.
box('Stone plinth',(0,0,.35),(20.6,11.6,.7),stone,.08)
for floor in range(3):
    z=.7+floor*3.2
    box('Floor slab '+str(floor),(0,0,z),(20,11,.2),wood)
    # Front wall pieces leave real window openings.
    box('Front lower spandrel',(0,-5.5,z+.5),(20,.28,1),plaster)
    box('Front upper spandrel',(0,-5.5,z+2.91),(20,.28,.58),plaster)
    xs=[-8,-5.35,-2.7,0,2.7,5.35,8]
    edges=[-10]+[v for x in xs for v in (x-.65,x+.65)]+[10]
    for i in range(0,len(edges)-1,2):
        a,b=edges[i:i+2]; box('Front pier',((a+b)/2,-5.5,z+1.82),(b-a,.28,1.64),plaster)
    for x in xs: window(x,-5.67,z+1.82,1.3,1.64)
    box('Rear wall',(0,5.5,z+1.6),(20,.28,3.2),plaster)
    for x in [-10,10]: box('End wall',(x,0,z+1.6),(.28,11,3.2),plaster)
    for y in [-5.72,5.7]: box('Continuous timber belt',(0,y,z),(20.3,.18,.24),wood)
for x in [-9.9,-6.65,-1.35,1.35,6.65,9.9]: box('Facade vertical timber',(x,-5.73,5.45),(.17,.15,9.7),wood)
roof(0,0,10.3,21.3,12.4,3.4)
for x in [-10,10]:
    mesh=bpy.data.meshes.new('Gable'); mesh.from_pydata([(x,-5.5,10.3),(x,5.5,10.3),(x,0,13.35)],[],[(0,1,2)]); o=bpy.data.objects.new('Plaster gable',mesh); C.objects.link(o); o.data.materials.append(plaster)
for x in [-6.7,0,6.7]:
    box('Dormer front',(x,-3.9,11.3),(2,.2,1.9),plaster); window(x,-4.04,11.4,.8,1.2); roof(x,-3.2,12.2,2.7,2.6,1)
for x in [-7,6]:
    box('Chimney',(x,1,12.9),(.95,.95,3.8),stone,.04); box('Chimney crown',(x,1,14.8),(1.2,1.2,.25),stone)
# Entrance porch and steps.
box('Porch platform',(0,-7,.65),(7.4,3.4,.35),stone)
for i in range(4): box('Entrance step',(0,-9.2+i*.38,.12+i*.14),(4.8,1.1,.24+i*.28),stone,.03)
for x in [-3.3,3.3]:
    for y in [-8.35,-5.9]: box('Porch oak post',(x,y,2.35),(.23,.23,3.4),wood,.025)
# porch ridge runs along Y
for side in [-1,1]:
    o=box('Porch pitched roof',(side*1.95,-7.1,4.45),(math.hypot(3.9,1.5),3.9,.15),slate); o.rotation_euler.y=side*math.atan2(1.5,3.9)
for s in [-1,1]: beam('Porch front truss',(0,-9.05,5.2),(s*3.9,-9.05,3.7),.22,wood)
box('Entry double door',(0,-5.88,1.9),(1.7,.2,2.4),wood,.03)
for x in [-.43,.43]:
    box('Door glass',(x,-6.01,2.28),(.61,.04,1.13),glass); box('Door handle',(x/3,-6.08,1.63),(.055,.1,.28),brass)
text('Facade hotel name','MISTPINE INN',(0,-5.91,7.0),.53,wood)
for x in [-2.3,2.3]:
    box('Porch lantern',(x,-6,2.65),(.22,.24,.4),glass); light('Entrance amber',(x,-6.7,3.1),100)
box('Roadside sign post',(-6.7,-10.4,2.1),(.2,.2,4.2),wood)
box('Signboard',(-5.7,-10.45,3.1),(1.9,.18,1.3),wood,.06)
text('Inn sign','MISTPINE\nINN',(-5.7,-10.56,3.22),.29,linen)
# Interiors on real floors, separately organized for editing.
C=collection('02 Lobby and reception')
box('Lobby rug',(-1,-1.5,.83),(5.4,5,.045),red)
for x in [-2.55, .55]: box('Rug border',(x,-1.5,.86),(.045,4.9,.015),brass)
box('Reception counter',(-4.3,.5,1.4),(4.8,.9,1.25),wood,.05)
box('Polished counter top',(-4.3,.5,2.07),(5,1.05,.14),trim,.04)
for x in [-6,-4.4,-2.8]: box('Counter raised panel',(x,-.0,1.42),(1.35,.08,.84),trim,.02)
box('Reception backdrop',(-4.3,2.3,2.3),(5,.18,3.1),wallpaper)
for x in range(9):
    for z in range(4):
        box('Key cubby',(-6.2+x*.48,2.12,1.5+z*.43),(.42,.22,.36),wood)
        box('Key tag',(-6.2+x*.48,1.98,1.5+z*.43),(.04,.025,.14),brass)
text('Reception label','RECEPTION',(-4.3,-.07,1.55),.24,brass)
def lamp(x,y,z):
    box('Lamp base',(x,y,z),(.28,.28,.07),brass,.03); beam('Lamp stem',(x,y,z),(x,y,z+.5),.045,brass)
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.3,radius2=.15,depth=.3,location=(x,y,z+.55)); put(bpy.context.object,'Linen lampshade').data.materials.append(linen); light('Lamplight',(x,y,z+.45),45,size=.4)
lamp(-5.8,.4,2.17)
for i in range(18):
    box('Stair tread',(4.2,-2.9+i*.32,.88+i*.177),(2,.34,.18),trim)
    for x in [3.24,5.16]: beam('Stair baluster',(x,-2.9+i*.32,1+i*.177),(x,-2.9+i*.32,2+i*.177),.045,wood)
for x in [3.24,5.16]: beam('Stair handrail',(x,-2.9,2),(x,2.54,5.01),.1,trim)
def chair(x,y,z):
    box('Chair seat',(x,y,z+.48),(.75,.75,.16),red,.08); box('Chair back',(x,y+.32,z+.98),(.75,.14,.95),wood,.06)
    for a in [-.28,.28]:
        for b in [-.28,.28]: box('Chair leg',(x+a,y+b,z+.22),(.075,.075,.45),wood)
for x in [-8,-6.7]: chair(x,-3.1,.8)
for x in [-9.4,9.4]:
    box('Lobby wainscot',(x,0,1.3),(.15,10,1.0),wood)
    for y in range(-4,5): box('Wall panel stile',(x-.12,y,1.3),(.08,.045,.85),trim)
for x in [-2,2]: light('Lobby ceiling warm',(x,-1,3.6),220,size=2)
beam('Chandelier chain',(0,-1,3.8),(0,-1,2.9),.035,brass)
for i in range(6):
    a=i*math.tau/6; x,y=math.cos(a)*.75,-1+math.sin(a)*.75; beam('Chandelier arm',(0,-1,2.9),(x,y,2.9),.035,brass); box('Chandelier candle',(x,y,3.04),(.07,.07,.25),glass)
cam_lobby=camera('CAM 02 Lobby',(1,-4.9,2.25),(-2,1,1.95),23)
C=collection('03 Guest corridor and rooms')
base=3.98
box('Corridor carpet',(0,0,base),(18,2,.035),red)
for y in [-1.3,1.3]:
    box('Hall partition',(0,y,5.48),(19,.16,3.05),wallpaper)
    box('Hall skirting',(0,y-.11,4.25),(19,.08,.48),wood)
    for x in [-7,-3,1,5,8]:
        yy=y+(.11 if y<0 else -.11)
        box('Guest door',(x,yy,5.12),(1.12,.08,2.3),wood,.025)
        for z in [4.63,5.48]: box('Door inset panel',(x,yy+(.06 if y<0 else -.06),z),(.86,.04,.65),trim,.015)
        box('Door brass knob',(x+.4,yy+(.08 if y<0 else -.08),5.0),(.08,.08,.1),brass)
        if y>0: text('Room number',str(201+int((x+7)/2)),(x,yy-.08,6.04),.16,brass)
    for x in [-8,-4,0,4,8]:
        box('Wall sconce',(x,y*.89,5.95),(.16,.16,.3),glass)
for x in [-7,-2,3,7]: light('Corridor pools',(x,0,6.65),95,size=.6)
box('Second floor ceiling',(0,0,7.0),(19.7,10.8,.12),plaster)
cam_hall=camera('CAM 03 Corridor',(-9.2,0,5.5),(8,0,5.4),23)
# Furnished front guest room with visible exterior window.
for x in [3.5,8.8]: box('Guest room partition',(x,-3.45,5.47),(.15,4,3.0),wallpaper)
box('Bed frame',(6.2,-3.1,4.35),(1.9,2.3,.38),wood,.07)
box('Mattress',(6.2,-3.1,4.65),(1.85,2.2,.3),linen,.12)
box('Burgundy quilt',(6.2,-3.55,4.84),(1.89,1.35,.13),red,.06)
box('Headboard',(6.2,-1.96,4.99),(2,.16,1.45),wood,.08)
for x in [5.75,6.65]: box('Pillow',(x,-2.35,4.9),(.72,.46,.17),linen,.08)
for x in [4.65,7.75]:
    box('Bedside cabinet',(x,-2.2,4.4),(.65,.6,.85),trim,.035); lamp(x,-2.2,4.86)
box('Travel trunk',(6.2,-4.6,4.35),(1.4,.55,.65),wood,.06)
for x in [5.7,6.7]: box('Trunk strap',(x,-4.89,4.35),(.07,.03,.6),brass)
cam_room=camera('CAM 04 Guest room',(3.85,-5,5.65),(6.3,-2.5,4.9),22)
C=collection('04 Landscape')
ground=mat('Rain soaked earth',(.055,.08,.068),.75,5)
road=mat('Wet asphalt',(.065,.075,.083),.21,30)
pine=mat('Pine needles',(.035,.085,.065),noise=12)
box('Forest ground',(0,0,-.18),(150,150,.3),ground)
box('Wet roadside',(0,-14,-.005),(110,7,.08),road)
for i in range(65):
    x=random.uniform(-42,42); y=random.uniform(10,40)
    if i<18: x=random.choice([-1,1])*random.uniform(17,35); y=random.uniform(-9,18)
    h=random.uniform(9,19); beam('Pine trunk',(x,y,0),(x,y,h),.22,wood)
    for j in range(4):
        bpy.ops.mesh.primitive_cone_add(vertices=9,radius1=h*.18*(1-j*.17),radius2=0,depth=h*.47,location=(x,y,h*.4+j*h*.16)); put(bpy.context.object,'Pine crown').data.materials.append(pine)
for i in range(45):
    x=random.uniform(-18,18); y=random.choice([random.uniform(-11,-9.6),random.uniform(6,10)])
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=random.uniform(.15,.6),location=(x,y,.15)); o=put(bpy.context.object,'Roadside rock'); o.scale=(1.5,1,.65); o.data.materials.append(stone)
C=collection('05 Cameras and lighting')
cam_ext=camera('CAM 01 Exterior',(27,-36,17),(0,-.8,5.5),42)
camera('CAM 05 Architectural overview',(25,-30,28),(0,0,4),45)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.use_denoising=True
scene.world.color=(.15,.15,.15); scene.world.use_nodes=True; next(nod for nod in scene.world.node_tree.nodes if nod.type=='BACKGROUND').inputs[0].default_value=(.22,.32,.48,1); next(nod for nod in scene.world.node_tree.nodes if nod.type=='BACKGROUND').inputs[1].default_value=.35
l=light('Moon softbox',(-10,-6,24),2600,(.55,.71,1),18)
l=light('Facade blue fill',(4,-18,12),1700,(.64,.75,1),14); l.rotation_euler=(Vector((0,0,5))-l.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=1200; scene.render.resolution_y=850; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.camera=cam_ext
scene.unit_settings.system='METRIC'
for name,cam in [('Exterior',cam_ext),('Lobby',cam_lobby),('Corridor',cam_hall),('GuestRoom',cam_room)]:
    marker=scene.timeline_markers.new(name,frame=len(scene.timeline_markers)*10+1); marker.camera=cam
scene.frame_set(1)
# Embed the design reference for portability.
ref=r'C:\Users\aa131\.codex\generated_images\01a089c2-bd6a-7ca3-a7bb-4865d4b2bc70\exec-3fa7951e-feb4-42bf-b7b2-65ec162e3ae3.png'
if os.path.exists(ref): bpy.data.images.load(ref).pack()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'; area.spaces.active.clip_end=500
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))
with open(os.path.join(OUT,'scene_manifest.json'),'w') as f: json.dump({'objects':len(scene.objects),'cameras':[o.name for o in scene.objects if o.type=='CAMERA'],'collections':[c.name for c in bpy.data.collections]},f,indent=2)
for name,cam in [('Exterior',cam_ext),('Lobby',cam_lobby),('GuestRoom',cam_room),('Corridor',cam_hall)]:
    scene.camera=cam; scene.render.filepath=os.path.join(OUT,name+'.png'); bpy.ops.render.render(write_still=True)
scene.camera=cam_ext
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'MistpineInn.blend'))

