"""Create hinge-origin opening parts in the owned Blender MCP session."""
import bpy, bmesh, json, sys
from pathlib import Path
from mathutils import Vector

ROOT=Path('D:/UE/Project/HorrorGame')
sys.path.insert(0,str(ROOT/'Scripts'))
import BuildOldTownDetailBlender as base
OUT=ROOT/'SourceArt/OldTownHotelOpenings_20261004'
COLLECTION='OldTownHotelOpenings_20261004'

def key(kind,w,h):
    return 'SM_OTS_'+kind+'_'+str(round(w*10))+'_'+str(round(h*10))

def mesh_bounds_cm(obj):
    """Read evaluated world coordinates from mesh vertices, never cached dimensions."""
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    assert points, 'Hotel sign mesh is empty'
    return [[min(p[i] for p in points)*100 for i in range(3)],
            [max(p[i] for p in points)*100 for i in range(3)]]

def validate_hotel_sign(obj):
    bounds=mesh_bounds_cm(obj)
    dimensions=[bounds[1][i]-bounds[0][i] for i in range(3)]
    assert 0<dimensions[0]<450, ('Hotel sign width',dimensions)
    assert abs(dimensions[2]-48.)<=.01, ('Hotel sign height',dimensions)
    assert 0<dimensions[1]<2, ('Hotel sign depth',dimensions)
    return bounds,dimensions

def normalize_hotel_sign(obj):
    """Normalize the converted, rotation-applied mesh to a 48 cm letter height."""
    assert obj.type=='MESH'
    points=[v.co.copy() for v in obj.data.vertices]
    low=[min(p[i] for p in points) for i in range(3)]
    high=[max(p[i] for p in points) for i in range(3)]
    assert high[2]>low[2], 'Hotel letters have no vertical extent'
    factor=.48/(high[2]-low[2])
    # Keep the asset pivot at the bottom center, with extrusion centered in depth.
    offset=Vector(((low[0]+high[0])*.5,(low[1]+high[1])*.5,low[2]))
    for vertex in obj.data.vertices:
        vertex.co=(vertex.co-offset)*factor
    obj.data.update()
    bpy.context.view_layer.update()
    return validate_hotel_sign(obj)

def ring(name,xs,zs,filled,mat,col,depth=3.5):
    vertices=[];faces=[];ids={}
    def vertex(x,y,z):
        k=(x,y,z)
        if k not in ids:ids[k]=len(vertices);vertices.append((x/100,y/100,z/100))
        return ids[k]
    def face(ps):faces.append(tuple(vertex(*p) for p in ps))
    for i,j in sorted(filled):
        x0,x1=xs[i:i+2];z0,z1=zs[j:j+2];a,c=-depth/2,depth/2
        face([(x0,a,z0),(x1,a,z0),(x1,a,z1),(x0,a,z1)])
        face([(x0,c,z0),(x0,c,z1),(x1,c,z1),(x1,c,z0)])
        if (i-1,j) not in filled:face([(x0,a,z0),(x0,a,z1),(x0,c,z1),(x0,c,z0)])
        if (i+1,j) not in filled:face([(x1,a,z0),(x1,c,z0),(x1,c,z1),(x1,a,z1)])
        if (i,j-1) not in filled:face([(x0,a,z0),(x0,c,z0),(x1,c,z0),(x1,a,z0)])
        if (i,j+1) not in filled:face([(x0,a,z1),(x1,a,z1),(x1,c,z1),(x0,c,z1)])
    obj=base.mesh_object(name,vertices,faces,mat,col)
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    base.bevel(obj,.002,lambda e:e.calc_face_angle()>.01)
    return obj

def generate():
    base.COLLECTION=COLLECTION;col=base.setup();OUT.mkdir(parents=True,exist_ok=True)
    mats={k:base.material(k,c) for k,c in {'Trim':(.13,.17,.14),'Green':(.22,.30,.25),'Metal':(.26,.22,.17),'Glass':(.12,.20,.22)}.items()}
    profiles=[]
    def add(kind,w,h,parts):
        name=key(kind,w,h);base.combine(parts,name);profiles.append({'name':name,'kind':kind,'width':w,'height':h,'pivot':'hinge' if kind not in ('DoorFrame','WindowFrame') else 'opening_bottom_center'})
    for w,h in ((140.,230.),(120.,186.),(90.,200.)):
        name=key('DoorFrame',w,h);xs=[-w/2-3,-w/2+4,w/2-4,w/2+3];zs=[0,h-(2 if h<200 else 4),h+3]
        add('DoorFrame',w,h,[ring(name,xs,zs,{(i,j) for i in range(3) for j in range(2) if i in (0,2) or j==1},mats['Trim'],col,5.)])
        length=w-8.8;parts=[base.box('Leaf',[length/2,0,(h-4)/2],[length,4,h-5.2],mats['Green'],col,.002)]
        for s in (-1,1):
            for z,hh in ((h*.28,h*.30),(h*.71,h*.29)):
                parts.append(base.box('RaisedPanel',[length/2,s*2.2,z],[length-20,.4,hh],mats['Green'],col,.002))
        for z in (22,h*.5,h-22):parts.append(base.cylinder('Hinge',[0,0,z],1.6,9,[0,0,1],mats['Metal'],col))
        add('DoorLeaf',w,h,parts)
        parts=[]
        for s in (-1,1):
            parts.append(base.box('Plate',[length-11,s*2.8,105],[4,1.2,16],mats['Metal'],col,.002))
            parts.append(base.cylinder('Stem',[length-11,s*4.1,105],.7,3,[0,1,0],mats['Metal'],col))
            parts.append(base.cylinder('Lever',[length-16,s*5.5,105],.7,11,[1,0,0],mats['Metal'],col))
        add('DoorHandle',w,h,parts)
    for w,h in ((125.,120.),(90.,90.)):
        xs=[-w/2-3,-w/2+4,w/2-4,w/2+3];zs=[-3,4,h-4,h+3]
        add('WindowFrame',w,h,[ring('WindowFrame',xs,zs,{(i,j) for i in range(3) for j in range(3) if i in (0,2) or j in (0,2)},mats['Trim'],col)])
        length=(w-8)/2-.5
        xs=[0,6,length-6,length];zs=[4.3,10.3,h/2-1.5,h/2+1.5,h-10.3,h-4.3]
        add('WindowSash',w,h,[ring('Sash',xs,zs,{(i,j) for i in range(3) for j in range(5) if i in (0,2) or j in (0,2,4)},mats['Trim'],col)])
        glass=[]
        for z0,z1 in ((10.2,h/2-1.4),(h/2+1.4,h-10.2)):
            glass.append(base.box('Glass',[(6+length-6)/2,0,(z0+z1)/2],[length-11.8,1,z1-z0],mats['Glass'],col,0))
        add('WindowGlass',w,h,glass)
    curve=bpy.data.curves.new('HotelSignLetters','FONT');curve.body='老城酒店'
    curve.font=bpy.data.fonts.load('C:/Windows/Fonts/simhei.ttf');curve.align_x='CENTER'
    curve.extrude=.002;curve.bevel_depth=.0005;curve.bevel_resolution=1
    text=bpy.data.objects.new('HotelSignLetters',curve);col.objects.link(text)
    text.rotation_euler=(1.5707963267948966,0,0)
    bpy.ops.object.select_all(action='DESELECT');text.select_set(True);bpy.context.view_layer.objects.active=text
    bpy.ops.object.convert(target='MESH');text=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    normalize_hotel_sign(text)
    bm=bmesh.new();bm.from_mesh(text.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(text.data);bm.free()
    text.data.materials.append(base.material('Concrete',(.65,.62,.52)))
    sign=base.combine([text],'SM_OTS_HotelSignLetters')
    _bounds,dimensions=validate_hotel_sign(sign)
    profiles.append({'name':'SM_OTS_HotelSignLetters','kind':'sign','width':dimensions[0],'height':48,'pivot':'bottom_center'})
    (OUT/'Profiles.json').write_text(json.dumps(profiles,indent=2),encoding='utf-8')
    print('OPENING_PARTS_CREATED',len(profiles),flush=True)

def export():
    profiles={r['name']:r for r in json.loads((OUT/'Profiles.json').read_text())};entries=[]
    for obj in sorted(bpy.data.collections[COLLECTION].objects,key=lambda o:o.name):
        if obj.name=='SM_OTS_HotelSignLetters':validate_hotel_sign(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.fbx(filepath=str(OUT/(obj.name+'.fbx')),use_selection=True,global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=True,use_triangles=True,bake_anim=False,axis_forward='-Y',axis_up='Z',bake_space_transform=False)
        pts=[obj.matrix_world@Vector(v) for v in obj.bound_box]
        bounds=[[min(p[i] for p in pts)*100 for i in range(3)],[max(p[i] for p in pts)*100 for i in range(3)]]
        bm=bmesh.new();bm.from_mesh(obj.data);nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free();assert nonmanifold==0,(obj.name,nonmanifold)
        entries.append(dict(profiles[obj.name],file=obj.name+'.fbx',bounds_cm=bounds,dimensions_cm=[bounds[1][i]-bounds[0][i] for i in range(3)],vertices=len(obj.data.vertices),polygons=len(obj.data.polygons),nonmanifold_edges=nonmanifold))
    (OUT/'ImportManifest.json').write_text(json.dumps({'assets':entries,'units':'centimeters','pivot_coordinates':'centimeters from hinge or opening bottom'},indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OldTownHotelOpenings.blend'))
    print('OPENING_PARTS_EXPORTED',len(entries),flush=True)
