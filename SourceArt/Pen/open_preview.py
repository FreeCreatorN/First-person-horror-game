"""Open the completed source in Blender, frame it, and connect the session MCP."""
import bpy
from mathutils import Vector
def arrange():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type!='VIEW_3D':continue
            sp=a.spaces.active;sp.clip_start=.00001;sp.clip_end=100
            sp.shading.type='MATERIAL';sp.shading.studio_light='studio.exr';sp.shading.studiolight_intensity=.8
            sp.overlay.show_overlays=False
            r=sp.region_3d;r.view_perspective='ORTHO';r.view_rotation=bpy.context.scene.camera.matrix_world.to_quaternion()
            r.view_location=Vector((0,0,.071));r.view_distance=.18;r.update();a.tag_redraw()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    try:
        bpy.ops.preferences.addon_enable(module='blender_mcp')
        bpy.context.scene.blendermcp_port=9876
        bpy.ops.blendermcp.start_server()
        print('PEN_BLENDER_MCP_READY',flush=True)
    except Exception as exc:
        print('PEN_MCP_INFO '+str(exc),flush=True)
    return None
bpy.app.timers.register(arrange,first_interval=1.5)
