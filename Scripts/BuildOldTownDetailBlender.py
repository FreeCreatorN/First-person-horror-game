"""Run inside the owned Blender helper through Blender MCP in two stages."""
import bpy, bmesh, json, math
from pathlib import Path
from mathutils import Vector

ROOT=Path('D:/UE/Project/HorrorGame')
OUT=ROOT/'SourceArt/OldTownDetailPolish_20261004'
COLLECTION='OldTownDetailPolish_20261004'

def material(name,color):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    return m

def setup():
    col=bpy.data.collections.get(COLLECTION)
    if col:
        for o in list(col.objects): bpy.data.objects.remove(o,do_unlink=True)
    else:
        col=bpy.data.collections.new(COLLECTION);bpy.context.scene.collection.children.link(col)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=1.
    return col

def mesh_object(name,vertices,faces,mat,col):
    mesh=bpy.data.meshes.new(name+'_Geometry');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);col.objects.link(obj);mesh.materials.append(mat)
    return obj

def bevel(obj,amount=.003,edges=None):
    bm=bmesh.new();bm.from_mesh(obj.data)
    selected=list(bm.edges) if edges is None else [e for e in bm.edges if edges(e)]
    if selected: bmesh.ops.bevel(bm,geom=selected,offset=amount,segments=3,affect='EDGES',clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()

def box(name,center,size,mat,col,rounding=.003):
    lo=[(center[i]-size[i]/2)/100 for i in range(3)]
    hi=[(center[i]+size[i]/2)/100 for i in range(3)]
    vertices=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
    faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    obj=mesh_object(name,vertices,faces,mat,col)
    if rounding: bevel(obj,rounding)
    return obj

def cylinder(name,center,radius,length,axis,mat,col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=radius/100,depth=length/100,location=Vector(center)/100)
    obj=bpy.context.object;obj.name=name
    for c in list(obj.users_collection): c.objects.unlink(obj)
    col.objects.link(obj)
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=Vector((0,0,1)).rotation_difference(Vector(axis))
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    obj.data.materials.append(mat);bevel(obj,.0015)
    return obj

def combine(objects,name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join();obj=objects[0];obj.name=name
    bpy.context.scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    # Unwrap only this new asset; leave the default helper scene untouched.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj

def generate():
    col=setup()
    mats={'Concrete':material('Concrete',(.65,.62,.52)),
          'Trim':material('Trim',(.13,.17,.14)),
          'Green':material('Green',(.22,.30,.25)),
          'Metal':material('Metal',(.26,.22,.17))}
    profiles=json.loads((OUT/'Profiles.json').read_text())
    for p in profiles:
        name=p['name'];kind=p['kind'];parts=[]
        if kind=='flight':
            n,r=p['steps'],p['rise'];run=n*28.
            top=[(0.,r)]
            for s in range(n):
                top.append(((s+1)*28.,(s+1)*r))
                if s+1<n:top.append(((s+1)*28.,(s+2)*r))
            boundary=[(0.,-20.-r),(run,n*r-20.-r)]+list(reversed(top))
            vertices=[(x/100,y/100,z/100) for x in (-70.,70.) for y,z in boundary]
            k=len(boundary)
            faces=[tuple(range(k-1,-1,-1)),tuple(range(k,2*k))]
            faces += [(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
            obj=mesh_object(name,vertices,faces,mats['Concrete'],col)
            def nose(e):
                a,b=e.verts
                if abs(a.co.x-b.co.x)<1.:return False
                y,z=a.co.y*100,a.co.z*100
                s=round(y/28.)
                return 0<=s<n and abs(y-s*28)<.001 and abs(z-(s+1)*r)<.001
            bevel(obj,.0025,nose);parts=[obj]
        elif kind=='landing':
            # Keep contacting top and bottom boundaries square; soften vertical corners.
            obj=box(name,[0,0,-p['size'][2]/2],p['size'],mats['Concrete'],col,0)
            bevel(obj,.0025,lambda e:abs(e.verts[0].co.z-e.verts[1].co.z)>.01)
            parts=[obj]
        elif kind=='trim':
            w,h=p['width'],p['height']
            xs=[-w/2-3,-w/2+4,-1.5,1.5,w/2-4,w/2+3]
            zs=[-h/2-3,-h/2+4,-1.5,1.5,h/2-4,h/2+3]
            filled={(i,j) for i in range(5) for j in range(5) if i in (0,2,4) or j in (0,2,4)}
            vertices=[];faces=[];ids={}
            def vertex(x,y,z):
                key=(x,y,z)
                if key not in ids:ids[key]=len(vertices);vertices.append((x/100,y/100,z/100))
                return ids[key]
            def face(points):faces.append(tuple(vertex(*p) for p in points))
            for i,j in sorted(filled):
                x0,x1=xs[i:i+2];z0,z1=zs[j:j+2];a,c=-1.75,1.75
                face([(x0,a,z0),(x1,a,z0),(x1,a,z1),(x0,a,z1)])
                face([(x0,c,z0),(x0,c,z1),(x1,c,z1),(x1,c,z0)])
                if (i-1,j) not in filled:face([(x0,a,z0),(x0,a,z1),(x0,c,z1),(x0,c,z0)])
                if (i+1,j) not in filled:face([(x1,a,z0),(x1,c,z0),(x1,c,z1),(x1,a,z1)])
                if (i,j-1) not in filled:face([(x0,a,z0),(x0,c,z0),(x1,c,z0),(x1,a,z0)])
                if (i,j+1) not in filled:face([(x0,a,z1),(x1,a,z1),(x1,c,z1),(x0,c,z1)])
            obj=mesh_object(name,vertices,faces,mats['Trim'],col)
            bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
            bevel(obj,.003,lambda e:e.calc_face_angle()>.01);parts=[obj]
        elif kind=='door':
            thick,length,height=p['size']
            parts=[box(name+'_Leaf',[0,0,0],p['size'],mats['Green'],col,.0025)]
            for face in (-1,1):
                for cz,ch in ((-height*.22,height*.32),(height*.22,height*.30)):
                    parts.append(box(name+'_Panel',[face*2.15,0,cz],[.5,length-22,ch],mats['Green'],col,.002))
                parts.append(box(name+'_Plate',[face*2.6,length/2-12,-height/2+110],[1.2,4,17],mats['Metal'],col,.003))
                parts.append(cylinder(name+'_Stem',[face*4.3,length/2-12,-height/2+110],.7,3,(1,0,0),mats['Metal'],col))
                parts.append(cylinder(name+'_Lever',[face*5.5,length/2-17,-height/2+110],.75,11,(0,1,0),mats['Metal'],col))
            for z in (-height/2+22,0,height/2-22):
                parts.append(cylinder(name+'_Hinge',[0,-length/2+.5,z],1.8,10,(0,0,1),mats['Metal'],col))
        combine(parts,name)
    print('DETAIL_PROFILES_GENERATED',len(profiles),flush=True)

def export():
    col=bpy.data.collections[COLLECTION]
    profiles={p['name']:p for p in json.loads((OUT/'Profiles.json').read_text())}
    entries=[]
    for obj in sorted(col.objects,key=lambda o:o.name):
        name=obj.name
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,global_scale=1.,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=True,use_triangles=True,bake_anim=False,
            axis_forward='-Y',axis_up='Z',bake_space_transform=False)
        pts=[obj.matrix_world@Vector(v) for v in obj.bound_box]
        bounds=[[min(p[i] for p in pts)*100 for i in range(3)],[max(p[i] for p in pts)*100 for i in range(3)]]
        bm=bmesh.new();bm.from_mesh(obj.data)
        nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free()
        # Joined disjoint decorative components are each closed volumes.
        assert nonmanifold==0,(name,nonmanifold)
        entries.append(dict(profiles[name],file=name+'.fbx',bounds_cm=bounds,dimensions_cm=[bounds[1][i]-bounds[0][i] for i in range(3)],
            vertices=len(obj.data.vertices),polygons=len(obj.data.polygons),nonmanifold_edges=nonmanifold))
    (OUT/'ImportManifest.json').write_text(json.dumps({'assets':entries,'units':'centimeters','contact_bevel_cm':.25},indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OldTownDetailPolish.blend'))
    print('DETAIL_ASSETS_EXPORTED',len(entries),flush=True)
