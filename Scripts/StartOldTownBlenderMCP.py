"""Start a session-local MCP listener without changing saved preferences."""
import bpy
try:
    import codex_blender_bridge
    codex_blender_bridge.stop()
except ImportError:
    pass
bpy.ops.preferences.addon_enable(module="blender_mcp")
bpy.context.scene.blendermcp_port = 9876
bpy.ops.blendermcp.start_server()
print("OLDTOWN_BLENDER_MCP_READY", flush=True)
