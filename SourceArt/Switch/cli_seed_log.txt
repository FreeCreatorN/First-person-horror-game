#!/usr/bin/env python3
"""Auto-generated Blender Python script from blender-cli."""

import bpy
import math
import os

# ���� Clear Default Scene ����������������������������������������������������������������������������
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ���� Scene Settings ������������������������������������������������������������������������������������
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
scene.frame_start = 1
scene.frame_end = 250
scene.frame_current = 1
scene.render.fps = 24

# ���� Render Settings ����������������������������������������������������������������������������������
scene.render.engine = 'CYCLES'
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.cycles.samples = 24
scene.cycles.use_denoising = True

# ���� World Settings ������������������������������������������������������������������������������������
world = bpy.data.worlds.get('World')
if world is None:
    world = bpy.data.worlds.new('World')
    scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs[0].default_value = (0.05, 0.05, 0.05, 1.0)

# ���� Materials ����������������������������������������������������������������������������������������������
mat_M_Switch_Ivory = bpy.data.materials.new(name='M_Switch_Ivory')
mat_M_Switch_Ivory.use_nodes = True
bsdf_M_Switch_Ivory = mat_M_Switch_Ivory.node_tree.nodes.get('Principled BSDF')
if bsdf_M_Switch_Ivory:
    bsdf_M_Switch_Ivory.inputs['Base Color'].default_value = (0.72, 0.7, 0.64, 1.0)
    bsdf_M_Switch_Ivory.inputs['Metallic'].default_value = 0.0
    bsdf_M_Switch_Ivory.inputs['Roughness'].default_value = 0.29
    bsdf_M_Switch_Ivory.inputs['Specular IOR Level'].default_value = 0.5
    bsdf_M_Switch_Ivory.inputs['Alpha'].default_value = 1.0


# ���� Objects ��������������������������������������������������������������������������������������������������
# Object: Faceplate
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, -0.003, 0.0))
obj = bpy.context.active_object
obj.name = 'Faceplate'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.043, 0.003, 0.043)
if 'mat_M_Switch_Ivory' in dir():
    obj.data.materials.append(mat_M_Switch_Ivory)

# Object: Rocker
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, -0.006, 0.0))
obj = bpy.context.active_object
obj.name = 'Rocker'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.027, 0.006, 0.029)
if 'mat_M_Switch_Ivory' in dir():
    obj.data.materials.append(mat_M_Switch_Ivory)


# ���� Object Parenting ������������������������������������������������������������������������������
# (none)

# ���� Cameras ��������������������������������������������������������������������������������������������������
cam_data = bpy.data.cameras.new(name='Camera_Switch')
cam_data.type = 'ORTHO'
cam_data.lens = 50.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.001
cam_data.clip_end = 1000.0
cam_obj = bpy.data.objects.new('Camera_Switch', cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (0.12, -0.23, 0.1)
cam_obj.rotation_euler = (math.radians(70.0), math.radians(0.0), math.radians(28.0))
scene.camera = cam_obj


# ���� Lights ����������������������������������������������������������������������������������������������������
light_data = bpy.data.lights.new(name='Studio_Key', type='AREA')
light_data.energy = 15.0
light_data.color = (1.0, 1.0, 1.0)
light_data.size = 1.0
light_data.size_y = 1.0
light_data.shape = 'RECTANGLE'
light_obj = bpy.data.objects.new('Studio_Key', light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = (0.1, -0.25, 0.2)
light_obj.rotation_euler = (math.radians(50.0), math.radians(0.0), math.radians(20.0))


# ���� Keyframes ����������������������������������������������������������������������������������������������
# (none)

# ���� Render Output ��������������������������������������������������������������������������������������
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'D:\\UE\\Project\\HorrorGame\\SourceArt\\Switch\\cli_seed.py'
scene.frame_set(1)

# Render single frame
bpy.ops.render.render(write_still=True)

print('Render complete: ' + 'D:\\UE\\Project\\HorrorGame\\SourceArt\\Switch\\cli_seed.py')
