"""Independent saved-world fixture and existing architectural regression checks."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from RefineOldTownSanitaryShapes import expected_actor,collision_signature
from PolishOldTownHotel import sha
WORK=ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    import AuditOldTownHotelDetails as hotel
    hotel.WORK=WORK;hotel.main()
    build=read(WORK/'BuildReport.json');repair=build['sanitary_finish_refinement'];before=read(WORK/'InputSnapshot.json')['actors'];after=read(WORK/'AfterSnapshot.json')['actors']
    checks=[];errors=[]
    def check(n,ok,**v):
        checks.append(dict(name=n,passed=bool(ok),**v))
        if not ok:errors.append(n)
    rows={r['actor']:r for r in build['hotel_v4']['placed_props'] if r.get('asset_key') in ('Toilet','Washbasin')}
    newcams={r['camera'] for r in repair['new_cameras']}
    check('exact_complete_actor_manifest',set(after)==set(before)|newcams)
    for n,old in before.items():
        expected=expected_actor(old,rows[n]['asset'],rows[n]['asset_key']) if n in rows else old
        check('approved_saved_actor_state:'+n,after.get(n)==expected)
    for n in repair['preserved_fixture_collision_actors']:check('fixture_collision_unchanged:'+n,after[n]==before[n])
    winding_rows=[]
    for asset in repair['new_assets']:
        original=unreal.load_asset(asset['source']);new=unreal.load_asset(asset['asset'])
        import RefineOldTownSanitaryShapes as mutator
        old_sections=mutator.section_faces(original);parts={'retained':{'positive':0,'negative':0,'zero':0},'new':{'positive':0,'negative':0,'zero':0},'new_relative_to_pure_outward_cross':{'positive':0,'negative':0,'zero':0}}
        # One-to-one source-recipe coordinates matched to actual float32 render
        # positions; no inferred normals, no bounding-box-only claim.
        import math
        data0=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(new,0,0)
        positions={tuple(float(getattr(v,q)) for q in ('x','y','z')) for v in data0[0]}
        cells={};budget=.00002
        for p in positions:
            cell=tuple(math.floor(v/budget) for v in p);cells.setdefault(cell,[]).append(p)
        correspondence={};pure_faces={}
        for piece in asset['shape_recipe']['pieces']:
            for p in {tuple(v) for v in piece['vertices']}:
                if p in correspondence:continue
                cell=tuple(math.floor(v/budget) for v in p);candidates=[]
                for dx in (-1,0,1):
                    for dy in (-1,0,1):
                        for dz in (-1,0,1):
                            candidates.extend(q for q in cells.get((cell[0]+dx,cell[1]+dy,cell[2]+dz),()) if all(abs(p[k]-q[k])<=budget for k in range(3)))
                assert len(candidates)==1,('Ambiguous new render recipe position',p,len(candidates))
                correspondence[p]=candidates[0]
            for t in piece['triangles']:
                pp=[tuple(piece['vertices'][i]) for i in t]
                sig=tuple(sorted(correspondence[p] for p in pp))
                assert sig not in pure_faces,'Duplicate recipe face'
                a,b,c=[unreal.Vector(*p) for p in pp]
                pure_faces[sig]=unreal.MathLibrary.cross_vector_vector(b-a,c-a)
        matched_new=set()
        for sec in range(new.get_num_sections(0)):
            data=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(new,0,sec)
            vv,tt,nn=data[0],data[1],data[2]
            for i in range(0,len(tt),3):
                ids=[int(tt[i+j]) for j in range(3)];a,b,c=[vv[j] for j in ids]
                signature=tuple(sorted(tuple(float(getattr(vv[j],q)) for q in ('x','y','z')) for j in ids))
                category='retained' if old_sections[sec][signature] else 'new'
                dot=unreal.MathLibrary.dot_vector_vector(unreal.MathLibrary.cross_vector_vector(b-a,c-a),nn[ids[0]]+nn[ids[1]]+nn[ids[2]])
                parts[category]['positive' if dot>1e-6 else 'negative' if dot < -1e-6 else 'zero']+=1
                if category=='new':
                    assert signature in pure_faces and signature not in matched_new,('New render face absent or duplicated',asset['asset_key'])
                    matched_new.add(signature)
                    relative=unreal.MathLibrary.dot_vector_vector(pure_faces[signature],nn[ids[0]]+nn[ids[1]]+nn[ids[2]])
                    parts['new_relative_to_pure_outward_cross']['positive' if relative>1e-6 else 'negative' if relative < -1e-6 else 'zero']+=1
        assert len(matched_new)==len(pure_faces)
        winding_rows.append(dict(asset_key=asset['asset_key'],asset=asset['asset'],sha256=sha(Path(asset['file'])),parts=parts))
        check('all_actual_new_normals_point_outward:'+asset['asset_key'],parts['new_relative_to_pure_outward_cross']==dict(positive=len(pure_faces),negative=0,zero=0))
        check('mesh_collision_unchanged:'+asset['asset_key'],collision_signature(original)==collision_signature(new)==asset['collision_signature'])
        check('original_mesh_file_unchanged:'+asset['asset_key'],sha(Path(asset['source_file']))==asset['source_sha256'])
        check('new_faces_in_correct_material_slot:'+asset['asset_key'],asset['added_triangles_per_material_section'][0]>0 and asset['added_triangles_per_material_section'][1]==0)
    digest=sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap');check('persisted_map_unchanged',digest==build['map_sha256'])
    report=dict(passed=not errors,target_level=build['target_level'],map_sha256=digest,source='fresh_persisted_map_load',persisted_map_unchanged=digest==build['map_sha256'],checks=checks,errors=errors,statistics=dict(checks=len(checks),toilets=30,basins=30,unchanged_existing_actors=len(before)-30,preserved_fixture_collision_actors=60))
    write('FinishRenderNormals.json',dict(map_sha256=digest,assets=winding_rows));write('FinishSavedAudit.json',report);assert report['passed'],errors[:20]
    unreal.log('SANITARY_FINISH_SAVED_AUDIT_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:write('FinishAuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
