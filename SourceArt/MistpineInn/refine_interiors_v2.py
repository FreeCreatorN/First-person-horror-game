import bpy,math,random,os,json
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn';s=bpy.context.scene
C=bpy.data.collections.new('07 Interior craftsmanship');s.collection.children.link(C)
wood=bpy.data.materials['Dark aged oak'];trim=bpy.data.materials['Carved walnut'];brass=bpy.data.materials['Aged brass'];linen=bpy.data.materials['Ivory linen'];red=bpy.data.materials['Burgundy carpet']
def mesh(name,v,f,m):
 d=bpy.data.meshes.new(name);d.from_pydata(v,[],f);d.update();o=bpy.data.objects.new(name,d);C.objects.link(o)
 if m:d.materials.append(m)
 return o
def box(name,loc,dim,m):
 v=[(a*dim[0]/2,b*dim[1]/2,c*dim[2]/2) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
 o=mesh(name,v,[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)],m);o.location=loc;return o
def beam(name,a,b,w,m=wood):
 a,b=Vector(a),Vector(b);o=box(name,(a+b)/2,(w,w,(b-a).length),m);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o
def frame(name,x,y,z,w,h,m=trim):
 for xx in [x-w/2,x+w/2]:box(name,(xx,y,z),(.07,.06,h),m)
 for zz in [z-h/2,z+h/2]:box(name,(x,y,zz),(w,.06,.07),m)
def mat(name,col):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(*col,1);return m
# Use the installed CLI's generated torus geometry in the actual scene.
source=open(os.path.join(out,'cli_details.py'),encoding='utf-8-sig').read();start=source.index('# Object: CLI brass chandelier ring');end=source.index('Object Parenting',start);chunk=source[start:end];chunk=chunk[:chunk.rfind('\n')]
exec(compile(chunk,'cli_chandelier','exec'))
o=bpy.context.object;o.data.materials.append(brass)
for c in list(o.users_collection):c.objects.unlink(o)
C.objects.link(o)
# Pendant fixtures: linen shades instead of floating rectangular candles.
for o in list(bpy.data.objects):
 if o.name.startswith('Chandelier candle'):bpy.data.objects.remove(o,do_unlink=True)
for i in range(6):
 a=i*math.tau/6;x,y=math.cos(a)*.75,-1+math.sin(a)*.75
 bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.13,radius2=.07,depth=.24,location=(x,y,3.13));o=bpy.context.object;o.name='Chandelier linen shade';o.data.materials.append(linen)
# Real key pigeonholes with a dark backing, shelves and small hanging tags.
for o in list(bpy.data.objects):
 if o.name.startswith('Key cubby'):bpy.data.objects.remove(o,do_unlink=True)
box('Key cabinet backing',(-4.28,2.16,2.14),(4.42,.12,1.82),wood)
for i in range(10):box('Key rack upright',(-6.45+i*.48,1.99,2.14),(.04,.27,1.82),trim)
for i in range(5):box('Key rack shelf',(-4.28,1.98,1.285+i*.43),(4.4,.30,.045),trim)
# Raised joinery on reception desk and skirting.
for x in [-6,-4.4,-2.8]:
 frame('Reception panel molding',x,-.07,1.42,1.38,.87)
 frame('Reception inset bead',x,-.11,1.42,1.20,.68,brass)
for z in [.86,1.94]:box('Counter horizontal molding',(-4.3,-.11,z),(4.85,.13,.08),trim)
for x in [-6.62,-5.2,-3.6,-2]:box('Counter fluted stile',(x,-.12,1.42),(.10,.10,1.07),wood)
# Planked timber flooring, seams no longer look like a flat plastic plane.
for level in [.815,3.955]:
 for j in range(42):
  y=-5.35+j*.255
  for i in range(7):
   x=-9.7+i*2.85+(j%2)*.3
   if level>1 and abs(y)<1.05:continue
   box('Oak floorboard',(x,y,level),(2.82,.247,.025),trim if (i+j)%5==0 else wood)
# Lobby wall paneling behind the stairs and reception.
wall=bpy.data.materials['Faded olive wallpaper']
box('Back lobby wallpaper',(0,5.27,2.35),(19.5,.09,2.95),wall)
for z in [1.12,1.69,3.58]:box('Lobby dado and cornice',(0,5.13,z),(19.5,.17,.10),trim)
for x in range(-9,10):
 frame('Back wall panel',x,5.12,1.17,.87,.84)
for y in [-4,-1,2,5]:box('Ceiling oak beam',(0,y,3.70),(19.8,.17,.20),wood)
# Stair runner and substantial newels.
for i in range(18):
 box('Stair carpet tread',(4.2,-2.9+i*.32,.979+i*.177),(1.30,.31,.018),red)
 box('Stair carpet riser',(4.2,-3.065+i*.32,.902+i*.177),(1.30,.016,.145),red)
for x in [3.24,5.16]:
 for y,z in [(-2.9,1.5),(2.54,4.51)]:
  box('Turned newel base',(x,y,z),(.22,.22,1.25),wood)
  bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.16,location=(x,y,z+.68));bpy.context.object.name='Newel finial';bpy.context.object.data.materials.append(trim)
# Framed landscape above reception: layered mountain silhouettes.
paint=mat('Painting dusk',(.10,.12,.12));box('Landscape canvas',(-4.3,2.06,3.19),(2.2,.025,.56),paint);frame('Landscape gilt frame',-4.3,2.015,3.19,2.3,.66,brass)
for layer in range(3):
 v=[(-5.37,2.02-layer*.005,2.94),(-3.23,2.02-layer*.005,2.94)]
 v += [(-3.23-i*.214,2.02-layer*.005,3.06+random.random()*.22-layer*.04) for i in range(11)]
 mesh('Painting mountain ridge',v,[tuple(range(len(v)))],mat('Painting ridge '+str(layer),(.045+layer*.008,.068,.063)))
# Desk props give the reception a readable use and scale.
for i in range(3):
 o=box('Guest register',(-3.0+i*.025,.37,2.17+i*.045),(.46,.34,.04),red if i==0 else linen);o.rotation_euler.z=.12
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.10,location=(-4,.05,2.23));o=bpy.context.object;o.name='Reception bell';o.scale.z=.5;o.data.materials.append(brass)
beam('Bell button',(-4,.05,2.25),(-4,.05,2.32),.027,brass)
# Carpet borders and repeating woven geometric motifs.
for x in [-3.55,1.55]:box('Lobby rug woven border',(x,-1.5,.863),(.09,4.8,.004),linen)
for y in [-3.87,.87]:box('Lobby rug woven border',(-1,y,.863),(5.15,.09,.004),linen)
for j in range(7):
 for i in range(6):
  x=-3.2+i*.87;y=-3.4+j*.64;r=.15
  o=mesh('Rug woven medallion',[(x-r,y,.869),(x,y+r,.869),(x+r,y,.869),(x,y-r,.869)],[(0,1,2,3)],trim)
for y in [-.92,.92]:box('Hall runner border',(0,y,4.004),(17.7,.065,.005),linen)
# Hall door surrounds and head moldings.
for y in [-1.3,1.3]:
 yy=y+(.19 if y<0 else -.19)
 for x in [-7,-3,1,5,8]:
  frame('Guest door architrave',x,yy,5.12,1.28,2.48)
  box('Guest door lintel',(x,yy,6.39),(1.5,.17,.11),trim)
# Guest room: replace the slab blanket with a draped, creased textile.
for o in list(bpy.data.objects):
 if o.name.startswith('Burgundy quilt'):bpy.data.objects.remove(o,do_unlink=True)
v=[];f=[];nx=48;ny=36
for j in range(ny+1):
 y=-4.28+j/ny*1.55
 for i in range(nx+1):
  dx=-1.11+i/nx*2.22;drop=max(0,abs(dx)-.88)*2.7
  z=4.85-drop+.024*math.sin(dx*24+y*8)+.012*math.cos(y*36+dx*3)
  v.append((6.2+dx,y,z))
for j in range(ny):
 for i in range(nx):a=j*(nx+1)+i;f.append((a,a+1,a+nx+2,a+nx+1))
o=mesh('Draped burgundy bedspread',v,f,red)
for p in o.data.polygons:p.use_smooth=True
mod=o.modifiers.new('Textile thickness','SOLIDIFY');mod.thickness=.015
for x in [4.65,7.75]:
 for z in [4.16,4.47]:
  frame('Bedside drawer',x,-2.515,z,.53,.23)
  box('Drawer pull',(x,-2.56,z),(.15,.04,.026),brass)
for x in [5.2,7.2]:
 beam('Bed turned post',(x,-1.98,4.1),(x,-1.98,5.7),.085,wood)
frame('Headboard raised molding',6.2,-2.065,5.12,1.7,.92)
# Better lobby composition: show the counter AND the staircase.
cam=bpy.data.objects['CAM 02 Lobby'];cam.location=(.1,-5.0,2.35);cam.rotation_euler=(Vector((-.2,1.0,2.15))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=20
s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior']
s['CLI skill integration']='CLI detail kit generated chandelier ring, imported without resetting existing scene.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'MistpineInn_Refined.blend'))
print('INTERIOR_SAVED',len(s.objects))
