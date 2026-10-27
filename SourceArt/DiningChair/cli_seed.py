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
scene.render.resolution_y = 1100
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
# Object: HardwoodSeat
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, -0.02, 0.4425))
obj = bpy.context.active_object
obj.name = 'HardwoodSeat'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.24, 0.22, 0.0175)

# Object: FrontLeg
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-0.194, -0.188, 0.22))
obj = bpy.context.active_object
obj.name = 'FrontLeg'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.025, 0.025, 0.22)

# Object: RearBackPost
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-0.194, 0.21, 0.52))
obj = bpy.context.active_object
obj.name = 'RearBackPost'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.024, 0.024, 0.52)

# Object: FrontLeg.001
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.194, -0.188, 0.22))
obj = bpy.context.active_object
obj.name = 'FrontLeg.001'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.025, 0.025, 0.22)

# Object: RearBackPost.001
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.194, 0.21, 0.52))
obj = bpy.context.active_object
obj.name = 'RearBackPost.001'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.024, 0.024, 0.52)

# Object: CrestRail
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.265, 1.025))
obj = bpy.context.active_object
obj.name = 'CrestRail'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.235, 0.02, 0.035)


# ���� Object Parenting ������������������������������������������������������������������������������
# (none)

# ���� Cameras ��������������������������������������������������������������������������������������������������
cam_data = bpy.data.cameras.new(name='ChairCamera')
cam_data.type = 'PERSP'
cam_data.lens = 50.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.005
cam_data.clip_end = 1000.0
cam_obj = bpy.data.objects.new('ChairCamera', cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (1.5, -2.0, 1.35)
cam_obj.rotation_euler = (math.radians(75.0), math.radians(0.0), math.radians(35.0))
scene.camera = cam_obj


# ���� Lights ����������������������������������������������������������������������������������������������������
light_data = bpy.data.lights.new(name='PreviewKey', type='AREA')
light_data.energy = 300.0
light_data.color = (1.0, 1.0, 1.0)
light_data.size = 1.0
light_data.size_y = 1.0
light_data.shape = 'RECTANGLE'
light_obj = bpy.data.objects.new('PreviewKey', light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = (0.0, -2.0, 3.0)
light_obj.rotation_euler = (math.radians(30.0), math.radians(0.0), math.radians(0.0))


# ���� Keyframes ����������������������������������������������������������������������������������������������
# (none)

# ���� Render Output ��������������������������������������������������������������������������������������
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'D:\\UE\\Project\\HorrorGame\\SourceArt\\DiningChair\\Seed.png'
scene.frame_set(1)

# Render single frame
bpy.ops.render.render(write_still=True)

print('Render complete: ' + 'D:\\UE\\Project\\HorrorGame\\SourceArt\\DiningChair\\Seed.png')
