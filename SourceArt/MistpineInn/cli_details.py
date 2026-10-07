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
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.cycles.samples = 128
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
# Object: CLI brass chandelier ring
bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.035, major_segments=48, minor_segments=12, location=(0.0, -1.0, 2.95))
obj = bpy.context.active_object
obj.name = 'CLI brass chandelier ring'
obj.rotation_euler = (math.radians(0.0), math.radians(0.0), math.radians(0.0))
obj.scale = (0.75, 0.75, 0.75)


# ���� Object Parenting ������������������������������������������������������������������������������
# (none)

# ���� Cameras ��������������������������������������������������������������������������������������������������
# (none)

# ���� Lights ����������������������������������������������������������������������������������������������������
# (none)

# ���� Keyframes ����������������������������������������������������������������������������������������������
# (none)

# ���� Render Output ��������������������������������������������������������������������������������������
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'D:\\UE\\Project\\HorrorGame\\SourceArt\\MistpineInn\\details.png'
scene.frame_set(1)

# Render single frame
bpy.ops.render.render(write_still=True)

print('Render complete: ' + 'D:\\UE\\Project\\HorrorGame\\SourceArt\\MistpineInn\\details.png')
