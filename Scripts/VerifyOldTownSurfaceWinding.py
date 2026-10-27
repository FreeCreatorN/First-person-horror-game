import json,math
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
data=json.loads((WORK/'GeometryInput.json').read_text(encoding='utf-8'))
checks={}
for path in sorted(set(r['mesh'] for r in data['components'])):
    m=unreal.load_asset(path);signs=[]
    for section in range(m.get_num_sections(0)):
        vs,ts,ns,*_=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(m,0,section)
        for i in range(0,len(ts),3):
            a,b,c=[vs[int(ts[i+j])] for j in range(3)]
            u=b-a;v=c-a;cross=unreal.MathLibrary.cross_vector_vector(u,v)
            normal=ns[int(ts[i])]+ns[int(ts[i+1])]+ns[int(ts[i+2])]
            dot=unreal.MathLibrary.dot_vector_vector(cross,normal)
            if abs(dot)>1e-6:signs.append(1 if dot>0 else -1)
    positive=signs.count(1);negative=signs.count(-1)
    checks[path]=dict(positive=positive,negative=negative,reverse_winding=negative>positive)
for r in data['components']:r['reverse_winding']=checks[r['mesh']]['reverse_winding']
(WORK/'WindingVerification.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
(WORK/'GeometryInput.json').write_text(json.dumps(data),encoding='utf-8')
unreal.log('SURFACE_WINDING_PASS meshes=%d'%len(checks))
