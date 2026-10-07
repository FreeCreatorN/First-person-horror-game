from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser')
source=(out/'refine.py').read_text(encoding='utf-8-sig')
split="bpy.ops.object.select_all(action='DESELECT')\nfor o in parts:o.select_set(True)"
head,tail=source.split(split,1)
exec(head)
# Eliminate stacked floating facade panels and build an actual open storage cabinet.
for prefix in ['Lower cabinet','Lower door seam','Lower service panel','Service latch','Front vent grille','Rear service panel','Rear vent opening','Rear screw']:remove_prefix(prefix)
box('Storage left wall',(-.148,0,.291),(.024,.302,.466),cream,.005)
box('Storage right wall',(.148,0,.291),(.024,.302,.466),cream,.005)
box('Storage rear wall',(0,.144,.290),(.276,.016,.468),cream,.004)
box('Storage floor',(0,-.004,.068),(.290,.292,.020),cream,.004)
box('Storage ceiling',(0,-.004,.514),(.290,.292,.022),cream,.004)
box('Storage floor insert',(0,-.004,.080),(.265,.264,.006),dark,.003)
box('Storage front sill',(0,-.143,.078),(.279,.018,.028),cream,.004)
# Tap feet are embedded into the fascia, not hovering in front of it.
for o in parts:
 if o.name.startswith('Tap base flange'):o.location.y=-.179
 if o.name.startswith('Maker label'):o.location.y=-.174
# Rear service panel touches the shell; vent inserts and fasteners touch that panel.
box('Rear fitted service panel',(0,.153,.647),(.276,.009,.400),dark,.003)
for j in range(12):box('Rear fitted louvre',(0,.159,.55+j*.018),(.216,.006,.007),steel,.001)
for x in [-.121,.121]:
 for z in [.474,.819]:cyl('Rear seated screw',(x,.161,z),.0033,.005,steel,(math.pi/2,0,0))
# Full-sized spare water container within the storage space, 25 cm wide, 38 cm tall.
profile=[(0,.084),(.108,.084),(.122,.092),(.125,.105),(.125,.344),(.119,.366),(.090,.397),(.042,.418),(.030,.426),(.030,.454),(0,.454)]
N=96;vs=[(r*math.cos(j*math.tau/N),.007+r*math.sin(j*math.tau/N),z) for r,z in profile for j in range(N)]
fs=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(profile)-1) for j in range(N)]
me=bpy.data.meshes.new('Spare water container');me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new('Spare bottle inside storage',me);s.collection.objects.link(o);finish(o,o.name,bottle)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
for p in me.polygons:p.use_smooth=True
sub=o.modifiers.new('Moulded curves','SUBSURF');sub.levels=2
sol=o.modifiers.new('Plastic thickness','SOLIDIFY');sol.thickness=.0015
cyl('Spare bottle screw cap',(0,.007,.453),.033,.017,blue)
for z in [.117,.138,.320,.341]:
 bpy.ops.mesh.primitive_torus_add(major_radius=.124,minor_radius=.0025,major_segments=96,minor_segments=12,location=(0,.007,z));o=finish(bpy.context.object,'Spare bottle rib',bottle)
 for p in o.data.polygons:p.use_smooth=True
tail=tail.replace('WaterDispenser_Refined.png','WaterDispenser_Fitted.png').replace('WaterDispenser_Refined.blend','WaterDispenser_Fitted.blend')
exec(split+tail)
