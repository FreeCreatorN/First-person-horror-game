"""Move buried side trim outside its wooden substrate, then audit coplanarity."""
import bpy,bmesh,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
assert s.name==R['source_scene']
body=bpy.data.objects[R['parts']['Body']['object']]
metal=bpy.data.objects[R['parts']['MetalFrame']['object']]

def polygon_clip(poly,a,b):
    def side(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        sp,sq=side(p),side(q)
        if sp>=-1e-12:out.append(p)
        if (sp>=0)!=(sq>=0):
            t=sp/(sp-sq);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return out

def coplanar_overlap(a,b):
    def triangles(obj):
        obj.data.calc_loop_triangles();result={}
        for t in obj.data.loop_triangles:
            v=[obj.matrix_world@obj.data.vertices[i].co for i in t.vertices]
            n=(v[1]-v[0]).cross(v[2]-v[0]);area=n.length*.5
            if area<1e-12:continue
            n.normalize();d=n.dot(v[0])
            key=tuple(round(x,5) for x in (*n,d))
            drop=max(range(3),key=lambda i:abs(n[i]));axes=[i for i in range(3) if i!=drop]
            p=[(x[axes[0]],x[axes[1]]) for x in v]
            signed=sum(p[i][0]*p[(i+1)%3][1]-p[(i+1)%3][0]*p[i][1] for i in range(3))
            if signed<0:p.reverse()
            result.setdefault(key,[]).append((t.polygon_index,p))
        return result
    aa,bb=triangles(a),triangles(b);hits=[];total=0
    for key in aa.keys()&bb.keys():
        for ia,pa in aa[key]:
            for ib,pb in bb[key]:
                # Ignore sub-micron contact slivers from float32 mesh coordinates.
                if any(min(max(p[i] for p in pa),max(p[i] for p in pb))-max(min(p[i] for p in pa),min(p[i] for p in pb))<1e-6 for i in (0,1)):continue
                pp=pa
                for j in range(3):
                    pp=polygon_clip(pp,pb[j],pb[(j+1)%3])
                    if not pp:break
                area=abs(sum(pp[i][0]*pp[(i+1)%len(pp)][1]-pp[(i+1)%len(pp)][0]*pp[i][1] for i in range(len(pp))))*.5 if len(pp)>2 else 0
                if area>1e-8:
                    total+=area;hits.append({'body_face':ia,'metal_face':ib,'normal_plane':key,'area_m2':area})
    return {'pairs':len(hits),'projected_overlap_area_m2':total,'hits':hits}

before=coplanar_overlap(body,metal)
bm=bmesh.new();bm.from_mesh(metal.data)
unseen=set(bm.verts);shifted=[]
while unseen:
    first=next(iter(unseen));stack=[first];island=set()
    while stack:
        v=stack.pop()
        if v in island:continue
        island.add(v);unseen.discard(v)
        stack.extend(e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in island)
    low=[min(v.co[i] for v in island) for i in range(3)];high=[max(v.co[i] for v in island) for i in range(3)]
    cx=(low[0]+high[0])/2
    if min(abs(abs(cx)-.979),abs(abs(cx)-.981))<1e-5 and abs((high[0]-low[0])-.002)<1e-5:
        dx=(.002 if cx>0 else -.002) if abs(abs(cx)-.979)<1e-5 else 0
        for v in island:v.co.x+=dx
        shifted.append({'before_min':low,'before_max':high,'shift_x_m':dx,'vertices':len(island)})
        # Horizontal side runners butt against the vertical corner strips.
        if high[1]-low[1]>.60:
            for v in island:v.co.y=max(-.268,min(.268,v.co.y))
    # Front horizontal runners also stop at the inside of the corner straps.
    elif abs((low[1]+high[1])/2+.3115)<1e-5 and high[0]-low[0]>1.9 and high[2]-low[2]<.012:
        for v in island:v.co.x=max(-.936,min(.936,v.co.x))
assert len(shifted)==8,(len(shifted),shifted)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(metal.data);bm.free();metal.data.update()
# The wooden foot must start at the top of its metal shoe, not share its floor face.
bm=bmesh.new();bm.from_mesh(body.data);unseen=set(bm.verts);feet=0
while unseen:
    stack=[next(iter(unseen))];island=set()
    while stack:
        v=stack.pop()
        if v in island:continue
        island.add(v);unseen.discard(v);stack.extend(e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in island)
    low=[min(v.co[i] for v in island) for i in range(3)];high=[max(v.co[i] for v in island) for i in range(3)]
    if abs(high[2]-.058)<1e-5 and abs((high[0]-low[0])-.076)<1e-5:
        if low[2]<.001:
            for v in island:
                if v.co.z<.01:v.co.z+=.014
        feet+=1
assert feet==6,feet
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(body.data);bm.free();body.data.update()
bpy.context.view_layer.update()
after=coplanar_overlap(body,metal)
assert after['pairs']==0,after
assert abs(min(v.co.x for v in metal.data.vertices)+.982)<1e-5
assert abs(max(v.co.x for v in metal.data.vertices)-.982)<1e-5
# Only the repaired clean scene and its dependencies are serialized.
bpy.data.libraries.write(str(ROOT/'ShopCounterPlan.blend'),{s},fake_user=True,compress=True)
receipt={'success':True,'moved_side_trim_pieces':shifted,'before':before,'after':after,
    'source_sha256':hashlib.sha256((ROOT/'ShopCounterPlan.blend').read_bytes()).hexdigest(),
    'triangles':R['total_triangles'],'planning_categories':8,'static_meshes':10}
(ROOT/'SideFix/side_overlap_repair.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('SIDE_OVERLAP_REPAIRED',json.dumps({k:v for k,v in receipt.items() if k not in ('before','moved_side_trim_pieces')}))
