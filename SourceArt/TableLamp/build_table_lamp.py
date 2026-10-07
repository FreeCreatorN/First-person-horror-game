import bpy,math,os,json
from mathutils import Vector
OUT=r'D:\UE\Project\HorrorGame\SourceArt\TableLamp'
# Keep the inn intact in its own scene and file.
scene=bpy.data.scenes.new('Table Lamp Asset')
bpy.context.window.scene=scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
parts=[]
def material(name,col,rough,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*col,1);p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
brass=material('M_TableLamp_Brass',(.31,.185,.065),.31,.82)
fabric=material('M_TableLamp_Linen',(.66,.51,.31),.88)
rubber=material('M_TableLamp_Cord',(.022,.017,.012),.82)
ceramic=material('M_TableLamp_Socket',(.12,.10,.076),.42)
bulb=material('M_TableLamp_Bulb',(.85,.64,.30),.24)
p=next(n for n in bulb.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Emission Color'].default_value=(1,.52,.16,1);p.inputs['Emission Strength'].default_value=3
n=fabric.node_tree.nodes;l=fabric.node_tree.links;p=next(n for n in n if n.type=='BSDF_PRINCIPLED');t=n.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=220;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.15;b.inputs['Distance'].default_value=.00018;l.new(t.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal']);p.inputs['Sheen Weight'].default_value=.22
# Shared fabric weave image gives Unreal an equivalent material input.
size=256;pixels=[]
for y in range(size):
 for x in range(size):
  v=.64+.075*math.sin(x*math.tau/4)+.065*math.sin(y*math.tau/4)+.022*math.sin((x+y)*1.713)
  pixels.extend((v,v,v,1))
im=bpy.data.images.new('T_TableLamp_Weave',width=size,height=size);im.pixels=pixels;im.filepath_raw=os.path.join(OUT,'T_TableLamp_Weave.png');im.file_format='PNG';im.save();im.pack()
def lathe(name,profile,mat,N=96,pleat=0,cap=True):
 vs=[];fs=[]
 for r,z in profile:
  for i in range(N):
   a=i*math.tau/N;rr=r+pleat*math.cos(a*48);vs.append((rr*math.cos(a),rr*math.sin(a),z))
 for j in range(len(profile)-1):
  for i in range(N):a=j*N+i;b=j*N+(i+1)%N;fs.append((a,b,b+N,a+N))
 if cap:fs.extend([tuple(range(N-1,-1,-1)),tuple((len(profile)-1)*N+i for i in range(N))])
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(name,me);scene.collection.objects.link(o);me.materials.append(mat);parts.append(o)
 for p in me.polygons:p.use_smooth=len(p.vertices)==4
 uv=me.uv_layers.new(name='UVMap')
 z0=profile[0][1];zd=max(.001,profile[-1][1]-z0)
 for poly in me.polygons:
  for li in poly.loop_indices:
   idx=me.loops[li].vertex_index;ridx=idx//N;col=idx%N;u=col/N
   if col==0 and any(me.loops[j].vertex_index%N==N-1 for j in poly.loop_indices):u=1
   uv.data[li].uv=(u,(profile[ridx][1]-z0)/zd)
 return o
def tube(name,points,radius,mat):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=12;cu.bevel_depth=radius;cu.bevel_resolution=3;sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 for p,co in zip(sp.points,points):p.co=(*co,1)
 ob=bpy.data.objects.new(name,cu);scene.collection.objects.link(ob);cu.materials.append(mat);parts.append(ob);return ob
lathe('Weighted stepped brass base',[(.004,0),(.105,0),(.112,.004),(.114,.010),(.114,.016),(.109,.022),(.10,.025),(.098,.031),(.088,.036),(.061,.043),(.034,.052),(.026,.061),(.026,.066)],brass)
lathe('Base underside felt',[(.002,.0003),(.096,.0003),(.096,.002)],rubber)
lathe('Turned stem',[(.025,.060),(.028,.065),(.028,.071),(.018,.078),(.014,.086),(.012,.11),(.010,.22),(.014,.243),(.019,.25),(.019,.259),(.014,.267)],brass)
lathe('Ceramic socket',[(.014,.257),(.022,.262),(.022,.296),(.020,.307)],ceramic,64)
for z in [.272,.278,.284]:lathe('Socket retaining ring',[(.022,z),(.0235,z+.002),(.022,z+.004)],brass,64)
# Tapered shade with a real open interior and thin fabric wall.
shade=lathe('Linen shade',[(.176,.312),(.177,.318),(.159,.374),(.141,.431),(.121,.49),(.111,.522)],fabric,192,.0007,False)
mod=shade.modifiers.new('Fabric thickness','SOLIDIFY');mod.thickness=.0012
for rad,z in [(.1765,.314),(.1115,.522)]:
 lathe('Rolled shade piping',[(rad-.001,z-.002),(rad+.001,z-.001),(rad+.002,z+.001),(rad+.001,z+.003),(rad-.001,z+.003)],fabric,128,0,True)
for a in [0,math.tau/3,2*math.tau/3]:tube('Shade spider spoke',[(.012*math.cos(a),.012*math.sin(a),.505),(.107*math.cos(a),.107*math.sin(a),.519)],.0016,brass)
# Harp bends around the light bulb and carries the finial.
pts=[]
for i in range(65):
 a=i*math.pi/64;pts.append((.045*math.cos(a),0,.302+.202*math.sin(a)))
tube('Brass shade harp',pts,.0025,brass)
lathe('Finial',[(.007,.503),(.007,.525),(.013,.531),(.014,.537),(.01,.543),(.003,.548)],brass,64)
lathe('Warm frosted bulb',[(.01,.301),(.015,.311),(.025,.325),(.031,.349),(.029,.369),(.020,.383),(.003,.39)],bulb,64)
# Pull chain beside the socket, ending in a weighted drop.
pts=[(.026,-.008,.286),(.041,-.018,.267),(.042,-.022,.244)]
tube('Socket pull chain',pts,.0011,brass)
knob=lathe('Pull switch end',[(.002,.231),(.0035,.235),(.0035,.243)],brass,24);knob.location=(.042,-.022,0)
# Cable lies naturally on the support surface, pivot remains under the base.
pts=[]
for i in range(100):
 t=i/99;x=.10+.23*t;y=.013+.03*math.sin(t*math.pi*2)-.08*t;z=.003+.012*math.exp(-t*15);pts.append((x,y,z))
tube('Power cable',pts,.0026,rubber)
bpy.ops.mesh.primitive_cube_add(size=1,location=(.346,-.067,.012));o=bpy.context.object;o.name='Power plug';o.dimensions=(.030,.019,.020);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(rubber);parts.append(o);m=o.modifiers.new('Rounded plug','BEVEL');m.width=.004;m.segments=3
for y in [-.073,-.061]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=(.365,y,.011));o=bpy.context.object;o.name='Plug brass pin';o.dimensions=(.014,.003,.005);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(brass);parts.append(o)
# Convert and combine only the lamp; five material slots are retained.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_TableLamp'
scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
# Regenerate a complete non-overlapping lightmap-ready authoring UV on all parts.
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Export triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT,'SM_TableLamp.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',use_mesh_modifiers=True,mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False,path_mode='AUTO')
# Presentation scene is excluded from the FBX selection.
floor=material('Preview backdrop',(.035,.041,.046),.72)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.003));bpy.context.object.name='Preview floor';bpy.context.object.data.materials.append(floor)
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
for loc,power,size,color in [((-.6,-.8,1.1),55,.8,(1,.86,.68)),((.5,.5,.8),75,.6,(.62,.76,1)),((.2,-.5,.45),8,.4,(1,.71,.43))]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.data.color=color;aim(o,(0,0,.25))
bpy.ops.object.light_add(type='POINT',location=(0,0,.35));bpy.context.object.data.energy=1.7;bpy.context.object.data.color=(1,.57,.24);bpy.context.object.data.shadow_soft_size=.018
bpy.ops.object.camera_add(location=(.95,-1.4,.89));cam=bpy.context.object;cam.name='Camera TableLamp';aim(cam,(.06,0,.275));cam.data.type='ORTHO';cam.data.ortho_scale=.78;scene.camera=cam
scene.world=bpy.data.worlds.new('Lamp studio world');scene.world.use_nodes=True;next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.10,.12,.15,1)
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True;scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False
with open(os.path.join(OUT,'model_report.json'),'w') as f:json.dump({'name':asset.name,'dimensions_m':list(asset.dimensions),'vertices':len(asset.data.vertices),'triangles':len(asset.data.polygons),'materials':[m.name for m in asset.data.materials],'uv_layers':len(asset.data.uv_layers)},f,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'TableLamp.blend'))
scene.render.filepath=os.path.join(OUT,'TableLamp_Preview.png');bpy.ops.render.render(write_still=True)
print('LAMP_EXPORTED')
