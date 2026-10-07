import bpy,math
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\CeramicMug')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.name='Ceramic Mug'
def mat(name,col,rough):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;return m,p
glaze,p=mat('M_Mug_IvoryGlaze',(.63,.55,.41),.23)
p.inputs['Coat Weight'].default_value=.3
n=glaze.node_tree.nodes;l=glaze.node_tree.links
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=210;noise.inputs['Detail'].default_value=2
b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.12;b.inputs['Distance'].default_value=.000075;l.new(noise.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
clay,_=mat('M_Mug_UnglazedFoot',(.34,.24,.15),.85)
band,_=mat('M_Mug_OliveBand',(.11,.14,.105),.3)
# Watertight radial section: recessed underside, foot, outer wall, rolled lip, inner wall and floor.
profile=[(0,.0025),(.024,.0025),(.027,.0025),(.027,0),(.031,0),(.033,.002),(.034,.006),(.035,.012),(.037,.03),(.039,.06),(.040,.087),(.040,.094),(.0397,.097),(.0388,.0985),(.0378,.0985),(.0368,.097),(.0367,.094),(.0365,.086),(.0355,.06),(.0335,.03),(.032,.014),(.030,.009),(.027,.007),(0,.007)]
N=96;verts=[];faces=[]
for r,z in profile:
 for j in range(N):
  t=2*math.pi*j/N;verts.append((r*math.cos(t),r*math.sin(t),z))
for k in range(len(profile)-1):
 for j in range(N):faces.append((k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j))
mesh=bpy.data.meshes.new('Cup continuous wall');mesh.from_pydata(verts,[],faces);mesh.update();body=bpy.data.objects.new('Cup body',mesh);s.collection.objects.link(body);mesh.materials.append(glaze);mesh.materials.append(clay)
for poly in mesh.polygons:
 poly.use_smooth=True
 if poly.center.z<.0026:poly.material_index=1
# Closed oval handle intersects the wall at both ends, then is fused into the ceramic body.
v=[];f=[];steps=72;sides=16
for j in range(steps):
 a=2*math.pi*j/steps;center=Vector((.046+.024*math.cos(a),0,.054+.032*math.sin(a)));normal=Vector((math.cos(a),0,math.sin(a)))
 for k in range(sides):
  t=2*math.pi*k/sides;pt=center+.006*(math.cos(t)*normal+Vector((0,math.sin(t),0)));v.append(tuple(pt))
for j in range(steps):
 for k in range(sides):f.append((j*sides+k,((j+1)%steps)*sides+k,((j+1)%steps)*sides+(k+1)%sides,j*sides+(k+1)%sides))
hm=bpy.data.meshes.new('Handle');hm.from_pydata(v,[],f);hm.update();h=bpy.data.objects.new('Handle',hm);s.collection.objects.link(h);hm.materials.append(glaze)
# Remove the inward half of the oval before union, so it cannot intrude into the drinking cavity.
import bmesh
bm=bmesh.new();bm.from_mesh(hm)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=(.0345,0,0),plane_no=(1,0,0),clear_inner=True)
edges=[e for e in bm.edges if e.is_boundary]
bmesh.ops.holes_fill(bm,edges=edges,sides=0);bm.to_mesh(hm);bm.free()
# Trim any handle material protruding through the inner wall.
cp=[(0,.007),(.027,.007),(.030,.009),(.032,.014),(.0335,.03),(.0355,.06),(.0365,.086),(.0367,.094),(.04,.13),(0,.13)]
cv=[(r*math.cos(2*math.pi*j/N),r*math.sin(2*math.pi*j/N),z) for r,z in cp for j in range(N)]
cf=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(cp)-1) for j in range(N)]
cm=bpy.data.meshes.new('Cavity trimming volume');cm.from_pydata(cv,[],cf);cm.update();cutter=bpy.data.objects.new('Cavity trim',cm);s.collection.objects.link(cutter)
for target in [body,cutter,h]:
 bm=bmesh.new();bm.from_mesh(target.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(target.data);bm.free()
bpy.context.view_layer.objects.active=h
trim=h.modifiers.new('Clear drinking cavity','BOOLEAN');trim.operation='DIFFERENCE';trim.solver='EXACT';trim.object=cutter;bpy.ops.object.modifier_apply(modifier=trim.name);bpy.data.objects.remove(cutter,do_unlink=True)
bpy.context.view_layer.objects.active=body;body.select_set(True)
mod=body.modifiers.new('Fused handle joints','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=h
bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(h,do_unlink=True)
bev=body.modifiers.new('Soft ceramic joints','BEVEL');bev.width=.0007;bev.segments=3;bev.limit_method='ANGLE';bev.angle_limit=.65
body.name='SM_CeramicMug'
for poly in body.data.polygons:poly.use_smooth=True
# Two narrow glazed accent rings below the rim.
for z in [.088,.091]:
 bpy.ops.mesh.primitive_torus_add(major_radius=.0400,minor_radius=.0003,major_segments=96,minor_segments=8,location=(0,0,z));o=bpy.context.object;o.name='Olive rim accent';o.data.materials.append(band)
 for poly in o.data.polygons:poly.use_smooth=True
floor,_=mat('Studio surface',(.20,.19,.17),.8)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0002));ground=bpy.context.object;ground.name='Studio floor';ground.data.materials.append(floor)
bpy.ops.object.camera_add(location=(.20,-.28,.23));cam=bpy.context.object;cam.rotation_euler=(Vector((.012,0,.05))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.19;s.camera=cam
for loc,power,size in [((.1,-.2,.4),12,.3),((-.2,.15,.3),9,.23)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,.04))-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.2,.2,.2);s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1200;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.region_3d.view_location=(.01,0,.05);sp.region_3d.view_distance=.24;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.shading.color_type='MATERIAL';sp.overlay.show_overlays=False
s.render.filepath=str(out/'CeramicMug_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'CeramicMug.blend'));bpy.ops.render.render(write_still=True)
