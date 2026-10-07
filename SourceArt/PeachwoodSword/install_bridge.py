import bpy, os, shutil, addon_utils
source=os.path.join(os.path.dirname(os.path.abspath(__file__)),'codex_blender_bridge.py')
target=bpy.utils.user_resource('SCRIPTS',path='addons',create=True)
dest=os.path.join(target,'codex_blender_bridge.py')
shutil.copy2(source,dest)
bpy.utils.refresh_script_paths()
addon_utils.enable('codex_blender_bridge',default_set=True,persistent=True)
bpy.ops.wm.save_userpref()
print('BRIDGE_INSTALLED',dest)
