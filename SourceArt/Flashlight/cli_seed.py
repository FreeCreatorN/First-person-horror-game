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
scene.render.resolution_x = 1000
scene.render.resolution_y = 800
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
mat_M_Flashlight_Anodized = bpy.data.materials.new(name='M_Flashlight_Anodized')
mat_M_Flashlight_Anodized.use_nodes = True
bsdf_M_Flashlight_Anodized = mat_M_Flashlight_Anodized.node_tree.nodes.get('Principled BSDF')
if bsdf_M_Flashlight_Anodized:
    bsdf_M_Flashlight_Anodized.inputs['Base Color'].default_value = (0.026, 0.036, 0.045, 1.0)
    bsdf_M_Flashlight_Anodized.inputs['Metallic'].default_value = 0.8
    bsdf_M_Flashlight_Anodized.inputs['Roughness'].default_value = 0.31
    bsdf_M_Flashlight_Anodized.inputs['Specular IOR Level'].default_value = 0.5
    bsdf_M_Flashlight_Anodized.inputs['Alpha'].default_value = 1.0


# ���� Objects ��������������������������������������������������������������������������������������������������
# Object: Body
bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.12, vertices=32, location=(-0.01, 0.0, 0.0))
obj = bpy.context.active_object
obj.name = 'Body'
obj.rotation_euler = (math.radians(0.0), math.radians(90.0), math.radians(0.0))
obj.scale = (1.0, 1.0, 1.0)
if 'mat_M_Flashlight_Anodized' in dir():
    obj.data.materials.append(mat_M_Flashlight_Anodized)

# Object: Head
bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.04, vertices=32, location=(0.07, 0.0, 0.0))
obj = bpy.context.active_object
obj.name = 'Head'
obj.rotation_euler = (math.radians(0.0), math.radians(90.0), math.radians(0.0))
obj.scale = (1.0, 1.0, 1.0)
if 'mat_M_Flashlight_Anodized' in dir():
    obj.data.materials.append(mat_M_Flashlight_Anodized)


# ���� Object Parenting ������������������������������������������������������������������������������
# (none)

# ���� Cameras ��������������������������������������������������������������������������������������������������
cam_data = bpy.data.cameras.new(name='Camera_Flashlight')
cam_data.type = 'PERSP'
cam_data.lens = 50.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.001
cam_data.clip_end = 1000.0
cam_obj = bpy.data.objects.new('Camera_Flashlight', cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (0.25, -0.34, 0.23)
cam_obj.rotation_euler = (math.radians(63.0), math.radians(0.0), math.radians(38.0))
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
light_obj.location = (0.14, -0.18, 0.28)
light_obj.rotation_euler = (math.radians(35.0), math.radians(0.0), math.radians(30.0))


# ���� Keyframes ����������������������������������������������������������������������������������������������
# (none)

# ���� Render Output ��������������������������������������������������������������������������������������
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'D:\\UE\\Project\\HorrorGame\\SourceArt\\Flashlight\\Seed.png'
scene.frame_set(1)

# Render single frame
bpy.ops.render.render(write_still=True)

print('Render complete: ' + 'D:\\UE\\Project\\HorrorGame\\SourceArt\\Flashlight\\Seed.png')
