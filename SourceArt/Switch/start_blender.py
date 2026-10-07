import bpy
bpy.ops.preferences.addon_enable(module='blender_mcp')
bpy.context.preferences.addons['blender_mcp'].preferences.telemetry_consent = False
bpy.context.scene.blendermcp_port = 9876
if not getattr(bpy.types, 'blendermcp_server', None):
    bpy.ops.blendermcp.start_server()
