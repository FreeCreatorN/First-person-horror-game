"""Start the already-installed Blender MCP add-on in this GUI session."""
import importlib.util
from pathlib import Path
import sys

import bpy

assert not bpy.app.background
installed = Path('C:/Users/aa131/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/blender_mcp.py')
if not hasattr(bpy.types, 'blendermcp_server'):
    spec = importlib.util.spec_from_file_location('blender_mcp', installed)
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    addon.register()
bpy.ops.blendermcp.start_server()
