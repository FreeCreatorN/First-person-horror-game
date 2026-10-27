"""Create a separate, source-only soft-furnishing refinement library.

No Unreal process or package is opened. Run --inventory with ordinary Python;
run --build in isolated Blender --background --factory-startup. Published
sources, packages, component transforms, material overrides and collisions
are inputs only. Cloth is refined inside its existing envelope; structural
wood/metal triangles and their vertices are retained.
"""
from collections import defaultdict, Counter
import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'SourceArt/OldTownRealism_20261012/Furniture'
EVIDENCE = ROOT / 'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
OLD_EVIDENCE = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
OUT = ROOT / 'SourceArt/OldTownRealismRefinement_20261013/SoftGoods'
KINDS = {'BedMattress', 'BedPillow', 'SeatBase', 'SeatBack'}
SOFT = {'Linen', 'LinenSeam'}
PHASES = {(0, 1): (0., 0.), (0, 2): (.031, .013), (1, 2): (.073, .027)}

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def write(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def bounds(points):
    return [[min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)]]

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def legacy_recipe(p, key, roles):
    """Recover the exact exported native surface, including its floor pivot.

    Native triangles are clockwise; authoring reverses their winding to obtain
    outward Blender faces. No old FBX, uasset or Yastar file is modified.
    """
    native = load(p)
    points, faces, ids, lookup = [], [], [], {}
    for section in native['sections']:
        local = []
        for point in section['vertices_cm']:
            token = tuple(point)
            if token not in lookup:
                lookup[token] = len(points)
                points.append(list(point))
            local.append(lookup[token])
        indices = section['triangle_indices']
        if indices and isinstance(indices[0], list):
            tris = indices
        else:
            tris = [indices[i:i+3] for i in range(0, len(indices), 3)]
        for tri in tris:
            faces.append([local[tri[0]], local[tri[2]], local[tri[1]]])
            ids.append(section['material_slot_index'])
    return dict(schema='OldTownRealismLegacyNativeSourceRecipeV1', key=key,
                vertices_cm=points, triangles=faces, material_indices=ids,
                material_roles=roles, physical_scale=[1., 1., 1.],
                native_slot_layout=native['static_material_slots'])

def repair_legacy_piping(source):
    """Replace the old native mattress's 32 open piping edges in NEW source.

    The casing is already closed. Preserve every casing triangle and rebuild
    the two welting cords from the measured piping bounds as closed tubes.
    Original Yastar/Native input files and source BodySetup remain untouched.
    """
    edges=Counter()
    for t in source['triangles']:
        for a,b in zip(t,t[1:]+t[:1]):edges[tuple(sorted((a,b)))]+=1
    bad=sum(n!=2 for n in edges.values());odd=sum(n%2 for n in edges.values())
    if not bad:return source,None
    assert odd==32 and all(mi==1 for t,mi in zip(source['triangles'],source['material_indices'])
        if any(edges[tuple(sorted((a,b)))]!=2 for a,b in zip(t,t[1:]+t[:1])))
    piping_ids={i for t,mi in zip(source['triangles'],source['material_indices']) if mi==1 for i in t}
    pipe=[source['vertices_cm'][i] for i in piping_ids];box=bounds(pipe)
    center=[(box[0][i]+box[1][i])/2 for i in range(3)]
    lower=[p[2] for p in pipe if p[2]<center[2]];upper=[p[2] for p in pipe if p[2]>center[2]]
    heights=[(min(z)+max(z))/2 for z in (lower,upper)]
    radius=min((max(z)-min(z))/2 for z in (lower,upper))*.90
    hx=(box[1][0]-box[0][0])/2-radius;hy=(box[1][1]-box[0][1])/2-radius;corner=2.6
    casing=[(t,mi) for t,mi in zip(source['triangles'],source['material_indices']) if mi==0]
    used=sorted({i for t,mi in casing for i in t});mapping={old:new for new,old in enumerate(used)}
    points=[source['vertices_cm'][i] for i in used];triangles=[[mapping[i] for i in t] for t,mi in casing];materials=[0]*len(triangles)
    path=[]
    for cx,cy,start in ((hx-corner,hy-corner,0),(-hx+corner,hy-corner,90),(-hx+corner,-hy+corner,180),(hx-corner,-hy+corner,270)):
        for j in range(9):
            angle=math.radians(start+j*90/8);path.append((center[0]+cx+corner*math.cos(angle),center[1]+cy+corner*math.sin(angle)))
    n=len(path);sides=8
    for height in heights:
        first=len(points)
        for i,p in enumerate(path):
            previous,following=path[(i-1)%n],path[(i+1)%n];tangent=(following[0]-previous[0],following[1]-previous[1]);length=math.hypot(*tangent);normal=(tangent[1]/length,-tangent[0]/length)
            for j in range(sides):
                a=2*math.pi*j/sides;points.append([p[0]+radius*normal[0]*math.cos(a),p[1]+radius*normal[1]*math.cos(a),height+radius*math.sin(a)])
        for i in range(n):
            for j in range(sides):
                a=first+i*sides+j;b=first+i*sides+(j+1)%sides;c=first+((i+1)%n)*sides+(j+1)%sides;d=first+((i+1)%n)*sides+j
                triangles.extend([[a,b,c],[a,c,d]]);materials.extend([1,1])
    result={**source,'vertices_cm':points,'triangles':triangles,'material_indices':materials}
    proof=dict(method='Rebuilt two closed rounded-rectangle welting cords from actual old slot1 bounds; old slot0 casing triangles/coordinates/material partition retained exactly',
        baseline_odd_boundary_edges=odd,baseline_non2_index_edges=bad,baseline_piping_bounds_cm=box,
        new_welting_ring_heights_cm=heights,new_welting_radius_cm=radius,preserved_casing_triangle_count=len(casing),
        original_native_input_file_unchanged=True)
    return result,proof

def repair_legacy_pillow(source):
    """Reconstruct the all-cloth old pillow's 16 missing boundary edges.

    Reuse only the closed casing of the measured hotel pillow template, affine
    mapped into the legacy native envelope and original floor pivot. The new
    legacy material array still has exactly its original one cloth slot.
    """
    edges=Counter()
    for t in source['triangles']:
        for a,b in zip(t,t[1:]+t[:1]):edges[tuple(sorted((a,b)))]+=1
    odd=sum(n%2 for n in edges.values());bad=sum(n!=2 for n in edges.values())
    assert odd==16,(odd,bad)
    template_file=OLD/'SM_OTS_Real_BedPillow_28x84x12.geometry.json';template=load(template_file)
    shell=[t for t,mi in zip(template['triangles'],template['material_indices']) if mi==0]
    used=sorted({i for t in shell for i in t});mapping={old:new for new,old in enumerate(used)}
    old_box=bounds(source['vertices_cm']);template_box=bounds([template['vertices_cm'][i] for i in used])
    points=[[old_box[0][a]+(template['vertices_cm'][i][a]-template_box[0][a])/(template_box[1][a]-template_box[0][a])*(old_box[1][a]-old_box[0][a]) for a in range(3)] for i in used]
    result={**source,'vertices_cm':points,'triangles':[[mapping[i] for i in t] for t in shell],
        'material_indices':[0]*len(shell)}
    proof=dict(method='Rebuilt complete closed stuffed casing from immutable closed hotel cloth template, affine-mapped to exact old native bounds/floor pivot; original one-slot cloth layout retained',
        baseline_odd_boundary_edges=odd,baseline_non2_index_edges=bad,template_file=str(template_file),template_sha256=sha(template_file),
        baseline_native_bounds_cm=old_box,original_native_input_file_unchanged=True)
    return result,proof

def inventory():
    old = load(OLD / 'ModelDataManifest.json')
    build = load(EVIDENCE / 'BuildReport.json')
    snapshot = load(EVIDENCE / 'AfterSnapshot.json')
    native_snapshot_file=EVIDENCE/'AppearanceSnapshot.json'
    native_snapshot=load(native_snapshot_file)
    assert native_snapshot['map_sha256']==build['map_sha256']
    wpo_file=OLD_EVIDENCE/'RealismApply.json'
    offsets={c['id']:c['expected_offset_cm'] for c in load(wpo_file)['components']}
    variants = []
    for v in old['variants']:
        if v['kind'] not in KINDS:
            continue
        recipe = Path(v['geometry_recipe_file'])
        data = load(recipe)
        source = ('/Game/CodexGenerated/OldTown/Realism_20261012/Meshes/Furniture/'
                  + v['mesh_name'] + '.' + v['mesh_name'])
        variants.append(dict(key=v['key'], kind=v['kind'], category='HotelSoftGoods',
            old_mesh_name=v['mesh_name'], source_asset=source,
            source_recipe_file=str(recipe), source_recipe_sha256=sha(recipe),
            source_fbx_file=str(OLD / v['fbx_file']), source_fbx_sha256=sha(OLD / v['fbx_file']),
            mesh_name='SM_RF_Soft_' + v['key'], orientation=v.get('orientation'),
            world_dimensions_cm=v['world_dimensions_cm'], physical_scale=data['physical_scale'],
            native_physical_scale=data['physical_scale'], material_roles=data['material_roles'],
            original_local_bounds_cm=bounds(data['vertices_cm']),
            grounded_extension_cm=v.get('grounded_extension_cm', 0.),
            legacy_design=False))
    for key, filename, role in (
        ('LegacyBedMattress', 'SM_OTS_Blender_BedMattress_003acd56d2.json', ['Linen', 'LinenSeam']),
        ('LegacyBedPillow', 'SM_OTS_Blender_BedPillow_19772eb597.json', ['Linen'])):
        p = OLD_EVIDENCE / 'AppearanceNative/NativeMeshes' / filename
        d = legacy_recipe(p, key, role)
        box = bounds(d['vertices_cm'])
        source = load(p)['asset']
        variants.append(dict(key=key, kind='BedMattress' if key.endswith('Mattress') else 'BedPillow',
            category='LegacyStreetSoftGoods', source_asset=source,
            old_mesh_name=source.rsplit('/', 1)[-1].split('.')[0],
            source_recipe_file=str(p), source_recipe_sha256=sha(p),
            source_recipe_is_native_sections=True, mesh_name='SM_RF_Soft_' + key,
            orientation=None, world_dimensions_cm=[box[1][i]-box[0][i] for i in range(3)],
            physical_scale=[1., 1., 1.], native_physical_scale=[1., 1., 1.],
            material_roles=role, original_local_bounds_cm=box, grounded_extension_cm=0.,
            legacy_design=True, legacy_pivot_note='Original native floor pivot retained; no recentering',
            original_native_material_slots=d['native_slot_layout']))
    all_components = []
    for v in variants:
        v['components'] = []
        for actor, state in snapshot['actors'].items():
            for component in state['components']:
                if component.get('mesh') != v['source_asset']:
                    continue
                native=next(c for c in native_snapshot['component_records'][actor] if c['name']==component['name'])
                assert native['uniform_slot_surface_translation']
                effective=native['expected_surface_translation_cm_to_preserve']
                assert max(abs(effective[i]-offsets[actor+'::'+component['name']][i]) for i in range(3))<1e-8
                row = dict(id=actor+'::'+component['name'], actor=actor,
                    component=component['name'], variant_key=v['key'], source_asset=v['source_asset'],
                    source_actor_state={k:x for k,x in state.items() if k != 'components'},
                    source_component_state=component,
                    source_materials=component.get('materials', []),
                    source_effective_offset_cm=effective,source_native_component_record=native,
                    source_native_world_pose=native['world_pose'])
                v['components'].append(row)
                all_components.append(row)
        v['source_actor_labels'] = [c['actor'] for c in v['components']]
        v['instance_count'] = len(v['components'])
        v['fbx_file'] = v['mesh_name'] + '.fbx'
        v['geometry_recipe_file'] = str(OUT / (v['mesh_name']+'.geometry.json'))
        v['native_source_model_read'] = True
        v['native_no_degenerate_merge'] = True
        v['native_import_cache_suffix'] = 'RefinementNoMerge'
        package = ROOT / 'Content' / (v['source_asset'].split('.')[0].removeprefix('/Game/')+'.uasset')
        v['source_asset_file'] = str(package)
        v['source_asset_sha256'] = sha(package)
    assert len(variants) == 20 and len(all_components) == 222
    assert len({c['id'] for c in all_components}) == 222
    assert sum(v['instance_count'] for v in variants if not v['legacy_design']) == 208
    result = dict(schema='OldTownRealismSoftGoodsRefinementManifestV1', status='AUTHORING',
        passed=False, variant_count=20, actor_count=222, component_count=222,
        hotel_variant_count=18, hotel_component_count=208, legacy_variant_count=2,
        legacy_component_count=14, source_map_sha256=build['map_sha256'],
        source_build_report_file=str(EVIDENCE/'BuildReport.json'),
        source_build_report_sha256=sha(EVIDENCE/'BuildReport.json'),
        source_snapshot_file=str(EVIDENCE/'AfterSnapshot.json'),
        source_snapshot_sha256=sha(EVIDENCE/'AfterSnapshot.json'),
        source_native_snapshot_file=str(native_snapshot_file),source_native_snapshot_sha256=sha(native_snapshot_file),
        source_wpo_file=str(wpo_file),source_wpo_sha256=sha(wpo_file),
        stage2_material_audit_file=str(EVIDENCE/'MaterialNativeAudit.json'),
        stage2_material_audit_sha256=sha(EVIDENCE/'MaterialNativeAudit.json'),
        source_manifest_file=str(OLD/'ModelDataManifest.json'),
        source_manifest_sha256=sha(OLD/'ModelDataManifest.json'),
        source_script_file=str(Path(__file__).resolve()), source_script_sha256=sha(__file__),
        coordinates='Author local +X/+Y/+Z retain existing mesh local axes. Export FBX -Y forward / Z up. Import with independently verified AxisProbe and SOURCE_MODEL.',
        units='Blender metres; recipe vertices in native local centimetres; physical_scale converts native cm into physical cm.',
        policy='Only Linen/LinenSeam surfaces change. Existing structural triangles and feet, source BodySetup, Actor/component pose, parent, visibility and material override arrays are frozen. No Unreal writes.',
        uv_mapping='Every real triangle uses its dominant physical coordinate plane at 1 UV per metre, with deterministic chart phases; no 0..1 packing.',
        source_asset_sha256={v['source_asset_file']:v['source_asset_sha256'] for v in variants},
        variants=variants, components=all_components)
    write(OUT/'ModelDataManifest.json', result)
    return result

def smoothstep(a, b, x):
    t = max(0., min(1., (x-a)/(b-a)))
    return t*t*(3.-2.*t)

def ribbon(x, y, start, end, width, amplitude, bend):
    """A finite tension fold: one ridge and two shallow troughs, not noise."""
    vx, vy = end[0]-start[0], end[1]-start[1]
    den = vx*vx+vy*vy
    t = max(0., min(1., ((x-start[0])*vx+(y-start[1])*vy)/den))
    bx = start[0]+t*vx - vy/math.sqrt(den)*bend*math.sin(math.pi*t)
    by = start[1]+t*vy + vx/math.sqrt(den)*bend*math.sin(math.pi*t)
    distance = math.hypot(x-bx, y-by)
    taper = math.sin(math.pi*t)**.65
    return amplitude*taper*(math.exp(-.5*(distance/width)**2)
        - .42*math.exp(-.5*(distance/(width*2.8))**2))

def make_fold_field(box, kind, orient, component_index):
    # All field parameters below are centimetres in the actual furniture.
    axis = (0 if orient and orient[0]=='X' else 1) if kind=='SeatBack' else 2
    axes = [i for i in range(3) if i != axis]
    center = [(box[0][i]+box[1][i])/2 for i in range(3)]
    extent = [max(.001, box[1][i]-box[0][i]) for i in range(3)]
    a, b = axes
    half_a, half_b = extent[a]/2, extent[b]/2
    sign = -(1 if orient[1]=='P' else -1) if kind=='SeatBack' else 1
    seed = .18 + component_index*.271
    folds = []
    # Corner tension gathers stay local and have irregular, finite lengths.
    for corner, (sa,sb) in enumerate(((-1,-1),(1,-1),(-1,1),(1,1))):
        for branch in range(3 if kind in ('BedMattress','BedPillow') else 2):
            start = (sa*(half_a-1.2-branch*.4), sb*(half_b-1.3))
            end = (sa*half_a*(.53-.09*branch), sb*half_b*(.38+.12*branch))
            width = (2.0 if kind=='BedMattress' else 1.5) + branch*.25
            amplitude = (1.16 if kind=='BedMattress' else .92 if kind=='BedPillow' else .76)
            amplitude *= 1-.12*branch + .07*math.sin(seed+corner*1.8)
            folds.append((start,end,width,amplitude,(corner%2*2-1)*(.65+branch*.22)))
    if kind=='BedMattress':
        folds += [((-half_a*.75,half_b*.95),(-half_a*.38,half_b*.18),2.25,.42,2.2),
                  ((half_a*.88,-half_b*.65),(half_a*.34,-half_b*.15),2.5,.48,-2.5)]
    elif kind=='BedPillow':
        folds += [((-half_a*.84,half_b*.48),(-half_a*.20,half_b*.18),1.25,.42,.7)]
    else:
        for s in (-1,1):
            folds.append(((s*half_a*.90,-half_b*.92),(s*half_a*.28,-half_b*.38),1.4,.45,s*.6))
    arm = kind=='SeatBase' and min(extent[0],extent[1]) < 15
    def field(point):
        x, y = point[a]-center[a], point[b]-center[b]
        normalized = sign*(point[axis]-center[axis])/extent[axis]
        top = smoothstep(-.08, .30, normalized)
        edge = min(1., max(0., (1-(x/half_a)**2)*(1-(y/half_b)**2)))
        wave = sum(ribbon(x,y,*f) for f in folds)
        if kind=='BedMattress':
            sag = -1.28*math.exp(-((x/half_a+.18)/.51)**2-((y/half_b-.12)/.62)**2)
            wave += sag - .13*edge
        elif kind=='BedPillow':
            wave -= 1.55*math.exp(-((x/half_a-.25)/.42)**2-((y/half_b+.06)/.55)**2)
        elif kind=='SeatBase':
            wave -= (1.8 if not arm else .18)*math.exp(-((x/half_a-.08)/.55)**2-((y/half_b+.1)/.54)**2)
        elif kind=='SeatBack':
            wave -= 1.2*math.exp(-((x/half_a+.09)/.58)**2-((y/half_b+.19)/.58)**2)
        if arm:
            wave *= .32
        delta = [0.,0.,0.]
        delta[axis] = sign*wave*top
        # Slight asymmetric fabric contraction breaks the perfectly straight
        # pillow/cushion silhouette without moving any supporting skeleton.
        if kind=='BedPillow':
            corner = (abs(x)/half_a)**7*(abs(y)/half_b)**7
            delta[a] = -math.copysign(.65*corner*(1+.10*math.sin(seed+y*.1)),x)
            delta[b] = -math.copysign(.48*corner,x if y==0 else y)
        return delta
    return field

def refine_soft_triangles(points, triangles, materials, roles, limit, budget, kind, orient):
    """Conforming edge bisection with explicit non-collinear triangle cases.

    Only an edge with two soft incident faces may split. The 1/2/3-edge
    templates preserve both winding and every structural triangle exactly.
    """
    points=[tuple(f32(x) for x in p) for p in points]
    triangles=[tuple(t) for t in triangles]
    axis=(0 if orient and orient[0]=='X' else 1) if kind=='SeatBack' else 2
    sign=-(1 if orient[1]=='P' else -1) if kind=='SeatBack' else 1
    linen_ids={i for t,mi in zip(triangles,materials) if roles[mi]=='Linen' for i in t}
    cloth_box=bounds([points[i] for i in linen_ids]);center=(cloth_box[0][axis]+cloth_box[1][axis])/2
    for iteration in range(6):
        edges=defaultdict(list)
        for ti,t in enumerate(triangles):
            for a,b in zip(t,t[1:]+t[:1]):edges[tuple(sorted((a,b)))].append(ti)
        def area(t):
            a,b,c=[points[i] for i in t];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            return math.sqrt(sum(x*x for x in (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])))/2
        areas=[area(t) for t in triangles]
        # The underside and the already dense piping are retained, rather than
        # spending the scene's triangle budget on unseen surfaces.
        chosen={e for e,ts in edges.items() if len(ts)==2 and math.dist(points[e[0]],points[e[1]])>limit
            and all(roles[materials[t]]=='Linen' and areas[t]>.018
                and sign*(sum(points[i][axis] for i in triangles[t])/3-center)>0 for t in ts)}
        remaining=max(0,(budget-len(triangles))//2)
        chosen=set(sorted(chosen,key=lambda e:(-math.dist(points[e[0]],points[e[1]]),e))[:remaining])
        if not chosen:break
        mid={}
        for a,b in sorted(chosen):
            mid[(a,b)]=len(points);points.append(tuple(f32((points[a][i]+points[b][i])/2) for i in range(3)))
        faces=[];ids=[]
        for t,mi in zip(triangles,materials):
            a,b,c=t;m=mid.get(tuple(sorted((a,b))));n=mid.get(tuple(sorted((b,c))));k=mid.get(tuple(sorted((c,a))))
            mask=(m is not None)+2*(n is not None)+4*(k is not None)
            splits={0:[t],1:[(a,m,c),(m,b,c)],2:[(b,n,a),(n,c,a)],4:[(c,k,b),(k,a,b)],
                3:[(b,n,m),(a,m,c),(m,n,c)],5:[(a,m,k),(b,c,m),(m,c,k)],
                6:[(c,k,n),(a,b,k),(k,b,n)],7:[(a,m,k),(m,b,n),(k,n,c),(m,n,k)]}[mask]
            faces.extend(splits);ids.extend([mi]*len(splits))
        triangles,materials=faces,ids
    return points,triangles,materials

def float32_local_cm_proof(points,triangles,normals,baseline,materials,roles):
    """Simulate the actual serialized native-cm position precision, not UE load."""
    q=[tuple(f32(x) for x in p) for p in points];edges=Counter();face_edges=defaultdict(list)
    inward=0;degenerate=0;min_area=float('inf')
    for ti,t in enumerate(triangles):
        a,b,c=[q[i] for i in t];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);area=math.sqrt(sum(x*x for x in cross));min_area=min(min_area,area)
        degenerate+=area<=1e-12
        inward+=sum(sum(cross[i]*n[i] for i in range(3))<=0 for n in normals[ti])
        for a,b in zip(t,t[1:]+t[:1]):
            e=tuple(sorted((q[a],q[b])));edges[e]+=1;face_edges[e].append(ti)
    adjacency=defaultdict(set)
    for ids in face_edges.values():
        for i in ids:adjacency[i].update(set(ids)-{i})
    unseen=set(range(len(triangles)));shells=[]
    while unseen:
        first=min(unseen);unseen.remove(first);stack=[first];ids=[]
        while stack:
            i=stack.pop();ids.append(i)
            for j in adjacency[i]&unseen:unseen.remove(j);stack.append(j)
        origin=q[triangles[first][0]];terms=[]
        for ti in ids:
            a,b,c=[tuple(q[i][k]-origin[k] for k in range(3)) for i in triangles[ti]]
            terms.append((a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6)
        shells.append(dict(triangles=len(ids),signed_volume_cm3=math.fsum(terms)))
    # Original indexed source topology remains strictly two-manifold. Some
    # frozen closed wood rails meet on the same native-float32 coordinate edge;
    # preserve and fully compare those inherited even ties instead of moving
    # the user's wood frame to manufacture a different coordinate weld.
    oldq=[tuple(f32(x) for x in p) for p in baseline['vertices_cm']];oldedges=defaultdict(list)
    for ti,t in enumerate(baseline['triangles']):
        for a,b in zip(t,t[1:]+t[:1]):oldedges[tuple(sorted((oldq[a],oldq[b])))].append(ti)
    def faces_signature(q,ts,triangles,materials):
        answer=[]
        for ti in ts:
            corners=tuple(q[i] for i in triangles[ti]);cyclic=min(corners[j:]+corners[:j] for j in range(3))
            answer.append((roles[materials[ti]],cyclic))
        return sorted(answer)
    inherited=[];unexpected=[]
    for edge,count in edges.items():
        if count==2:continue
        ts=face_edges[edge];oldts=oldedges.get(edge,[])
        new_faces=faces_signature(q,ts,triangles,materials)
        old_faces=faces_signature(oldq,oldts,baseline['triangles'],baseline['material_indices'])
        if count%2==0 and count==len(oldts) and new_faces==old_faces and all(role not in SOFT for role,_ in new_faces):
            inherited.append(dict(edge_vertices_cm=edge,face_count=count,roles=[role for role,_ in new_faces],
                old_oriented_faces=old_faces,new_oriented_faces=new_faces,exact_old_frozen_structural_faces=True))
        else:unexpected.append(dict(edge_vertices_cm=edge,face_count=count,old_face_count=len(oldts),new_faces=new_faces))
    result=dict(passed=not unexpected and not any(v%2 for v in edges.values()) and not degenerate and not inward and all(s['signed_volume_cm3']>0 for s in shells),
        nonmanifold_edges=sum(v!=2 for v in edges.values()),odd_boundary_edges=sum(v%2 for v in edges.values()),
        unexpected_nonmanifold_edges=len(unexpected),unexpected_edges=unexpected,inherited_even_shared_edges=inherited,
        degenerate_triangles=degenerate,inward_corner_normals=inward,minimum_double_area_cm2=min_area,shells=shells,
        description='Float32 native local-cm serialization simulation of real vertices/triangles/corner normals; actual saved Unreal readback remains separately required')
    assert result['passed'],result
    return result

def closest_point_triangle(p,a,b,c):
    """Actual nearest point on a nondegenerate triangle (Ericson regions)."""
    sub=lambda x,y:tuple(x[i]-y[i] for i in range(3));dot=lambda x,y:sum(x[i]*y[i] for i in range(3))
    add=lambda base,x,f:tuple(base[i]+x[i]*f for i in range(3))
    ab,ac,ap=sub(b,a),sub(c,a),sub(p,a);d1,d2=dot(ab,ap),dot(ac,ap)
    if d1<=0 and d2<=0:return a
    bp=sub(p,b);d3,d4=dot(ab,bp),dot(ac,bp)
    if d3>=0 and d4<=d3:return b
    vc=d1*d4-d3*d2
    if vc<=0 and d1>=0 and d3<=0:return add(a,ab,d1/(d1-d3))
    cp=sub(p,c);d5,d6=dot(ab,cp),dot(ac,cp)
    if d6>=0 and d5<=d6:return c
    vb=d5*d2-d1*d6
    if vb<=0 and d2>=0 and d6<=0:return add(a,ac,d2/(d2-d6))
    va=d3*d6-d5*d4
    if va<=0 and d4-d3>=0 and d5-d6>=0:return add(b,sub(c,b),(d4-d3)/((d4-d3)+(d5-d6)))
    den=1/(va+vb+vc);v,w=vb*den,vc*den
    return tuple(a[i]+ab[i]*v+ac[i]*w for i in range(3))

def measure_contacts(manifest):
    """Certify all 55 assembled pillow contacts against real mattress triangles.

    A nearest vertex/triangle witness must attain the true global vertical
    separation lower bound. Thus the reported surface minimum is certified by
    actual surfaces, rather than inferred from touching bounding boxes.
    """
    by_actor={c['actor']:(v,c) for v in manifest['variants'] for c in v['components']}
    thresholds=dict(contact_distance_cm=.02,penetration_tolerance_cm=.002,
        minimum_contact_vertices=10,minimum_contact_area_fraction=.20)
    pairs=[];recipes={v['key']:load(v['geometry_recipe_file']) for v in manifest['variants'] if v.get('passed')}
    for pv in manifest['variants']:
        if pv['kind']!='BedPillow' or not pv.get('passed'):continue
        for pc in pv['components']:
            mate=pc['actor'].replace('BedPillow','BedMattress') if pv['legacy_design'] else pc['actor'][:-6]+'Mattress'
            mv,mc=by_actor[mate]
            if not mv.get('passed'):continue
            pr,mr=recipes[pv['key']],recipes[mv['key']]
            def world_points(recipe,component):
                pose=component['source_native_world_pose'];assert pose['rotation_quaternion_xyzw']==[0.,0.,0.,1.],pose
                off=component['source_effective_offset_cm']
                # Subtract the mattress world origin to retain full precision.
                return [tuple(p[i]*pose['scale'][i]+pose['translation'][i]-mc['source_native_world_pose']['translation'][i]+off[i] for i in range(3)) for p in recipe['vertices_cm']]
            pp,mp=world_points(pr,pc),world_points(mr,mc);cell=6.;grid=defaultdict(list)
            for ti,t in enumerate(mr['triangles']):
                a,b,c=[mp[i] for i in t];crossz=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                if crossz<=1e-10:continue
                for x in range(math.floor(min(a[0],b[0],c[0])/cell),math.floor(max(a[0],b[0],c[0])/cell)+1):
                    for y in range(math.floor(min(a[1],b[1],c[1])/cell),math.floor(max(a[1],b[1],c[1])/cell)+1):grid[(x,y)].append(ti)
            bottom=[]
            for ti,t in enumerate(pr['triangles']):
                a,b,c=[pp[i] for i in t]
                if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<-1e-10:bottom.append(ti)
            ids=sorted({i for ti in bottom for i in pr['triangles'][ti]});witnesses=[];gaps={};best=float('inf');min_gap=float('inf')
            for vi in ids:
                p=pp[vi];hit=None
                for ti in grid[(math.floor(p[0]/cell),math.floor(p[1]/cell))]:
                    a,b,c=[mp[i] for i in mr['triangles'][ti]]
                    den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                    if abs(den)<1e-12:continue
                    u=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den
                    v=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;w=1-u-v
                    if min(u,v,w)<-1e-7:continue
                    height=u*a[2]+v*b[2]+w*c[2]
                    if hit is None or height>hit[0]:hit=(height,ti,[u,v,w])
                assert hit is not None,(pc['id'],'pillow underside outside mattress',vi,p)
                gap=p[2]-hit[0];gaps[vi]=gap;min_gap=min(min_gap,gap)
                a,b,c=[mp[i] for i in mr['triangles'][hit[1]]];closest=closest_point_triangle(p,a,b,c);distance=math.dist(p,closest);best=min(best,distance)
                if abs(gap)<=thresholds['contact_distance_cm'] and len(witnesses)<24:
                    origin=mc['source_native_world_pose']['translation']
                    witnesses.append(dict(pillow_vertex_index=vi,mattress_triangle_index=hit[1],pillow_vertex_relative_world_cm=p,
                        pillow_vertex_world_cm=[p[i]+origin[i] for i in range(3)],
                        closest_triangle_point_relative_world_cm=closest,closest_point_cm=[closest[i]+origin[i] for i in range(3)],
                        barycentric=hit[2],distance_cm=distance,vertical_gap_cm=gap))
            contact_vertices=sum(abs(x)<=thresholds['contact_distance_cm'] for x in gaps.values());area=0.
            for ti in bottom:
                t=pr['triangles'][ti]
                if all(abs(gaps[i])<=thresholds['contact_distance_cm'] for i in t):
                    a,b,c=[pp[i] for i in t];area+=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
            footprint=(max(p[0] for p in pp)-min(p[0] for p in pp))*(max(p[1] for p in pp)-min(p[1] for p in pp));fraction=area/footprint
            separation=max(0.,min(p[2] for p in pp)-max(p[2] for p in mp));certified=abs(best-separation)<1e-7
            passed=best<=thresholds['contact_distance_cm'] and min_gap>=-thresholds['penetration_tolerance_cm'] and contact_vertices>=thresholds['minimum_contact_vertices'] and fraction>=thresholds['minimum_contact_area_fraction'] and certified
            pair=dict(passed=passed,pillow_id=pc['id'],mattress_id=mc['id'],minimum_vertex_triangle_distance_cm=best,
                minimum_surface_distance_cm=best,global_minimum_distance_certified=certified,global_vertical_separation_lower_bound_cm=separation,
                minimum_vertical_gap_cm=min_gap,contact_vertex_count=contact_vertices,contact_area_cm2=area,contact_area_fraction=fraction,
                tested_underside_vertices=len(ids),tested_underside_triangles=len(bottom),contact_points=witnesses)
            for name,v,c in [('pillow',pv,pc),('mattress',mv,mc)]:
                pair.update({name+'_recipe_file':v['geometry_recipe_file'],name+'_recipe_sha256':sha(v['geometry_recipe_file']),
                    name+'_fbx_file':str(OUT/v['fbx_file']),name+'_fbx_sha256':sha(OUT/v['fbx_file']),
                    name+'_source_actor_state':c['source_actor_state'],name+'_source_component_state':c['source_component_state'],
                    name+'_source_native_world_pose':c['source_native_world_pose'],name+'_source_native_component_record':c['source_native_component_record'],
                    name+'_effective_offset_cm':c['source_effective_offset_cm']})
            pairs.append(pair)
    result=dict(schema='OldTownSoftGoodsSourceContactProofV1',passed=len(pairs)==55 and all(p['passed'] for p in pairs),
        pair_count=len(pairs),source_map_sha256=manifest['source_map_sha256'],thresholds=thresholds,pairs=pairs,
        method='Actual assembled recipe triangles; all underside vertices ray-tested against actual upper triangles; true closest-point witnesses attain the global surface separation lower bound; broad contact triangle areas independently summed.',
        **{k:manifest[k] for k in ('source_snapshot_file','source_snapshot_sha256','source_native_snapshot_file','source_native_snapshot_sha256','source_wpo_file','source_wpo_sha256','stage2_material_audit_file','stage2_material_audit_sha256')})
    path=OUT/'SourceContactProof.json';write(path,result);manifest['source_contact_proof_file']=str(path);manifest['source_contact_proof_sha256']=sha(path)
    if len(pairs)==55:assert result['passed'],[(p['pillow_id'],p['minimum_vertical_gap_cm'],p['contact_area_fraction']) for p in pairs if not p['passed']]
    return result

def legacy_mattress_top_weight(point, box):
    """Keep its long, sparsely triangulated side walls completely stationary.

    A vertical displacement of an interior point on a vertical side can cross
    the long diagonal of a neighbouring unrefined face. Only the interior of
    the old horizontal top may wrinkle; X/Y never change. The final envelope
    remap is blended too, so it cannot move the pinned side walls or welting.
    """
    radial=max(abs((point[a]-(box[0][a]+box[1][a])/2)/((box[1][a]-box[0][a])/2)) for a in (0,1))
    return 1-smoothstep(.84,.92,radial)


def build(manifest, only=None, *, preserve_library=False, preserve_previews=False):
    import bpy
    import bmesh
    import numpy as np
    from mathutils import Vector
    import io_scene_fbx.export_fbx_bin as writer
    if preserve_library:
        assert only=={'LegacyBedMattress'},'The incremental repair is limited to LegacyBedMattress'
        collection=bpy.data.collections.get('RefinementSourceLibrary')
        assert collection is not None
        victim=bpy.data.objects.get('SM_RF_Soft_LegacyBedMattress')
        assert victim is not None and victim.name in collection.objects
        old_mesh=victim.data
        bpy.data.objects.remove(victim,do_unlink=True)
        if old_mesh.users==0:bpy.data.meshes.remove(old_mesh)
    else:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=1.
    colors={'Linen':(.36,.33,.27,1),'LinenSeam':(.20,.18,.13,1),
            'Wood':(.12,.055,.024,1),'DarkMetal':(.055,.055,.045,1)}
    mats={}
    for role in colors:
        if preserve_library:
            mat=bpy.data.materials.get(role)
            assert mat is not None,(role,'missing original library material')
            mats[role]=mat
            continue
        mat=bpy.data.materials.new(role);mat.diffuse_color=colors[role];mat.use_nodes=True
        bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value=colors[role]
        bsdf.inputs['Roughness'].default_value=.86 if role in SOFT else .62
        bsdf.inputs['Metallic'].default_value=.7 if role=='DarkMetal' else 0.
        mats[role]=mat
    # Blender stores custom normals in a compressed loop-normal encoding.
    # Keep original rigid buffers outside that encoding and restore them at
    # the actual serialization boundary, keyed by oriented face/corner.
    structural_source={};current_roles=[]
    def preserved_corners(mesh):
        result={}
        for polygon in mesh.polygons:
            if current_roles[polygon.material_index] in SOFT:continue
            corners=tuple(tuple(f32(mesh.vertices[i].co[a]*100.) for a in range(3)) for i in polygon.vertices)
            key=(polygon.material_index,min(corners[j:]+corners[:j] for j in range(3)))
            assert key in structural_source,(mesh.name,'unknown rigid oriented face',key)
            kept=structural_source[key]
            for li,position in zip(polygon.loop_indices,corners):result[li]=kept[position]
        assert len(result)==sum(len(face) for face in structural_source.values()),(mesh.name,'rigid corner coverage')
        return result
    def authored_normals(mesh, normal_source, output):
        normal_source.foreach_get('vector',output)
        kept=preserved_corners(mesh)
        if kept:assert len(output)==len(mesh.loops)*3,(mesh.name,'rigid normals must be ByPolygonVertex')
        for li,corner in kept.items():output[li*3:li*3+3]=corner['normal']
    def authored_uv(mesh, uv_source, output):
        uv_source.foreach_get('vector',output)
        for li,corner in preserved_corners(mesh).items():output[li*2:li*2+2]=corner['uv']
    def frames(mesh, kind, output):
        mesh.calc_loop_triangles();uv=mesh.uv_layers.active;values=[None]*len(mesh.loops)
        for tri in mesh.loop_triangles:
            p=[mesh.vertices[i].co.copy() for i in tri.vertices];u=[uv.data[i].uv.copy() for i in tri.loops]
            e1,e2=p[1]-p[0],p[2]-p[0];a,b=u[1]-u[0],u[2]-u[0];det=a.x*b.y-a.y*b.x
            assert abs(det)>=1e-12,(mesh.name,'singular UV',tri.index,det)
            tangent=(e1*b.y-e2*a.y)/det;bitangent=(e2*a.x-e1*b.x)/det
            for li in tri.loops:
                normal=mesh.corner_normals[li].vector.normalized();projected=tangent-normal*tangent.dot(normal)
                assert projected.length>1e-12,(mesh.name,'invalid derivative',tri.index)
                t=projected.normalized();sign=-1 if normal.cross(t).dot(bitangent)<0 else 1
                values[li]=t if kind=='tangent' else normal.cross(t).normalized()*sign
        for li,corner in preserved_corners(mesh).items():values[li]=Vector(corner[kind])
        assert all(v is not None and all(math.isfinite(x) for x in v) and v.length>.99 for v in values)
        for i,v in enumerate(values):output[i*3:i*3+3]=tuple(v)
    code=inspect.getsource(writer.fbx_data_mesh_elements)
    normal_allocation='t_normal = np.empty(len(normal_source) * 3, dtype=normal_bl_dtype)'
    assert code.count(normal_allocation)==1
    code=code.replace(normal_allocation,'normal_source = me.corner_normals\n        normal_mapping = b"ByPolygonVertex"\n        '+normal_allocation)
    for needle,replacement in (
        ('normal_source.foreach_get("vector", t_normal)','_refinement_authored_normals(me,normal_source,t_normal)'),
        ('uvlayer.uv.foreach_get("vector", t_luv)','_refinement_authored_uv(me,uvlayer.uv,t_luv)')):
        assert code.count(needle)==1
        code=code.replace(needle,replacement)
    for kind in ('tangent','bitangent'):
        needle='me.loops.foreach_get("'+kind+'", t_ln)';assert code.count(needle)==1
        code=code.replace(needle,'_refinement_actual_uv_frames(me,"'+kind+'",t_ln)')
    writer.__dict__['_refinement_actual_uv_frames']=frames
    writer.__dict__['_refinement_authored_normals']=authored_normals
    writer.__dict__['_refinement_authored_uv']=authored_uv
    exec(compile(code,'<softgoods actual UV derivative FBX writer>','exec'),writer.__dict__)
    if not preserve_library:
        collection=bpy.data.collections.new('RefinementSourceLibrary');bpy.context.scene.collection.children.link(collection)
    objects={}
    for v in manifest['variants']:
        if only and v['key'] not in only:continue
        if v.get('source_recipe_is_native_sections'):
            source=legacy_recipe(v['source_recipe_file'],v['key'],v['material_roles'])
        else:source=load(v['source_recipe_file'])
        original_source=source
        if v['key']=='LegacyBedMattress':
            source,legacy_repair=repair_legacy_piping(source)
            v['legacy_preexisting_piping_repair']=legacy_repair
        if v['key']=='LegacyBedPillow':
            source,legacy_repair=repair_legacy_pillow(source)
            v['legacy_preexisting_casing_repair']=legacy_repair
        scale=v['physical_scale'];roles=v['material_roles'];old_local=source['vertices_cm']
        points=[[p[i]*scale[i] for i in range(3)] for p in old_local]
        protected_ids={i for tri,mi in zip(source['triangles'],source['material_indices']) if roles[mi] not in SOFT for i in tri}
        protected_triangles=[(tri,mi) for tri,mi in zip(source['triangles'],source['material_indices']) if roles[mi] not in SOFT]
        protected_physical={tuple(f32(x) for x in points[i]):old_local[i] for i in protected_ids}
        def corner_key(point):return tuple(f32(x) for x in point)
        def oriented_key(corners,mi):return (mi,min(corners[i:]+corners[:i] for i in range(3)))
        structural_corners={}
        for ti,(tri,mi) in enumerate(zip(source['triangles'],source['material_indices'])):
            if roles[mi] in SOFT:continue
            corners=tuple(corner_key(old_local[i]) for i in tri)
            structural_corners[oriented_key(corners,mi)]={corners[j]:dict(
                uv=source['triangle_corner_uv0'][ti][j],normal=source['triangle_corner_normals'][ti][j],
                tangent=source['triangle_corner_tangents'][ti][j],bitangent=source['triangle_corner_bitangents'][ti][j]) for j in range(3)}
        structural_source.clear();structural_source.update(structural_corners);current_roles[:]=roles
        limit=1.8 if v['kind']=='BedPillow' else 2.25
        budget=14500 if v['kind'] in ('BedMattress','BedPillow') else max(8000,11000 if len(source['triangles'])>8000 else 8000)
        dense,triangles,materials=refine_soft_triangles(points,source['triangles'],source['material_indices'],roles,limit,budget,v['kind'],v.get('orientation'))
        data=bpy.data.meshes.new(v['mesh_name']);data.from_pydata(dense,[],triangles);data.update()
        for role in roles:data.materials.append(mats[role])
        for p,mi in zip(data.polygons,materials):p.material_index=mi;p.use_smooth=True
        # Face connectivity separates the two cushions and arm rests. Each
        # cloth part receives its own localized, deterministic tension field.
        adjacency=defaultdict(set);linen_faces=[p for p in data.polygons if roles[p.material_index]=='Linen']
        for p in linen_faces:
            for a,b in zip(p.vertices,list(p.vertices)[1:]+[p.vertices[0]]):adjacency[a].add(b);adjacency[b].add(a)
        groups=[];unseen=set(adjacency)
        while unseen:
            first=next(iter(unseen));stack=[first];group=set();unseen.remove(first)
            while stack:
                a=stack.pop();group.add(a)
                for b in adjacency[a]&unseen:unseen.remove(b);stack.append(b)
            groups.append(sorted(group))
        groups.sort(key=lambda ids:tuple(sum(data.vertices[i].co[a] for i in ids)/len(ids) for a in range(3)))
        original=[tuple(p.co) for p in data.vertices];fields=[]
        normal_axis=(0 if v.get('orientation') and v['orientation'][0]=='X' else 1) if v['kind']=='SeatBack' else 2
        for index,ids in enumerate(groups):
            box=bounds([original[i] for i in ids]);field=make_fold_field(box,v['kind'],v.get('orientation'),index)
            for i in ids:
                p=original[i]
                if p in protected_physical:continue
                delta=field(p)
                q=[p[a]+delta[a] for a in range(3)]
                if v['kind']=='BedPillow':
                    lateral=[a for a in range(3) if a!=normal_axis]
                    radial=max(abs((p[a]-(box[0][a]+box[1][a])/2)/((box[1][a]-box[0][a])/2)) for a in lateral)
                    flat=1-smoothstep(.78,.99,radial)
                    bottom=smoothstep(.015,.10,((box[0][normal_axis]+box[1][normal_axis])/2-p[normal_axis])/(box[1][normal_axis]-box[0][normal_axis]))
                    weight=flat*bottom
                    q[normal_axis]=(1-weight)*q[normal_axis]+weight*box[0][normal_axis]
                if v['kind']=='BedMattress':
                    length_axis=max((a for a in range(3) if a!=normal_axis),key=lambda a:box[1][a]-box[0][a])
                    width_axis=next(a for a in range(3) if a not in (normal_axis,length_axis))
                    u=(p[length_axis]-(box[0][length_axis]+box[1][length_axis])/2)/((box[1][length_axis]-box[0][length_axis])/2)
                    w=(p[width_axis]-(box[0][width_axis]+box[1][width_axis])/2)/((box[1][width_axis]-box[0][width_axis])/2)
                    head_sign=-1 if v['legacy_design'] else 1
                    support=smoothstep(.58,.70,head_sign*u)*(1-smoothstep(.91,.985,head_sign*u))*(1-smoothstep(.88,.98,abs(w)))
                    top=smoothstep(.16,.30,(p[normal_axis]-(box[0][normal_axis]+box[1][normal_axis])/2)/(box[1][normal_axis]-box[0][normal_axis]))
                    weight=support*top
                    # The old pillow's lowest point equals the mattress's maxZ.
                    # A broad head support zone reaches that existing maxZ, so
                    # the stuffed pillow rests on the casing rather than hovering
                    # above the original, excessively domed mattress surface.
                    q[normal_axis]=(1-weight)*q[normal_axis]+weight*box[1][normal_axis]
                data.vertices[i].co=tuple(max(box[0][a],min(box[1][a],q[a])) for a in range(3))
            # Restore the broad casing envelope smoothly, with an affine scale
            # around its unchanged underside. A single fixed crest vertex would
            # produce a tiny spike next to a pressed area.
            new_box=bounds([tuple(data.vertices[i].co) for i in ids])
            span=new_box[1][normal_axis]-new_box[0][normal_axis]
            factor=(box[1][normal_axis]-box[0][normal_axis])/span
            def remap(value,lo=new_box[0][normal_axis],target=box[0][normal_axis],ratio=factor):return target+(value-lo)*ratio
            for i in ids:
                if original[i] not in protected_physical:data.vertices[i].co[normal_axis]=remap(data.vertices[i].co[normal_axis])
            fields.append((box,field,remap))
        # Piping remains a closed cord and follows its nearest cloth casing.
        seam_ids={i for p in data.polygons if roles[p.material_index]=='LinenSeam' for i in p.vertices}
        for i in seam_ids-set(adjacency):
            p=original[i]
            if p in protected_physical or not fields:continue
            def distance(box):return sum(max(box[0][a]-p[a],0.,p[a]-box[1][a])**2 for a in range(3))
            box,field,remap=min(fields,key=lambda x:distance(x[0]));delta=field(p)
            q=[p[a]+delta[a] for a in range(3)];q[normal_axis]=remap(q[normal_axis]);data.vertices[i].co=tuple(q)
        # A fixed measured envelope and grounded frame remain reviewable.
        old_box=bounds(points)
        for p in data.vertices:
            p.co=tuple(max(old_box[0][i],min(old_box[1][i],p.co[i])) for i in range(3))
        legacy_side_proof=None
        if v['key']=='LegacyBedMattress':
            weights=[legacy_mattress_top_weight(p,old_box) if p[2]>(old_box[0][2]+old_box[1][2])/2 else 0. for p in original]
            changed_faces=[];pinned=sum(w==0 for w in weights)
            for i,p in enumerate(data.vertices):
                old=original[i];weight=weights[i]
                if weight==0:p.co=old
                else:p.co=(old[0],old[1],old[2]+weight*(p.co[2]-old[2]))
                assert p.co.x==old[0] and p.co.y==old[1]
            for p in data.polygons:
                if not any(data.vertices[i].co[2]!=original[i][2] for i in p.vertices):continue
                q=[original[i] for i in p.vertices]
                u=[q[1][a]-q[0][a] for a in range(3)];w=[q[2][a]-q[0][a] for a in range(3)]
                cross=(u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0])
                length=math.sqrt(sum(x*x for x in cross))
                assert cross[2]/length>.999999,(v['key'],'repair would move a non-horizontal side face',p.index)
                changed_faces.append(p.index)
            assert all(weights[i]==0 and tuple(data.vertices[i].co)==original[i] for i in seam_ids)
            assert all(tuple(data.vertices[i].co)==original[i] for i,w in enumerate(weights) if w==0)
            legacy_side_proof=dict(passed=True,method='Only original horizontal top interiors move in Z; all XY coordinates, side/bevel/bottom vertices and welting cords are pinned after the final envelope remap',
                edge_mask='1-smoothstep(0.84,0.92,max(abs((x-cx)/hx),abs((y-cy)/hy)))',
                total_vertices=len(weights),pinned_vertices=pinned,changed_horizontal_top_faces=len(changed_faces),
                changed_faces_original_normal_z_min=1.,xy_coordinates_exactly_preserved=True,
                piping_vertices_exactly_preserved=True,affine_envelope_remap_cannot_move_pinned_vertices=True)
        bm=bmesh.new();bm.from_mesh(data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        for e in bm.edges:
            same_material=len({f.material_index for f in e.link_faces})==1
            soft=all(roles[f.material_index] in SOFT for f in e.link_faces)
            e.smooth=e.is_manifold and same_material and (soft or e.calc_face_angle(0)<math.radians(38))
        bm.to_mesh(data);bm.free();data.update()
        physical=[tuple(p.co) for p in data.vertices]
        physical_normals=[tuple(n.vector) for n in data.corner_normals]
        uv=data.uv_layers.new(name='SoftGoodsPhysicalUV_1m')
        for p in data.polygons:
            assert len(p.vertices)==3
            a,b,c=[Vector(physical[i]) for i in p.vertices];n=(b-a).cross(c-a)
            if n.length<=1e-10:
                write(OUT/'DegenerateSourceDebug.json',dict(key=v['key'],face=p.index,material=roles[p.material_index],indices=list(p.vertices),physical=[physical[i] for i in p.vertices],original=[original[i] for i in p.vertices]))
                raise AssertionError((v['key'],'zero physical triangle',p.index))
            drop=max(range(3),key=lambda i:round(abs(n.normalized()[i]),5));axes=tuple(i for i in range(3) if i!=drop);phase=PHASES[axes]
            if roles[p.material_index] not in SOFT:
                corners=tuple(corner_key(protected_physical[physical[i]]) for i in p.vertices)
                kept=structural_corners[oriented_key(corners,p.material_index)]
                for li,token in zip(p.loop_indices,corners):uv.data[li].uv=kept[token]['uv']
            else:
                for li,vi in zip(p.loop_indices,p.vertices):uv.data[li].uv=(physical[vi][axes[0]]/100+phase[0],physical[vi][axes[1]]/100+phase[1])
        for p in data.vertices:
            physical_point=tuple(p.co)
            if physical_point in protected_physical:
                old=protected_physical[physical_point];p.co=tuple(old[i]/100 for i in range(3))
            else:p.co=tuple(p.co[i]/(100*scale[i]) for i in range(3))
        data.update()
        normals=[tuple(Vector(tuple(n[i]*scale[i] for i in range(3))).normalized()) for n in physical_normals]
        for p in data.polygons:
            if roles[p.material_index] not in SOFT:
                corners=tuple(corner_key([data.vertices[i].co[a]*100 for a in range(3)]) for i in p.vertices)
                kept=structural_corners[oriented_key(corners,p.material_index)]
                for li,token in zip(p.loop_indices,corners):normals[li]=tuple(kept[token]['normal'])
        data.normals_split_custom_set(normals);data.update()
        # Explicit source and float32 native-cm orientation guards, including
        # any tiny inherited structural bevel faces.
        fallbacks=0
        def double_unit_normal(q):
            u=[q[1][i]-q[0][i] for i in range(3)];w=[q[2][i]-q[0][i] for i in range(3)]
            cross=(u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0])
            length=math.sqrt(sum(x*x for x in cross));assert length>1e-14,(v['key'],'actual degenerate triangle',q)
            return tuple(x/length for x in cross)
        dot=lambda a,b:sum(a[i]*b[i] for i in range(3))
        for p in data.polygons:
            q=[tuple(data.vertices[i].co) for i in p.vertices];g=double_unit_normal(q)
            q32=[tuple(f32(qi[a]*100.) for a in range(3)) for qi in q];g32=double_unit_normal(q32)
            assert dot(g,g32)>0,(v['key'],'float32 face reversal',p.index)
            if any(min(dot(normals[li],g),dot(normals[li],g32))<=1e-5 for li in p.loop_indices):
                assert roles[p.material_index] in SOFT,(v['key'],'preserved structural normal became invalid',p.index)
                n=Vector(tuple(g[i]+g32[i] for i in range(3))).normalized()
                for li in p.loop_indices:normals[li]=tuple(n)
                fallbacks+=1
        data.normals_split_custom_set(normals);data.update();data.calc_loop_triangles()
        encoded_repairs=0
        for attempt in range(5):
            # Blender stores compressed custom normals in loop-normal space;
            # validate the decoded array that the FBX writer will really read.
            actual=[tuple(n.vector) for n in data.corner_normals];bad=[]
            for t in data.loop_triangles:
                q=[tuple(data.vertices[i].co) for i in t.vertices]
                g=double_unit_normal(q);g32=double_unit_normal([tuple(f32(x*100.) for x in p) for p in q])
                if any(min(dot(actual[li],g),dot(actual[li],g32))<=1e-4 for li in t.loops):
                    assert roles[t.material_index] in SOFT,(v['key'],'encoded structural normal invalid',t.index)
                    bad.append((t,g,g32))
            if not bad:break
            for t,g,g32 in bad:
                n=Vector(tuple(g[i]+g32[i] for i in range(3))).normalized()
                for li in t.loops:actual[li]=tuple(n)
            encoded_repairs+=len(bad)
            data.normals_split_custom_set(actual);data.update();data.calc_loop_triangles()
        assert not bad,(v['key'],'decoded custom normal repair did not converge',len(bad))
        data.calc_tangents(uvmap=uv.name)
        ts=np.empty(len(data.loops)*3,dtype=np.float64);bs=np.empty_like(ts);frames(data,'tangent',ts);frames(data,'bitangent',bs)
        serialized_normals=np.empty(len(data.loops)*3,dtype=np.float64)
        serialized_uv=np.empty(len(data.loops)*2,dtype=np.float64)
        authored_normals(data,data.corner_normals,serialized_normals)
        authored_uv(data,uv.uv,serialized_uv)
        kept_corners=preserved_corners(data)
        for li,corner in kept_corners.items():
            for field,values,width in (('normal',serialized_normals,3),('uv',serialized_uv,2),('tangent',ts,3),('bitangent',bs,3)):
                assert list(values[li*width:li*width+width])==corner[field],(v['key'],'rigid serialized buffer differs',li,field)
        after_local=[[float(x)*100. for x in p.co] for p in data.vertices]
        local_box=bounds(after_local);error=max(abs(local_box[j][i]-v['original_local_bounds_cm'][j][i]) for j in range(2) for i in range(3));assert error<.0002,(v['key'],'bounds',error)
        bm=bmesh.new();bm.from_mesh(data);bad_edges=sum(not e.is_manifold for e in bm.edges);bad_faces=sum(f.calc_area()<=1e-14 for f in bm.faces);volume=bm.calc_volume(signed=True);bm.free()
        assert bad_edges==0 and bad_faces==0 and volume>0,(v['key'],'closed source',bad_edges,bad_faces,volume)
        # Structural triangle coordinates/material partitions are independently
        # compared as exact local float32 values, rather than merely claiming
        # that a deformation mask was used.
        def triangle_signature(positions,tri,mi):
            corners=tuple(tuple(f32(positions[i][a]) for a in range(3)) for i in tri)
            return (mi,min(corners[i:]+corners[:i] for i in range(3)))
        before_structure=Counter(triangle_signature(old_local,t,mi) for t,mi in protected_triangles)
        after_structure=Counter(triangle_signature(after_local,list(p.vertices),p.material_index) for p in data.polygons if roles[p.material_index] not in SOFT)
        assert before_structure==after_structure,(v['key'],'structural geometry changed',len(before_structure),len(after_structure))
        recipe=dict(schema='OldTownRealismRefinedSoftGoodsRecipeV1',key=v['key'],source_asset=v['source_asset'],
            vertices_cm=after_local,triangles=[list(t.vertices) for t in data.loop_triangles],material_indices=[t.material_index for t in data.loop_triangles],
            material_roles=roles,physical_scale=scale,uv_projection_chart_offsets={str(k):x for k,x in PHASES.items()},
            triangle_corner_normals=[[serialized_normals[i*3:i*3+3].tolist() for i in t.loops] for t in data.loop_triangles],
            triangle_corner_uv0=[[serialized_uv[i*2:i*2+2].tolist() for i in t.loops] for t in data.loop_triangles],
            triangle_corner_tangents=[[ts[i*3:i*3+3].tolist() for i in t.loops] for t in data.loop_triangles],
            triangle_corner_bitangents=[[bs[i*3:i*3+3].tolist() for i in t.loops] for t in data.loop_triangles],
            features=['Finite curved tension folds and tapered corner gathers','Asymmetric stuffed or seated depression','Original closed casing/piping and measured envelope','Frozen wood/metal support triangles'],
            structural_triangles_preserved=True,structural_triangle_count=sum(before_structure.values()),
            structural_original_corner_uv_and_normals_preserved=True,
            structural_all_corner_buffers_preserved_exactly=True,structural_serialized_corner_count=len(kept_corners),
            topology=dict(nonmanifold_edges=bad_edges,degenerate_faces=bad_faces,signed_local_volume_cm3=volume*1e6),
            normal_float32_cm_guard_passed=True,geometric_corner_normal_fallback_faces=fallbacks,
            decoded_custom_normal_repair_faces=encoded_repairs)
        recipe['float32_local_cm_topology']=float32_local_cm_proof(recipe['vertices_cm'],recipe['triangles'],recipe['triangle_corner_normals'],original_source,recipe['material_indices'],roles)
        if v.get('legacy_preexisting_piping_repair'):
            recipe['legacy_preexisting_piping_repair']={**v['legacy_preexisting_piping_repair'],
                'old_native_file':v['source_recipe_file'],'old_native_sha256':v['source_recipe_sha256'],
                'new_indexed_odd_boundary_edges':0,'new_float32_odd_boundary_edges':recipe['float32_local_cm_topology']['odd_boundary_edges']}
        if v.get('legacy_preexisting_casing_repair'):
            recipe['legacy_preexisting_casing_repair']={**v['legacy_preexisting_casing_repair'],
                'old_native_file':v['source_recipe_file'],'old_native_sha256':v['source_recipe_sha256'],
                'new_indexed_odd_boundary_edges':0,'new_float32_odd_boundary_edges':recipe['float32_local_cm_topology']['odd_boundary_edges']}
        if legacy_side_proof:
            recipe['legacy_side_fold_prevention']=legacy_side_proof
            v['legacy_side_fold_prevention']=legacy_side_proof
            recipe['legacy_lateral_fold_guard']=legacy_side_proof
            v['legacy_lateral_fold_guard']=legacy_side_proof
        recipe['float32_local_cm_topology']['old_recipe_file']=v['source_recipe_file']
        recipe['float32_local_cm_topology']['old_recipe_sha256']=v['source_recipe_sha256']
        recipe['float32_local_cm_topology']['source_indexed_two_manifold_verified']=bad_edges==0
        obj=bpy.data.objects.new(v['mesh_name'],data);collection.objects.link(obj);objects[v['key']]=obj
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        path=OUT/v['fbx_file'];bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,global_scale=1.,apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',use_space_transform=True,bake_space_transform=False,object_types={'MESH'},use_mesh_modifiers=True,mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,bake_anim=False,path_mode='AUTO')
        write(v['geometry_recipe_file'],recipe)
        minimum_uv=min(abs((uv.data[t.loops[1]].uv.x-uv.data[t.loops[0]].uv.x)*(uv.data[t.loops[2]].uv.y-uv.data[t.loops[0]].uv.y)-(uv.data[t.loops[1]].uv.y-uv.data[t.loops[0]].uv.y)*(uv.data[t.loops[2]].uv.x-uv.data[t.loops[0]].uv.x)) for t in data.loop_triangles)
        assert minimum_uv>=1e-12
        v.update(status='READY',passed=True,local_bounds_cm=local_box,maximum_bounds_change_cm=error,
            fbx_sha256=sha(path),source_file_sha256=sha(path),geometry_recipe_sha256=sha(v['geometry_recipe_file']),
            vertices=len(data.vertices),triangles=len(data.loop_triangles),material_slots=roles,
            closed_manifold=True,boundary_or_nonmanifold_edges=0,degenerate_faces=0,
            uv_degenerate_triangle_count=0,minimum_uv_area2=minimum_uv,invalid_tangent_count=0,
            normal_float32_cm_guard_passed=True,structural_triangles_preserved=True,
            structural_original_corner_uv_and_normals_preserved=True,
            structural_all_corner_buffers_preserved_exactly=True,structural_serialized_corner_count=len(kept_corners),
            float32_local_cm_topology=recipe['float32_local_cm_topology'],
            structural_triangle_count=sum(before_structure.values()),cloth_connected_part_count=len(groups),
            uv_mapping=manifest['uv_mapping'],physical_deformation_max_cm=max((Vector(tuple(p.co[a]*100*scale[a] for a in range(3)))-Vector(original[i])).length for i,p in enumerate(data.vertices)))
        write(OUT/'ModelDataManifest.json',manifest)
        obj.hide_render=True;obj.hide_set(True)
        print('SOFTGOODS_MODEL_READY',v['key'],len(data.loop_triangles),error,flush=True)
    manifest['completed_variant_count']=sum(v.get('passed',False) for v in manifest['variants'])
    manifest['passed']=manifest['completed_variant_count']==20
    manifest['status']='READY' if manifest['passed'] else 'PARTIAL'
    manifest['blend_file']=str(OUT/'OldTownRefinedSoftGoods.blend')
    bpy.ops.wm.save_as_mainfile(filepath=manifest['blend_file'])
    manifest['blend_sha256']=sha(manifest['blend_file'])
    measure_contacts(manifest)
    write(OUT/'ModelDataManifest.json',manifest)
    if not preserve_previews:preview(manifest,objects,bpy,mats)
    print('SOFTGOODS_SOURCE_REFINEMENT_COMPLETE',manifest['completed_variant_count'],flush=True)

def preview(manifest, objects, bpy, mats):
    """Two lit source previews; these are not saved Unreal-map captures."""
    from mathutils import Vector
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.world.color=(.055,.055,.055);scene.view_settings.exposure=-.8
    preview_collection=bpy.data.collections.new('PreviewOnlyPhysicalAssembly');scene.collection.children.link(preview_collection)
    old=load(OLD/'ModelDataManifest.json');old_by_key={v['key']:v for v in old['variants']}
    old_by_actor={a['actor_label']:a for a in old['actors']}
    def place(key,position=(0,0,0),preview_key=None):
        v=next((v for v in manifest['variants'] if v['key']==key),None)
        if key in objects:
            data=objects[key].data.copy();scale=v['physical_scale']
        else:
            ov=old_by_key[key];r=load(ov['geometry_recipe_file']);scale=r['physical_scale'];data=bpy.data.meshes.new('Preview_'+key)
            data.from_pydata([[p[i]/100 for i in range(3)] for p in r['vertices_cm']],[],r['triangles']);data.update()
            for role in r['material_roles']:data.materials.append(mats.get(role,mats['Wood']))
            for p,mi in zip(data.polygons,r['material_indices']):p.material_index=mi;p.use_smooth=True
        obj=bpy.data.objects.new('Preview_'+(preview_key or key),data);preview_collection.objects.link(obj);obj.scale=scale;obj.location=position
        return obj
    def assembly(room,bed,shift):
        stem=f'OTS_HotelV4_Room{room}_Bed{bed}';base=old_by_actor[stem+'Base'];floor=base['original_world_bounds_cm'][0][2]-5
        origin=base['position_cm']
        for ending in ('Base','Mattress','Head','Pillow'):
            a=old_by_actor[stem+ending];pos=[(a['position_cm'][i]-(origin[i] if i<2 else floor))/100 for i in range(3)]
            pos[0]+=shift[0];pos[1]+=shift[1];place(a['key'],pos,stem+ending)
    assembly(201,0,(0,0));assembly(203,0,(0,1.65))
    for ending in ('Base','Back'):
        a=old_by_actor['OTS_HotelV4_Room201_Armchair_'+ending];base=old_by_actor['OTS_HotelV4_Room201_Armchair_Base'];floor=base['original_world_bounds_cm'][0][2]-8
        pos=[(a['position_cm'][i]-(base['position_cm'][i] if i<2 else floor))/100 for i in range(3)];pos[0]+=2.3;pos[1]+=.5;place(a['key'],pos)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));plane=bpy.context.object;plane.name='PreviewFloor';floor_mat=bpy.data.materials.new('PreviewFloor');floor_mat.diffuse_color=(.21,.20,.18,1);plane.data.materials.append(floor_mat)
    for name,pos,energy,size in [('PreviewKey',(1,2,4),450,3),('PreviewRaking',(-3,2,1.15),350,1.5),('PreviewFill',(3,-3,2.5),150,3)]:
        ld=bpy.data.lights.new(name,'AREA');ld.energy=energy;ld.shape='DISK';ld.size=size;o=bpy.data.objects.new(name,ld);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((.8,.8,.4))-o.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.cameras.new('PreviewCamera');cam=bpy.data.objects.new('PreviewCamera',camera);scene.collection.objects.link(cam);scene.camera=cam
    for name,position,target,lens in [('Preview_SoftGoods_Overall.png',(-3.7,4.4,3.1),(.35,1.0,.48),46),('Preview_ClothFolds_Close.png',(-1.5,-1.2,1.18),(-.08,-.03,.44),58),('Preview_SeatDepressions_Close.png',(3.6,2.1,1.48),(2.3,.5,.56),59)]:
        cam.location=position;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camera.lens=lens;scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
    manifest['source_previews']=[dict(file=str(OUT/n),sha256=sha(OUT/n),note='Physical geometry with simple role colors, isolated Blender lights; final Unreal PBR/lighting reviewed separately') for n in ('Preview_SoftGoods_Overall.png','Preview_ClothFolds_Close.png','Preview_SeatDepressions_Close.png')]
    write(OUT/'ModelDataManifest.json',manifest)

def repair_legacy_mattress_source():
    """Transactional source-only repair without resetting the other 19 models.

    The ordinary --only path starts an empty library, so it is deliberately not
    used for this operation. A staging library is built from the existing full
    Blend; source bytes are committed only after the local scan/contact guards.
    """
    import bpy
    import copy
    from datetime import datetime, timezone
    import shutil
    global OUT
    destination=OUT
    evidence=ROOT/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013/OverlapDiagnosis'
    backup_receipt=load(evidence/'BeforeCorrectionBackup.json')
    backup=Path(backup_receipt['backup_directory']);backup_manifest=backup/'Manifest.json'
    assert backup_receipt['passed'] and sha(backup_manifest)==backup_receipt['manifest_sha256']
    backup_files={r['relative_path']:r for r in load(backup_manifest)['files']}
    manifest=load(destination/'ModelDataManifest.json')
    assert manifest['passed'] and manifest['status']=='READY' and len(manifest['variants'])==20
    before=copy.deepcopy(manifest)
    victim=next(v for v in manifest['variants'] if v['key']=='LegacyBedMattress')
    protected={}
    for v in manifest['variants']:
        for p,digest in ((destination/v['fbx_file'],v['fbx_sha256']),(Path(v['geometry_recipe_file']),v['geometry_recipe_sha256'])):
            assert sha(p)==digest,(str(p),'stale source')
            relative=p.relative_to(ROOT).as_posix()
            assert relative in backup_files and backup_files[relative]['sha256']==digest and sha(backup/relative)==digest
            if v['key']!='LegacyBedMattress':protected[str(p)]=digest
    for r in manifest['source_previews']:
        p=Path(r['file']);assert sha(p)==r['sha256'];protected[str(p)]=r['sha256']
    original_blend=Path(manifest['blend_file']);assert sha(original_blend)==manifest['blend_sha256']
    assert sha(backup/original_blend.relative_to(ROOT))==manifest['blend_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(original_blend))
    def object_fingerprint(obj):
        mesh=obj.data
        payload=dict(name=obj.name,mesh=mesh.name,matrix=[list(r) for r in obj.matrix_world],
            parent=obj.parent.name if obj.parent else None,hidden=obj.hide_get(),hide_render=obj.hide_render,
            vertices=[list(v.co) for v in mesh.vertices],polygons=[(list(p.vertices),p.material_index,p.use_smooth) for p in mesh.polygons],
            edges=[(list(e.vertices),e.use_seam,e.use_edge_sharp) for e in mesh.edges],
            materials=[m.name if m else None for m in mesh.materials],
            uv_layers={uv.name:[list(x.uv) for x in uv.data] for uv in mesh.uv_layers},
            corner_normals=[list(n.vector) for n in mesh.corner_normals])
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    keep_names=[v['mesh_name'] for v in manifest['variants'] if v['key']!='LegacyBedMattress']
    preserved_objects={name:object_fingerprint(bpy.data.objects[name]) for name in keep_names}
    assert len(bpy.data.collections['RefinementSourceLibrary'].objects)==20
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stage=evidence/('LegacySourceRepair_'+stamp)
    stage.mkdir(parents=True,exist_ok=False)
    # The contact prover resolves FBX provenance relative to OUT. Give the
    # isolated stage read-only-equivalent copies of its 19 unchanged inputs.
    for v in manifest['variants']:
        if v['key']!='LegacyBedMattress':
            shutil.copy2(destination/v['fbx_file'],stage/v['fbx_file'])
            assert sha(stage/v['fbx_file'])==v['fbx_sha256']
    write(stage/'BeforeManifest.json',before)
    write(stage/'PreservedSourceFiles.json',protected)
    manifest['source_script_file']=str(Path(__file__).resolve())
    manifest['source_script_sha256']=sha(manifest['source_script_file'])
    manifest['incremental_legacy_mattress_repair']=dict(backup_manifest_file=str(backup_manifest),
        backup_manifest_sha256=sha(backup_manifest),before_manifest_sha256=sha(destination/'ModelDataManifest.json'),
        retained_other_variant_count=19,retained_source_preview_count=3,
        preview_scope='The three retained source previews depict hotel furniture, not the legacy mattress; they are unchanged historical previews, not new legacy-mattress visual evidence.')
    final_recipe=Path(victim['geometry_recipe_file'])
    victim['geometry_recipe_file']=str(stage/final_recipe.name)
    OUT=stage
    try:
        build(manifest,{'LegacyBedMattress'},preserve_library=True,preserve_previews=True)
        assert len(bpy.data.collections['RefinementSourceLibrary'].objects)==20
        assert preserved_objects=={name:object_fingerprint(bpy.data.objects[name]) for name in keep_names},'Other Blend library data changed'
        assert all(sha(p)==digest for p,digest in protected.items()),'Protected source bytes changed'
        assert [v for v in manifest['variants'] if v['key']!='LegacyBedMattress']==[v for v in before['variants'] if v['key']!='LegacyBedMattress']
        assert manifest['source_previews']==before['source_previews']
        # Same production scanner and exact tolerances; no special exemptions.
        sys.path.insert(0,str(ROOT/'Scripts'))
        from OldTownCoplanarScan import scan_components
        from ClassifyOldTownInternalSurfaceOcclusion import classify_internal_occlusion
        recipe=load(victim['geometry_recipe_file'])
        record=dict(id='LegacyBedMattress::RefinedSource',actor='LegacyBedMattress',component='RefinedSource',
            mesh=victim['mesh_name'],vertices=[[f32(x) for x in p] for p in recipe['vertices_cm']],
            triangles=recipe['triangles'],visible=True,reverse_winding=False)
        write(stage/'LocalGeometry.json',dict(components=[record],source_recipe_sha256=sha(victim['geometry_recipe_file'])))
        scan=scan_components([record],plane_tolerance_cm=.03,normal_tolerance=.0001,min_overlap_area_cm2=1.,include_internal=True,axis_only=False)
        write(stage/'LocalCoplanarScan.json',scan)
        classified=classify_internal_occlusion([record],scan)
        write(stage/'LocalInternalOcclusionScan.json',classified)
        exposed=[r for r in classified['overlaps'] if not r['buried']]
        assert not exposed,('Legacy source still has exposed overlaps',exposed)
        contacts=load(stage/'SourceContactProof.json')
        assert contacts['passed'] and contacts['pair_count']==55
        for v in manifest['variants']:
            if v['key']!='LegacyBedMattress':continue
            assert sha(stage/v['fbx_file'])!=before['variants'][next(i for i,x in enumerate(before['variants']) if x['key']=='LegacyBedMattress')]['fbx_sha256']
            shutil.copy2(stage/v['fbx_file'],destination/v['fbx_file'])
            shutil.copy2(stage/final_recipe.name,final_recipe)
            v['geometry_recipe_file']=str(final_recipe)
            assert sha(final_recipe)==v['geometry_recipe_sha256'] and sha(destination/v['fbx_file'])==v['fbx_sha256']
        shutil.copy2(Path(manifest['blend_file']),original_blend)
        manifest['blend_file']=str(original_blend)
        assert sha(original_blend)==manifest['blend_sha256']
        OUT=destination
        measure_contacts(manifest)
        assert all(sha(p)==digest for p,digest in protected.items())
        assert manifest['source_script_sha256']==sha(__file__)
        manifest['incremental_legacy_mattress_repair'].update(passed=True,staging_directory=str(stage),
            local_scan_file=str(stage/'LocalInternalOcclusionScan.json'),local_scan_sha256=sha(stage/'LocalInternalOcclusionScan.json'),
            local_exposed_groups=0,all_other_source_bytes_unchanged=True,all_other_variant_records_unchanged=True,
            all_other_blend_objects_unchanged=True,retained_blend_object_fingerprints=preserved_objects)
        write(destination/'ModelDataManifest.json',manifest)
        report=dict(passed=True,source_manifest_file=str(destination/'ModelDataManifest.json'),
            source_manifest_sha256=sha(destination/'ModelDataManifest.json'),source_script_sha256=sha(__file__),
            repaired_variant='LegacyBedMattress',protected_file_count=len(protected),
            preserved_other_variants=19,preserved_blend_objects=19,preserved_hotel_source_previews=3,
            local_exposed_groups=0,local_total_overlap_groups=len(classified['overlaps']),
            contact_pairs=55,all_contacts_passed=True,stage_directory=str(stage))
        write(evidence/'SourceRepairReport.json',report)
        print('LEGACY_MATTRESS_SOURCE_REPAIR_PASS',json.dumps(report),flush=True)
    finally:
        OUT=destination


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inventory',action='store_true');parser.add_argument('--build',action='store_true');parser.add_argument('--only',nargs='*');parser.add_argument('--repair-legacy-mattress',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    if args.repair_legacy_mattress:
        assert not args.inventory and not args.build and not args.only
        repair_legacy_mattress_source()
        return
    m=inventory()
    if args.build:build(m,set(args.only) if args.only else None)
    else:print('SOFTGOODS_INVENTORY_READY',m['variant_count'],m['component_count'])

if __name__=='__main__':main()
