import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownSurfaceMeshClones import clone_and_separate
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
try:
    mesh=unreal.load_asset('/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005/SM_OTS_Arch_Toilet')
    clone,report=clone_and_separate(mesh)
    (WORK/'MeshProbe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('SURFACE_MESH_PROBE_PASS '+clone.get_path_name())
except Exception:
    (WORK/'MeshProbeFailure.json').write_text(traceback.format_exc(),encoding='utf-8');raise
