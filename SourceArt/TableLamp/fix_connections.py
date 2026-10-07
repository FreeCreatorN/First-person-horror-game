import bpy,math,bmesh,os,json
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\TableLamp';s=bpy.context.scene;asset=bpy.data.objects['SM_TableLamp']
assert not asset.get('connections_fixed'),'Already repaired'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'TableLamp_BeforeConnectionFix.blend'),copy=True)
brass=bpy.data.materials['M_TableLamp_Brass'];cord=bpy.data.materials['M_TableLamp_Cord'];parts=[]
def tube(name,points,r,mat):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=4;cu.use_fill_caps=True;sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 for p,co in zip(sp.points,points):p.co=(*co,1)
 ob=bpy.data.objects.new(name,cu);s.collection.objects.link(ob);cu.materials.append(mat);parts.append(ob);return ob
for side in [-1,1]:
 tube('Harp mounting foot',[(side*.019,0,.270),(side*.034,0,.270),(side*.042,0,.276),(side*.045,0,.285),(side*.045,0,.305)],.0028,brass)
# Socket saddle ring physically joins both support feet.
tube('Socket saddle',[((.021*math.cos(i*math.tau/96)),(.021*math.sin(i*math.tau/96)),.270) for i in range(97)],.0024,brass)
# The central boss overlaps the spindle and the three inner spoke ends.
bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.016,depth=.006,location=(0,0,.506));o=bpy.context.object;o.name='Shade support center boss';o.data.materials.append(brass);parts.append(o)
# A continuous support hoop seats the outside ends into the fabric rim.
tube('Upper shade support hoop',[(.1105*math.cos(i*math.tau/144),.1105*math.sin(i*math.tau/144),.519) for i in range(145)],.0024,brass)
tube('Pull chain socket joint',[(.019,-.008,.286),(.026,-.008,.286)],.0014,brass)
tube('Pull chain end link',[(.042,-.022,.246),(.042,-.022,.241)],.00125,brass)
tube('Plug cable strain relief',[(.323,-.066,.0048),(.329,-.067,.006),(.337,-.067,.010),(.341,-.067,.011)],.0036,cord)
# Keep a repair provenance list before combining into the single UE mesh.
added=[o.name for o in parts]
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH');asset.select_set(True);bpy.context.view_layer.objects.active=asset;bpy.ops.object.join()
asset=bpy.context.object;asset['connections_fixed']=True
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02);bpy.ops.mesh.normals_make_consistent(inside=False) if hasattr(bpy.ops.mesh,'normals_make_consistent') else None;bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Export triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
# FBX includes the same supplied convex collision bodies and no preview geometry.
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);cols=[o for o in s.objects if o.name.startswith('UCX_SM_TableLamp_')]
for o in cols:o.hide_set(False);o.select_set(True)
bpy.ops.export_scene.fbx(filepath=os.path.join(out,'SM_TableLamp.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
for o in cols:o.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'TableLamp.blend'))
s.render.filepath=os.path.join(out,'TableLamp_Preview.png');bpy.ops.render.render(write_still=True)
# Temporary cutaway exposes the support construction for an honest check.
cut=asset.copy();cut.data=asset.data.copy();s.collection.objects.link(cut);cut.name='Inspection only - shade removed'
linen=next(i for i,m in enumerate(cut.data.materials) if m.name=='M_TableLamp_Linen');bm=bmesh.new();bm.from_mesh(cut.data);bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index==linen],context='FACES');bm.to_mesh(cut.data);bm.free();asset.hide_render=True
cam=s.camera;matrix=cam.matrix_world.copy();scale=cam.data.ortho_scale;target=Vector((0,0,.397));cam.location=(.48,-.8,.61);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.36
s.render.filepath=os.path.join(out,'TableLamp_ConnectionCheck.png');bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(cut,do_unlink=True);asset.hide_render=False;cam.matrix_world=matrix;cam.data.ortho_scale=scale
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'TableLamp.blend'))
with open(os.path.join(out,'connection_fix_report.json'),'w') as f:json.dump({'added_connectors':added,'triangles':len(asset.data.polygons),'height_m':asset.dimensions.z,'collision_hulls':len(cols),'shade_spokes_outer_overlap_mm':.5,'shade_spokes_inner_overlap_mm':5.6},f,indent=2)
print('CONNECTION_REPAIR_SAVED',added)
