"""Read-only axis-face overlap audit; ignores opposite-normal assembly contacts."""
import bpy,json,math,hashlib
from pathlib import Path
from collections import defaultdict
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8-sig'))
source=Path(bpy.data.filepath)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
EPS=2e-6
rows=[]
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def area(p):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))*.5 if len(p)>2 else 0
def clip(subject, boundary):
    result=subject
    if cross(*boundary)<0:boundary=list(reversed(boundary))
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        old=result;result=[]
        if not old:break
        for p,q in zip(old,old[1:]+old[:1]):
            cp,cq=cross(a,b,p),cross(a,b,q)
            ip,iq=cp>=-1e-12,cq>=-1e-12
            if ip:result.append(p)
            if ip!=iq:
                t=cp/(cp-cq)
                result.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return result

objects=[]
for key,part in R['parts'].items():
    for o in bpy.data.collections[part['collection']].objects:
        if o.type!='MESH':continue
        objects.append((key,o))
        me=o.data;me.calc_loop_triangles()
        # Connected shells identify the individual authored boards and straps.
        adj=defaultdict(set)
        for e in me.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
        comp={};shells=[]
        for v in me.vertices:
            if v.index in comp:continue
            index=len(shells);todo=[v.index];ids=[]
            while todo:
                j=todo.pop()
                if j in comp:continue
                comp[j]=index;ids.append(j);todo.extend(adj[j]-comp.keys())
            points=[o.matrix_world@me.vertices[j].co for j in ids]
            shells.append({'index':index,'vertices':len(ids),'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]})
        for t in me.loop_triangles:
            p=[o.matrix_world@me.vertices[i].co for i in t.vertices]
            n=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
            axis=max(range(3),key=lambda i:abs(n[i]))
            if abs(n[axis])<.999999:continue
            plane=sum(v[axis] for v in p)/3
            other=[i for i in range(3) if i!=axis]
            poly=[(float(v[other[0]]),float(v[other[1]])) for v in p]
            rows.append({'part':key,'object':o.name,'shell':comp[t.vertices[0]],'polygon':t.polygon_index,'triangle':t.index,
                'axis':axis,'sign':1 if n[axis]>0 else -1,'plane':plane,'poly':poly,
                'min':[min(v[i] for v in poly) for i in range(2)],'max':[max(v[i] for v in poly) for i in range(2)]})
        part['shells']=shells

groups=defaultdict(list)
for row in rows:groups[(row['axis'],row['sign'],round(row['plane'],5))].append(row)
overlaps=[]
totals=defaultdict(float)
for bucket in groups.values():
    for i,a in enumerate(bucket):
        for b in bucket[i+1:]:
            if a['object']==b['object'] and a['polygon']==b['polygon']:continue
            if a['object']==b['object'] and a['shell']==b['shell']:continue
            if abs(a['plane']-b['plane'])>EPS:continue
            if any(min(a['max'][i],b['max'][i])-max(a['min'][i],b['min'][i])<=EPS for i in range(2)):continue
            overlap=clip(a['poly'],b['poly']);ar=area(overlap)
            if ar<1e-9:continue
            key=(a['part'],a['shell'],b['part'],b['shell'],a['axis'],a['sign'],round(a['plane'],6))
            totals[key]+=ar
            overlaps.append({'a':{k:a[k] for k in ('part','object','shell','polygon')},
                'b':{k:b[k] for k in ('part','object','shell','polygon')},'axis':'XYZ'[a['axis']],
                'sign':a['sign'],'plane_m':a['plane'],'area_m2':ar,'overlap_bounds_2d':[
                    [min(v[i] for v in overlap) for i in range(2)],[max(v[i] for v in overlap) for i in range(2)]]})
summary=[{'a_part':k[0],'a_shell':k[1],'b_part':k[2],'b_shell':k[3],'axis':'XYZ'[k[4]],'sign':k[5],'plane_m':k[6],'area_m2':v}
    for k,v in sorted(totals.items())]
result={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scene':s.name,
    'objects':{key:{'object':o.name,'shells':R['parts'][key]['shells']} for key,o in objects},
    'outward_coplanar_triangle_pairs':len(overlaps),'outward_coplanar_area_m2':sum(v['area_m2'] for v in overlaps),
    'summary':summary,'pairs':overlaps}
out=Path(__file__).with_name('coplanar_audit.json');out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('COPLANAR_AUDIT',json.dumps({'pairs':len(overlaps),'area_m2':result['outward_coplanar_area_m2'],'summary':summary}),flush=True)
