from pathlib import Path
import bpy,math,bmesh
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\AirConditioner')
src=(out/'build.py').read_text(encoding='utf-8-sig');marker="bpy.ops.object.select_all(action='DESELECT')\nfor o in parts:o.select_set(True)";head,tail=src.split(marker,1);exec(head)
def remove(prefix):
 for o in list(parts):
  if o.name.startswith(prefix):parts.remove(o);bpy.data.objects.remove(o,do_unlink=True)
for prefix in ['Front fascia','Front opening seam','Horizontal airflow blade','Internal guide vane','Top intake recess','Intake grille rib','Side end cap']:remove(prefix)
# One continuous, gently convex front cover with an actual return at top and bottom.
cross=[]
for j in range(25):
 t=j/24;z=-.039+.171*t;y=-.205-.012*math.sin(math.pi*t);cross.append((y,z))
cross += [(y+.016,z) for y,z in reversed(cross)]
N=len(cross);verts=[(x,y,z) for x in [-.413,.413] for y,z in cross]
faces=[tuple(range(N-1,-1,-1)),tuple(range(N,N*2))]+[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)]
me=bpy.data.meshes.new('Curved fascia');me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new('Curved front cover',me);s.collection.objects.link(o);o.data.materials.append(white);parts.append(o)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
for p in me.polygons:p.use_smooth=len(p.vertices)==4
b=o.modifiers.new('Fascia edge radius','BEVEL');b.width=.002;b.segments=3;o.modifiers.new('Fascia normals','WEIGHTED_NORMAL')
for x in [-.422,.422]:
 box('Fitted side cover',(x,-.110,.002),(.026,.212,.285),white,.012)
 box('Side service seam',(x*.999,-.022,.005),(.027,.0015,.220),grey,.0005)
# Make the intake a real cutout in the top housing.
upper=next(o for o in parts if o.name=='Upper enclosure')
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.096,.148));cut=bpy.context.object;cut.dimensions=(.736,.104,.030);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bpy.context.view_layer.objects.active=upper
for mod in list(upper.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
bo=upper.modifiers.new('Recessed intake aperture','BOOLEAN');bo.operation='DIFFERENCE';bo.solver='EXACT';bo.object=cut;bpy.ops.object.modifier_apply(modifier=bo.name);bpy.data.objects.remove(cut,do_unlink=True)
box('Washable filter backing',(0,-.096,.134),(.729,.099,.002),dark,.001)
for i in range(42):box('Inset intake rib',(-.351+i*.0171,-.096,.144),(.005,.106,.007),white,.001)
for j in range(8):box('Fine filter mesh',(0,-.139+j*.012,.136),(.728,.001,.001),grey,.0002)
# Deeper black guide vanes and a shaped wide swing flap, rather than two white bars.
for j in range(15):
 o=box('Airflow guide fin',(-.357+j*.051,-.146,-.082),(.0025,.055,.066),dark,.001);o.rotation_euler.z=math.radians(-8)
o=box('Wide swing flap',(0,-.186,-.106),(.766,.048,.006),white,.002);o.rotation_euler.x=math.radians(-24)
for x in [-.383,.383]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.006,depth=.015,location=(x,-.183,-.107),rotation=(0,math.pi/2,0));o=bpy.context.object;o.name='Swing flap axle';o.data.materials.append(grey);parts.append(o)
box('Outlet upper lip',(0,-.202,-.041),(.785,.012,.008),white,.003)
# Place printed marks on the curved face and seat the display in a compact bezel.
for o in parts:
 if o.name=='Printed brand':o.location.y=-.216
 if o.name=='Display smoked window':o.location.y=-.218;o.dimensions=(.069,.004,.039)
 if o.name=='Temperature display':o.location.y=-.22003;o.data.size=.024
 if o.name=='Receiver':o.location.y=-.2175
label('INVERTER',(-.278,-.216,.040),.006,grey,'Secondary print')
for x in [-.325,.325]:box('Cover release tab',(x,-.207,-.034),(.022,.007,.005),white,.001)
# Rear mounting slots and service identification are seated against the chassis.
for x in [-.31,.31]:
 box('Rear mounting bracket',(x,-.004,.056),(.075,.008,.100),grey,.003)
 box('Mounting slot',(x,.0003,.080),(.025,.001,.006),dark,.001)
tail=tail.replace('AirConditioner_Preview.png','AirConditioner_Refined.png').replace('AirConditioner.blend','AirConditioner_Refined.blend')
exec(marker+tail)
