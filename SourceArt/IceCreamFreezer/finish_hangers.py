import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
assert not R.get('basket_hangers'), 'Hangers already installed'
for key,sign in [('BasketLeft',-1),('BasketRight',1)]:
    o=bpy.data.objects[R['parts'][key]['object']];bm=bmesh.new();bm.from_mesh(o.data)
    for v in bm.verts:v.co.z+=.050
    def rod(a,b,r=.002):
        a,b=Vector(a),Vector(b);axis=(b-a).normalized();u=axis.cross(Vector((0,0,1)))
        if u.length<.1:u=axis.cross(Vector((0,1,0)))
        u.normalize();v=axis.cross(u)
        vertices=[bm.verts.new(p+u*r*math.cos(i*math.pi/2+math.pi/4)+v*r*math.sin(i*math.pi/2+math.pi/4)) for p in (a,b) for i in range(4)]
        for ids in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:bm.faces.new([vertices[i] for i in ids])
    for x in (sign*.285-.19,sign*.285+.19):
        for side in (-1,1):
            z=.771+.002/math.sqrt(2)
            rod((x,side*.24,.745),(x,side*.24,z))
            rod((x,side*.24,z),(x,side*.312,z))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
    for row in R['collision_boxes'][key]:row['center_m'][2]+=.050
R['basket_hangers']=True
for key,row in R['parts'].items():
    me=bpy.data.objects[row['object']].data;me.calc_loop_triangles();R['triangles_by_part'][key]=len(me.loop_triangles)
R['total_triangles']=sum(R['triangles_by_part'].values());assert R['total_triangles']<=3400
(ROOT/'model_report.json').write_text(json.dumps(R,indent=2,ensure_ascii=False),encoding='utf-8')
bpy.data.libraries.write(str(ROOT/'IceCreamFreezer.blend'),{bpy.context.scene},fake_user=True,compress=True)
print('BASKETS_MOUNTED',R['total_triangles'])
