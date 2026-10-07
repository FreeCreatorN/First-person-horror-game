import bpy,math,random,os
from mathutils import Vector
random.seed(71)
s=bpy.context.scene;out=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn';C=bpy.data.collections.new('08 Guest room furnishings');s.collection.children.link(C)
wood=bpy.data.materials['Dark aged oak'];brass=bpy.data.materials['Aged brass'];linen=bpy.data.materials['Ivory linen'];red=bpy.data.materials['Burgundy carpet']
def mesh(name,v,f,m):
 d=bpy.data.meshes.new(name);d.from_pydata(v,[],f);d.update();o=bpy.data.objects.new(name,d);C.objects.link(o);o.data.materials.append(m);return o
def box(name,loc,size,m):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);b=o.modifiers.new('Small crafted edges','BEVEL');b.width=.008;b.segments=2;return o
def rod(name,a,b,r,m):
 a,b=Vector(a),Vector(b);bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=r,depth=(b-a).length,location=(a+b)/2);o=bpy.context.object;o.name=name;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();o.data.materials.append(m);return o
# Reduce the rigid egg-crate ripple and give the fabric localized folds.
blank=bpy.data.objects['Draped burgundy bedspread']
for vert in blank.data.vertices:
 x,y=vert.co.x,vert.co.y;dx=x-6.2;edge=max(0,abs(dx)-.87)
 fold=.009*math.sin(dx*13+y*4)+.007*math.sin(y*18+dx*7)
 fold+=.020*math.exp(-((y+3.92)/.14)**2)*math.sin(dx*6+1)
 vert.co.z=4.85-edge*2.55+fold
p=next(n for n in red.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Roughness'].default_value=.94;p.inputs['Specular IOR Level'].default_value=.16;p.inputs['Sheen Weight'].default_value=.18
# Woven grain, no broad glossy plastic highlights.
for m in [linen,red]:
 for n in m.node_tree.nodes:
  if n.type=='BUMP':n.inputs['Distance'].default_value=.00045;n.inputs['Strength'].default_value=.13
# Soft curtains beside two real front windows.
curtain=linen.copy();curtain.name='Heavy muted flax curtains';p=next(n for n in curtain.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Roughness'].default_value=.98
for cx in [5.35,8.0]:
 rod('Curtain pole',(cx-.95,-5.20,6.80),(cx+.95,-5.20,6.80),.028,brass)
 for side in [-1,1]:
  v=[];f=[];nu=20;nv=36
  for j in range(nv+1):
   t=j/nv;z=6.70-t*2.55
   for i in range(nu+1):
    u=i/nu;x=cx+side*(.45+u*.48+.08*math.sin(t*math.pi));y=-5.14+.065*math.sin(u*math.tau*4)+.018*math.sin(t*5+u*12)
    v.append((x,y,z+.016*math.cos(u*17)*t))
  for j in range(nv):
   for i in range(nu):a=j*(nu+1)+i;f.append((a,a+1,a+nu+2,a+nu+1))
  o=mesh('Gathered linen curtain',v,f,curtain)
  for p in o.data.polygons:p.use_smooth=True
  so=o.modifiers.new('Curtain cloth thickness','SOLIDIFY');so.thickness=.008
# Carved headboard spindles and brass finials.
for x in [5.2,7.2]:
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=10,radius=.085,location=(x,-1.98,5.77));o=bpy.context.object;o.name='Bedpost brass finial';o.data.materials.append(brass)
for x in [5.45,5.7,5.95,6.2,6.45,6.7,6.95]:rod('Headboard spindle',(x,-2.08,4.9),(x,-2.08,5.5),.02,brass)
# Trunk metal corner caps, lock and leather straps.
for x in [5.58,6.82]:
 for z in [4.08,4.61]:box('Trunk corner plate',(x,-4.889,z),(.14,.025,.14),brass)
box('Trunk latch',(6.2,-4.904,4.44),(.13,.035,.22),brass)
rod('Trunk carry handle',(6.04,-4.96,4.31),(6.36,-4.96,4.31),.026,wood)
# Artwork above the headboard, as framed geometry rather than a blank wall.
paint=wood.copy();paint.name='Muted mountain painting';paint.diffuse_color=(.06,.09,.085,1)
p=next(n for n in paint.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.06,.09,.085,1)
box('Guest landscape panel',(6.2,-1.41,6.16),(1.65,.04,.68),paint)
for x in [5.33,7.07]:box('Painting vertical frame',(x,-1.46,6.16),(.065,.065,.80),brass)
for z in [5.77,6.55]:box('Painting horizontal frame',(6.2,-1.46,z),(1.8,.065,.065),brass)
for k in range(3):
 mat=paint.copy();mat.name='Guest landscape ridge '+str(k)
 p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.09-k*.02,.115-k*.015,.10-k*.012,1)
 v=[(5.4,-1.437-k*.005,5.84),(7,-1.437-k*.005,5.84)]
 v.extend([(7-i*.1,-1.437-k*.005,6.12+random.random()*.25-k*.10) for i in range(17)])
 mesh('Guest mountain silhouette',v,[tuple(range(len(v)))],mat)
# A narrow writing desk by the window, with legs and an openable-looking drawer.
box('Window writing desk',(4.05,-4.35,4.75),(.70,1.1,.08),wood)
for x in [3.80,4.30]:
 for y in [-4.77,-3.93]:rod('Desk leg',(x,y,3.99),(x,y,4.72),.035,wood)
box('Writing paper',(4.06,-4.40,4.796),(.32,.40,.005),linen)
rod('Desk pen',(3.97,-4.64,4.805),(4.17,-4.58,4.805),.008,brass)
# Camera sees both the bed and the window treatment.
cam=bpy.data.objects['CAM 04 Guest room'];cam.location=(8.48,-1.72,5.60);cam.rotation_euler=(Vector((5.75,-3.9,5.0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=22
s.frame_set(31);s.camera=cam
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'MistpineInn_Refined.blend'))
s.render.filepath=os.path.join(out,'GuestRoom_LiveRefinement.png');s.cycles.samples=24;bpy.ops.render.render(write_still=True)
print('GUEST_ROOM_SAVED',len(s.objects))
