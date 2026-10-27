"""Import/preserve the altar-table asset and select it in the UE content browser."""
import json, traceback
from pathlib import Path
import unreal

task_out=Path(r'D:\UE\Project\HorrorGame\SourceArt\AltarTable')
task_status={'success':False}
try:
    exec(compile((task_out/'import_ue.py').read_text(encoding='utf-8-sig'),str(task_out/'import_ue.py'),'exec'),globals())
    task_import=json.loads((task_out/'ue_import_report.json').read_text(encoding='utf-8'))
    assert task_import['success'],task_import.get('error')
    task_path='/Game/Yastars/Mesh/AltarTable/SM_AltarTable'
    task_mesh=unreal.EditorAssetLibrary.load_asset(task_path)
    assert task_mesh and all(slot.material_interface for slot in task_mesh.static_materials)
    assert len(task_import['textures'])==3 and len(task_import['materials'])==1
    unreal.EditorAssetLibrary.sync_browser_to_objects([task_path])
    task_status={'success':True,'selected_assets':[task_path],'assets':task_import['assets'],'texture_count':3,'material_count':1}
except Exception:
    task_status['error']=traceback.format_exc()
(task_out/'ue_open_report.json').write_text(json.dumps(task_status,indent=2),encoding='utf-8')
unreal.log('ALTAR_TABLE_OPEN '+json.dumps(task_status))
