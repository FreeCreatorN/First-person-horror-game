import bpy,bmesh,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
s=bpy.context.scene
liner=bpy.data.objects[R['parts']['Liner']['object']]
for v in liner.data.vertices:
    if abs(v.co.z-.757)<1e-5:v.co.z=.765
for row in R['collision_boxes']['Liner']:
    if abs(row['center_m'][2]-.487)<1e-5:row['center_m'][2]=.491;row['half_m'][2]=.274
# Join the liner rim to the body top with one closed rectangular sealing collar.
frame=bpy.data.objects[R['parts']['TopFrame']['object']]
bm=bmesh.new();bm.from_mesh(frame.data)
rings=[]
for z,a,b in [(.765,.626,.326),(.771,.626,.326),(.771,.599,.299),(.765,.599,.299)]:
    rings.append([bm.verts.new((x,y,z)) for x,y in [(-a,-b),(a,-b),(a,b),(-a,b)]])
for j in range(4):
    for i in range(4):bm.faces.new((rings[j][i],rings[j][(i+1)%4],rings[(j+1)%4][(i+1)%4],rings[(j+1)%4][i]))
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(frame.data);bm.free();frame.data.update()
for key,row in R['parts'].items():
    if not key.startswith('Wheel'):continue
    o=bpy.data.objects[row['object']];bm=bmesh.new();bm.from_mesh(o.data);remaining=set(bm.verts)
    while remaining:
        todo=[next(iter(remaining))];island=set()
        while todo:
            v=todo.pop()
            if v in island:continue
            island.add(v);remaining.discard(v);todo.extend(e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in island)
        low=[min(v.co[i] for v in island) for i in range(3)];high=[max(v.co[i] for v in island) for i in range(3)]
        if abs(low[2]-.004)<1e-5 and abs(high[2]-.056)<1e-5:
            for v in island:v.co.z-=.004
        elif abs(low[2]-.0265)<1e-5 and abs(high[2]-.0715)<1e-5:
            for v in island:v.co.z=.020+(v.co.z-.0265)*.05/.045
        elif abs(low[2]-.025)<1e-5 and abs(high[2]-.035)<1e-5:
            cy=(low[1]+high[1])/2
            for v in island:v.co.z-=.004;v.co.y=cy+(v.co.y-cy)*1.05
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
    assert abs(min(v.co.z for v in o.data.vertices))<1e-5,key
for key in ('GlassDoorLeft','GlassDoorRight'):
    o=bpy.data.objects[R['parts'][key]['object']]
    for p in o.data.polygons:
        if len(p.vertices)==4:
            vs=[o.data.vertices[i].co for i in p.vertices]
            if max(v.y for v in vs)-min(v.y for v in vs)>.001 and max(v.z for v in vs)-min(v.z for v in vs)>.0001:p.use_smooth=True
R['triangles_by_part']={}
for key,row in R['parts'].items():
    me=bpy.data.objects[row['object']].data;me.calc_loop_triangles();R['triangles_by_part'][key]=len(me.loop_triangles)
R['total_triangles']=sum(R['triangles_by_part'].values());assert 1800<=R['total_triangles']<=3400
(ROOT/'model_report.json').write_text(json.dumps(R,indent=2,ensure_ascii=False),encoding='utf-8')
s.frame_set(1);bpy.context.view_layer.update();bpy.data.libraries.write(str(ROOT/'IceCreamFreezer.blend'),{s},fake_user=True,compress=True)
print('FREEZER_FIT_FINISHED',R['total_triangles'])
