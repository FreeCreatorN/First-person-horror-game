"""Reopen the saved counter Blueprint in a small editor session for wiring."""
import json
from pathlib import Path
import sys

import unreal

folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder))
from blueprint import verify_blueprint

target = '/Game/Yastars/Mesh/GlassDisplayCounter'
data = json.loads((folder / '..' / 'Exports' / 'export_report.json').read_text(encoding='utf-8'))
assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
blueprint = assets.load_asset(target + '/BP_GlassDisplayCounter')
meshes = {row['name']: assets.load_asset(target + '/' + row['name']) for row in data['assets']}
verified = verify_blueprint(blueprint, meshes, data['doors'])
(folder / 'ue_blueprint_reopen_report.json').write_text(json.dumps(verified, indent=2), encoding='utf-8')
unreal.EditorPythonScriptingLibrary.set_keep_python_script_alive(True)
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([blueprint])
unreal.log('GLASS_COUNTER_BLUEPRINT_REOPENED')
