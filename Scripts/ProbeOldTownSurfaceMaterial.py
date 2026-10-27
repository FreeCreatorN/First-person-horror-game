import sys,json
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownSurfaceMaterials import make_offset_material,get_report
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
material=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete')
m=make_offset_material(material,[.09,.18,.27])
report=get_report();report['test_material']=m.get_path_name()
report['API']={}
for clsname,methods in {'GeometryScript_MeshTransforms':['scale_mesh'], 'GeometryScript_MeshBasicEdit':['set_vertex_position'],
 'GeometryScript_MeshQueries':['get_triangle_indices','get_vertex_position','get_all_vertex_i_ds'],
 'StaticMeshComponent':[]}.items():
 c=getattr(unreal,clsname,None);report['API'][clsname]=dict(doc=getattr(c,'__doc__',''))
 for method in methods:report['API'][clsname][method]=getattr(getattr(c,method,None),'__doc__',None)
(WORK/'MaterialProbe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('SURFACE_MATERIAL_PROBE_PASS')
