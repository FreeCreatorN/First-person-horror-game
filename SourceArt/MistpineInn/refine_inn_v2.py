import bpy,math,random,os,json
from mathutils import Vector
random.seed(41)
out=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn'
bpy.ops.wm.open_mainfile(filepath=os.path.join(out,'MistpineInn.blend'))
s=bpy.context.scene;s.frame_set(1)
if bpy.context.screen and bpy.context.screen.is_animation_playing:bpy.ops.screen.animation_cancel(restore_frame=False)
C=bpy.data.collections.new('06 Refined architecture');s.collection.children.link(C)
wood=bpy.data.materials['Dark aged oak'];stone=bpy.data.materials['Foundation stone'];slate=bpy.data.materials['Blue slate'];plaster=bpy.data.materials['Weathered warm plaster'];brass=bpy.data.materials['Aged brass']
def mesh(name,v,f,m):
 d=bpy.data.meshes.new(name);d.from_pydata(v,[],f);d.update();o=bpy.data.objects.new(name,d);C.objects.link(o)
 if m:d.materials.append(m)
 return o
def box(name,loc,dim,m):
 v=[(a*dim[0]/2,b*dim[1]/2,c*dim[2]/2) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
 o=mesh(name,v,[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)],m);o.location=loc;return o
def beam(name,a,b,w,m=wood):
 a,b=Vector(a),Vector(b);o=box(name,(a+b)/2,(w,w,(b-a).length),m);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o
def material(name,col,rough=.7):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;return m
# Correct the exaggerated metre-scale bump on every surface.
for m in bpy.data.materials:
 if not m.use_nodes:continue
 for n in m.node_tree.nodes:
  if n.type=='BUMP':n.inputs['Distance'].default_value=.006 if 'plaster' in m.name.lower() else .0015;n.inputs['Strength'].default_value=.24
for m in [wood,bpy.data.materials['Carved walnut']]:
 n=m.node_tree.nodes;l=m.node_tree.links;tex=n.new('ShaderNodeTexCoord');scale=n.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(3,3,.18);l.new(tex.outputs['Generated'],scale.inputs[0]);noise=next(x for x in n if x.type=='TEX_NOISE');l.new(scale.outputs[0],noise.inputs['Vector']);noise.inputs['Scale'].default_value=24
# Remove incorrectly oriented miniature dormer roofs.
for o in list(bpy.data.objects):
 remove=o.name.startswith('Dormer front') or (o.name.startswith('Slate roof pitch') and o.dimensions.x<5) or (o.name.startswith(('Roof bargeboard','Ridge cap')) and max(o.dimensions)<4)
 remove=remove or (o.name.startswith(('Recessed window','Window mullion','Window transom','Stone sill','Wood shutter','Shutter strap')) and o.location.z>10.4)
 if remove:bpy.data.objects.remove(o,do_unlink=True)
# Slate tiles: actual overlapping geometry with restrained color variation.
tilemats=[material('Slate variation %02d'%i,(.042+i*.005,.061+i*.006,.076+i*.006),.57) for i in range(7)]
def tiled_roof(name,origin,u,v,nu,nv):
 origin=Vector(origin);u=Vector(u);v=Vector(v);normal=u.cross(v).normalized()
 if normal.z<0:normal=-normal
 verts=[];faces=[];indices=[]
 for j in range(nv):
  for i in range(nu):
   a=(i+.5*(j%2))/nu;b=j/nv
   if a>=1:continue
   p=origin+u*a+v*b+normal*(.025+random.random()*.006);du=u*(min(1/nu,1-a)*.965);dv=v*(min(1.17/nv,1-b))
   k=len(verts);verts.extend([p,p+du,p+du+dv,p+dv]);faces.append((k,k+1,k+2,k+3));indices.append(random.randrange(7))
 o=mesh(name,verts,faces,None)
 for m in tilemats:o.data.materials.append(m)
 for p,i in zip(o.data.polygons,indices):p.material_index=i
 mod=o.modifiers.new('Slate thickness','SOLIDIFY');mod.thickness=.012
 return o
for side in [-1,1]:tiled_roof('Main overlapping slate '+str(side),(-10.65,side*6.2,10.43),(21.3,0,0),(0,-side*6.2,3.4),64,22)
def gable(cx,front,w,eave,rise,depth):
 verts=[(cx-w/2,front,eave),(cx+w/2,front,eave),(cx,front,eave+rise)]
 o=mesh('Front gable plaster',verts,[(0,1,2)],plaster);so=o.modifiers.new('Solid gable','SOLIDIFY');so.thickness=.22
 for side in [-1,1]:
  a=(cx+side*(w/2+.15),front-.14,eave);b=(cx,front-.14,eave+rise)
  beam('Carved gable bargeboard',a,b,.18)
  tiled_roof('Cross gable slate',a,(0,depth,0),Vector(b)-Vector(a),max(6,int(depth/.4)),max(6,int(w/.36)))
 beam('Gable king post',(cx,front-.12,eave),(cx,front-.12,eave+rise-.1),.16)
 beam('Gable tie beam',(cx-w/2,front-.12,eave),(cx+w/2,front-.12,eave),.18)
 box('Gable window',(cx,front-.14,eave+.75),(w*.32,.1,1.25),bpy.data.materials['Amber window glow'])
 for dx in [-w*.16,0,w*.16]:box('Gable window frame',(cx+dx,front-.22,eave+.75),(.07,.1,1.37),wood)
 for dz in [.07,.75,1.42]:box('Gable window crossbar',(cx,front-.22,eave+dz),(w*.32+.12,.1,.07),wood)
gable(0,-5.96,5.0,10.34,3.65,5.9)
for x in [-6.7,6.7]:
 box('Dormer cheek',(x,-3.2,11.53),(2,2.6,1.9),plaster)
 gable(x,-4.55,2.3,11.3,1.8,3.2)
# Reduce repeated uniform orange squares; vary occupied and unoccupied windows.
windowmats=[]
for i in range(6):
 m=material('Window occupancy '+str(i),(.035,.045,.05) if i==0 else (.23,.13,.05),.28);p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Emission Color'].default_value=(1,.48+.025*i,.16,1);p.inputs['Emission Strength'].default_value=[.025,.18,.35,.65,1.1,1.5][i];windowmats.append(m)
for o in bpy.data.objects:
 if o.name.startswith(('Recessed window','End elevation window','Gable window')) and not o.name.startswith(('Gable window frame','Gable window crossbar')):
  o.data.materials.clear();o.data.materials.append(random.choices(windowmats,[2,1,2,3,2,1])[0])
# Doorway clearance: front lower spandrel was blocking the door at ankle height.
old=next(o for o in bpy.data.objects if o.name.startswith('Front lower spandrel') and o.location.z<2)
bpy.data.objects.remove(old,do_unlink=True)
for side in [-1,1]:box('Entrance lower wall',(side*5.5,-5.5,1.2),(9,.28,1),plaster)
# Stone pier courses, carved post collars, porch braces and railings.
for x in [-3.3,3.3]:
 for y in [-8.35,-5.9]:
  for row in range(4):
   for col in [-1,1]:box('Dressed porch pier stone',(x+col*.17,y,.83+row*.18),(.33,.68,.165),stone)
  box('Pier coping',(x,y,1.52),(.8,.8,.13),stone)
  for z in [1.65,3.5]:box('Post collar',(x,y,z),(.32,.32,.12),wood)
  beam('Porch knee brace',(x,y,2.9),(x-math.copysign(.75,x),y,3.7),.14)
for side in [-1,1]:
 for z in [1.05,1.77]:beam('Porch side rail',(side*3.3,-8.3,z),(side*3.3,-5.9,z),.11)
 for i in range(9):beam('Porch railing spindle',(side*3.3,-8.2+i*.27,1.08),(side*3.3,-8.2+i*.27,1.72),.055)
beam('Porch tie beam',(-3.85,-9.05,3.72),(3.85,-9.05,3.72),.2)
beam('Porch king post',(0,-9.05,3.72),(0,-9.05,5.18),.18)
# Stone base and chimney masonry use layered block joints.
for row in range(3):
 for i in range(34):box('Foundation ashlar',(-10.1+i*.61+(row%2)*.25,-5.85,.14+row*.2),(.58,.18,.18),stone)
for x in [-7,6]:
 for row in range(12):
  z=11.1+row*.30
  for side in [-1,1]:
   box('Chimney mortar course',(x,1+side*.486,z),(.98,.02,.023),wood)
  box('Chimney brick joint',(x+(-.19 if row%2 else .21),.505,z+.15),(.022,.02,.27),wood)
# Replace cone trees with irregular tiered silhouettes and individual branches.
for o in list(bpy.data.objects):
 if o.name.startswith('Pine crown'):bpy.data.objects.remove(o,do_unlink=True)
pine=bpy.data.materials['Pine needles']
for trunk in [o for o in bpy.data.objects if o.name.startswith('Pine trunk')]:
 x,y=trunk.location.x,trunk.location.y;h=trunk.dimensions.z
 vs=[];fs=[]
 for j in range(13):
  z=h*(.23+j*.055);radius=h*.14*(1-j/15)
  count=10
  for k in range(count):
   a=k*math.tau/count+j*1.8;r=radius*random.uniform(.65,1.2);center=Vector((x,y,z));tip=Vector((x+math.cos(a)*r,y+math.sin(a)*r,z-r*.12));perp=Vector((-math.sin(a),math.cos(a),0))*r*.32
   n=len(vs);vs.extend([center+Vector((0,0,.75)),tip,center+perp,center-perp]);fs.extend([(n,n+1,n+2),(n,n+3,n+1)])
 mesh('Irregular fir foliage',vs,fs,pine)
# Sparse ivy follows facade edges, leaving windows legible.
leaf=material('Muted ivy',(.055,.075,.025))
vs=[];fs=[]
for stemx in [-9.6,-6.55,1.65,9.5]:
 for i in range(160):
  z=random.uniform(.6,9.9);x=stemx+math.sin(z*1.4)*.17+random.gauss(0,.30);y=-5.86-random.random()*.12;r=random.uniform(.035,.10);k=len(vs)
  vs.extend([(x-r,y,z),(x,y-.035,z+r*1.4),(x+r,y,z),(x,y+.02,z-r)]);fs.append((k,k+1,k+2,k+3))
mesh('Climbing ivy leaves',vs,fs,leaf)
# Cinematic eye-level view, subtle blue atmosphere.
cam=bpy.data.objects['CAM 01 Exterior'];cam.location=(25,-36,12.5);target=Vector((0,-1,6.1));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=43
s.camera=cam;s.render.resolution_x=1400;s.render.resolution_y=1000;s.cycles.samples=32
s['Revision']='V2: gable silhouette, overlapping slate, stone piers, braced porch, varied windows, branched firs, ivy, corrected material scale.'
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'MistpineInn_Refined.blend'))
print('REFINED_SAVED',len(s.objects))

