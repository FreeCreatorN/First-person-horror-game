"""Read-only attribution of faces skipped by the unchanged whole-map scanner."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownCoplanarScan import annotate_axisaligned_cubes,box_faces,_is_box,_visible
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
path=WORK/'GeometryAfter.json'
raw=path.read_bytes()
geometry_sha=hashlib.sha256(raw).hexdigest()
data=json.loads(raw)
del raw
scan=json.loads((WORK/'SavedScan.json').read_text(encoding='utf-8'))
assert geometry_sha==scan['source_geometry_sha256']
names=set()
for category in ('Architecture','Furniture','Sanitary','Street'):
    manifest=json.loads((ROOT/'SourceArt/OldTownRealism_20261012'/category/'ModelDataManifest.json').read_text(encoding='utf-8'))
    names.update(v['mesh_name'] for v in manifest['variants'])
rows=[]
for owner,original in enumerate(data['components']):
    record=annotate_axisaligned_cubes([original])[0]
    if not _visible(record):continue
    if _is_box(record):
        faces=enumerate(box_faces(record['bounds_cm']))
    elif record.get('vertices') is not None:
        verts=record['vertices']
        faces=((i,[verts[int(j)] for j in tri]) for i,tri in enumerate(record.get('triangles',())))
    else:
        faces=enumerate(record.get('triangles',()))
    for index,points in faces:
        a,b,c=points[:3]
        u=[float(b[i])-float(a[i]) for i in range(3)]
        v=[float(c[i])-float(a[i]) for i in range(3)]
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        magnitude=math.sqrt(sum(x*x for x in cross))
        if magnitude<1e-10:
            mesh=str(record.get('mesh',''))
            name=mesh.rsplit('.',1)[-1]
            rows.append(dict(actor=record.get('actor'),component=record.get('component'),id=record.get('id'),
                mesh=mesh,face_index=index,kind=record.get('kind'),points_world_cm=points,
                mathematical_cross_magnitude_cm2=magnitude,
                among_this_round_143_new_models=name in names))
report=dict(schema='OldTownRealismScanDegenerateAttributionV1',passed=len(rows)==scan['stats']['degenerate_faces_skipped'] and not any(r['among_this_round_143_new_models'] for r in rows),
    created_utc=datetime.now(timezone.utc).isoformat(),geometry_file=str(path),geometry_sha256=geometry_sha,
    map_sha256=data['map_sha256'],scanner_file=str(ROOT/'Scripts/OldTownCoplanarScan.py'),
    scanner_sha256=hashlib.sha256((ROOT/'Scripts/OldTownCoplanarScan.py').read_bytes()).hexdigest(),
    original_scanner_degenerate_cross_threshold_cm2=1e-10,actual_skipped_face_count=len(rows),
    expected_skipped_face_count=scan['stats']['degenerate_faces_skipped'],
    skipped_faces_in_143_new_models=sum(r['among_this_round_143_new_models'] for r in rows),rows=rows)
output=WORK/'ScanDegenerateFaces.json'
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False),flush=True)
print(json.dumps(rows,ensure_ascii=False),flush=True)
assert report['passed']
