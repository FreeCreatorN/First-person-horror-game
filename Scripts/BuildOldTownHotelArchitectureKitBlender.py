"""Isolated Blender source model and measured fixture exports for the hotel."""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path('D:/UE/Project/HorrorGame')
OUT=ROOT/'SourceArt/OldTownHotelArchitecture_20261005'
PLAN=ROOT/'Saved/CodexOutputs/HotelArchitecture_20261005/ArchitecturePlan.json'
OUT.mkdir(parents=True,exist_ok=True)
plan=json.loads(PLAN.read_text(encoding='utf-8-sig'))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
colors={'Ceramic':(.61,.58,.49,1),'Glass':(.25,.31,.26,1),'DarkMetal':(.12,.13,.10,1),
        'Wood':(.18,.11,.065,1),'Linen':(.49,.47,.39,1),'Letters':(.71,.67,.49,1)}
mats={}
for k,c in colors.items():
    m=bpy.data.materials.new(k);m.diffuse_color=c;m.use_nodes=True;m.use_fake_user=True
    shader=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if shader is None:shader=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value=c
    shader.inputs['Roughness'].default_value=.76
    mats[k]=m
parts=[]
def cube(name,loc,size,mat='Ceramic',bevel=.006):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name
    o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mats[mat])
    if bevel:
        mod=o.modifiers.new('WornEdge','BEVEL');mod.width=bevel;mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    parts.append(o);return o
def cylinder(name,loc,r,depth,mat='Ceramic',scale=(1,1,1)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r,depth=depth,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mats[mat]);parts.append(o);return o
def rim(name,loc,r,minor,scale):
    bpy.ops.mesh.primitive_torus_add(major_segments=32,minor_segments=8,location=loc,major_radius=r,minor_radius=minor)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mats['Ceramic']);parts.append(o)
assets=[];prototypes={}
def finish(key):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join()
    o=bpy.context.object;o.name='SM_OTS_Arch_'+key
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    pts=[o.matrix_world@v.co for v in o.data.vertices]
    low=[min(q[i] for q in pts)*100 for i in range(3)];high=[max(q[i] for q in pts)*100 for i in range(3)]
    assert min(high[i]-low[i] for i in range(3))>.01
    path=OUT/(o.name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=True,use_triangles=True,bake_anim=False,
        axis_forward='-Y',axis_up='Z',bake_space_transform=False)
    assets.append(dict(key=key,name=o.name,file=path.name,bounds_cm=[low,high],
          dimensions_cm=[high[i]-low[i] for i in range(3)],vertices=len(o.data.vertices),
          materials=[m.name for m in o.data.materials],source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    prototypes[key]=o;parts.clear();return o

# Toilet: shaped base, elliptical seat rim, bowl and rear cistern.
cylinder('Pedestal',(-.06,0,.16),.14,.32,scale=(1.1,.8,1))
cylinder('Bowl',(-.09,0,.3285),.17,.157,scale=(1.28,1,1))
rim('SeatRim',(-.09,0,.415),.165,.012,(1.3,1,1))
# A connected rear ceramic foot/shoulder carries the cistern from the floor.
cylinder('RearCeramicPedestal',(.13,0,.155),.12,.31,scale=(1,.75,1))
cylinder('RearCeramicShoulder',(.13,0,.3775),.16,.165,scale=(1,.75,1))
cube('Cistern',(.23,0,.615),(.20,.35,.33))
cube('CisternLid',(.23,0,.767),(.20,.35,.026))
cube('FlushLever',(.326,0,.68),(.008,.035,.02),'DarkMetal',.002)
finish('Toilet')
# Seat the drain inside the ceramic underside, rather than ending 5cm below
# its bracket. Keep the floor endpoint, diameter and basin envelope unchanged.
cylinder('TrapStem',(.12,0,.3665),.025,.733,'DarkMetal')
cube('BasinSupport',(.16,0,.72),(.10,.50,.06),'DarkMetal')
cube('BasinUnder',(-.005,0,.77),(.41,.58,.08))
cube('BasinBack',(.20,0,.81),(.05,.60,.08))
cube('BasinFront',(-.20,0,.81),(.05,.60,.08))
for y in (-.275,.275):cube('BasinRim',(-.005,y,.81),(.36,.05,.08))
# The lower end embeds 3mm into the basin instead of floating 4mm above it.
cylinder('Tap',(.16,0,.8285),.012,.043,'DarkMetal')
cylinder('TapSleeve',(.16,0,.892),.013,.096,'DarkMetal')
c=cylinder('TapSpout',(.10,0,.924),.0105,.12,'DarkMetal');c.rotation_euler[1]=math.pi/2
cylinder('TapDrop',(.04,0,.909),.0095,.032,'DarkMetal')
cylinder('TapAerator',(.04,0,.8955),.011,.0085,'DarkMetal')
cylinder('TapValve',(.16,0,.941),.0065,.019,'DarkMetal')
cylinder('TapCap',(.16,0,.953),.0185,.015,'DarkMetal')
c=cylinder('TapBar',(.16,0,.953),.0065,.06,'DarkMetal');c.rotation_euler[0]=math.pi/2
finish('Washbasin')
cube('ShowerTray',(0,0,.02),(.9,.9,.04),bevel=.012)
cylinder('Drain',(.32,.32,.038),.028,.004,'DarkMetal')
finish('ShowerTray')
cube('GlassPanel',(0,0,1),(.88,.006,1.98),'Glass',.001)
for x in (-.445,.445):cube('Frame',(x,0,1),(.01,.01,2),'DarkMetal',.002)
for z in (.005,1.995):cube('Frame',(0,0,z),(.90,.01,.01),'DarkMetal',.002)
finish('ShowerScreen')
cube('WardrobeBody',(0,0,1.05),(.6,1.2,2.1),'Wood')
for y in (-.3,.3):
    cube('Door',(-.302,y,1.05),(.015,.585,2.03),'Wood',.003)
    cube('Handle',(-.318,y*.08,1.03),(.015,.015,.15),'DarkMetal',.002)
finish('Wardrobe')
cube('FixtureBack',(0,0,.085),(.14,1,.03),'DarkMetal',.003)
for x in (-.04,.04):
    c=cylinder('Tube',(x,0,.04),.015,.94,'Ceramic');c.rotation_euler[0]=math.pi/2
for y in (-.48,.48):cube('TubeCap',(0,y,.045),(.14,.04,.07),'DarkMetal',.003)
finish('FluorescentFixture')
cube('RackBack',(0,0,.475),(.10,1.5,.95),'Wood')
for y in [-.69+i*.15 for i in range(10)]:
    cube('Divider',(-.065,y,.475),(.03,.008,.87),'Wood',.001)
for z in (.08,.25,.42,.59,.76,.93):cube('Shelf',(-.065,0,z),(.03,1.44,.008),'Wood',.001)
finish('KeyRack')
cube('VentFrame',(0,0,.15),(.05,.45,.3),'DarkMetal')
for z in [.035+i*.023 for i in range(11)]:cube('Slat',(-.03,0,z),(.012,.40,.01),'DarkMetal',.002)
finish('WallVent')
# Actual extruded room numbers, no billboard text.
for r in plan['rooms']:
    bpy.ops.object.text_add();o=bpy.context.object;o.data.body=r['id'];o.data.extrude=.00125
    o.data.align_x='CENTER';o.rotation_euler[0]=math.pi/2
    bpy.ops.object.convert(target='MESH');o=bpy.context.object
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    xs=[v.co.x for v in o.data.vertices];zs=[v.co.z for v in o.data.vertices]
    factor=.12/(max(zs)-min(zs))
    for v in o.data.vertices:
        v.co.x*=factor;v.co.z=(v.co.z-min(zs))*factor
    ys=[v.co.y for v in o.data.vertices];mid=(max(ys)+min(ys))/2
    for v in o.data.vertices:v.co.y-=mid
    o.data.materials.append(mats['Letters']);parts.append(o)
    a=finish('RoomNumber_'+r['id']);prototypes['RoomNumber_'+r['id']]=a
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OldTownHotelArchitectureKit.blend'))
(OUT/'ImportManifest.json').write_text(json.dumps({'units':'cm','assets':assets},indent=2),encoding='utf-8')
# Independently reload every exported FBX in a disposable validation scene.
verified=[]
for row in assets:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(OUT/row['file']))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1
    pts=[meshes[0].matrix_world@v.co for v in meshes[0].data.vertices]
    dims=[(max(q[i] for q in pts)-min(q[i] for q in pts))*100 for i in range(3)]
    assert all(abs(dims[i]-row['dimensions_cm'][i])<.01 for i in range(3)),(row['name'],dims)
    verified.append(row['name'])
(OUT/'IndependentFBXVerification.json').write_text(json.dumps(dict(passed=True,asset_count=len(verified),assets=verified),indent=2),encoding='utf-8')
# Full editable architecture source: storeys, structure, fixtures and numbered rooms.
bpy.ops.wm.open_mainfile(filepath=str(OUT/'OldTownHotelArchitectureKit.blend'))
mats={k:bpy.data.materials[k] for k in colors}
for o in list(bpy.context.scene.objects):o.hide_render=True;o.hide_viewport=True
def collection(name):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
levels={i:collection('Floor_%d'%(i+1)) for i in range(4)}
structure=collection('WholeBuildingStructure')
matmap={'plaster':'Ceramic','concrete':'Ceramic','wood':'Wood','green':'DarkMetal','dark':'DarkMetal',
        'linen':'Linen','ceramic':'Ceramic','glass':'Glass'}
for row in plan['boxes']:
    lo,hi=row['world_min'],row['world_max'];center=[(lo[i]+hi[i])/200 for i in range(3)];size=[(hi[i]-lo[i])/100 for i in range(3)]
    o=cube(row['id'],center,size,matmap[row['material']],0);parts.clear()
    c=levels.get(row['floor'],structure)
    for oldc in list(o.users_collection):oldc.objects.unlink(o)
    c.objects.link(o)
for row in plan['props']:
    proto=bpy.data.objects.get('SM_OTS_Arch_'+row['asset_key']);assert proto,row
    o=proto.copy();o.data=proto.data;o.name=row['id'];o.hide_render=False;o.hide_viewport=False
    o.location=Vector(row['position_cm'])/100;o.rotation_euler[2]=math.radians(row['yaw']);o.scale=row['scale']
    f=min(range(4),key=lambda i:abs(row['position_cm'][2]-plan['floor_z_cm'][i]))
    levels[f].objects.link(o)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OldTownHotelArchitecture.blend'))
print('HOTEL_ARCHITECTURE_SOURCE_PASS assets=%d boxes=%d'%(len(assets),len(plan['boxes'])))
