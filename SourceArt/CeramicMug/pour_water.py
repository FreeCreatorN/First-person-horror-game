import bpy,math,json
from mathutils import Vector,Matrix
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\CeramicMug')
bpy.ops.wm.open_mainfile(filepath=str(out/'CeramicMug_Repaired.blend'))
s=bpy.context.scene;s.frame_start=1;s.frame_end=220;s.render.fps=24
root=bpy.data.objects.new('Cup pouring control',None);s.collection.objects.link(root)
for o in list(s.objects):
 if o.type=='MESH' and o.name!='Studio floor':o.parent=root
def ease(a,b,f):
 t=max(0,min(1,(f-a)/(b-a)));return t*t*(3-2*t)
def pose(f):
 lift=.19*(ease(12,42,f)-ease(174,210,f))
 angle=math.radians(68)*(ease(40,132,f)-ease(142,178,f))
 return lift,angle
water=bpy.data.materials.new('Water - clear');water.use_nodes=True;water.diffuse_color=(.22,.55,.64,1)
p=next(n for n in water.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.78,.94,.98,1);p.inputs['Roughness'].default_value=.07;p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.333
def animated_mesh(name,coords,faces):
 m=bpy.data.meshes.new(name);m.from_pydata(coords,[],[tuple(reversed(f)) for f in faces]);m.update();o=bpy.data.objects.new(name,m);s.collection.objects.link(o);m.materials.append(water)
 for p in m.polygons:p.use_smooth=True
 o.shape_key_add(name='Basis');return o
def shape(o,coords,f,end):
 k=o.shape_key_add(name='Frame %03d'%f)
 for v,co in zip(k.data,coords):v.co=co
 for frame,val in [(max(1,f-2),0),(f,1),(min(end,f+2),0)]:
  if f==end and frame==end and val==0:continue
  k.value=val;k.keyframe_insert(data_path='value',frame=frame)
 # Do not let Bezier overshoot the neighboring sampled water surfaces.
 for layer in o.data.shape_keys.animation_data.action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for pt in fc.keyframe_points:pt.interpolation='LINEAR'
N=64;R=8;bottom=.0075;top=.095
def water_coords(level,angle,lift):
 result=[];c=math.cos(angle);a=math.sin(angle)
 for j in range(R+1):
  u=j/R
  for i in range(N):
   phi=2*math.pi*i/N;cp=math.cos(phi)
   z=(level-lift-a*u*.0313*cp)/(c+a*u*.060*cp)
   z=max(bottom,min(top,z));r=u*(.0313+.060*z)
   result.append((r*cp,r*math.sin(phi),z))
 for i in range(N):
  phi=2*math.pi*i/N;result.append((.0315*math.cos(phi),.0315*math.sin(phi),bottom))
 result.append((0,0,bottom));return result
faces=[]
for j in range(R):
 for i in range(N):faces.append((j*N+i,j*N+(i+1)%N,(j+1)*N+(i+1)%N,(j+1)*N+i))
for i in range(N):
 faces.append((R*N+i,R*N+(i+1)%N,(R+1)*N+(i+1)%N,(R+1)*N+i));faces.append(((R+1)*N+i,(R+1)*N+(i+1)%N,(R+2)*N))
liquid=animated_mesh('Water inside cup',water_coords(.075,0,0),faces);liquid.parent=root
# Sample the interior to keep the surface level while reducing the retained water.
samples=[]
for j in range(28):
 z=bottom+(top-bottom)*(j+.5)/28
 for k in range(5):
  r=(.0313+.060*z)*math.sqrt((k+.5)/5)
  for i in range(16):samples.append((r*math.cos(i*math.tau/16),z))
SN=10;ST=40
sf=[(j*SN+i,j*SN+(i+1)%SN,(j+1)*SN+(i+1)%SN,(j+1)*SN+i) for j in range(ST) for i in range(SN)]
stream=animated_mesh('Falling water stream',[(0,0,0)]*((ST+1)*SN),sf)
retained=.77;checks=[]
for f in range(1,221):
 lift,angle=pose(f);root.location.z=lift;root.rotation_euler.y=-angle;root.keyframe_insert(data_path='location',frame=f);root.keyframe_insert(data_path='rotation_euler',frame=f)
 if f%2==0:
  heights=sorted(lift+math.sin(angle)*x+math.cos(angle)*z for x,z in samples)
  lip=lift-math.sin(angle)*.0372+math.cos(angle)*.095
  capacity=sum(z<=lip for z in heights)/len(heights)
  retained=min(retained,max(.02,capacity))
  level=min(lip,heights[min(len(heights)-1,int(retained*len(heights)))])
  shape(liquid,water_coords(level,angle,lift),f,220)
  strength=ease(66,76,f)*(1-ease(126,138,f))
  origin=Matrix.Rotation(-angle,4,'Y')@Vector((-.0388,0,.097));origin.z+=lift
  coords=[]
  # Ballistic trajectory under gravity; width narrows as downward speed grows.
  tmax=max(.01,math.sqrt(max(.001,2*(origin.z-.001)/9.81)))
  for j in range(ST+1):
   t=tmax*j/ST;x=origin.x-.20*t;z=origin.z-4.905*t*t
   rad=.0026*strength/math.sqrt(1+12*t)
   for i in range(SN):
    phi=math.tau*i/SN;coords.append((x+rad*math.cos(phi),rad*math.sin(phi),z))
  shape(stream,coords,f,220)
  if f in [2,90,132,220]:checks.append({'frame':f,'retained_fraction':retained})
# Shallow spreading puddle where the stream hits the surface.
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=24,location=(-.15,0,.0004));puddle=bpy.context.object;puddle.name='Spreading puddle';puddle.data.materials.append(water)
for p in puddle.data.polygons:p.use_smooth=True
for f in [1,66,80,110,140,220]:
 t=ease(66,140,f);puddle.scale=(max(.000001,.060*t),max(.000001,.044*t),max(.000001,.0007*t));puddle.keyframe_insert(data_path='scale',frame=f)
for j in range(16):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);drop=bpy.context.object;drop.name='Impact droplet %02d'%j;drop.data.materials.append(water)
 for p in drop.data.polygons:p.use_smooth=True
 start=78+j*3;phi=j*2.39996
 for f in [1,start,start+2,start+4,start+6,start+8,start+10,220]:
  age=max(0,(f-start)/24);active=start<f<start+10
  drop.location=(-.145+.16*age*math.cos(phi),.16*age*math.sin(phi),max(.001,.6*age-4.905*age*age))
  r=.0011 if active and drop.location.z>.001 else .0000001;drop.scale=(r,r,r*1.4)
  drop.keyframe_insert(data_path='location',frame=f);drop.keyframe_insert(data_path='scale',frame=f)
s.camera.location=(.40,-.60,.39);target=Vector((-.045,0,.125));s.camera.rotation_euler=(target-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.ortho_scale=.44
for sc in bpy.data.screens:
 for ar in sc.areas:
  if ar.type=='VIEW_3D':
   v=ar.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.6;v.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
s.render.engine='CYCLES';s.cycles.samples=32;s.frame_set(108);s.render.filepath=str(out/'Cup_Pouring.png');bpy.ops.render.render(write_still=True)
s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'CeramicMug_Pouring.blend'))
(out/'pour_report.json').write_text(json.dumps({'frames':220,'fps':24,'water_samples':checks,'method':'Animated water surfaces with ballistic stream'},indent=2))
