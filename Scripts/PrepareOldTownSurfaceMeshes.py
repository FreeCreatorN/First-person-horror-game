"""Build isolated render mesh repairs; never change the saved map."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownSurfaceMeshClones import clone_and_separate
from PolishOldTownHotel import sha
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    scan=json.loads((WORK/'BeforeScanOcclusion.json').read_text(encoding='utf-8'))
    paths=sorted(set(r['component_metadata'][0]['mesh'] for r in scan['overlaps'] if r['intra_component'] and r['exposed_area_cm2']>1e-6))
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';digest=sha(mapfile)
    reports=[];mapping={}
    for path in paths:
        mesh=unreal.load_asset(path);assert mesh,path
        clone,report=clone_and_separate(mesh)
        mapping[path]=clone.get_path_name();reports.append(report)
        write('MeshPreparationPending.json',dict(mapping=mapping,reports=reports,completed=len(reports),total=len(paths)))
        unreal.log('SURFACE_MESH_PREPARE %d/%d %s'%(len(reports),len(paths),path))
    assert sha(mapfile)==digest
    write('MeshPreparation.json',dict(passed=True,map_sha256_unchanged=digest,mapping=mapping,reports=reports,
        mesh_count=len(paths),moved_face_patches=sum(len(r.get('moved_patches',[])) for r in reports)))
    unreal.log('SURFACE_MESH_PREPARE_PASS meshes=%d'%len(paths))
if __name__=='__main__':
    try:main()
    except Exception:
        write('MeshPreparationFailure.json',dict(traceback=traceback.format_exc()));raise
