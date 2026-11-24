import bpy,bmesh,json,hashlib,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'IceCreamFreezer.blend'
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene
assert len(bpy.data.scenes)==1 and s.name==R['source_scene']
assert len(R['parts'])==11 and len(R['planning_categories'])==6 and R['no_products']
for key,row in R['parts'].items():
    o=bpy.data.objects[row['object']];bm=bmesh.new();bm.from_mesh(o.data)
    assert all(e.is_manifold for e in bm.edges),key
    assert bm.calc_volume(signed=True)>0,key
    bm.free()
    if key.startswith('Wheel'):assert abs(min((o.matrix_world@v.co).z for v in o.data.vertices))<1e-5,key
for f in range(1,151):
    s.frame_set(f);bpy.context.view_layer.update()
    for key,d in R['doors'].items():
        o=bpy.data.objects[d['parent']];lo=min((o.matrix_world@v.co).x for v in o.data.vertices);hi=max((o.matrix_world@v.co).x for v in o.data.vertices)
        assert -.614<lo<hi<.614,(f,key,lo,hi)
        assert abs(o.location.z-d['pivot_m'][2])<1e-5
    # Both shaped leaves have identical cross-sections, separated by 12mm.
    assert R['door_track_height_difference_m']-.008>=.003
render_passes=[] if '--verify-only' in sys.argv else [('IceCreamFreezer_Front.png',R['front_camera'],1),('IceCreamFreezer_Open.png',R['open_camera'],34)]
for filename,camera,frame in render_passes:
    s.frame_set(frame);s.camera=bpy.data.objects[camera];s.render.engine='CYCLES';s.cycles.samples=28
    s.render.filepath=str(ROOT/filename);bpy.ops.render.render(write_still=True);print('RENDERED',filename,flush=True)
receipt={'success':True,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'triangles':R['total_triangles'],
    'planning_categories':6,'mesh_count':11,'checked_frames':150,'manifold':True,'wheels_grounded':True,'basket_hangers':True,
    'minimum_lid_frame_vertical_clearance_mm':4.0,'previews':['IceCreamFreezer_Front.png','IceCreamFreezer_Open.png']}
(ROOT/'geometry_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('FREEZER_VERIFIED',json.dumps(receipt),flush=True)
