"""Open the already imported table asset without importing or touching a map.

Run in the visible full editor. This script does not load a level, place any
Actor, modify assets, save packages, or call the import script.
"""
import json
import traceback
from pathlib import Path

import unreal

OUT = Path(r'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable')
ASSET = '/Game/Yastars/Mesh/LargeDiningTable/SM_LargeDiningTable'
report = {'success': False, 'asset': ASSET,
          'import_executed': False, 'asset_or_map_save_executed': False,
          'level_load_executed': False, 'actors_spawned': 0}

try:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor, 'Requires the full Unreal Editor'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    mesh = unreal.EditorAssetLibrary.load_asset(ASSET)
    assert mesh and isinstance(mesh, unreal.StaticMesh), 'Table must already be imported: ' + ASSET
    report['asset'] = mesh.get_path_name()
    unreal.EditorAssetLibrary.sync_browser_to_objects([ASSET])
    report['content_browser_selection_requested'] = True
    asset_editors = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    assert asset_editors, 'Asset editor subsystem unavailable'
    report['asset_editor_open_result'] = bool(asset_editors.open_editor_for_assets([mesh]))
    assert report['asset_editor_open_result'], 'Static mesh editor could not be opened'
    world_after = editor.get_editor_world()
    report['world_after'] = world_after.get_path_name() if world_after else None
    report['same_world_object'] = world_before == world_after
    assert report['same_world_object'] and report['world_before'] == report['world_after'], report
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

(OUT / 'ue_open_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('LARGE_DINING_TABLE_OPEN ' + json.dumps(report))
