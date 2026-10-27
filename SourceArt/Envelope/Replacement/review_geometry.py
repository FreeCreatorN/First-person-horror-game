"""Read-only source/FBX review; writes a separate report only."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'EnvelopeSet.blend'))
source=bpy.data.collections['SOURCE - individual paper folds']
source.hide_viewport=False
bpy.context.view_layer.update()

def geometry(obj):
    graph=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(graph)
    mesh=evaluated.to_mesh()
    mesh.calc_loop_triangles()
    verts=[evaluated.matrix_world@v.co for v in mesh.vertices]
    faces=[tuple(t.vertices) for t in mesh.loop_triangles]
    evaluated.to_mesh_clear()
    return verts,faces

def tree(obj):
    verts,faces=geometry(obj)
    return BVHTree.FromPolygons(verts,faces,all_triangles=True)

def bounds(obj,offset=Vector((0,0,0))):
    vs=[obj.matrix_world@v.co+offset for v in obj.data.vertices]
    return [min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]

hinges=[o for o in source.objects if o.name.startswith('Continuous rolled fold hinge')]
fronts=[o for o in source.objects if o.name.startswith('Front sheet and continuous fold roots')]
open_flaps=[o for o in source.objects if o.name.startswith('Large V sealing flap') and bounds(o)[1][2]>.01]
assert hinges and fronts and len(open_flaps)==1
hinge=hinges[0]
hinge_checks={
    'hinge_front_surface_intersections':len(tree(hinge).overlap(tree(fronts[0]))),
    'hinge_open_flap_surface_intersections':len(tree(hinge).overlap(tree(open_flaps[0]))),
    'source_open_flap':open_flaps[0].name,
}
assert hinge_checks['hinge_front_surface_intersections']>0,hinge_checks
assert hinge_checks['hinge_open_flap_surface_intersections']>0,hinge_checks

before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(OUT/'SM_Envelope_Open.fbx'),use_anim=False)
open_imported=set(bpy.data.objects)-before
envelope_hulls=[o for o in open_imported if o.name.startswith('UCX_')]
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(OUT/'SM_LetterPaper.fbx'),use_anim=False)
paper_imported=set(bpy.data.objects)-before
paper_hulls=[o for o in paper_imported if o.name.startswith('UCX_')]
assert len(paper_hulls)==1
paper_bounds=bounds(paper_hulls[0],Vector((0,0,.0013)))
collision_checks=[]
for hull in envelope_hulls:
    low,high=bounds(hull)
    a,b=paper_bounds
    gaps=[max(low[i]-b[i],a[i]-high[i],0) for i in range(3)]
    separation=math.sqrt(sum(g*g for g in gaps))
    collision_checks.append({'name':hull.name,'aabb_separation_mm':separation*1000,'axis_gaps_mm':[g*1000 for g in gaps]})
    assert separation>1e-7,('Potential collision overlap requiring SAT test',collision_checks[-1])
report={'success':True,'hinge':hinge_checks,'open_ucx_count':len(envelope_hulls),
        'paper_collision_pose_offset_m':[0,0,.0013],
        'minimum_ucx_aabb_separation_mm':min(c['aabb_separation_mm'] for c in collision_checks),
        'collision_checks':collision_checks}
(OUT/'review_geometry_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('READ_ONLY_GEOMETRY_REVIEW '+json.dumps({k:v for k,v in report.items() if k!='collision_checks'}),flush=True)
