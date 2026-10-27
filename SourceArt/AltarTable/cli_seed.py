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
scene.render.resolution_x = 1200
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
# (none)

# ���� Objects ��������������������������������������������������������������������������������������������������
# Object: LongTabletop
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.928))
obj = bpy.context.active_object
obj.name = 'LongTabletop'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (1.1, 0.3, 0.022)

# Object: SquareLeg
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-0.9, -0.215, 0.455))
obj = bpy.context.active_object
obj.name = 'SquareLeg'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.038, 0.038, 0.455)

# Object: SquareLeg.001
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-0.9, 0.215, 0.455))
obj = bpy.context.active_object
obj.name = 'SquareLeg.001'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.038, 0.038, 0.455)

# Object: SquareLeg.002
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.9, -0.215, 0.455))
obj = bpy.context.active_object
obj.name = 'SquareLeg.002'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.038, 0.038, 0.455)

# Object: SquareLeg.003
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.9, 0.215, 0.455))
obj = bpy.context.active_object
obj.name = 'SquareLeg.003'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.038, 0.038, 0.455)

# Object: FrontApron
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, -0.226, 0.82))
obj = bpy.context.active_object
obj.name = 'FrontApron'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.94, 0.016, 0.085)


# ���� Object Parenting ������������������������������������������������������������������������������
# (none)

# ���� Cameras ��������������������������������������������������������������������������������������������������
cam_data = bpy.data.cameras.new(name='Camera_Altar')
cam_data.type = 'PERSP'
cam_data.lens = 50.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.01
cam_data.clip_end = 1000.0
cam_obj = bpy.data.objects.new('Camera_Altar', cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (2.8, -3.1, 1.8)
cam_obj.rotation_euler = (math.radians(73.0), math.radians(0.0), math.radians(42.0))
scene.camera = cam_obj


# ���� Lights ����������������������������������������������������������������������������������������������������
light_data = bpy.data.lights.new(name='Preview_Key', type='AREA')
light_data.energy = 250.0
light_data.color = (1.0, 1.0, 1.0)
light_data.size = 1.0
light_data.size_y = 1.0
light_data.shape = 'RECTANGLE'
light_obj = bpy.data.objects.new('Preview_Key', light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = (0.7, -2.0, 3.0)
light_obj.rotation_euler = (math.radians(35.0), math.radians(0.0), math.radians(15.0))


# ���� Keyframes ����������������������������������������������������������������������������������������������
# (none)

# ���� Render Output ��������������������������������������������������������������������������������������
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'D:\\UE\\Project\\HorrorGame\\SourceArt\\AltarTable\\Seed.png'
scene.frame_set(1)

# Render single frame
bpy.ops.render.render(write_still=True)

print('Render complete: ' + 'D:\\UE\\Project\\HorrorGame\\SourceArt\\AltarTable\\Seed.png')
