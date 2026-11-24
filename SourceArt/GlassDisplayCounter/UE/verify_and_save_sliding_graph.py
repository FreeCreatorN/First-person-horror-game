"""Compile and save only the display counter after its native graph is pasted."""

from pathlib import Path
import sys
import traceback

import unreal

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from blueprint import BLUEPRINT_NAME, EVENT_NAMES, compiled_events
from cabinet_manifest import DESTINATION, TARGET, digest, write


def verify_and_save():
    unreal.load_module('BlueprintEditorLibrary')
    asset_path = TARGET + '/' + BLUEPRINT_NAME
    editor_assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    bp = editor_assets.load_asset(asset_path)
    assert isinstance(bp, unreal.Blueprint), asset_path
    graph = unreal.BlueprintEditorLibrary.find_event_graph(bp)
    assert graph, 'Blueprint has no EventGraph'
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    events = {EVENT_NAMES[side]: exists for side, exists in compiled_events(bp).items()}
    assert all(events.values()), f'Paste the door nodes and check the Blueprint compile output: {events}'
    assert editor_assets.save_loaded_asset(bp, False), asset_path
    package_file = DESTINATION / (BLUEPRINT_NAME + '.uasset')
    package_data = package_file.read_bytes()
    assert all(label.encode('ascii') in package_data for label in (*EVENT_NAMES.values(), 'MoveComponentTo', 'SelectVector'))
    return {'success': True, 'asset': bp.get_path_name(), 'events': events,
            'blueprint_sha256': digest(package_file), 'clipboard_graph_saved': True}


try:
    result = verify_and_save()
except Exception:
    result = {'success': False, 'error': traceback.format_exc()}
write(here / 'ue_blueprint_graph_report.json', result)
if result['success']:
    unreal.log('GLASS_COUNTER_SLIDING_GRAPH_SAVED')
else:
    unreal.log_error(result['error'])
