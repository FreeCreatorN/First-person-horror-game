"""Load/import missing desk assets and select the two meshes in the UE browser."""
import json
import traceback
from pathlib import Path
import unreal

task_out = Path(r'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk')
task_status = {'success': False}
try:
    exec(compile((task_out / 'import_ue.py').read_text(encoding='utf-8-sig'),
                 str(task_out / 'import_ue.py'), 'exec'), globals())
    task_import = json.loads((task_out / 'ue_import_report.json').read_text(encoding='utf-8'))
    assert task_import['success'], task_import.get('error')
    task_paths = ['/Game/Yastars/Mesh/OldWoodDesk/SM_OldWoodDesk_Base',
                  '/Game/Yastars/Mesh/OldWoodDesk/SM_OldWoodDesk_Drawer']
    task_meshes = [unreal.EditorAssetLibrary.load_asset(p) for p in task_paths]
    assert all(task_meshes), task_paths
    assert len(task_import['textures']) == 6
    assert len(task_import['materials']) == 2
    for task_mesh in task_meshes:
        assert all(slot.material_interface for slot in task_mesh.static_materials)
    unreal.EditorAssetLibrary.sync_browser_to_objects(task_paths)
    task_status = {'success': True, 'selected_assets': task_paths,
                   'preserved_existing_assets': True,
                   'assets': task_import['assets'],
                   'texture_count': len(task_import['textures']),
                   'material_count': len(task_import['materials'])}
except Exception:
    task_status['error'] = traceback.format_exc()
(task_out / 'ue_open_report.json').write_text(json.dumps(task_status, indent=2), encoding='utf-8')
unreal.log('OLD_DESK_OPEN ' + json.dumps(task_status))
