"""Apply reviewed fit corrections to the preserved MCP working scene."""
import bpy, bmesh, json
from pathlib import Path
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parent
s=bpy.context.scene
assert s.name.startswith('Shop counter') and s.name.endswith('.001'),s.name
report=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
parts={key:next(c for c in s.collection.children if c.name.split('.')[0]==key) for key in report['parts']}
def remap(o,axis,lo,hi):
    mn=min(v.co[axis] for v in o.data.vertices);mx=max(v.co[axis] for v in o.data.vertices)
    for v in o.data.vertices:v.co[axis]=lo+(v.co[axis]-mn)*(hi-lo)/(mx-mn)
    o.data.update()
for spec in report['doors'].values():
    c=parts[spec['part']];p=next(o for o in c.objects if o.type=='EMPTY')
    s.frame_set(1);bpy.context.view_layer.update()
    p.location=spec['pivot_m']
    for o in p.children:
        o.matrix_parent_inverse=p.matrix_world.inverted()
        o.matrix_basis=Matrix.Identity(4)
    spec['parent']=p.name
for o in parts['MetalFrame'].objects:
    if o.name.startswith(('Display upright','Front center mullion')):remap(o,2,.771,1.070)
for o in parts['FixedGlass'].objects:
    if o.name.startswith('Front continuous glass'):remap(o,0,-.956,.956)
    elif o.name.startswith('Side fixed glass'):remap(o,1,-.286,.286)
    if not o.name.startswith('Flush glass'):remap(o,2,.771,1.070)
for key in ('GlassDoorLeft','GlassDoorRight'):
    c=parts[key];spec=report['doors']['glass_'+key.removeprefix('GlassDoor').lower()];cx,cy,_=spec['pivot_m']
    for o in c.objects:
        if o.type!='MESH':continue
        if o.name.startswith('Sliding glass leaf'):
            remap(o,0,cx-.464,cx+.464);remap(o,2,.785,1.056)
        elif o.name.startswith('Door vertical edge'):remap(o,2,.771,1.070)
        elif o.name.startswith('Door horizontal edge') and max(v.co.z for v in o.data.vertices)<.80:
            remap(o,2,.771,.785)
        elif o.name.startswith('Small glass pull backing'):remap(o,1,cy+.005,cy+.0085)
shelf=next(o for o in parts['InteriorShelf'].objects if o.type=='MESH')
other=shelf.copy();other.data=shelf.data.copy();parts['InteriorShelf'].objects.link(other)
remap(shelf,0,-.936,-.009);remap(other,0,.009,.936)
for key,c in parts.items():
    for o in c.objects:
        if o.type=='MESH':
            bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            assert all(e.is_manifold for e in bm.edges),o.name
            if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
            assert bm.calc_volume(signed=True)>0,o.name
            bm.to_mesh(o.data);bm.free();o.data.update()
bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get()
def triangles(o):
    e=o.evaluated_get(deps);me=e.to_mesh();me.calc_loop_triangles();n=len(me.loop_triangles);e.to_mesh_clear();return n
report['triangles_by_part']={key:sum(triangles(o) for o in c.objects if o.type=='MESH') for key,c in parts.items()}
report['total_triangles']=sum(report['triangles_by_part'].values())
assert 1800<=report['total_triangles']<=3500,report['triangles_by_part']
for key,c in parts.items():report['parts'][key]['collection']=c.name
report['collision_boxes']['InteriorShelf']=[{'center_m':[x,-.027,.405],'half_m':[.4635,.241,.010]} for x in (-.4725,.4725)]
report['collision_boxes']['FixedGlass']=[{'center_m':[0,-.290,.9205],'half_m':[.956,.003,.1495]},
    *[{'center_m':[x,0,.9205],'half_m':[.003,.286,.1495]} for x in (-.968,.968)],
    {'center_m':[0,0,1.086],'half_m':[.956,.286,.004]}]
report['preview_collection']=next(c.name for c in s.collection.children if c.name.startswith('Preview only'))
report['stock_collection']=next(c.name for c in s.collection.children if c.name.startswith('Optional display stock'))
report['source_scene']=s.name
report['front_camera']=s.camera.name
report['rear_camera']=next(o.name for o in s.objects if o.type=='CAMERA' and o.name.startswith('02 Rear'))
report['reviewed_fixes']=['closed non-self-crossing cup shells','real door local transforms','split inner shelves',
    'fixed glass fitted to uprights','uprights butt joined','door glass fitted inside metal perimeter']
s.eevee.use_raytracing=True
s.frame_set(1);bpy.context.view_layer.update()
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'ShopCounterPlan.blend'))
print('FINAL_SOURCE_SAVED',json.dumps({'triangles':report['total_triangles'],'parts':report['triangles_by_part']}))
