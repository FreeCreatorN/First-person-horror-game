import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
assert not R.get('origins_finished')
for key,row in R['parts'].items():
    if key.startswith('Basket'):pivot=Vector((-.285 if key.endswith('Left') else .285,0,.515))
    elif key.startswith('Wheel'):
        pivot=Vector((-.570 if key.endswith(('FL','RL')) else .570,-.270 if key.endswith(('FL','FR')) else .270,.100))
    else:continue
    o=bpy.data.objects[row['object']]
    for v in o.data.vertices:v.co-=pivot
    o.location=pivot;row['pivot_m']=list(pivot)
R['origins_finished']=True
(ROOT/'model_report.json').write_text(json.dumps(R,indent=2,ensure_ascii=False),encoding='utf-8')
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
bpy.data.libraries.write(str(ROOT/'IceCreamFreezer.blend'),{bpy.context.scene},fake_user=True,compress=True)
print('FREEZER_COMPONENT_ORIGINS_FINISHED')
