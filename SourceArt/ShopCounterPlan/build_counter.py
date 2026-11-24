"""Shop-counter planning-sheet revision. All distances in meters."""
import bpy, bmesh, math, json, runpy
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parent
S = bpy.data.scenes.new('Shop counter · planning sheet · low poly')
if bpy.context.window:
    bpy.context.window.scene = S
S.unit_settings.system = 'METRIC'
M = runpy.run_path(str(ROOT/'make_materials.py'))['create_counter_materials']()
PARTS = {}
COLLISIONS = {}
for key in ('Body','MetalFrame','FixedGlass','DisplayShelf','InteriorShelf','WoodDoorLeft','WoodDoorRight','GlassDoorLeft','GlassDoorRight'):
    c = bpy.data.collections.new(key)
    S.collection.children.link(c)
    PARTS[key] = c
    COLLISIONS[key] = []
STUDIO = bpy.data.collections.new('Preview only · cameras and lights')
S.collection.children.link(STUDIO)
PROPS = bpy.data.collections.new('Optional display stock · independent')
S.collection.children.link(PROPS)

def finish(name, rgb, rough=.6, metal=0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*rgb,1)
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb,1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    return m

def seam_material(key, axis, spacing):
    mat=M[key].copy()
    mat.name='M_Plan_InsetBoard_'+axis
    t=mat.node_tree
    p=next(n for n in t.nodes if n.type=='BSDF_PRINCIPLED')
    old=p.inputs['Base Color'].links[0].from_socket
    g=t.nodes.new('ShaderNodeNewGeometry')
    xyz=t.nodes.new('ShaderNodeSeparateXYZ');t.links.new(g.outputs['Position'],xyz.inputs[0])
    n=t.nodes.new('ShaderNodeMath');n.operation='MULTIPLY';n.inputs[1].default_value=1/spacing;t.links.new(xyz.outputs[axis],n.inputs[0])
    f=t.nodes.new('ShaderNodeMath');f.operation='PINGPONG';f.inputs[1].default_value=.5;t.links.new(n.outputs[0],f.inputs[0])
    edge=t.nodes.new('ShaderNodeMath');edge.operation='LESS_THAN';edge.inputs[1].default_value=.003;t.links.new(f.outputs[0],edge.inputs[0])
    mix=t.nodes.new('ShaderNodeMixRGB');mix.inputs[2].default_value=(.033,.016,.009,1)
    t.links.new(edge.outputs[0],mix.inputs[0]);t.links.new(old,mix.inputs[1]);t.links.new(mix.outputs[0],p.inputs['Base Color'])
    return mat
M['front']=seam_material('wood_red','X',.234)
M['side']=seam_material('wood_red','Y',.179)

def mesh(name, verts, faces, material, part, wear=.55):
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces);data.update()
    data.materials.append(M[material] if isinstance(material,str) else material)
    # The authored topology is closed. Normalize its winding once, before export.
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free()
    attr=data.color_attributes.new(name='Wear',type='FLOAT_COLOR',domain='POINT')
    attr.data.foreach_set('color',[v for _ in data.vertices for v in (wear,0,0,1)])
    obj=bpy.data.objects.new(name,data)
    (PARTS[part] if isinstance(part,str) else part).objects.link(obj)
    return obj

def bevel(obj, width):
    if width:
        mod=obj.modifiers.new('Single chamfer · budgeted','BEVEL');mod.width=width;mod.segments=1;mod.harden_normals=True
        mod=obj.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');mod.keep_sharp=True
    return obj

def box(name, center, size, material, part, chamfer=0, wear=.55, collision=False):
    x,y,z=center;a,b,c=[v/2 for v in size]
    verts=[(x+sx*a,y+sy*b,z+sz*c) for sz in (-1,1) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
    faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o=bevel(mesh(name,verts,faces,material,part,wear),chamfer)
    if collision:
        COLLISIONS[part].append({'center_m':center,'half_m':[a,b,c]})
    return o

# Exact shell dimensions: 196 x 62 x 109 cm. Front is -Y; staff is +Y.
for x in (-.915,0,.915):
    for y in (-.255,.255):
        box('Square hardwood foot',(x,y,.029),(.076,.076,.058),'wood_dark','Body',.0025,.85,True)
        box('Metal foot shoe',(x,y,.007),(.078,.078,.014),'metal','MetalFrame',0,.87)
box('Recessed bottom plinth',(0,0,.076),(1.888,.536,.036),'wood_dark','Body',.0018,.8,True)
box('Storage bottom',(0,0,.107),(1.872,.536,.026),'wood_inside','Body',.001,.35,True)
for x in (-.958,.958):
    for y in (-.289,.289):
        box('Cabinet corner stile',(x,y,.415),(.044,.042,.602),'wood_dark','Body',0,.72,True)
    box('Inset side panel',(x+math.copysign(.008,x),0,.415),(.028,.536,.530),'side','Body',.0011,.38,True)
    for z in (.132,.698):
        box('Side joinery rail',(x,0,z),(.044,.536,.036),'wood_red','Body',.0014,.7,True)
box('Inset front boards',(0,-.302,.415),(1.872,.016,.530),'front','Body',.0011,.31,True)
for z in (.132,.698):
    for y in (-.302,.302):
        box('Perimeter wood belt',(0,y,z),(1.872,.016,.036),'wood_red','Body',.0014,.75,True)
box('Storage center divider',(0,-.027,.412),(.018,.482,.584),'wood_inside','Body',0,.2,True)
for x in (-.4725,.4725):
    box('Removable internal shelf',(x,-.027,.405),(.927,.482,.020),'wood_inside','InteriorShelf',.001,.42,True)
box('Removable display base',(0,0,.734),(1.960,.620,.036),'wood_inside','DisplayShelf',.0017,.48,True)

# Narrow hardware follows the outer joinery. No overlapping duplicate surfaces.
for x in (-.979,.979):
    for y in (-.289,.289):
        box('Vertical corner strap',(x,y,.415),(.002,.042,.602),'metal','MetalFrame',0,.8)
for x in (-.958,.958):
    for y in (-.3115,.3115):
        box('Front and rear folded corner strap',(x,y,.415),(.044,.003,.602),'metal','MetalFrame',0,.8)
for z in (.124,.706):
    box('Front rubbed metal edge',(0,-.3115,z),(1.960,.003,.011),'metal','MetalFrame',0,.85)
    for x in (-.979,.979):
        box('Side rubbed metal edge',(x,0,z),(.002,.620,.011),'metal','MetalFrame',0,.83)

for x in (-.968,.968):
    for y in (-.298,.298):
        box('Display upright',(x,y,.9205),(.024,.024,.299),'metal','MetalFrame',.00065,.8,True)
for z in (.761,1.080):
    for y in (-.298,.298):
        box('Display long frame',(0,y,z),(1.960,.024,.020),'metal','MetalFrame',.00065,.83,True)
    for x in (-.968,.968):
        box('Display end frame',(x,0,z),(.024,.572,.020),'metal','MetalFrame',.00065,.81,True)
box('Front center mullion',(0,-.301,.9205),(.012,.014,.299),'metal','MetalFrame',0,.69,True)
box('Front continuous glass',(0,-.290,.9205),(1.912,.006,.299),'glass','FixedGlass',0,.0,True)
for x in (-.968,.968):
    box('Side fixed glass',(x,0,.9205),(.006,.572,.299),'glass','FixedGlass',0,.0,True)
box('Flush glass countertop',(0,0,1.086),(1.912,.572,.008),'glass','FixedGlass',0,.0,True)

# Each sliding pair runs on two physical tracks with distinct Y coordinates.
for family,zs,ys in [('Wood',(.140,.690),(.222,.254,.290)),('Glass',(.766,1.070),(.247,.272,.297))]:
    for z in zs:
        for y in ys:
            box(f'{family} track divider',(0,y,z),(1.894,.004,.008),'brass','MetalFrame',0,.64)

def rounded_rect(cx,cz,w,h,r):
    # Clockwise ordering viewed from the staff side; eight real corner vertices.
    return [(cx-w/2+r,cz-h/2),(cx+w/2-r,cz-h/2),(cx+w/2,cz-h/2+r),(cx+w/2,cz+h/2-r),
            (cx+w/2-r,cz+h/2),(cx-w/2+r,cz+h/2),(cx-w/2,cz+h/2-r),(cx-w/2,cz-h/2+r)]

def recessed_pull(name,cx,front_y,cz,part,w=.028,h=.108):
    # A closed pressed-metal cup. Its rim sits on the leaf and its recess is
    # genuinely hollow on the visible side, rather than a floating black plate.
    specs=[(w-.005,h-.005,.002,front_y-.0095),
           (w-.005,h-.005,.002,front_y+.0003),
           (w,h,.003,front_y+.0003),(w,h,.003,front_y+.0015),
           (w-.007,h-.007,.002,front_y+.0015),(w-.010,h-.010,.002,front_y-.007)]
    verts=[]
    for wi,hi,r,y in specs:
        verts.extend((x,y,z) for x,z in rounded_rect(cx,cz,wi,hi,r))
    faces=[tuple(reversed(range(8)))]
    for ring in range(len(specs)-1):
        for i in range(8):
            faces.append((ring*8+i,ring*8+(i+1)%8,(ring+1)*8+(i+1)%8,(ring+1)*8+i))
    faces.append(tuple(range((len(specs)-1)*8,len(specs)*8)))
    o=mesh(name,verts,faces,'metal',part,.85)
    o.data.materials.append(M['wood_dark'])
    o.data.polygons[-1].material_index=1
    return o

def holed_wood_leaf(name,cx,cy,cz,w,h,t,pull_x,part):
    # 8 matched outer and hole loops, 4 closed side ribbons. No coplanar stack.
    outer=rounded_rect(cx,cz,w,h,.001)
    inner=rounded_rect(pull_x,cz,.024,.104,.002)
    verts=[(x,y,z) for y in (cy-t/2,cy+t/2) for ring in (outer,inner) for x,z in ring]
    faces=[]
    for i in range(8):
        n=(i+1)%8
        faces += [(i,n,8+n,8+i),(16+i,24+i,24+n,16+n),
                  (i,16+i,16+n,n),(8+i,8+n,24+n,24+i)]
    o=mesh(name,verts,faces,'front',part,.42)
    COLLISIONS[part].append({'center_m':[cx,cy,cz],'half_m':[w/2,t/2,h/2]})
    recessed_pull('Recessed wood door pull',pull_x,cy+t/2,cz,part)
    return o

DOORS={}
for side,sign in [('Left',-1),('Right',1)]:
    part='WoodDoor'+side;cx=sign*.463;cy=.238 if side=='Left' else .272
    holed_wood_leaf('Sliding wood panel',cx,cy,.415,.940,.536,.018,cx+sign*.355,part)
    DOORS['wood_'+side.lower()]={'part':part,'mesh':'SM_ShopCounterPlan_'+part,'pivot_m':[cx,cy,.147],
        'closed_ue_cm':[cx*100,-cy*100,14.7],'travel_cm':-sign*92.6,'width_m':.940,'thickness_m':.018}
    part='GlassDoor'+side;cx=sign*.466;cy=.2595 if side=='Left' else .2885
    box('Sliding glass leaf',(cx,cy,.9205),(.928,.006,.271),'glass',part,0,.0,True)
    for x in (cx-.471,cx+.471):
        box('Door vertical edge',(x,cy,.9205),(.014,.010,.299),'metal',part,0,.78)
    for z in (.778,1.063):
        box('Door horizontal edge',(cx,cy,z),(.928,.010,.014),'metal',part,0,.8)
    # Handle is a metal sleeve fitting the stile, on the rear side only.
    px=cx+sign*.471
    box('Small glass pull backing',(px,cy+.00675,.916),(.019,.0035,.073),'metal',part,0,.67)
    recessed_pull('Recessed glass pull',px,cy+.018,.916,part,.018,.068)
    DOORS['glass_'+side.lower()]={'part':part,'mesh':'SM_ShopCounterPlan_'+part,'pivot_m':[cx,cy,.770],
        'closed_ue_cm':[cx*100,-cy*100,77.0],'travel_cm':-sign*93.2,'width_m':.956,'thickness_m':.006}

for key,spec in DOORS.items():
    c=PARTS[spec['part']]
    pivot=bpy.data.objects.new(spec['part']+'_SlideX',None);c.objects.link(pivot)
    pivot.location=spec['pivot_m'];pivot.empty_display_size=.04
    bpy.context.view_layer.update()
    for obj in list(c.objects):
        if obj==pivot:continue
            obj.parent=pivot;obj.matrix_parent_inverse=Matrix.Translation(-Vector(spec['pivot_m']));obj.matrix_basis=Matrix.Identity(4)
    start={'glass_left':16,'glass_right':76,'wood_left':136,'wood_right':196}[key]
    for frame,alpha in [(1,0),(start,0),(start+18,1),(start+36,1),(start+54,0),(260,0)]:
        pivot.location.x=spec['pivot_m'][0]+spec['travel_cm']*.01*alpha
        pivot.keyframe_insert(data_path='location',frame=frame)
    pivot['UE_component']=spec['part'];pivot['travel_local_x_cm']=spec['travel_cm']
    spec['parent']=pivot.name
    S.timeline_markers.new(key+' open',frame=start+18)
S.frame_start=1;S.frame_end=260;S.render.fps=30;S.frame_set(1)

# Optional simple merchandise is excluded from cabinet budget and UE export.
colors=[finish('Stock · red',(.28,.035,.018)),finish('Stock · green',(.025,.12,.065)),
        finish('Stock · yellow',(.40,.22,.035)),finish('Stock · blue',(.025,.09,.14))]
label=finish('Stock · old ivory print',(.66,.59,.43),.8)
for row in range(2):
    for i in range(10):
        x=(i-4.5)*.17;y=-.16+row*.19;h=.067+.014*(i%2)
        box('Removable merchandise carton',(x,y,.752+h/2),(.157,.16,h),colors[(i//2+row)%4],PROPS)
        box('Carton label',(x,y-.0801,.752+h/2),(.108,.0002,h*.60),label,PROPS)

def jar(cx,r,h,cap):
    z=1.090;cy=.13;n=12
    rings=[(r*.82,z),(r,z+.008),(r,z+h*.77),(r*.69,z+h*.9),(r*.69,z+h)]
    verts=[(cx+rr*math.cos(i*math.tau/n),cy+rr*math.sin(i*math.tau/n),zz) for rr,zz in rings for i in range(n)]
    faces=[tuple(reversed(range(n)))]
    for j in range(len(rings)-1):
        faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
    faces.append(tuple(range(4*n,5*n)))
    # Tinted opaque candy-filled silhouette keeps stock cheap; glass cabinet is real glass.
    o=mesh('Removable candy jar',verts,faces,colors[2],PROPS,.2)
    for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
    capmat=colors[0] if cap=='red' else colors[2]
    ring=[(cx+r*.73*math.cos(i*math.tau/n),cy+r*.73*math.sin(i*math.tau/n),zz) for zz in (z+h-.002,z+h+.012) for i in range(n)]
    f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    mesh('Removable jar lid',ring,f,capmat,PROPS,.4)
    box('Jar paper label',(cx,cy-r-.0001,z+h*.43),(r*1.05,.0002,h*.37),label,PROPS)
jar(.69,.067,.17,'red');jar(.51,.058,.155,'yellow')

def camera(name,loc,target,scale):
    data=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,data);STUDIO.objects.link(o)
    o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO';data.ortho_scale=scale;return o
front=camera('01 Front45',(-2.4,-4.7,2.05),(0,0,.57),2.47)
camera('02 Rear45',(-2.1,4.8,1.90),(0,0,.57),2.47)
camera('03 Front orthographic',(0,-5,.64),(0,0,.64),2.2)
for name,loc,power,size in [('Soft key',(-2,-3.2,3.5),500,3),('Rear fill',(-1,3,2.7),350,2.5),('Side rim',(3,.2,2.5),270,2.3)]:
    data=bpy.data.lights.new(name,'AREA');o=bpy.data.objects.new(name,data);STUDIO.objects.link(o)
    o.location=loc;o.rotation_euler=(Vector((0,0,.6))-o.location).to_track_quat('-Z','Y').to_euler();data.energy=power;data.shape='DISK';data.size=size
ground=finish('Preview charcoal',(.024,.022,.019),.86)
box('Preview floor',(0,0,-.021),(200,200,.04),ground,STUDIO)
S.world=bpy.data.worlds.new('Preview world');S.world.use_nodes=True
S.world.node_tree.nodes['Background'].inputs[0].default_value=(.14,.135,.12,1)
S.world.node_tree.nodes['Background'].inputs[1].default_value=.3
S.render.engine='CYCLES';S.cycles.samples=32;S.cycles.use_denoising=True;S.cycles.transmission_bounces=10
S.eevee.use_raytracing=True
S.render.resolution_x=1500;S.render.resolution_y=1080;S.render.resolution_percentage=100
S.view_settings.view_transform='AgX';S.camera=front
S.render.image_settings.file_format='PNG'

def tris(obj):
    with bpy.context.temp_override(scene=S,view_layer=S.view_layers[0]):
        S.view_layers[0].update()
        e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());data=e.to_mesh();data.calc_loop_triangles();n=len(data.loop_triangles);e.to_mesh_clear();return n
bpy.context.view_layer.update()
budget={part:sum(tris(o) for o in coll.objects if o.type=='MESH') for part,coll in PARTS.items()}
total=sum(budget.values())
assert 1800 <= total <= 3500, (total,budget)
report={'success':True,'nominal_case_m':[1.96,.62,1.09],'triangle_budget':[1800,3500],'triangles_by_part':budget,'total_triangles':total,
        'optional_stock_triangles':sum(tris(o) for o in PROPS.objects if o.type=='MESH'),
        'parts':{p:{'collection':c.name,'mesh':'SM_ShopCounterPlan_'+p,'pivot_m':next((d['pivot_m'] for d in DOORS.values() if d['part']==p),[0,0,0])} for p,c in PARTS.items()},
        'doors':DOORS,'collision_boxes':COLLISIONS,'preview_collection':STUDIO.name,'stock_collection':PROPS.name,
        'door_track_spacing_mm':{'wood':34,'glass':29},'front':'-Y','access':'+Y'}
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    w.scene=S
    for a in w.screen.areas:
        if a.type=='VIEW_3D':
            sp=a.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False
            sp.region_3d.view_location=(0,0,.56);sp.region_3d.view_distance=3.0
            sp.region_3d.view_rotation=front.rotation_euler.to_quaternion();sp.region_3d.view_perspective='ORTHO'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'ShopCounterPlan.blend'))
print('SHOP_COUNTER_CREATED',json.dumps({'total_triangles':total,'parts':budget}),flush=True)
