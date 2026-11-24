import bpy,json,shutil,bmesh,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
S=bpy.context.scene;assert S.name=='BeverageDisplayFridge';S.frame_set(1)
source=ROOT/'BeverageDisplayFridge.blend'
(ROOT/'Revisions').mkdir(exist_ok=True)
backup=ROOT/'Revisions'/'BeforeSeamFix.blend'
if not backup.exists():shutil.copy2(source,backup)
def shells(o):
    adj={v.index:set() for v in o.data.vertices}
    for e in o.data.edges:
        a,b=e.vertices;adj[a].add(b);adj[b].add(a)
    result=[];seen=set()
    for v in o.data.vertices:
        if v.index in seen:continue
        todo=[v.index];ids=[]
        while todo:
            j=todo.pop()
            if j in seen:continue
            seen.add(j);ids.append(j);todo.extend(adj[j]-seen)
        result.append(ids)
    return result
def remap(o,ids,axis,low,high,newlow,newhigh):
    assert o.parent is None
    for i in ids:
        v=o.data.vertices[i];v.co[axis]=newlow+(v.co[axis]-low)*(newhigh-newlow)/(high-low)
o=S.objects['SM_BeverageDisplayFridge_OuterBody'];cs=shells(o)
for i in (9,10):remap(o,cs[i],2,.285,1.685,.285,1.680)
for i in cs[12]:o.data.vertices[i].co.z-=.005
for j in (18,19):remap(o,cs[j],0,.285,.315,.286,.314)
for i in cs[21]:o.data.vertices[i].co.y+=.004
o.data.update()
o=S.objects['SM_BeverageDisplayFridge_InnerLiner'];cs=shells(o)
assert len(cs)==25
for ids in cs[5:]:
    center=sum(o.data.vertices[i].co.x for i in ids)/len(ids)
    for i in ids:o.data.vertices[i].co.x=center+(o.data.vertices[i].co.x-center)*(.015/.016)
o.data.update()
o=S.objects['SM_BeverageDisplayFridge_VentGrille'];cs=shells(o);assert len(cs)==13
for j in (0,1):remap(o,cs[j],2,.130,.305,.130,.281)
for i in cs[3]:o.data.vertices[i].co.z-=.024
for j in range(7):
    for i in cs[4+j]:o.data.vertices[i].co.z-=j*.003
for j in (11,12):remap(o,cs[j],2,.144,.291,.144,.267)
o.data.update()
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
for k,part in R['parts'].items():
    o=S.objects[part['mesh']];bm=bmesh.new();bm.from_mesh(o.data)
    assert all(e.is_manifold for e in bm.edges),k
    assert bm.calc_volume(signed=True)>0,k
    bm.free()
R['collision_boxes']['VentGrille']=[{'center_m':[0,-.334,.2055],'half_m':[.285,.012,.0755]}]
(ROOT/'model_report.json').write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.libraries.write(str(source),{S},fake_user=True,compress=True)
print('SEAMS_FIXED_SOURCE_SAVED',hashlib.sha256(source.read_bytes()).hexdigest())
