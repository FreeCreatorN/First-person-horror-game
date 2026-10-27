"""Repair only this round's Blender/FBX source art, never Unreal packages.

Exact unions remove overlapping internal shells in diagnosed variants. All 143
meshes receive fresh per-triangle physical UVs. Original role slots, local
pivots, and outer envelopes are acceptance constraints, not approximations.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'SourceArt/OldTownRealism_20261012'
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
DIAGNOSTIC=WORK/'BeforePrecisionEvidence/DiagnosticScanOcclusion.json'
CATEGORIES=('Architecture','Furniture','Sanitary','Street')
UV_CHART_OFFSETS={(0,1):(0.,0.),(0,2):(.000137,.000223),(1,2):(.000271,.000389)}


def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def double_cross(points):
    a,b,c=points
    u=[b[i]-a[i] for i in range(3)]
    v=[c[i]-a[i] for i in range(3)]
    return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])


def native_precision_facing(points,scale):
    precise=double_cross(points)
    rounded=[[f32(f32(p[i]/(100*scale[i]))*100)*scale[i] for i in range(3)] for p in points]
    native=double_cross(rounded)
    lengths=[math.sqrt(sum(v*v for v in cross)) for cross in (precise,native)]
    physical_facing=sum(a*b for a,b in zip(precise,native))/max(lengths[0]*lengths[1],1e-30)
    local=[[float(f32(p[i]/(100*scale[i])))*100.0 for i in range(3)] for p in points]
    quantized=[[f32(v) for v in p] for p in local]
    a,b=double_cross(local),double_cross(quantized)
    local_facing=sum(x*y for x,y in zip(a,b))/max(math.sqrt(sum(x*x for x in a)*sum(y*y for y in b)),1e-30)
    return min(physical_facing,local_facing)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnosed_mesh_names():
    doc=load(DIAGNOSTIC)
    rows=[r for r in doc['overlaps'] if r['intra_component'] and not r.get('buried') and r.get('exposed_area_cm2',0)>0]
    return {m['mesh'].rsplit('.',1)[-1] for r in rows for m in r['component_metadata']}


def physical_scale(category,variant):
    if category=='Furniture':
        return [v/100 for v in variant['world_dimensions_cm']]
    if category=='Sanitary':
        return [1.,1.,1.]
    return variant['component_scale']


def components(data):
    adjacency=[[] for _ in data.vertices]
    for edge in data.edges:
        a,b=edge.vertices
        adjacency[a].append(b)
        adjacency[b].append(a)
    unseen=set(range(len(data.vertices)))
    groups=[]
    while unseen:
        seed=next(iter(unseen))
        group={seed}
        unseen.remove(seed)
        stack=[seed]
        while stack:
            for other in adjacency[stack.pop()]:
                if other in unseen:
                    unseen.remove(other)
                    group.add(other)
                    stack.append(other)
        groups.append(group)
    return groups


def manifold_face_components(data):
    """Recover closed physical parts even when separate solids share a vertex edge."""
    incidence=defaultdict(list)
    for poly in data.polygons:
        ids=list(poly.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):
            incidence[tuple(sorted((a,b)))].append(poly.index)
    adjacency=[[] for _ in data.polygons]
    for faces in incidence.values():
        if len(faces)==2:
            a,b=faces
            adjacency[a].append(b)
            adjacency[b].append(a)
    unseen=set(range(len(data.polygons)));groups=[]
    while unseen:
        seed=min(unseen);unseen.remove(seed);group={seed};stack=[seed]
        while stack:
            for other in adjacency[stack.pop()]:
                if other in unseen:
                    unseen.remove(other);group.add(other);stack.append(other)
        groups.append(group)
    return groups


def inspect():
    import bpy
    import bmesh
    result={}
    diagnosed=diagnosed_mesh_names()
    for category in CATEGORIES:
        manifest=load(BASE/category/'ModelDataManifest.json')
        blend=manifest.get('blend_file') or manifest['source_blend_file']
        bpy.ops.wm.open_mainfile(filepath=blend)
        for variant in manifest['variants']:
            obj=bpy.data.objects[variant['mesh_name']]
            groups=components(obj.data)
            bm=bmesh.new()
            bm.from_mesh(obj.data)
            row=dict(category=category,parts=len(groups),vertices=len(obj.data.vertices),
                     faces=len(obj.data.polygons),nonmanifold=sum(not e.is_manifold for e in bm.edges),
                     degenerate=sum(f.calc_area()<=1e-15 for f in bm.faces),volume=bm.calc_volume(signed=True),
                     material_roles=[m.name for m in obj.data.materials],diagnosed=obj.name in diagnosed)
            bm.free()
            result[obj.name]=row
            print('INSPECT',obj.name,row,flush=True)
    write(WORK/'SourceSolidsInventory.json',result)
    return result


def backup_category(category,manifest):
    folder=BASE/category
    backup=folder/'BeforeSolids'
    backup.mkdir(exist_ok=True)
    paths=[folder/'ModelDataManifest.json',Path(manifest.get('blend_file') or manifest['source_blend_file'])]
    for v in manifest['variants']:
        paths.append(folder/v['fbx_file'])
        if v.get('geometry_recipe_file'):
            paths.append(Path(v['geometry_recipe_file']))
    records={}
    for path in paths:
        destination=backup/(path.name+'.bak')
        if not destination.exists():
            shutil.copy2(path,destination)
        records[str(path)]=dict(backup=str(destination),sha256=sha(destination))
    index=backup/'BackupIndex.json'
    if not index.exists():
        write(index,records)
    return load(index)


def repair():
    import bpy
    import bmesh
    from mathutils import Vector
    import inspect as python_inspect
    import io_scene_fbx.export_fbx_bin as fbx_writer

    def actual_uv_tangent_space(mesh,kind,output):
        """FBX corner frame computed from positions, UV derivatives and normals."""
        mesh.calc_loop_triangles()
        layer=mesh.uv_layers.active
        frames=[None]*len(mesh.loops)
        for tri in mesh.loop_triangles:
            points=[mesh.vertices[i].co.copy() for i in tri.vertices]
            tex=[layer.data[i].uv.copy() for i in tri.loops]
            e1,e2=points[1]-points[0],points[2]-points[0]
            u1,u2=tex[1]-tex[0],tex[2]-tex[0]
            det=u1.x*u2.y-u1.y*u2.x
            assert abs(det)>=1e-12,(mesh.name,'UV derivative singular',tri.index,det)
            tangent=(e1*u2.y-e2*u1.y)/det
            bitangent=(e2*u1.x-e1*u2.x)/det
            for li in tri.loops:
                normal=mesh.corner_normals[li].vector.normalized()
                projected=tangent-normal*tangent.dot(normal)
                assert projected.length>1e-12,(mesh.name,'normal parallel to UV derivative',tri.index,li)
                t=projected.normalized()
                sign=-1 if normal.cross(t).dot(bitangent)<0 else 1
                b=normal.cross(t).normalized()*sign
                frames[li]=t if kind=='tangent' else b
        assert all(v is not None and v.length>.99 and all(math.isfinite(c) for c in v) for v in frames)
        for i,vector in enumerate(frames):
            output[i*3:i*3+3]=tuple(vector)

    # The built-in exporter recomputes Mikk inside export, so supplying an
    # external array alone would not reach the FBX. Replace only its two corner
    # frame readers in this isolated process; installed Blender files are read-only.
    export_source=python_inspect.getsource(fbx_writer.fbx_data_mesh_elements)
    for kind in ('tangent','bitangent'):
        needle='me.loops.foreach_get("'+kind+'", t_ln)'
        assert export_source.count(needle)==1
        export_source=export_source.replace(needle,'_codex_actual_uv_tangent_space(me, "'+kind+'", t_ln)')
    fbx_writer.__dict__['_codex_actual_uv_tangent_space']=actual_uv_tangent_space
    exec(compile(export_source,'<owned source exact UV derivative FBX tangent writer>','exec'),fbx_writer.__dict__)
    diagnosed=diagnosed_mesh_names()
    result=dict(schema='OldTownRealismSourceSolidUVRepairV1',passed=False,
        diagnostic_file=str(DIAGNOSTIC),diagnostic_sha256=sha(DIAGNOSTIC),
        source_script_sha256=sha(__file__),diagnosed_unique_mesh_count=len(diagnosed),
        target_variant_count=143,variants=[],errors=[],categories={},
        policy='Exact UNION of actual closed parts; retain material indices, measured local pivots and envelopes; dominant geometric-plane physical UVs on every actual triangle; no Unreal writes')
    selected_categories=CATEGORIES
    if '--resume-street' in sys.argv:
        result=load(WORK/'SourceSolidsRepair.json')
        assert all(c in result['categories'] for c in CATEGORIES[:-1])
        result['variants']=[r for r in result['variants'] if r['category']!='Street']
        result['categories'].pop('Street',None)
        result['passed']=False
        result['source_script_sha256']=sha(__file__)
        selected_categories=('Street',)
    elif '--resume-furniture' in sys.argv:
        result=load(WORK/'SourceSolidsRepair.json')
        assert set(CATEGORIES)-{'Furniture'}<=set(result['categories'])
        result['variants']=[r for r in result['variants'] if r['category']!='Furniture']
        result['categories'].pop('Furniture',None)
        result['passed']=False
        result['source_script_sha256']=sha(__file__)
        selected_categories=('Furniture',)
    write(WORK/'SourceSolidsRepair.json',result)

    def topology(data):
        bm=bmesh.new()
        bm.from_mesh(data)
        def actual_double_area(face):
            points=[tuple(v.co) for v in face.verts]
            a=points[0]
            total=0.
            for i in range(1,len(points)-1):
                b,c=points[i],points[i+1]
                u=[b[j]-a[j] for j in range(3)]
                v=[c[j]-a[j] for j in range(3)]
                cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                total+=math.sqrt(sum(value*value for value in cross))/2
            return total
        report=dict(nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
            degenerate_faces=sum(actual_double_area(f)<=1e-10 for f in bm.faces),
            geometric_area_method='Double precision cross from actual vertex buffers; no float Newell cancellation',
            signed_volume_cm3=bm.calc_volume(signed=True))
        bm.free()
        return report

    def closed_orient(part,close_source_holes=False):
        bm=bmesh.new()
        bm.from_mesh(part.data)
        # Sub-micrometre zero edges are geometric noise, not useful surfaces.
        # Preserve material boundaries and all actual architectural features.
        bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
        boundary=[e for e in bm.edges if e.is_boundary]
        filled=0
        if boundary and close_source_holes:
            filled=len(bmesh.ops.holes_fill(bm,edges=boundary,sides=0).get('faces',[]))
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        if bm.calc_volume(signed=True)<0:
            bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
        bm.to_mesh(part.data)
        bm.free()
        part.data.update()
        report=topology(part.data)
        assert report['nonmanifold_edges']==0 and report['degenerate_faces']==0 and report['signed_volume_cm3']>0,(part.name,report)
        report['filled_original_boundary_faces']=filled
        return report

    for category in selected_categories:
        manifest_path=BASE/category/'ModelDataManifest.json'
        manifest=load(manifest_path)
        backups=backup_category(category,manifest)
        manifest=load(backups[str(manifest_path)]['backup'])
        blend=Path(manifest.get('blend_file') or manifest['source_blend_file'])
        bpy.ops.wm.open_mainfile(filepath=backups[str(blend)]['backup'])
        scene=bpy.context.scene
        scene.unit_settings.system='METRIC'
        scene.unit_settings.scale_length=1
        original_manifest_sha=sha(backups[str(manifest_path)]['backup'])
        category_reports=[]
        for variant in manifest['variants']:
            name=variant['mesh_name']
            obj=bpy.data.objects[name]
            obj.hide_set(False)
            obj.hide_render=False
            assert len(obj.modifiers)==0 and tuple(obj.scale)==(1,1,1) and obj.location.length<1e-9,name
            roles=[m.name for m in obj.data.materials]
            assert roles==variant['material_roles'],(name,'role order',roles,variant['material_roles'])
            scale=physical_scale(category,variant)
            before_bounds=[[min(v.co[i]*100 for v in obj.data.vertices) for i in range(3)],
                           [max(v.co[i]*100 for v in obj.data.vertices) for i in range(3)]]
            before_triangles=len(obj.data.polygons)
            # Physical centimetres avoid giant axis ratios on normalized engine cubes.
            for vertex in obj.data.vertices:
                for i in range(3):
                    vertex.co[i]*=100*scale[i]
            obj.data.update()
            original_physical_vertices={tuple(v.co) for v in obj.data.vertices}
            source_topology=topology(obj.data)
            source_multi_edge_repair=category=='Street' and 'CardboardBox' in name and source_topology['nonmanifold_edges']>0
            union=name in diagnosed or source_multi_edge_repair
            groups=manifold_face_components(obj.data)
            part_objects=[]
            source_part_checks=[]
            for number,group in enumerate(groups):
                polygons=[obj.data.polygons[i] for i in sorted(group)]
                ids=sorted({i for p in polygons for i in p.vertices})
                mapping={v:i for i,v in enumerate(ids)}
                mesh=bpy.data.meshes.new(name+'_ClosedPart_%03d'%number)
                mesh.from_pydata([tuple(obj.data.vertices[i].co) for i in ids],[],
                    [tuple(mapping[i] for i in p.vertices) for p in polygons])
                mesh.update()
                for mat in obj.data.materials:
                    mesh.materials.append(mat)
                for p,old in zip(mesh.polygons,polygons):
                    p.material_index=old.material_index
                    p.use_smooth=old.use_smooth
                part=bpy.data.objects.new(mesh.name,mesh)
                scene.collection.objects.link(part)
                report=closed_orient(part,category=='Street')
                source_part_checks.append(report)
                part_objects.append(part)
            olddata=obj.data
            # Replace the old disconnected object with the exact union result.
            if union:
                part_objects.sort(key=lambda p:topology(p.data)['signed_volume_cm3'],reverse=True)
                solid=part_objects.pop(0)
                bpy.context.view_layer.objects.active=solid
                bpy.ops.object.select_all(action='DESELECT')
                solid.select_set(True)
                unions=[]
                for operand in part_objects:
                    before=topology(solid.data)
                    mod=solid.modifiers.new('ExactClosedPartUnion','BOOLEAN')
                    mod.operation='UNION'
                    mod.solver='EXACT'
                    mod.object=operand
                    mod.use_self=True
                    mod.use_hole_tolerant=True
                    if hasattr(mod,'material_mode'):
                        mod.material_mode='INDEX'
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    after=closed_orient(solid)
                    unions.append(dict(operand=operand.name,before=before,after=after))
                    data=operand.data
                    bpy.data.objects.remove(operand,do_unlink=True)
                    if not data.users:
                        bpy.data.meshes.remove(data)
                obj.data=solid.data
                bpy.data.objects.remove(solid,do_unlink=True)
                part_objects.clear()
            else:
                # Joining preserves separate parts; repaired source holes and
                # corrected windings are retained without unnecessary unions.
                verts,faces,materials=[],[],[]
                for part in part_objects:
                    offset=len(verts)
                    verts.extend(tuple(v.co) for v in part.data.vertices)
                    for p in part.data.polygons:
                        faces.append(tuple(offset+i for i in p.vertices))
                        materials.append(p.material_index)
                data=bpy.data.meshes.new(name+'_RepairedPhysical')
                data.from_pydata(verts,[],faces)
                data.update()
                for mat in olddata.materials:
                    data.materials.append(mat)
                for p,mat in zip(data.polygons,materials):
                    p.material_index=mat
                    p.use_smooth=True
                obj.data=data
                for part in part_objects:
                    data=part.data
                    bpy.data.objects.remove(part,do_unlink=True)
                    if not data.users:
                        bpy.data.meshes.remove(data)
                part_objects.clear()
                unions=[]
            if not olddata.users:
                bpy.data.meshes.remove(olddata)
            data=obj.data
            # Exact coplanar simplification avoids thin diagonals introduced by
            # intersection tessellation. No material borders are dissolved.
            bm=bmesh.new()
            bm.from_mesh(data)
            bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
            bmesh.ops.dissolve_limit(bm,angle_limit=1e-7,verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL'})
            bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
            collinear_removed=0
            collinear_edges_rotated=0
            numerical_boundary_collapses=0
            maximum_numerical_boundary_collapse_cm=0.
            native_precision_needle_repairs=0
            for _ in range(300):
                candidate=None
                rotate=None
                collapse=None
                for face in bm.faces:
                    if len(face.verts)!=3:
                        continue
                    verts=list(face.verts)
                    points=[tuple(v.co) for v in verts]
                    normal=double_cross(points)
                    precision_risk=native_precision_facing(points,scale)<.995
                    if max(abs(v) for v in normal)>=2e-7 and not precision_risk:
                        continue
                    longest=max(face.edges,key=lambda e:e.calc_length())
                    middle=next(v for v in verts if v not in longest.verts)
                    a,b=[v.co for v in longest.verts]
                    if (b-a).length<=1e-12:
                        continue
                    distance=(middle.co-a).cross(b-a).length/(b-a).length
                    if distance<1e-5:
                        if len({f.material_index for f in middle.link_faces})==1:
                            candidate=middle
                        else:
                            def stable_rotation(edge):
                                if len(edge.link_faces)!=2 or not all(len(f.verts)==3 and f.material_index==face.material_index for f in edge.link_faces):
                                    return False
                                a,b=edge.verts
                                c,d=[next(v for v in f.verts if v not in edge.verts) for f in edge.link_faces]
                                for triangle in ((tuple(c.co),tuple(d.co),tuple(a.co)),(tuple(d.co),tuple(c.co),tuple(b.co))):
                                    if max(abs(v) for v in double_cross(triangle))<2e-7 or native_precision_facing(triangle,scale)<.995:
                                        return False
                                return True
                            usable=[e for e in face.edges if stable_rotation(e)]
                            if usable:
                                rotate=max(usable,key=lambda e:e.calc_length())
                            else:
                                target=min(longest.verts,key=lambda v:(v.co-middle.co).length)
                                if (target.co-middle.co).length<.0001:
                                    collapse=(middle,target)
                        if candidate is not None or rotate is not None or collapse is not None:
                            if precision_risk:
                                native_precision_needle_repairs+=1
                            break
                if candidate is None and rotate is None and collapse is None:
                    break
                # Remove only a sub-micrometre deviation along an existing edge.
                # This fixes rational boolean tessellation slivers instead of
                # retaining triangles whose true UV area is effectively zero.
                if candidate is not None:
                    bmesh.ops.dissolve_verts(bm,verts=[candidate],use_face_split=False,use_boundary_tear=False)
                    collinear_removed+=1
                elif rotate is not None:
                    bmesh.ops.rotate_edges(bm,edges=[rotate],use_ccw=False)
                    collinear_edges_rotated+=1
                else:
                    middle,target=collapse
                    distance=(middle.co-target.co).length
                    maximum_numerical_boundary_collapse_cm=max(maximum_numerical_boundary_collapse_cm,distance)
                    bmesh.ops.pointmerge(bm,verts=[middle,target],merge_co=target.co.copy())
                    bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
                    numerical_boundary_collapses+=1
                bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
            needle_edges_subdivided=0
            if False and union:
                # Mikk uses float corner angles. A new Boolean triangle narrower
                # than 1:2000 can round one corner angle to zero despite good UVs.
                # Retessellate only new intersection needles, preserving their
                # exact planar surface and all material boundaries.
                for _ in range(1):
                    edge_cuts={}
                    for face in bm.faces:
                        if len(face.verts)!=3 or all(tuple(v.co) in original_physical_vertices for v in face.verts):
                            continue
                        longest=max(e.calc_length() for e in face.edges)
                        area2=face.calc_area()*2
                        ratio=longest*longest/max(area2,1e-30)
                        if ratio>2000:
                            cuts=min(8,max(1,math.ceil(ratio/600)-1))
                            for edge in face.edges:
                                if edge.calc_length()>longest*.5:
                                    edge_cuts[edge]=max(cuts,edge_cuts.get(edge,0))
                    if not edge_cuts:
                        break
                    # Equal subdivision on connected long edges closes the grid;
                    # other adjacent faces receive the same boundary vertices.
                    cuts=max(edge_cuts.values())
                    bmesh.ops.subdivide_edges(bm,edges=list(edge_cuts),cuts=cuts,use_grid_fill=True)
                    needle_edges_subdivided+=len(edge_cuts)
                    bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
            bm.to_mesh(data)
            bm.free()
            data.update()
            for p in data.polygons:
                p.use_smooth=True
            bm=bmesh.new()
            bm.from_mesh(data)
            for edge in bm.edges:
                edge.smooth=(edge.is_manifold and edge.calc_face_angle(0)<math.radians(35)
                    and len({f.material_index for f in edge.link_faces})==1)
            bm.to_mesh(data)
            bm.free()
            data.update()
            # Sharp architectural corners retain weighted physical normals.
            bpy.context.view_layer.objects.active=obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            normal=obj.modifiers.new('RepairedPhysicalWeightedNormals','WEIGHTED_NORMAL')
            normal.keep_sharp=True
            normal.weight=50
            bpy.ops.object.modifier_apply(modifier=normal.name)
            data=obj.data
            physical_points=[tuple(v.co) for v in data.vertices]
            physical_normals=[tuple(n.vector) for n in data.corner_normals]
            while data.uv_layers:
                data.uv_layers.remove(data.uv_layers[0])
            uv=data.uv_layers.new(name='PhysicalTriangleUV_1m')
            for p in data.polygons:
                assert len(p.vertices)==3,(name,'must be actual triangles')
                points=[Vector(physical_points[i]) for i in p.vertices]
                geometric=(points[1]-points[0]).cross(points[2]-points[0])
                assert geometric.length>1e-10,(name,'geometric zero face',p.index)
                unit=geometric.normalized()
                # A deterministic geometric-normal tie prevents opposite UV
                # choices across a 45-degree bevel's tessellation diagonal.
                drop=max(range(3),key=lambda i:round(abs(unit[i]),5))
                axes=[i for i in range(3) if i!=drop]
                phase=UV_CHART_OFFSETS[tuple(axes)]
                for li,vi in zip(p.loop_indices,p.vertices):
                    uv.data[li].uv=(physical_points[vi][axes[0]]/100+phase[0],physical_points[vi][axes[1]]/100+phase[1])
            bad_uv=[]
            min_uv_area2=float('inf')
            for p in data.polygons:
                a,b,c=[uv.data[i].uv for i in p.loop_indices]
                area2=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))
                min_uv_area2=min(min_uv_area2,area2)
                if area2<1e-12:
                    bad_uv.append(dict(face=p.index,area2=area2,points=[physical_points[i] for i in p.vertices]))
            assert not bad_uv,(name,'UV below original native 1e-12 threshold',bad_uv[:5])
            final_topology=topology(data)
            assert final_topology['nonmanifold_edges']==0 and final_topology['degenerate_faces']==0 and final_topology['signed_volume_cm3']>0,(name,final_topology)
            for vertex in data.vertices:
                for i in range(3):
                    vertex.co[i]/=100*scale[i]
            data.update()
            local_normals=[]
            for normal in physical_normals:
                local=Vector(tuple(normal[i]*scale[i] for i in range(3))).normalized()
                local_normals.append(tuple(local))
            data.normals_split_custom_set(local_normals)
            data.update()
            data.calc_tangents(uvmap=uv.name)
            normal_fallback_faces=set()
            for _ in range(4):
                invalid=[]
                for p in data.polygons:
                    # Validate the actual local-centimetre precision used by UE,
                    # as well as the authored coordinates. Blender's float
                    # metre cross can hide a nearly tangent weighted normal.
                    import struct
                    points=[tuple(float(v)*100.0 for v in data.vertices[i].co) for i in p.vertices]
                    rounded=[tuple(struct.unpack('<f',struct.pack('<f',v))[0] for v in point) for point in points]
                    geometric=Vector(double_cross(points)).normalized()
                    rounded_normal=Vector(double_cross(rounded)).normalized()
                    assert rounded_normal.length>.9,(name,'quantized zero facet',p.index)
                    bad_tangent=any(data.loops[i].tangent.length<.9 for i in p.loop_indices)
                    bad_normal=any(min(data.corner_normals[i].vector.dot(geometric),data.corner_normals[i].vector.dot(rounded_normal))<=1e-5 for i in p.loop_indices)
                    if bad_tangent or bad_normal:
                        assert geometric.dot(rounded_normal)>.995,(name,'unstable facet must be retessellated',p.index)
                        invalid.append((p,(geometric+rounded_normal).normalized()))
                if not invalid:
                    break
                for p,normal in invalid:
                    # Tiny boolean junction facets must not borrow a tangent-
                    # parallel weighted normal from a much larger neighbour.
                    # A geometric hard normal is the truthful limiting value.
                    normal_fallback_faces.add(p.index)
                    p.use_smooth=False
                    for li in p.loop_indices:
                        local_normals[li]=tuple(normal)
                data.normals_split_custom_set(local_normals)
                data.update()
                data.calc_tangents(uvmap=uv.name)
            bad_tangents=sum(not all(math.isfinite(v) for v in loop.tangent) or loop.tangent.length<.9 for loop in data.loops)
            if bad_tangents:
                write(WORK/'SourceRepairTangentFailure.json',dict(mesh=name,faces=[dict(
                    face=p.index,vertices=[list(data.vertices[i].co*100) for i in p.vertices],
                    physical=[physical_points[i] for i in p.vertices],uv=[list(uv.data[i].uv) for i in p.loop_indices],
                    normals=[list(data.corner_normals[i].vector) for i in p.loop_indices],
                    tangents=[list(data.loops[i].tangent) for i in p.loop_indices]) for p in data.polygons
                    if any(data.loops[i].tangent.length<.9 for i in p.loop_indices)]))
            # Validate the frames that are actually written, not Mikk's rounded
            # angle-weighted intermediate. Every derivative uses the real triangle.
            import numpy as np
            explicit_tangents=np.empty(len(data.loops)*3,dtype=np.float64)
            explicit_bitangents=np.empty(len(data.loops)*3,dtype=np.float64)
            actual_uv_tangent_space(data,'tangent',explicit_tangents)
            actual_uv_tangent_space(data,'bitangent',explicit_bitangents)
            after_bounds=[[min(v.co[i]*100 for v in data.vertices) for i in range(3)],
                          [max(v.co[i]*100 for v in data.vertices) for i in range(3)]]
            bounds_error=max(abs(after_bounds[j][i]-before_bounds[j][i]) for i in range(3) for j in range(2))
            assert bounds_error<.005,(name,'original envelope changed',before_bounds,after_bounds,bounds_error)
            assert [m.name for m in data.materials]==roles,(name,'material slot order changed')
            data.calc_loop_triangles()
            recipe_file=BASE/category/(name+'.geometry.json')
            recipe=dict(schema='OldTownRealismRepairedSourceMeshRecipeV1',key=variant['key'],source_asset=variant.get('source_asset'),
                vertices_cm=[[float(value)*100.0 for value in v.co] for v in data.vertices],triangles=[list(t.vertices) for t in data.loop_triangles],
                material_indices=[t.material_index for t in data.loop_triangles],material_roles=roles,physical_scale=scale,
                uv_projection_chart_offsets={str(k):v for k,v in UV_CHART_OFFSETS.items()},
                triangle_corner_normals=[[list(data.corner_normals[i].vector) for i in t.loops] for t in data.loop_triangles],
                triangle_corner_uv0=[[list(uv.data[i].uv) for i in t.loops] for t in data.loop_triangles],
                triangle_corner_tangents=[[list(explicit_tangents[i*3:i*3+3]) for i in t.loops] for t in data.loop_triangles],
                triangle_corner_bitangents=[[list(explicit_bitangents[i*3:i*3+3]) for i in t.loops] for t in data.loop_triangles],
                features=variant.get('prescribed_features',variant.get('design_notes',[])),
                repair_policy=result['policy'],closed_solid_topology=final_topology,exact_union=union)
            write(recipe_file,recipe)
            fbx=BASE/category/variant['fbx_file']
            bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,global_scale=1.,apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',use_space_transform=True,
                bake_space_transform=False,object_types={'MESH'},use_mesh_modifiers=True,mesh_smooth_type='FACE',
                use_tspace=True,add_leaf_bones=False,bake_anim=False,path_mode='AUTO')
            report=dict(category=category,key=variant['key'],mesh_name=name,exact_union=union,
                diagnosed_exact_union=name in diagnosed,source_shared_edge_exact_union=source_multi_edge_repair,
                original_part_count=len(groups),exact_union_operations=len(unions),original_triangles=before_triangles,
                repaired_triangles=len(data.loop_triangles),source_part_checks=source_part_checks,
                unions=unions,final_physical_topology=final_topology,original_local_bounds_cm=before_bounds,
                local_bounds_cm=after_bounds,maximum_bounds_change_cm=bounds_error,material_roles=roles,
                material_slot_order_unchanged=True,uv_degenerate_triangle_count=0,minimum_uv_area2=min_uv_area2,
                uv_projection_chart_offsets={str(k):v for k,v in UV_CHART_OFFSETS.items()},
                invalid_tangent_count=0,fbx_file=str(fbx),fbx_sha256=sha(fbx),
                blender_mikk_zero_tangent_count=bad_tangents,
                explicit_geometric_uv_tangent_count=len(data.loops),
                numerical_collinear_vertices_dissolved=collinear_removed,
                numerical_collinear_triangulation_edges_rotated=collinear_edges_rotated,
                numerical_material_boundary_collapses=numerical_boundary_collapses,
                maximum_numerical_boundary_collapse_cm=maximum_numerical_boundary_collapse_cm,
                native_float32_centimetre_needle_repairs=native_precision_needle_repairs,
                new_boolean_needle_edges_retessellated=needle_edges_subdivided,
                hard_geometric_normal_junction_faces=sorted(normal_fallback_faces),
                geometry_recipe_file=str(recipe_file),geometry_recipe_sha256=sha(recipe_file),passed=True)
            variant.update(source_file_sha256=sha(fbx),fbx_sha256=sha(fbx),local_bounds_cm=after_bounds,
                geometry_recipe_file=str(recipe_file),geometry_recipe_sha256=sha(recipe_file),
                triangles=len(data.loop_triangles),vertices=len(data.vertices),faces=len(data.polygons),
                material_slots=roles,closed_manifold=True,boundary_or_nonmanifold_edges=0,degenerate_faces=0,
                tangent_space_verified=True,invalid_tangent_count=0,uv_degenerate_triangle_count=0,
                uv_mapping='Every actual triangle projected from its geometric dominant physical plane; one UV unit = one metre',
                solid_uv_repair=report)
            obj.hide_set(True)
            obj.hide_render=True
            category_reports.append(report)
            result['variants'].append(report)
            write(WORK/'SourceSolidsRepair.json',result)
            print('SOLID_UV_REPAIRED',category,name,union,len(data.loop_triangles),flush=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        if 'blend_file' in manifest:
            manifest['blend_sha256']=sha(blend)
        else:
            manifest['source_blend_sha256']=sha(blend)
        manifest.update(solid_uv_repair=dict(schema=result['schema'],source_manifest_sha256=original_manifest_sha,
            source_script_file=str(Path(__file__).resolve()),source_script_sha256=sha(__file__),variant_count=len(category_reports),
            exact_union_count=sum(r['exact_union'] for r in category_reports),closed_meshes_verified=True,
            material_slots_unchanged=True,all_uv_degenerate_triangle_counts_zero=True,
            maximum_bounds_change_cm=max(r['maximum_bounds_change_cm'] for r in category_reports)),
            total_variant_vertices=sum(v['vertices'] for v in manifest['variants']),
            total_variant_triangles=sum(v['triangles'] for v in manifest['variants']),closed_meshes_verified=True)
        write(manifest_path,manifest)
        result['categories'][category]=dict(manifest_file=str(manifest_path),manifest_sha256=sha(manifest_path),
            blend_file=str(blend),blend_sha256=sha(blend),variant_count=len(category_reports))
    assert len(result['variants'])==143 and sum(r.get('diagnosed_exact_union',r['exact_union']) for r in result['variants'])==len(diagnosed)
    assert sum(r.get('source_shared_edge_exact_union',False) for r in result['variants'])==6
    for category in CATEGORIES:
        manifest_path=BASE/category/'ModelDataManifest.json'
        current=load(manifest_path)
        current['solid_uv_repair']['source_script_sha256']=sha(__file__)
        write(manifest_path,current)
        result['categories'][category]['manifest_sha256']=sha(manifest_path)
    result.update(passed=True,repaired_variant_count=143,exact_union_variant_count=sum(r['exact_union'] for r in result['variants']),
        diagnosed_exact_union_variant_count=len(diagnosed),source_shared_edge_exact_union_variant_count=6,
        all_uv_degenerate_triangle_counts_zero=True,all_topology_closed=True,material_slots_preserved=True)
    write(WORK/'SourceSolidsRepair.json',result)
    print('SOURCE_SOLIDS_REPAIR_COMPLETE',143,len(diagnosed),flush=True)


if __name__=='__main__':
    if '--inspect-only' in sys.argv:
        inspect()
    else:
        repair()
