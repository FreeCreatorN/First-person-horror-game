"""Author four sanitary mesh replacements from current saved native RenderData.

Run Blender --background --factory-startup --python this script. No Unreal
runtime, asset import, map mutation, or original source-art writes occur here.
All geometry calculations use centimetres; Blender vertices are cm/100 metres.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
NATIVE = ROOT/'Saved/CodexOutputs/OldTownRealism_20261012/NativeMeshes'
OUT = ROOT/'SourceArt/OldTownRealism_20261012/Sanitary'
ROLES = ('Ceramic', 'Chrome', 'DarkMetal', 'Glass', 'Rubber')
PARTS = []
AUDITS = []
N = 128


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def bounds(vertices):
    return [[min(p[j] for p in vertices) for j in range(3)],
            [max(p[j] for p in vertices) for j in range(3)]]


def sources():
    build, snapshot = read(SOURCE/'BuildReport.json'), read(SOURCE/'AfterSnapshot.json')
    assert build['map_sha256'] == snapshot['source_map_sha256']
    prefixes = ('SM_OTS_Arch_Toilet_', 'SM_OTS_Arch_Washbasin_',
                'SM_OTS_Arch_ShowerTray_', 'SM_OTS_Arch_ShowerScreen_')
    native = [dict(read(p), geometry_file=str(p), geometry_sha256=sha(p))
              for p in NATIVE.glob('*.json') if p.name.startswith(prefixes)]
    by = {p['asset']: p for p in native}
    rows = []
    for key, count in (('Toilet', 30), ('Washbasin', 30), ('ShowerTray', 27), ('ShowerScreen', 27)):
        members = [r for r in build['hotel_v4']['placed_props'] if r.get('asset_key') == key]
        assert len(members) == count, (key, len(members))
        meshes = {snapshot['actors'][r['actor']]['components'][0]['mesh'] for r in members}
        assert len(meshes) == 1, (key, meshes)
        asset = next(iter(meshes))
        if asset not in by:
            raise FileNotFoundError('Current native source has not been exported: '+asset)
        data = by[asset]
        points = [p for s in data['sections'] for p in s['vertices_cm']]
        source_file = ROOT/('Content/'+asset.split('.')[0][6:]+'.uasset')
        rows.append(dict(key=key, source_asset=asset, source_file=str(source_file),
                         source_sha256=sha(source_file), native=data,
                         source_local_bounds_cm=bounds(points),
                         source_actor_labels=[r['actor'] for r in members],
                         source_actor_count=count,
                         source_triangle_count=sum(s['triangle_count'] for s in data['sections']),
                         source_poses={r['actor']: snapshot['actors'][r['actor']] for r in members}))
    return rows, build['map_sha256']


def main():
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    rows, map_sha = sources()
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.
    colors = dict(Ceramic=(.56,.535,.47,1), Chrome=(.42,.435,.44,1),
                  DarkMetal=(.065,.06,.055,1), Glass=(.29,.35,.33,1), Rubber=(.025,.028,.025,1))
    materials = {}
    for role in ROLES:
        mat = bpy.data.materials.new(role)
        mat.diffuse_color = colors[role]
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = colors[role]
        bsdf.inputs['Metallic'].default_value = .95 if role == 'Chrome' else .7 if role == 'DarkMetal' else 0.
        bsdf.inputs['Roughness'].default_value = .25 if role == 'Ceramic' else .22 if role == 'Chrome' else .65
        if role == 'Glass':
            bsdf.inputs['Transmission Weight'].default_value = .7
            bsdf.inputs['IOR'].default_value = 1.45
            bsdf.inputs['Roughness'].default_value = .28
        materials[role] = mat

    objects_by_name = {}

    def mesh(name, vertices_cm, faces, role, smooth=True, bevel_cm=0., source_retained=False):
        data = bpy.data.meshes.new(name)
        data.from_pydata([[v/100 for v in p] for p in vertices_cm], [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        data.materials.append(materials[role])
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bm = bmesh.new()
        bm.from_mesh(data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1.e-7)
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(data)
        bm.free()
        if bevel_cm:
            mod = obj.modifiers.new('Fine physical edge radius', 'BEVEL')
            mod.width = bevel_cm/100
            mod.segments = 3
            mod.limit_method = 'ANGLE'
            mod.angle_limit = math.radians(50)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            data = obj.data
        for polygon in data.polygons:
            polygon.use_smooth = smooth
        # Rounded pieces retain continuous normals; sharp caps stay sharp.
        bm = bmesh.new()
        bm.from_mesh(data)
        for edge in bm.edges:
            if edge.is_manifold:
                edge.smooth = edge.calc_face_angle() < math.radians(45)
        bm.to_mesh(data)
        bm.free()
        obj.select_set(False)
        PARTS.append(dict(name=name, role=role, source_retained=source_retained, object=obj))
        objects_by_name[name] = obj
        return obj

    def box(name, center, size, role, bevel=.15):
        h = [x/2 for x in size]
        vv = [[center[0]+sx*h[0],center[1]+sy*h[1],center[2]+sz*h[2]]
              for sz in (-1,1) for sy,sx in ((-1,-1),(-1,1),(1,1),(1,-1))]
        ff = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        return mesh(name,vv,ff,role,False,bevel)

    def cylinder(name, center, radius, length, role, axis='Z', bevel=.04, n=64):
        vv = []
        for axial in (-length/2,length/2):
            for i in range(n):
                a = 2*math.pi*i/n
                x,y,z = radius*math.cos(a),radius*math.sin(a),axial
                p = [z,y,-x] if axis == 'X' else [x,z,-y] if axis == 'Y' else [x,y,z]
                vv.append([center[j]+p[j] for j in range(3)])
        ff = []
        for i in range(n):
            j=(i+1)%n
            ff.append((i,j,j+n,i+n))
        ff += [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        return mesh(name,vv,ff,role,True,bevel)

    def profile_solid(name, rings, role, closed_loop=True, smooth=True):
        n=len(rings[0]); vv=[p for ring in rings for p in ring]; ff=[]
        last=len(rings) if closed_loop else len(rings)-1
        for k in range(last):
            a,b=k*n,((k+1)%len(rings))*n
            for i in range(n):
                j=(i+1)%n
                ff.append((a+i,a+j,b+j,b+i))
        if not closed_loop:
            ff += [tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
        return mesh(name,vv,ff,role,smooth)

    def ellipse(z,rx,ry,cx=0.,cy=0.,power=2.,n=N):
        result=[]
        for i in range(n):
            a=2*math.pi*i/n;c,s=math.cos(a),math.sin(a)
            result.append([cx+rx*math.copysign(abs(c)**(2/power),c),
                           cy+ry*math.copysign(abs(s)**(2/power),s),z])
        return result

    def annular_tube(name, center_xy, zlo,zhi,outer,inner,role):
        cx,cy=center_xy
        return profile_solid(name,[ellipse(zlo,outer,outer,cx,cy),ellipse(zhi,outer,outer,cx,cy),
                                  ellipse(zhi,inner,inner,cx,cy),ellipse(zlo,inner,inner,cx,cy)],role)

    def sweep_tube(name,path,outer,inner,role,n=48):
        # These pipes lie in X/Z; global Y is a stable cross-section direction.
        rings_outer,rings_inner=[],[]
        for k,p in enumerate(path):
            a=Vector(path[max(0,k-1)]);b=Vector(path[min(len(path)-1,k+1)])
            tangent=(b-a).normalized();u=Vector((tangent.z,0,-tangent.x));v=Vector((0,1,0))
            for radius,rings in ((outer,rings_outer),(inner,rings_inner)):
                rings.append([[p[j]+radius*(u[j]*math.cos(2*math.pi*i/n)+v[j]*math.sin(2*math.pi*i/n))
                               for j in range(3)] for i in range(n)])
        # Outer path then inner path backwards form one watertight tube wall.
        return profile_solid(name,rings_outer+list(reversed(rings_inner)),role)

    def import_native(row, section_filter=None, excluded_bounds=None, prefix=None, bevel=0.):
        made=[]
        for section in row['native']['sections']:
            if section_filter is not None and not section_filter(section):
                continue
            vertices = section['vertices_cm']
            triples=[section['triangle_indices'][i:i+3] for i in range(0,len(section['triangle_indices']),3)]
            normals=section['normals']
            if excluded_bounds:
                # Identify complete position-welded source islands by their
                # exact current native bounds, never face centroid regions.
                ids={};weld=[]
                for p in vertices:
                    key=tuple(round(x,5) for x in p)
                    if key not in ids:ids[key]=len(ids)
                    weld.append(ids[key])
                parents=list(range(len(ids)))
                def find(i):
                    while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
                    return i
                for t in triples:
                    for i in t[1:]:parents[find(weld[i])]=find(weld[t[0]])
                groups={}
                for ti,t in enumerate(triples):groups.setdefault(find(weld[t[0]]),[]).append(ti)
                removed=set()
                for target in excluded_bounds:
                    matches=[]
                    for ts in groups.values():
                        pts=[vertices[i] for ti in ts for i in triples[ti]]
                        if all(abs(a-b)<.005 for aa,bb in zip(bounds(pts),target) for a,b in zip(aa,bb)):
                            matches.append(ts)
                    assert len(matches)==1, ('native complete island missing',row['key'],target,len(matches))
                    removed.update(matches[0])
                triples=[t for ti,t in enumerate(triples) if ti not in removed]
            fixed=[]
            for t in triples:
                a,b,c=[Vector(vertices[i]) for i in t]
                ns=sum((Vector(normals[i]) for i in t),Vector((0,0,0)))
                fixed.append(tuple(reversed(t)) if (b-a).cross(c-a).dot(ns)<0 else tuple(t))
            role = 'Glass' if 'Glass' in section['default_material'] else 'Ceramic' if 'Ceramic' in section['default_material'] else 'DarkMetal'
            made.append(mesh((prefix or row['key'])+'_RetainedSection%d'%section['section_index'],
                             vertices,fixed,role,True,bevel,True))
        return made

    def inside(obj, point_cm):
        vv=[v.co*100 for v in obj.data.vertices]
        obj.data.calc_loop_triangles()
        total=0.; point=Vector(point_cm)
        for tri in obj.data.loop_triangles:
            a,b,c=[vv[i]-point for i in tri.vertices]
            la,lb,lc=a.length,b.length,c.length
            if min(la,lb,lc)<1.e-8:return True
            total+=2*math.atan2(a.dot(b.cross(c)),la*lb*lc+a.dot(b)*lc+b.dot(c)*la+c.dot(a)*lb)
        return abs(total)>2*math.pi

    def join_check(name,point,a,b):
        tests={n:inside(objects_by_name[n],point) for n in (a,b)}
        AUDITS.append(dict(name=name,passed=all(tests.values()),point_cm=point,inside_parts=tests))

    def authored_topology(obj):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1.e-7)
        closed=all(e.is_manifold for e in bm.edges)
        bm.free()
        return closed

    def uv_physical(obj):
        data=obj.data
        uv=data.uv_layers.get('UVPhysicalMetres') or data.uv_layers.new(name='UVPhysicalMetres')
        for poly in data.polygons:
            normal=poly.normal
            drop=max(range(3),key=lambda j:abs(normal[j]));axes=[j for j in range(3) if j!=drop]
            for li in poly.loop_indices:
                p=data.vertices[data.loops[li].vertex_index].co
                uv.data[li].uv=(p[axes[0]],p[axes[1]])
        data.uv_layers.active=uv

    variants=[]
    for row in rows:
        PARTS.clear();AUDITS.clear();objects_by_name.clear()
        key=row['key']; source_box=row['source_local_bounds_cm']
        if key=='Toilet':
            # Keep current hollow bowl, rounded tank, seat and support forms.
            import_native(row,lambda s:'Ceramic' in s['default_material'],bevel=.10)
            for sign in (-1,1):
                y=sign*6.
                box('SeatHingeMount_%s'%sign,[13.,y,41.3],[3.,3.,1.], 'Chrome',.12)
                cylinder('SeatHingeBarrel_%s'%sign,[12.2,y,42.0],.75,2.6,'Chrome','Y')
                cylinder('SeatHingePin_%s'%sign,[12.2,y,42.0],.3,3.,'DarkMetal','Y',.025)
                join_check('SeatMountIntoExistingSeat_%s'%sign,[12.,y,41.5],
                           'SeatHingeMount_%s'%sign,'Toilet_RetainedSection0')
                join_check('SeatMountIntoExistingShoulder_%s'%sign,[13.5,y,41.0],
                           'SeatHingeMount_%s'%sign,'Toilet_RetainedSection0')
                join_check('SeatBarrelIntoMount_%s'%sign,[12.2,y,41.6],
                           'SeatHingeMount_%s'%sign,'SeatHingeBarrel_%s'%sign)
            cylinder('FlushLeverWallBoss',[33.15,0.,68.],1.1,1.2,'Chrome','X',.08)
            cylinder('FlushLeverSpindle',[33.8,0.,68.],.48,1.3,'Chrome','X')
            cylinder('FlushLeverGrip',[34.0,2.0,68.],.48,5.0,'Chrome','Y',.12)
            join_check('FlushBossIntoTank',[32.7,0.,68.],'FlushLeverWallBoss','Toilet_RetainedSection0')
            join_check('FlushSpindleIntoBoss',[33.65,0.,68.],'FlushLeverWallBoss','FlushLeverSpindle')
            join_check('FlushGripIntoSpindle',[34.0,0.,68.],'FlushLeverGrip','FlushLeverSpindle')
            notes=['Current hollow bowl, rounded cistern, ceramic seat and ceramic support positions retained.',
                   'Source flat disconnected metal lever replaced by an attached outside boss, spindle and grip.',
                   'Fine 1 mm ceramic edge treatment; source curved profiles keep their existing positions.']
        elif key=='Washbasin':
            # Keep the measured tap, rounded spout and valve. The source thick
            # support is not attached to a wall: the actual basin sits 9 cm
            # from its nearest side wall. Replace it with a real floor frame;
            # the separate outlet stack remains exclusively a drain.
            stem_box=[[9.5,-2.5,0.],[14.5,2.5,73.3]]
            mounting_beam_box=[[11.,-25.,69.],[21.,25.,75.]]
            import_native(row,lambda s:'Ceramic' not in s['default_material'],
                          [stem_box,mounting_beam_box],bevel=.035)
            # A single closed porcelain shell, including its open drain throat.
            # The displaced opening leaves a genuine rear faucet deck at x16.
            profiles=[(73.,17.6,23.2,0.,2.6),(73.4,18.,23.8,0.,2.7),
                      (75.,19.1,25.6,0.,2.8),(78.,20.6,28.0,0.,3.),
                      (81.6,22.,29.65,0.,3.3),(83.9,22.5,30.,0.,3.5),
                      (84.6,22.35,29.85,0.,3.5),(85.,22.0,29.5,0.,3.5),
                      (84.3,15.,25.2,-5.5,2.5),(83.5,14.6,24.5,-5.5,2.5),
                      (81.,13.,21.5,-4.7,2.5),(78.5,9.5,15.4,-3.3,2.3),
                      (77.,5.8,8.4,-1.2,2.1),(76.2,1.9,1.9,0.,2.),
                      (73.,1.9,1.9,0.,2.)]
            profile_solid('ContinuousPorcelainBasin',
                          [ellipse(z,rx,ry,cx,0.,power) for z,rx,ry,cx,power in profiles],'Ceramic')
            # Two slim cantilever arms, tied at the rear, carry the basin.
            # Their steel legs have distinct floor pads with anchor heads.
            # Every member stays within the existing 45 x 60 cm envelope.
            box('BasinRearTie',[20.4,0.,73.8],[1.4,50.,2.0],'DarkMetal',.08)
            for side in (-1,1):
                y=side*18.
                arm='BasinSupportArm_%s'%side
                leg='BasinSupportLeg_%s'%side
                foot='BasinSupportFoot_%s'%side
                box(arm,[16.,y,73.1],[10.,1.4,1.4],'DarkMetal',.08)
                box(leg,[20.3,y,36.8],[1.5,1.5,73.0],'DarkMetal',.09)
                box(foot,[20.,y,.35],[5.,4.,.7],'DarkMetal',.08)
                join_check('ArmIntoPorcelain_%s'%side,[12.,y,73.5],
                           arm,'ContinuousPorcelainBasin')
                join_check('ArmIntoRearTie_%s'%side,[20.3,y,73.1],arm,'BasinRearTie')
                join_check('LegIntoArm_%s'%side,[20.3,y,73.1],leg,arm)
                join_check('LegIntoFoot_%s'%side,[20.3,y,.5],leg,foot)
                for x in (18.2,21.8):
                    bolt='BasinFloorAnchor_%s_%s'%(side,x)
                    cylinder(bolt,[x,y,.82],.25,.36,'Chrome','Z',.025,n=32)
                    join_check('AnchorIntoFoot_%s_%s'%(side,x),[x,y,.68],bolt,foot)
            annular_tube('BasinDrainFlange',[0.,0.],76.0,76.35,2.55,1.7,'Chrome')
            annular_tube('BasinDrainOutlet',[0.,0.],71.9,76.2,2.02,1.7,'Chrome')
            trap_path=[[0.,0.,74.2],[0.,0.,71.],[0.,0.,68.],[0.,0.,65.]]
            trap_path += [[6.+6.*math.cos(a),0.,65.+6.*math.sin(a)]
                          for a in [math.pi+(math.pi)*i/32 for i in range(1,33)]]
            sweep_tube('ConnectedPTrap',trap_path,1.9,1.6,'Chrome')
            annular_tube('ExistingFloorOutletStack',[12.,0.],0.,66.0,2.5,1.6,'DarkMetal')
            for z in (3.,54.5,65.):
                annular_tube('FloorStackCoupling_%s'%z,[12.,0.],z-.6,z+.6,2.75,2.3,'Chrome')
            join_check('DrainFlangeIntoPorcelain',[2.3,0.,76.1],
                       'BasinDrainFlange','ContinuousPorcelainBasin')
            join_check('DrainOutletIntoFlange',[1.9,0.,76.1],'BasinDrainFlange','BasinDrainOutlet')
            join_check('TrapIntoDrainOutlet',[1.8,0.,73.5],'BasinDrainOutlet','ConnectedPTrap')
            # At its return, the trap wall embeds into the stack wall, forming
            # a physical tee contact without a free pipe end or closed throat.
            join_check('TrapIntoFloorStack',[12.,1.8,64.8],'ConnectedPTrap','ExistingFloorOutletStack')
            join_check('ExistingFaucetStubIntoRearDeck',[16.,0.,81.0],
                       'Washbasin_RetainedSection0','ContinuousPorcelainBasin')
            notes=['Original local bounds, faucet location and rounded spout retained.',
                   'Porcelain is one continuous rounded shell with a real open bowl and through drain.',
                   'Thick unsupported source beam replaced by two narrow arms and floor legs with grounded pads.',
                   'Floor frame independently carries the basin; the hollow P trap and stack carry drainage only.',
                   'Open metal drain, hollow P trap, existing floor outlet position and coupling collars.',
                   'Drain cavity is not filled by a solid disc; source original floor stem island replaced.']
        elif key=='ShowerTray':
            # Ray-based nested rounded rectangles keep the offset drain hole
            # fully open, avoiding a triangulated fan across the drain cavity.
            cx,cy=32.,32.
            def sdf(x,y,hx,hy,r):
                qx,qy=abs(x)-hx+r,abs(y)-hy+r
                return math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-r
            def tray_ring(hx,hy,r,z):
                ring=[]
                for i in range(N):
                    a=2*math.pi*i/N;dx,dy=math.cos(a),math.sin(a);lo,hi=0.,180.
                    for unused in range(45):
                        t=(lo+hi)/2
                        if sdf(cx+dx*t,cy+dy*t,hx,hy,r)>0:hi=t
                        else:lo=t
                    t=(lo+hi)/2;x,y=cx+dx*t,cy+dy*t
                    height=z(x,y) if callable(z) else z
                    ring.append([x,y,height])
                return ring
            floor=lambda x,y:2.2+.011*math.hypot(x-cx,y-cy)
            rings=[tray_ring(44.7,44.7,1.4,0.),tray_ring(45.,45.,1.6,.3),
                   tray_ring(45.,45.,1.6,3.7),tray_ring(44.7,44.7,1.4,4.),
                   tray_ring(42.5,42.5,2.2,4.),tray_ring(41.8,41.8,2.3,3.65),
                   tray_ring(41.5,41.5,2.4,floor),ellipse(2.2,2.8,2.8,cx,cy),
                   ellipse(0.,2.8,2.8,cx,cy)]
            profile_solid('RoundedSlopingShowerTray',rings,'Ceramic')
            annular_tube('ShowerDrainFrame',[cx,cy],2.14,2.34,3.25,2.65,'Chrome')
            annular_tube('ShowerDrainThroat',[cx,cy],0.,2.28,2.75,2.45,'DarkMetal')
            for i,dy in enumerate((-2.,-1.2,-.4,.4,1.2,2.)):
                half=math.sqrt(2.8**2-dy**2)
                box('ShowerGrateBar_%02d'%i,[cx,cy+dy,2.26],[2*half+.2,.24,.16],'Chrome',.035)
                join_check('GrateBarJoinsFrame_%02d'%i,[cx+half,cy+dy,2.26],
                           'ShowerGrateBar_%02d'%i,'ShowerDrainFrame')
            join_check('DrainFrameIntoTray',[35.02,32.,2.19],
                       'ShowerDrainFrame','RoundedSlopingShowerTray')
            join_check('DrainThroatIntoFrame',[34.7,32.,2.2],'ShowerDrainThroat','ShowerDrainFrame')
            AUDITS.append(dict(name='AllFloorSamplesSlopeToCurrentDrain',
                passed=all(2.2<=p[2]<=3.65 for p in rings[6]),
                drain_position_cm=[cx,cy,2.2],maximum_floor_z_cm=max(p[2] for p in rings[6]),
                slope=0.011))
            notes=['Same 90x90x4 cm envelope and offset drain position as current saved fixture.',
                   'Rounded ceramic edge, recessed floor with 1.1 percent slope toward the drain.',
                   'Physical metal grate bars with open spaces and a hollow recessed metal throat.']
        else:
            import_native(row,lambda s:'Glass' in s['default_material'],bevel=.035)
            # One closed annular extrusion avoids the source frame's four
            # overlapping bars and their coincident faces at the corners.
            outer=[(-45.,0.),(45.,0.),(45.,200.),(-45.,200.)]
            inner=[(-44.,1.),(44.,1.),(44.,199.),(-44.,199.)]
            frame_vertices=[[x,y,z] for y in (-.5,.5) for ring in (outer,inner) for x,z in ring]
            frame_faces=[]
            for i in range(4):
                j=(i+1)%4
                frame_faces += [(i,j,j+8,i+8),(i+4,i+12,j+12,j+4),
                                (i,i+4,j+4,j),(i+8,j+8,j+12,i+12)]
            mesh('ContinuousShowerFrame',frame_vertices,frame_faces,'DarkMetal',False,.08)
            for side in (-1,1):
                x=side*43.9
                box('GlassSeal_%s'%side,[x,.31,100.],[.32,.18,197.8],'Rubber',.04)
                for z in (40.,160.):
                    box('GlassClamp_%s_%s'%(side,z),[side*43.70,0.,z],[2.5,2.0,4.0],'Chrome',.20)
                    join_check('ClampIntoGlass_%s_%s'%(side,z),[side*43.5,0.,z],
                               'GlassClamp_%s_%s'%(side,z),'ShowerScreen_RetainedSection0')
            for z in (1.15,198.85):
                box('HorizontalGlassSeal_%s'%z,[0.,.31,z],[87.8,.18,.4],'Rubber',.035)
            for z in (88.,112.):
                cylinder('ShowerHandleStandoff_%s'%z,[28.,1.25,z],.60,2.0,'Chrome','Y',.08)
                join_check('HandleMountIntoGlass_%s'%z,[28.,.28,z],
                           'ShowerHandleStandoff_%s'%z,'ShowerScreen_RetainedSection0')
            cylinder('ShowerHandleGrip',[28.,2.2,100.],.45,24.,'Chrome','Z',.10)
            for z in (88.,112.):
                join_check('HandleGripIntoStandoff_%s'%z,[28.,2.2,z+(.2 if z==88. else -.2)],
                           'ShowerHandleStandoff_%s'%z,'ShowerHandleGrip')
            notes=['Current glass and frame origin, opening width and height retained.',
                   'Real rubber glazing seals, screwed metal clamps and connected pull-handle standoffs.',
                   'Maximum pull-handle projection is 2.15 cm beyond original front plane; collision unchanged.']

        for part in PARTS:
            uv_physical(part['object'])
            closed=authored_topology(part['object'])
            AUDITS.append(dict(name=part['name']+':closed_surface',passed=closed,role=part['role']))
        raw_parts=[dict(name=p['name'],role=p['role'],source_retained=p['source_retained'],
                        bounds_cm=bounds([[c*100 for c in v.co] for v in p['object'].data.vertices])) for p in PARTS]
        bpy.ops.object.select_all(action='DESELECT')
        for part in PARTS:part['object'].select_set(True)
        bpy.context.view_layer.objects.active=PARTS[0]['object']
        bpy.ops.object.join()
        obj=bpy.context.object;obj.name='SM_OTS_Real_'+key
        bpy.context.scene.cursor.location=(0,0,0)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        # Deduplicate material slots by role, preserving an explicit stable order.
        old_slots=list(obj.data.materials)
        actual_roles=[role for role in ROLES if any(m.name==role for m in old_slots)]
        ids=[actual_roles.index(old_slots[p.material_index].name) for p in obj.data.polygons]
        obj.data.materials.clear()
        for role in actual_roles:obj.data.materials.append(materials[role])
        for poly,idx in zip(obj.data.polygons,ids):poly.material_index=idx
        triangulate=obj.modifiers.new('Explicit final triangles','TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=triangulate.name)
        actual_box=bounds([[c*100 for c in v.co] for v in obj.data.vertices])
        protrusion=[max(0.,source_box[0][j]-actual_box[0][j],actual_box[1][j]-source_box[1][j]) for j in range(3)]
        AUDITS.append(dict(name='NoHardwareProtrusionOverThreeCentimetres',passed=max(protrusion)<3.001,
                           protrusion_cm=protrusion))
        if key=='Washbasin':
            AUDITS.append(dict(name='BasinGroundAndFaucetHeightPreserved',
                passed=abs(actual_box[0][2])<.001 and abs(actual_box[1][2]-source_box[1][2])<.001))
            frame_parts=[p for p in raw_parts if p['name'].startswith(('BasinSupport','BasinRearTie'))]
            frame_box=bounds([point for p in frame_parts for point in p['bounds_cm']])
            AUDITS.append(dict(name='IndependentLoadBearingFrameGroundedWithinOriginalFootprint',
                passed=abs(frame_box[0][2])<.001 and frame_box[1][2]<=75.001
                    and all(frame_box[0][j]>=source_box[0][j]-.001
                            and frame_box[1][j]<=source_box[1][j]+.001 for j in (0,1)),
                frame_bounds_cm=frame_box,drainage_is_not_structural=True))
        if key=='ShowerTray':
            AUDITS.append(dict(name='ShowerTrayGroundAndTopPreserved',
                passed=abs(actual_box[0][2])<.001 and abs(actual_box[1][2]-4.)<.001))
        fbx=OUT/(obj.name+'.fbx')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,global_scale=1.,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_NONE',use_mesh_modifiers=True,use_triangles=True,bake_anim=False,
            axis_forward='-Y',axis_up='Z',bake_space_transform=False,add_leaf_bones=False,
            mesh_smooth_type='FACE',use_custom_props=False)
        row_out={k:v for k,v in row.items() if k not in ('native','source_poses')}
        row_out.update(mesh_name=obj.name,fbx_file=str(fbx),fbx_sha256=sha(fbx),
                       source_native_geometry_file=row['native']['geometry_file'],
                       source_native_geometry_sha256=row['native']['geometry_sha256'],
                       local_bounds_cm=actual_box,triangles=len(obj.data.polygons),
                       vertices=len(obj.data.vertices),material_roles=actual_roles,parts=raw_parts,
                       maximum_local_protrusion_cm=protrusion,checks=list(AUDITS),
                       passed=all(a['passed'] for a in AUDITS),design_notes=notes,
                       coordinates='Local Blender metres = current native UE local centimetres / 100',
                       export_axis_forward='-Y',export_axis_up='Z',export_apply_scale_options='FBX_SCALE_NONE',
                       collision='NoCollision; preserve all existing independent collision actors')
        variants.append(row_out)
        obj.select_set(False)
        obj.hide_render=True

    blend=OUT/'OldTownRealismSanitary.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    manifest=dict(schema='OldTownRealismSanitaryV1',status='PASS' if all(v['passed'] for v in variants) else 'FAIL',
                  source_map_sha256=map_sha,source_build_report_sha256=sha(SOURCE/'BuildReport.json'),
                  source_snapshot_sha256=sha(SOURCE/'AfterSnapshot.json'),source_script_sha256=sha(__file__),
                  source_blend_file=str(blend),source_blend_sha256=sha(blend),
                  variant_count=len(variants),actor_count=sum(v['source_actor_count'] for v in variants),
                  unchanged_independent_collider_count=87,material_roles=list(ROLES),variants=variants,
                  UV0='Per-face physical metres; one tile per metre, cm/100',
                  import_policy='Root applies verified FBX axis correction if required; keep original actor poses and WPO overrides.')
    write(OUT/'ModelDataManifest.json',manifest)
    print('SANITARY_REALISM_MODELS_'+manifest['status'],len(variants))
    if manifest['status']!='PASS':
        raise RuntimeError('Sanitary model checks failed; inspect ModelDataManifest.json')


if __name__=='__main__':
    main()
