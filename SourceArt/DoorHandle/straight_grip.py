import bpy,math
from pathlib import Path
from mathutils import Vector
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\DoorHandle')
bpy.ops.wm.open_mainfile(filepath=str(p/'DoorHandle.blend'))
panel=bpy.data.objects.get('Preview door panel')
if panel:bpy.data.objects.remove(panel,do_unlink=True)
bpy.context.scene.render.film_transparent=True
old=bpy.data.objects.get('Lever');material=old.data.materials[0]
bpy.data.objects.remove(old,do_unlink=True)
# Straight grip with a rounded capsule section; its root overlaps the spindle.
profile=[(-.008,0),(-.0075,.003),(-.0055,.006),(-.002,.0075),(.004,.008),(.109,.008),(.115,.0075),(.119,.0058),(.121,.003),(.1215,0)]
N=48;verts=[]
for x,r in profile:
 for j in range(N):
  a=math.tau*j/N;verts.append((x,-.047+r*math.cos(a),.036+r*math.sin(a)))
faces=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(profile)-1) for j in range(N)]
me=bpy.data.meshes.new('Straight grip');me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new('Lever',me);bpy.context.scene.collection.objects.link(o);me.materials.append(material)
import bmesh
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
for f in me.polygons:f.use_smooth=True
sub=o.modifiers.new('Rounded grip ends','SUBSURF');sub.levels=2;sub.render_levels=2
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
bpy.context.scene.cursor.location=(0,-.035,.036);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.context.scene.cursor.location=(0,0,0)
for ob in bpy.context.scene.objects:
 if ob.type=='MESH':ob.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(p/'DoorHandle.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
s=bpy.context.scene;s.render.filepath=str(p/'DoorHandle_Straight.png')
bpy.ops.wm.save_as_mainfile(filepath=str(p/'DoorHandle.blend'));bpy.ops.render.render(write_still=True)

