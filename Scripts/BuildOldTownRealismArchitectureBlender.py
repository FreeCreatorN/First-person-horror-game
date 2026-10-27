"""Rebuild measured hotel architecture as source art; never operate Unreal.

Existing component pivots, transforms, bounds, and collision remain the input
contract. Physical centimetre features are normalized back to each source mesh's
local coordinates. Materials have metre-scale UVs and stable role names.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012/RealismInput.json'
OUT = ROOT / 'SourceArt/OldTownRealism_20261012/Architecture'
ROLES = ('Wood', 'PaintedWood', 'Stone', 'PaintedMetal', 'DarkMetal',
         'Chrome', 'Ceramic', 'Glass', 'Rubber')
CUBE_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def source_rows():
    data = load(INPUT)
    assert data['passed'] and data['statistics']['blueprint_variants'] == 18
    rows = []
    components = data['component_records']
    layout = data['layout_manifest']
    boxes = {r['id']: r for r in layout['boxes']}

    def add(actor, component, kind, orientation=None, metadata=None):
        c = next(r for r in components[actor] if r['name'] == component)
        assert c.get('mesh') and c['primitive_properties']['visible'] and not c['primitive_properties']['hidden_in_game'], (actor, component)
        scale = c['world_pose']['scale']
        assert all(v > 0 for v in scale) and not c['world_transform_negative_determinant']
        bounds = c['local_render_bounds_cm']
        dims = [(bounds[1][i] - bounds[0][i]) * scale[i] for i in range(3)]
        props = dict(kind=kind, orientation=orientation, metadata=metadata or {},
                     source_asset=c['mesh'], source_local_bounds_cm=bounds,
                     component_scale=scale)
        digest = hashlib.sha256(json.dumps(props, sort_keys=True).encode()).hexdigest()[:10]
        key = kind + '_' + digest
        row = dict(key=key, kind=kind, actor=actor, actor_label=actor,
                   component=component, source_asset=c['mesh'],
                   source_local_bounds_cm=bounds, component_scale=scale,
                   world_dimensions_cm=dims, orientation=orientation,
                   metadata=metadata or {}, original_component=c,
                   source_file_sha256=data['meshes'][c['mesh']]['sha256'])
        rows.append(row)

    for r in layout['doors']:
        actor = r['actor']
        glass = r['id'] in ('MainEntry', 'VestibuleInnerDoor')
        for c in components[actor]:
            name = c['name']
            if not c.get('mesh') or 'Collision' in name:
                continue
            if name in ('FrameLeft', 'FrameRight', 'FrameTop'):
                kind = {'FrameLeft': 'DoorJambLeft', 'FrameRight': 'DoorJambRight', 'FrameTop': 'DoorHeader'}[name]
                add(actor, name, kind)
            elif 'GlassPanel' in name:
                add(actor, name, 'EntranceGlazing')
            elif name in ('DoorLeaf', 'LeftLeaf', 'RightLeaf'):
                kind = 'EntranceLeaf' if glass else 'ElevatorLeaf' if r.get('locked') and r['role'] == 'lift' else 'SwingLeaf' if r['kind'] == 'swing' else 'SlidingLeaf'
                add(actor, name, kind, metadata={'opening_height_cm': r['height']} if glass else None)
            elif name in ('Handle', 'LeftHandle', 'RightHandle'):
                add(actor, name, 'LeverHandle' if name == 'Handle' else 'PullHandle', r.get('hinge_side') if name == 'Handle' else None)
            else:
                raise ValueError(('Unclassified visible door component', actor, name))

    for r in layout['windows']:
        for c in components[r['actor']]:
            name = c['name']
            if not c.get('mesh') or 'Collision' in name:
                continue
            if name.startswith('Frame'):
                add(r['actor'], name, 'Window' + {'FrameLeft': 'JambLeft', 'FrameRight': 'JambRight', 'FrameTop': 'Header', 'FrameBottom': 'Sill'}[name])
            elif name.endswith('Sash'):
                add(r['actor'], name, 'WindowGlazing')
            elif name.endswith('MeetingRail'):
                add(r['actor'], name, 'WindowMeetingRail')
            elif name.endswith('UpperRail') or name.endswith('LowerRail'):
                add(r['actor'], name, 'WindowHorizontalRail')
            else:
                raise ValueError(('Unclassified visible window component', r['actor'], name))

    for r in layout['boxes']:
        if r['role'] not in ('guard', 'stair_baseplate', 'stair_tread'):
            continue
        c = next(c for c in components[r['actor']] if c.get('mesh'))
        kind = {'guard': 'StairPost', 'stair_baseplate': 'StairBaseplate', 'stair_tread': 'StairTread'}[r['role']]
        orientation = None
        if kind == 'StairTread':
            stem, number = re.match(r'(.*Tread)(\d+)$', r['id']).groups()
            next_r = boxes.get(stem + '%02d' % (int(number) + 1))
            prev_r = boxes.get(stem + '%02d' % (int(number) - 1))
            reference = next_r or prev_r
            delta = [(reference['world_min'][i] + reference['world_max'][i] - r['world_min'][i] - r['world_max'][i]) / 2 for i in range(2)]
            if not next_r:
                delta = [-v for v in delta]
            axis = max(range(2), key=lambda i: abs(delta[i]))
            # The nosing lies towards the lower step, opposite ascent.
            orientation = ('X' if axis == 0 else 'Y') + ('N' if delta[axis] > 0 else 'P')
        add(r['actor'], c['name'], kind, orientation)

    for r in layout['props']:
        kind = 'HandrailPipe' if r.get('detail_kind') == 'round_handrail' else 'FluorescentHousing' if r.get('asset_key') == 'FluorescentFixture' else None
        if kind:
            c = next(c for c in components[r['actor']] if c.get('mesh'))
            add(r['actor'], c['name'], kind)
    kinds = Counter(r['kind'] for r in rows)
    assert kinds['StairPost'] == 240 and kinds['StairBaseplate'] == 240 and kinds['StairTread'] == 198
    assert kinds['HandrailPipe'] == 60 and kinds['FluorescentHousing'] == 24
    assert len({(r['actor'], r['component']) for r in rows}) == len(rows)
    return data, rows


def early_manifest(data, rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['key']].append(r)
    manifest = dict(schema_version=1, schema='OldTownRealismArchitectureSourceV1',
        status='AUTHORING', actor_count=len({r['actor'] for r in rows}), component_count=len(rows),
        variant_count=len(groups), source_map_sha256=data['source_map_sha256'],
        source_native_inventory_file=str(INPUT), source_native_inventory_sha256=sha(INPUT),
        source_script_sha256=sha(__file__), material_roles=list(ROLES),
        coordinates='Original UE local centimetres converted to Blender metres; FBX -Y forward Z up; root importer corrects measured Y reflection',
        export_units='metres converted to centimetres by FBX importer',
        source_asset_file_sha256=data['source_asset_file_sha256'],
        kinds=dict(Counter(r['kind'] for r in rows)), variants=[], actors=rows)
    for key, members in sorted(groups.items()):
        r = members[0]
        mesh = 'SM_OTS_Real_Arch_' + key
        manifest['variants'].append(dict(key=key, kind=r['kind'], mesh_name=mesh,
            source_asset=r['source_asset'], source_asset_sha256=r['source_file_sha256'],
            source_local_bounds_cm=r['source_local_bounds_cm'], local_bounds_cm=r['source_local_bounds_cm'],
            world_dimensions_cm=r['world_dimensions_cm'], component_scale=r['component_scale'],
            orientation=r['orientation'], metadata=r['metadata'],
            source_actor_labels=[m['actor'] for m in members],
            components=[dict(actor=m['actor'], component=m['component']) for m in members],
            instance_count=len(members), fbx_file=mesh + '.fbx'))
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / 'ModelDataManifest.json', manifest)
    return manifest


def blender_build(manifest):
    import bpy
    import bmesh
    from mathutils import Vector
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    colors = {'Wood': (.15, .075, .033, 1), 'PaintedWood': (.11, .15, .105, 1),
        'Stone': (.40, .39, .34, 1), 'PaintedMetal': (.10, .15, .095, 1),
        'DarkMetal': (.065, .065, .055, 1), 'Chrome': (.43, .44, .42, 1),
        'Ceramic': (.59, .575, .515, 1), 'Glass': (.29, .355, .345, 1), 'Rubber': (.033, .032, .028, 1)}
    mats = {}
    for role in ROLES:
        mat = bpy.data.materials.new(role)
        mat.diffuse_color = colors[role]
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = colors[role]
        bsdf.inputs['Roughness'].default_value = .16 if role in ('Glass', 'Chrome') else .62
        bsdf.inputs['Metallic'].default_value = .95 if role in ('DarkMetal', 'Chrome') else .45 if role == 'PaintedMetal' else 0
        if role == 'Glass':
            bsdf.inputs['Transmission Weight'].default_value = .82
            bsdf.inputs['IOR'].default_value = 1.46
        mats[role] = mat
    current_parts = []
    features = []
    serial = 0

    def mesh(vertices, faces, role, bevel=0, smooth=False):
        nonlocal serial
        serial += 1
        name = 'ArchitecturePart_%05d' % serial
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        data.materials.append(mats[role])
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if bevel:
            mod = obj.modifiers.new('Physical edge radius', 'BEVEL')
            mod.width = bevel
            mod.segments = 3
            mod.limit_method = 'ANGLE'
            bpy.ops.object.modifier_apply(modifier=mod.name)
        for f in data.polygons:
            f.use_smooth = smooth or bool(bevel)
        bm = bmesh.new()
        bm.from_mesh(data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(data)
        bm.free()
        if bevel:
            mod = obj.modifiers.new('Physical weighted normals', 'WEIGHTED_NORMAL')
            mod.keep_sharp = True
            mod.weight = 50
            bpy.ops.object.modifier_apply(modifier=mod.name)
        obj.select_set(False)
        current_parts.append(obj)
        return obj

    def box(center, dims, role, bevel=.12):
        x, y, z = [v / 2 for v in dims]
        verts = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                 (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
        return mesh([tuple(p[i] + center[i] for i in range(3)) for p in verts], CUBE_FACES,
                    role, min(bevel, min(dims) * .2))

    def cylinder(a, b, radius, role, sides=32):
        a, b = Vector(a), Vector(b)
        direction = (b - a).normalized()
        helper = Vector((0, 0, 1)) if abs(direction.z) < .9 else Vector((0, 1, 0))
        u = direction.cross(helper).normalized()
        v = direction.cross(u)
        verts = [tuple(p + radius * (math.cos(2 * math.pi * i / sides) * u + math.sin(2 * math.pi * i / sides) * v))
                 for p in (a, b) for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
        faces.extend((i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides))
        return mesh(verts, faces, role, smooth=True)

    def swept(points, radius, role, sides=24):
        # Open centreline, closed capped surface. The path lies in an X/Y or Y/Z plane.
        verts = []
        for i, point in enumerate(points):
            prev = Vector(points[max(0, i - 1)])
            nxt = Vector(points[min(len(points) - 1, i + 1)])
            tangent = (nxt - prev).normalized()
            u = Vector((0, 0, 1)) if abs(tangent.z) < .1 else Vector((1, 0, 0))
            u = (u - tangent * u.dot(tangent)).normalized()
            v = tangent.cross(u).normalized()
            for j in range(sides):
                ang = j * math.tau / sides
                verts.append(tuple(Vector(point) + radius * (math.cos(ang) * u + math.sin(ang) * v)))
        faces = [tuple(reversed(range(sides))), tuple((len(points)-1)*sides+j for j in range(sides))]
        for i in range(len(points) - 1):
            for j in range(sides):
                faces.append((i*sides+j, i*sides+(j+1)%sides, (i+1)*sides+(j+1)%sides, (i+1)*sides+j))
        return mesh(verts, faces, role, smooth=True)

    def extrusion(profile, axis, length, role, bevel=.1):
        axes = [i for i in range(3) if i != axis]
        verts = []
        for coord in (-length / 2, length / 2):
            for p in profile:
                v = [0, 0, 0]
                v[axis], v[axes[0]], v[axes[1]] = coord, p[0], p[1]
                verts.append(tuple(v))
        n = len(profile)
        faces = [tuple(reversed(range(n))), tuple(range(n, n*2))]
        faces.extend((i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n))
        return mesh(verts, faces, role, bevel)

    def ring(width, height, depth, hole_w, hole_h, hole_z=0, role='PaintedMetal', bevel=.09):
        # A single closed annulus; its centre is a real hole through the full depth.
        def rounded(w,h,r,zoff=0):
            points=[]
            for cx,cz,angle in ((w/2-r,-h/2+r,-90),(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180)):
                for j in range(5):
                    theta=math.radians(angle+j*22.5)
                    points.append((cx+r*math.cos(theta),cz+r*math.sin(theta)+zoff))
            return points
        edge=min(bevel,depth*.2,(width-hole_w)*.12,(height-hole_h)*.12)
        n=20
        levels=[(-depth/2,edge),(-depth/2+edge,0),(depth/2-edge,0),(depth/2,edge)]
        verts=[]
        for y,inset in levels:
            outer=rounded(width-2*inset,height-2*inset,max(.01,bevel),0)
            inner=rounded(hole_w+2*inset,hole_h+2*inset,max(.01,bevel),hole_z)
            verts.extend((x,y,z) for loop in (outer,inner) for x,z in loop)
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces.extend(((i,j,j+n,i+n), (6*n+i,7*n+i,7*n+j,6*n+j)))
            for row in range(3):
                a=row*2*n
                faces.extend(((a+i,a+2*n+i,a+2*n+j,a+j),
                              (a+n+i,a+n+j,a+3*n+j,a+3*n+i)))
        return mesh(verts,faces,role,smooth=True)

    def paneled_leaf(d, role):
        w, dep, h = d
        stile = min(8., w * .10)
        low, mid, high = -h/2+16, -h*.06, h/2-18
        panels = [(-w/2+stile, w/2-stile, low, mid-5), (-w/2+stile, w/2-stile, mid+5, high)]
        xs = sorted(set([-w/2,w/2]+[p[i]+delta for p in panels for i in (0,1) for delta in (0, -.6 if i==1 else .6)]))
        zs = sorted(set([-h/2,h/2]+[p[i]+delta for p in panels for i in (2,3) for delta in (0, -.6 if i==3 else .6)]))
        def inset(x,z):
            for xa,xb,za,zb in panels:
                if xa <= x <= xb and za <= z <= zb:
                    f = min(1, (x-xa)/.6, (xb-x)/.6, (z-za)/.6, (zb-z)/.6)
                    return .60 * max(0,f)
            return 0
        verts = [(x, s*(dep/2-inset(x,z)), z) for s in (-1,1) for z in zs for x in xs]
        nx,nz = len(xs),len(zs)
        n = nx*nz
        faces = []
        for side in range(2):
            for j in range(nz-1):
                for i in range(nx-1):
                    a=side*n+j*nx+i
                    faces.append((a,a+1,a+nx+1,a+nx))
        perimeter = list(range(nx))+[j*nx+nx-1 for j in range(1,nz)]+list(range(n-2,n-nx-1,-1))+[j*nx for j in range(nz-2,0,-1)]
        faces.extend((perimeter[i],perimeter[(i+1)%len(perimeter)],perimeter[(i+1)%len(perimeter)]+n,perimeter[i]+n) for i in range(len(perimeter)))
        mesh(verts,faces,role)
        features.append(dict(name='Two recessed framed door panels', recess_cm=.60, stile_cm=stile, panel_bounds_xz_cm=panels))

    def frame(d, kind):
        w,dep,h=d
        vertical='Jamb' in kind or kind=='WindowMeetingRail'
        rail=kind in ('WindowMeetingRail','WindowHorizontalRail')
        axis=2 if vertical else 0
        span=w if vertical else h
        length=h if vertical else w
        # Stepped glazing/door rebate: the solid outer side retains the envelope,
        # while the opening side has a recessed channel and narrow stop.
        rabbet=min(span*.38,1.2)
        profile=[(-span/2,-dep/2),(span/2,-dep/2), (span/2,-dep*.28),
                 (span/2-rabbet,-dep*.28),(span/2-rabbet,dep*.23),
                 (span/2,dep*.23),(span/2,dep/2),(-span/2,dep/2)]
        positive_inner='Left' in kind or kind in ('WindowSill','WindowHorizontalRail','WindowMeetingRail')
        if not positive_inner:
            profile=[(-a,b) for a,b in profile]
        if not vertical:
            profile=[(b,a) for a,b in profile]  # axis X leaves profile Y/Z
        extrusion(profile,axis,length,'PaintedMetal',.08 if rail else .10)
        features.append(dict(name='Stepped solid frame rebate', channel_depth_cm=rabbet, extrude_axis=axis))

    def glazing(d, entrance=False):
        w,dep,h=d
        border=.22 if entrance else .7
        glass_depth=.36 if entrance else .6
        ring(w,h,dep,w-2*border,h-2*border,role='PaintedMetal',bevel=.025 if entrance else .07)
        # The glass edge embeds in the annulus, rather than resting on another face.
        box((0,0,0),(w-1.7*border,glass_depth,h-1.7*border),'Glass',.025)
        for sign in (-1,1):
            gasket=ring(w-.65*border,h-.65*border,.08,w-1.95*border,h-1.95*border,role='Rubber',bevel=.015)
            for v in gasket.data.vertices:
                v.co.y += sign*(glass_depth/2+.025)
        features.append(dict(name='Thin glass pane held by metal bead and two rubber seals', glass_thickness_cm=glass_depth, metal_depth_cm=dep, edge_embed_cm=border*.15))

    def lever(d, side):
        # Rosette on the latch side; grip points back towards the hinge.
        sign=-side
        pivot=sign*3.5
        cylinder((pivot,.8,0),(pivot,1.5,0),1.5,'Chrome',48)
        path=[(pivot,1.10,0),(pivot,.25,0),(pivot-sign*.12,-.35,0),
              (pivot-sign*.55,-.6,0),(pivot-sign*1.0,-.6,0),(-sign*5.0,-.6,0)]
        swept(path,.9,'Chrome',32)
        features.append(dict(name='Latch rosette and curved lever', rosette_diameter_cm=3, lever_radius_cm=.9, rosette_side=sign))

    def pull(d):
        for z in (-10.5,10.5):
            cylinder((0,.8,z),(0,1.5,z),1.5,'Chrome',48)
        path=[(0,1.10,-10.5),(0,.15,-10.5),(0,-.45,-10.20),(0,-.60,-9.55),
              (0,-.60,9.55),(0,-.45,10.20),(0,.15,10.5),(0,1.10,10.5)]
        swept(path,.9,'Chrome',32)
        features.append(dict(name='Two mounting rosettes and curved continuous pull', rosette_diameter_cm=3, grip_radius_cm=.9))

    def post(d):
        w,dep,h=d
        # Actual square steel post with a welded top collar, rather than a flat cube.
        box((0,0,-.18),(w-.8,dep-.8,h-.36),'PaintedMetal',.35)
        box((0,0,h/2-.55),(w,dep,1.1),'PaintedMetal',.18)
        box((0,0,-h/2+.22),(w-.25,dep-.25,.44),'DarkMetal',.13)
        features.append(dict(name='Rounded square steel post, welded cap and foot sleeve', post_corner_radius_cm=.35))

    def plate(d):
        w,dep,h=d
        box((0,0,-.20),(w,dep,h-.4),'DarkMetal',.22)
        for x in (-2.55,2.55):
            for y in (-2.55,2.55):
                cylinder((x,y,.10),(x,y,h/2),.55,'Chrome',8)
                # Recessed screw slot is made from two separated halves of the cap.
        features.append(dict(name='Rounded anchor plate with four octagonal bolts', bolt_diameter_cm=1.1, bolt_centres_cm=[[-2.55,-2.55],[-2.55,2.55],[2.55,-2.55],[2.55,2.55]]))

    def pipe(d):
        radius=d[0]/2
        assert abs(d[0]-d[1])<1e-4
        length=d[2]
        sides=64
        rows=[(-length/2,radius-.22),(-length/2+.12,radius-.05),(-length/2+.35,radius),
              (length/2-.35,radius),(length/2-.12,radius-.05),(length/2,radius-.22)]
        verts=[(r*math.cos(j*math.tau/sides),r*math.sin(j*math.tau/sides),z) for z,r in rows for j in range(sides)]
        faces=[tuple(reversed(range(sides))),tuple((len(rows)-1)*sides+j for j in range(sides))]
        for i in range(len(rows)-1):
            faces.extend((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for j in range(sides))
        mesh(verts,faces,'PaintedMetal',smooth=True)
        features.append(dict(name='64-sided steel handrail with rolled capped ends', radius_cm=radius, length_cm=length, original_endpoints_preserved=True))

    def tread(d, orientation):
        # Keep the entire walking height. Recessed inserts occupy disjoint top faces.
        walk=0 if orientation[0]=='X' else 1
        cross=1-walk
        direction=-1 if orientation[1]=='N' else 1
        depth=d[walk]
        xs=sorted(set([-depth/2,depth/2]+[direction*(depth/2-dist) for dist in (2.2,2.8,4.3,4.9,6.4,7.0)]))
        stripes=[sorted((direction*(depth/2-a),direction*(depth/2-b))) for a,b in ((2.2,2.8),(4.3,4.9),(6.4,7.0))]
        tops=[]
        for i in range(len(xs)-1):
            mid=(xs[i]+xs[i+1])/2
            tops.append(d[2]/2-.14 if any(a<mid<b for a,b in stripes) else d[2]/2)
        # A single extruded stone solid, with real recesses in its top profile.
        # Adjacent stone strips would leave coincident internal partition faces.
        profile=[(-depth/2,-d[2]/2),(depth/2,-d[2]/2),(depth/2,d[2]/2-.20),
                 (depth/2-.20,d[2]/2)]
        for i in range(len(tops)-1,-1,-1):
            left=xs[i]
            if i==0:
                left += .20
            profile.append((left,tops[i]))
            if i>0 and tops[i-1]!=tops[i]:
                profile.append((left,tops[i-1]))
        profile.extend(((-depth/2,d[2]/2-.20),))
        # Axis X or Y extrusion leaves profile [walk,Z] in both cases.
        extrusion(profile,cross,d[cross],'Stone',0)
        for a,b in stripes:
            center=[0,0,d[2]/2-.07]
            size=[d[0]-.08,d[1]-.08,.14]
            center[walk]=(a+b)/2
            size[walk]=b-a-.03
            box(center,size,'Rubber',.015)
        features.append(dict(name='Three recessed non-slip nosing inserts', front_orientation=orientation, insert_depth_cm=.14, front_strips_cm=stripes))

    def fluorescent(d):
        w,length,h=d
        # Centred physical source bounds: Z[-4.5,+4.5], source pivot remains Z5.5.
        box((0,0,h/2-1.0),(w,length,2.0),'PaintedMetal',.20)
        for x in (-w/2+1.0,w/2-1.0):
            box((x,0,.45),(1.3,length-7,4.0),'PaintedMetal',.16)
        for sign in (-1,1):
            box((0,sign*(length/2-2.0),-.75),(w,4,7.5),'PaintedMetal',.18)
            for x in (-4,4):
                box((x,sign*(length/2-4),-1.65),(3.6,3,3.6),'Ceramic',.22)
        for x in (-4,4):
            cylinder((x,-length/2+5,-1.5),(x,length/2-5,-1.5),1.45,'Ceramic',48)
            for sign in (-1,1):
                cylinder((x,sign*(length/2-5),-1.5),(x,sign*(length/2-6),-1.5),1.49,'Chrome',48)
        features.append(dict(name='Pressed luminaire housing, twin tubes, ceramic lamp holders and terminal bands', tube_diameter_cm=2.9, tube_separation_cm=8))

    collection=bpy.data.collections.new('MeasuredHotelArchitecture')
    bpy.context.scene.collection.children.link(collection)
    for variant in manifest['variants']:
        d=variant['world_dimensions_cm']
        kind=variant['kind']
        features.clear()
        if kind in ('SwingLeaf','SlidingLeaf','ElevatorLeaf'):
            paneled_leaf(d,'Wood' if kind=='SwingLeaf' else 'DarkMetal' if kind=='ElevatorLeaf' else 'PaintedWood')
        elif kind=='EntranceLeaf':
            h=variant['metadata']['opening_height_cm']
            hole_w=d[0]-12.8
            hole_h=h*.6-.8
            ring(d[0],d[2],d[1],hole_w,hole_h,h*.1,'PaintedMetal',.12)
            features.append(dict(name='Real entrance glazing aperture', aperture_width_cm=hole_w, aperture_height_cm=hole_h, aperture_center_z_cm=h*.1, glass_edge_embed_cm=.4))
            start=len(current_parts)
            glazing((d[0]-12,.8,h*.6),True)
            for part in current_parts[start:]:
                for v in part.data.vertices:
                    v.co.z += h*.1
        elif kind in ('DoorJambLeft','DoorJambRight','DoorHeader','WindowJambLeft','WindowJambRight','WindowHeader','WindowSill','WindowMeetingRail','WindowHorizontalRail'):
            frame(d,kind)
        elif kind in ('WindowGlazing','EntranceGlazing'):
            glazing(d,kind=='EntranceGlazing')
        elif kind=='LeverHandle':
            lever(d,variant['orientation'])
        elif kind=='PullHandle':
            pull(d)
        elif kind=='StairPost':
            post(d)
        elif kind=='StairBaseplate':
            plate(d)
        elif kind=='HandrailPipe':
            pipe(d)
        elif kind=='StairTread':
            tread(d,variant['orientation'])
        elif kind=='FluorescentHousing':
            fluorescent(d)
        else:
            raise ValueError(kind)

        vertices,faces,face_roles,corner_normals,face_axes=[],[],[],[],[]
        scale=variant['component_scale']
        bounds=variant['source_local_bounds_cm']
        center=[(bounds[0][i]+bounds[1][i])/2 for i in range(3)]
        part_reports=[]
        for part in current_parts:
            bm=bmesh.new()
            bm.from_mesh(part.data)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            boundary=sum(not e.is_manifold for e in bm.edges)
            degenerate=sum(f.calc_area()<=1e-9 for f in bm.faces)
            volume=bm.calc_volume(signed=True)
            assert boundary==0 and degenerate==0 and volume>0,(variant['key'],part.name,boundary,degenerate,volume)
            bm.to_mesh(part.data)
            bm.free()
            part.data.calc_loop_triangles()
            offset=len(vertices)
            vertices.extend(tuple(v.co) for v in part.data.vertices)
            part_reports.append(dict(name=part.name,role=part.data.materials[0].name,vertices=len(part.data.vertices),triangles=len(part.data.loop_triangles),closed=True,signed_volume_cm3=volume))
            for tri in part.data.loop_triangles:
                faces.append(tuple(offset+i for i in tri.vertices))
                face_roles.append(part.data.materials[tri.material_index].name)
                # Both triangles of a planar bevel quad share one projection.
                # Choosing separately from float triangle normals at 45 degrees
                # can rotate UV axes across its diagonal and cancel Mikk tangents.
                pn=part.data.polygons[tri.polygon_index].normal
                dominant=max(range(3),key=lambda i:round(abs(pn[i]),4))
                face_axes.append([i for i in range(3) if i!=dominant])
                for li in tri.loops:
                    normal=part.data.corner_normals[li].vector
                    normal=Vector(tuple(normal[i]*scale[i] for i in range(3))).normalized()
                    corner_normals.append(tuple(normal))
        physical=vertices
        measured=[[min(v[i] for v in physical) for i in range(3)],[max(v[i] for v in physical) for i in range(3)]]
        expected=[[-v/2 for v in d],[v/2 for v in d]]
        error=max(abs(measured[j][i]-expected[j][i]) for i in range(3) for j in range(2))
        assert error<.003,(variant['key'],'physical envelope mismatch',measured,expected,error)
        local=[tuple(v[i]/scale[i]+center[i] for i in range(3)) for v in physical]
        data=bpy.data.meshes.new(variant['mesh_name'])
        data.from_pydata([tuple(c/100 for c in v) for v in local],[],faces)
        data.update()
        used=[r for r in ROLES if r in face_roles]
        for r in used:
            data.materials.append(mats[r])
        layer=data.uv_layers.new(name='RealScaleUV')
        for poly,role,axes in zip(data.polygons,face_roles,face_axes):
            poly.material_index=used.index(role)
            poly.use_smooth=True
            for li,vi in zip(poly.loop_indices,poly.vertices):
                layer.data[li].uv=(physical[vi][axes[0]]/100,physical[vi][axes[1]]/100)
        data.normals_split_custom_set(corner_normals)
        data.update()
        data.calc_tangents(uvmap='RealScaleUV')
        bad_tangents=sum(not all(math.isfinite(c) for c in loop.tangent) or loop.tangent.length<.9 for loop in data.loops)
        if bad_tangents:
            write(OUT/'TangentDebug.json',dict(key=variant['key'],faces=[dict(vertices=[list(data.vertices[i].co) for i in poly.vertices],
                uv=[list(layer.data[i].uv) for i in poly.loop_indices],normals=[list(data.corner_normals[i].vector) for i in poly.loop_indices],
                tangents=[list(data.loops[i].tangent) for i in poly.loop_indices]) for poly in data.polygons
                if any(data.loops[i].tangent.length<.9 for i in poly.loop_indices)]))
        assert bad_tangents==0,(variant['key'],'tangent failure',bad_tangents)
        obj=bpy.data.objects.new(variant['mesh_name'],data)
        collection.objects.link(obj)
        for old in current_parts:
            olddata=old.data
            bpy.data.objects.remove(old,do_unlink=True)
            if not olddata.users:
                bpy.data.meshes.remove(olddata)
        current_parts.clear()
        actual_bounds=[[min(v.co[i]*100 for v in data.vertices) for i in range(3)],[max(v.co[i]*100 for v in data.vertices) for i in range(3)]]
        source_error=max(abs(actual_bounds[j][i]-bounds[j][i]) for i in range(3) for j in range(2))
        assert source_error<.005,(variant['key'],'source local bounds changed',source_error)
        data.calc_loop_triangles()
        recipe_file=OUT/(variant['mesh_name']+'.geometry.json')
        recipe=dict(schema='OldTownRealismArchitectureMeshRecipeV1',key=variant['key'],source_asset=variant['source_asset'],
                    vertices_cm=[list(v.co*100) for v in data.vertices],triangles=[list(t.vertices) for t in data.loop_triangles],
                    material_indices=[t.material_index for t in data.loop_triangles],material_roles=used,
                    triangle_corner_normals=[[list(data.corner_normals[i].vector) for i in t.loops] for t in data.loop_triangles],
                    triangle_corner_uv0=[[list(layer.data[i].uv) for i in t.loops] for t in data.loop_triangles],
                    prescribed_features=list(features),closed_parts=part_reports)
        write(recipe_file,recipe)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        fbx=OUT/variant['fbx_file']
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,global_scale=1,
            apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',
            use_space_transform=True,bake_space_transform=False,object_types={'MESH'},use_mesh_modifiers=True,
            mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,bake_anim=False,path_mode='AUTO')
        variant.update(local_bounds_cm=actual_bounds,physical_mesh_bounds_cm=measured,
            maximum_source_bounds_error_cm=source_error,vertices=len(data.vertices),triangles=len(data.loop_triangles),
            material_roles=used,material_slots=used,prescribed_features=list(features),closed_parts=part_reports,
            closed_manifold=True,boundary_or_nonmanifold_edges=0,degenerate_faces=0,tangent_space_verified=True,
            geometry_recipe_file=str(recipe_file),geometry_recipe_sha256=sha(recipe_file),
            uv_mapping='Physical centimetre dominant-plane UVs /100: one UV unit per metre',
            source_file_sha256=sha(fbx),fbx_path=str(fbx))
        obj.hide_set(True)
        obj.hide_render=True
        print('ARCHITECTURE_VARIANT',variant['key'],len(data.vertices),len(data.loop_triangles),flush=True)
        write(OUT/'ModelDataManifest.json',manifest)
    blend=OUT/'OldTownRealArchitecture.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    manifest.update(status='COMPLETE',blend_file=str(blend),blend_sha256=sha(blend),source_script_sha256=sha(__file__),
        total_variant_vertices=sum(v['vertices'] for v in manifest['variants']),
        total_variant_triangles=sum(v['triangles'] for v in manifest['variants']),
        total_instanced_triangles=sum(v['triangles']*v['instance_count'] for v in manifest['variants']),
        closed_meshes_verified=True,no_original_files_modified=True)
    write(OUT/'ModelDataManifest.json',manifest)
    print('ARCHITECTURE_COMPLETE',manifest['variant_count'],manifest['component_count'],flush=True)


def render_previews(manifest):
    """Assemble exact source component poses for visible geometry inspection."""
    import bpy
    from mathutils import Vector, Quaternion
    bpy.ops.wm.open_mainfile(filepath=manifest['blend_file'])
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=32
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1200
    scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.11,.12,.10,1)
    bg.inputs['Strength'].default_value=.35
    scene.view_settings.view_transform='AgX'
    for original in bpy.data.objects:
        original.hide_set(True)
        original.hide_render=True
    bpy.ops.mesh.primitive_plane_add(size=16,location=(0,0,-.02))
    ground=bpy.context.object
    ground.name='ArchitectureReviewGround'
    mat=bpy.data.materials.new('ArchitectureReviewGround')
    mat.diffuse_color=(.14,.14,.13,1)
    ground.data.materials.append(mat)
    for name,location,power,size in (('Key',(-4,-5,6),1100,4),('Fill',(5,-1,4),700,3),('Rim',(1,4,5),1000,3)):
        data=bpy.data.lights.new('Review'+name,'AREA')
        data.energy=power
        data.size=size
        obj=bpy.data.objects.new(data.name,data)
        scene.collection.objects.link(obj)
        obj.location=location
        obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('ArchitectureReviewCamera')
    cam=bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=52
    variants={v['key']:v for v in manifest['variants']}
    inventory=load(INPUT)
    rows=manifest['actors']
    displayed=[]

    def assembly(actor,center=(0,0,0),yaw_correction=None):
        members=[r for r in rows if r['actor']==actor]
        assert members,actor
        actual=inventory['component_records'][actor]
        root=next((c for c in actual if c['name']=='OpeningRoot'),None)
        origin=root['world_pose']['translation'] if root else members[0]['original_component']['world_pose']['translation']
        rot=Quaternion((1,0,0,0))
        if yaw_correction is not None:
            rot=Quaternion((0,0,1),yaw_correction)
        else:
            q=root['world_pose']['rotation_quaternion_xyzw'] if root else [0,0,0,1]
            rot=Quaternion((q[3],q[0],q[1],q[2])).inverted()
        for r in members:
            v=variants[r['key']]
            obj=bpy.data.objects[v['mesh_name']].copy()
            scene.collection.objects.link(obj)
            obj.hide_set(False)
            obj.hide_render=False
            pose=r['original_component']['world_pose']
            q=pose['rotation_quaternion_xyzw']
            obj.rotation_mode='QUATERNION'
            obj.rotation_quaternion=rot @ Quaternion((q[3],q[0],q[1],q[2]))
            obj.location=rot @ (Vector(pose['translation'])-Vector(origin))/100+Vector(center)
            obj.scale=pose['scale']
            displayed.append(obj)

    def single(kind,center=(0,0,0),orientation=None):
        v=next(v for v in manifest['variants'] if v['kind']==kind and (orientation is None or v['orientation']==orientation))
        obj=bpy.data.objects[v['mesh_name']].copy()
        scene.collection.objects.link(obj)
        obj.hide_set(False)
        obj.hide_render=False
        obj.location=center
        obj.scale=v['component_scale']
        displayed.append(obj)
        return obj,v

    def clear():
        for obj in displayed:
            bpy.data.objects.remove(obj,do_unlink=True)
        displayed.clear()

    def render(name,pos,target):
        cam.location=pos
        cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
        path=OUT/name
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        return str(path)

    door=next(r['actor'] for r in inventory['layout_manifest']['doors'] if r['id']=='Room201Entry') if any(r['id']=='Room201Entry' for r in inventory['layout_manifest']['doors']) else next(r['actor'] for r in rows if r['kind']=='SwingLeaf')
    assembly(door,(-1.45,0,0))
    window=next(r['actor'] for r in inventory['layout_manifest']['windows'] if r.get('kind')!='stair')
    assembly(window,(1.15,0,.40))
    first=render('Preview_DoorWindowGeometry.png',(-3.8,-6.6,3.3),(0,.2,1.1))
    clear()
    entrance=next(r['actor'] for r in inventory['layout_manifest']['doors'] if r['id']=='MainEntry')
    assembly(entrance)
    second=render('Preview_EntranceGlazing.png',(-3.3,-6.2,3.2),(0,.1,1.15))
    clear()
    # Source physical stairs: eleven consecutive treads, posts and plates of one flight.
    selected=[r for r in rows if r['actor'].startswith('OTS_HotelV4_South_F0_First') and r['kind'] in ('StairTread','StairPost','StairBaseplate')]
    if not selected:
        selected=[r for r in rows if r['actor'].startswith('OTS_HotelV4_South_F0_') and r['kind'] in ('StairTread','StairPost','StairBaseplate')]
    origin=[min(r['original_component']['world_render_bounds_before_wpo_cm'][0][i] for r in selected) for i in range(3)]
    for r in selected:
        v=variants[r['key']]
        obj=bpy.data.objects[v['mesh_name']].copy()
        scene.collection.objects.link(obj)
        obj.hide_set(False)
        obj.hide_render=False
        pose=r['original_component']['world_pose']
        q=pose['rotation_quaternion_xyzw']
        obj.rotation_mode='QUATERNION'
        obj.rotation_quaternion=Quaternion((q[3],q[0],q[1],q[2]))
        obj.location=(Vector(pose['translation'])-Vector(origin))/100
        obj.scale=pose['scale']
        displayed.append(obj)
    third=render('Preview_StairStoneAndPosts.png',(-4.2,-4.8,4.1),(.8,1.1,.8))
    clear()
    lamp,v=single('FluorescentHousing',(0,0,.4))
    # Tilt the actual fixture so its underside faces the review camera.
    lamp.rotation_euler.x=math.radians(150)
    fourth=render('Preview_LuminaireConstruction.png',(1.4,-1.9,1.2),(0,0,.4))
    manifest['source_geometry_previews']=[first,second,third,fourth]
    manifest['preview_note']='Measured physical source assemblies under neutral role materials. Unreal supplies authored PBR materials and preserved surface offsets.'
    manifest['source_script_sha256']=sha(__file__)
    write(OUT/'ModelDataManifest.json',manifest)
    print('ARCHITECTURE_PREVIEWS_COMPLETE',flush=True)


if __name__=='__main__':
    if '--preview-only' in sys.argv:
        render_previews(load(OUT/'ModelDataManifest.json'))
    else:
        data,rows=source_rows()
        manifest=early_manifest(data,rows)
        print('ARCHITECTURE_MANIFEST',manifest['variant_count'],manifest['component_count'],manifest['kinds'],flush=True)
        if '--manifest-only' not in sys.argv:
            blender_build(manifest)
