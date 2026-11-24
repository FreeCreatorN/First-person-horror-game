"""Inspect actual source topology/animated clearance and render two source views."""
import bpy,bmesh,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'ShopCounterPlan.blend'
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene
errors=[];min_pair={'wood':9.,'glass':9.}
for part in R['parts'].values():
    for o in bpy.data.collections[part['collection']].objects:
        if o.type!='MESH':continue
        bm=bmesh.new();bm.from_mesh(o.data)
        assert all(e.is_manifold for e in bm.edges),o.name
        assert bm.calc_volume(signed=True)>0,o.name
        bm.free()
for frame in range(1,261):
    s.frame_set(frame);bpy.context.view_layer.update()
    bounds={}
    for key,d in R['doors'].items():
        p=bpy.data.objects[d['parent']]
        leaves=[p] if p.type=='MESH' else [o for o in p.children if o.type=='MESH']
        points=[o.matrix_world@Vector(v) for o in leaves for v in o.bound_box]
        low=[min(v[i] for v in points) for i in range(3)];high=[max(v[i] for v in points) for i in range(3)]
        bounds[key]=(low,high)
        limit=.956 if key.startswith('glass') else .936
        assert low[0]>-limit-.00001 and high[0]<limit+.00001,(frame,key,low,high)
        assert all(abs(p.location[i]-d['pivot_m'][i])<.00001 for i in (1,2)),(frame,key)
    for family in ('wood','glass'):
        gap=bounds[family+'_right'][0][1]-bounds[family+'_left'][1][1]
        min_pair[family]=min(gap,min_pair[family]);assert gap>.002,(frame,family,gap)
for filename,camera,frame in [('ShopCounterPlan_Front.png',R['front_camera'],1),('ShopCounterPlan_RearOpen.png',R['rear_camera'],154)]:
    s.frame_set(frame)
    if frame==154:
        p=bpy.data.objects[R['doors']['glass_left']['parent']]
        p.location.x=R['doors']['glass_left']['pivot_m'][0]+R['doors']['glass_left']['travel_cm']*.01
    s.camera=bpy.data.objects[camera];s.render.engine='CYCLES';s.cycles.samples=28;s.cycles.use_denoising=True
    s.render.filepath=str(ROOT/filename);bpy.ops.render.render(write_still=True)
    print('RENDERED',filename,flush=True)
report={'success':True,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'triangles':R['total_triangles'],
        'checked_frames':260,'manifold':True,'normals_outward':True,'minimum_pair_clearance_mm':{k:1000*v for k,v in min_pair.items()},
        'previews':['ShopCounterPlan_Front.png','ShopCounterPlan_RearOpen.png']}
(ROOT/'geometry_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('GEOMETRY_VERIFIED',json.dumps(report),flush=True)
