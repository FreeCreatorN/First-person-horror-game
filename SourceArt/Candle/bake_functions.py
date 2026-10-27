def input_socket(node, identifier):
    return next(socket for socket in node.inputs
                if socket.identifier == identifier or socket.name == identifier)


def bake_channel(obj, channel, resolution):
    assert channel in ('BaseColor', 'Roughness', 'Normal', 'Metallic'), channel
    name = texture_prefix + '_' + channel
    image = bpy.data.images.new(name, width=resolution, height=resolution,
                                alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'sRGB' if channel == 'BaseColor' else 'Non-Color'
    image.file_format = 'PNG'
    image.filepath_raw = str(TEXTURES / (name + '.png'))
    materials = list(dict.fromkeys(slot.material for slot in obj.material_slots if slot.material))
    original_outputs, temporary_nodes = [], []
    disk_image = None
    channel_started = time.perf_counter()
    log('Bake begin ' + channel + ' ' + str(resolution))
    try:
        for material in materials:
            assert material.use_nodes, material.name
            material.use_fake_user = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
            output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
            surface = output.inputs[0]
            original_outputs.append((material, surface, [(link.from_socket, link.to_socket) for link in surface.links]))
            target = nodes.new('ShaderNodeTexImage')
            target.image = image
            target.label = 'Temporary bake target'
            temporary_nodes.append((material, target))
            if channel != 'Normal':
                source = input_socket(shader, {'BaseColor': 'Base Color',
                                               'Roughness': 'Roughness',
                                               'Metallic': 'Metallic'}[channel])
                emission = nodes.new('ShaderNodeEmission')
                temporary_nodes.append((material, emission))
                emission.inputs[1].default_value = 1.
                if source.is_linked:
                    links.new(source.links[0].from_socket, emission.inputs[0])
                else:
                    value = source.default_value
                    emission.inputs[0].default_value = (value, value, value, 1.) if channel in ('Roughness', 'Metallic') else value
                links.new(emission.outputs[0], surface)
            for node in nodes:
                node.select = False
            target.select = True
            nodes.active = target
        bpy.ops.object.select_all(action='DESELECT')
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.object.bake(type='NORMAL' if channel == 'Normal' else 'EMIT',
                                     margin=16, margin_type='EXTEND', use_selected_to_active=False,
                                     normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y',
                                     normal_b='POS_Z', target='IMAGE_TEXTURES', use_clear=True)
        assert result == {'FINISHED'} and image.has_data, (channel, result)
        image.save()
        path = Path(image.filepath_raw)
        assert path.is_file() and path.stat().st_size > 1024, str(path)
        disk_image = bpy.data.images.load(str(path), check_existing=False)
        disk_image.colorspace_settings.name = image.colorspace_settings.name
        disk_size = tuple(disk_image.size)
        _first_pixel = disk_image.pixels[0]  # Force the lazy PNG decode after color-space changes.
        assert disk_image.has_data and disk_size == tuple(image.size), (name, disk_size)
        width, height = disk_image.size
        channels = disk_image.channels
        pixels = array('f', [0.]) * (width * height * channels)
        samples = []
        try:
            disk_image.pixels.foreach_get(pixels)
            for y in range(height // 64, height, max(1, height // 32)):
                for x in range(width // 64, width, max(1, width // 32)):
                    index = (y * width + x) * channels
                    samples.append(tuple(pixels[index + i] for i in range(3)))
        finally:
            del pixels
        minimum = [min(p[i] for p in samples) for i in range(3)]
        maximum = [max(p[i] for p in samples) for i in range(3)]
        # A pure black metallic atlas is valid for any nonmetallic surface.
        if channel != 'Metallic':
            assert max(maximum) > .001, (channel, minimum, maximum)
        if channel in ('Metallic', 'Roughness'):
            assert all(max(p) - min(p) < .002 for p in samples), (channel, 'Data map is not grayscale')
        report['bakes'][name] = {
            'path': str(path), 'resolution': list(disk_image.size),
            'colorspace': disk_image.colorspace_settings.name,
            'bytes': path.stat().st_size, 'sha256': sha256(path),
            'sample_min_rgb': minimum, 'sample_max_rgb': maximum,
            'method': 'NORMAL' if channel == 'Normal' else 'EMIT from Principled input',
            'reloaded_from_saved_png': True,
            'elapsed_seconds': time.perf_counter() - channel_started,
        }
        disk_image.filepath_raw = '//Textures/' + path.name
        write_report()
    finally:
        for material, surface, original_links in original_outputs:
            for link in list(surface.links):
                material.node_tree.links.remove(link)
            for from_socket, to_socket in original_links:
                material.node_tree.links.new(from_socket, to_socket)
        for material, node in temporary_nodes:
            material.node_tree.nodes.remove(node)
    assert disk_image, name
    if image.users == 0:
        bpy.data.images.remove(image)
    disk_image.name = name
    log('Bake complete ' + channel + ' seconds=' + str(round(time.perf_counter() - channel_started, 1)))
    return disk_image


def baked_material(images):
    material = bpy.data.materials.new(texture_prefix + '_Baked')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (520, 60)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (200, 80)
    input_socket(shader, 'Metallic').default_value = 0.
    # This atlas contains both wax and metal, so unmasked SSS would also affect
    # the holder. Preserve a neutral PBR material and no authored light emission.
    input_socket(shader, 'Subsurface Weight').default_value = 0.
    input_socket(shader, 'Emission Color').default_value = (0., 0., 0., 1.)
    input_socket(shader, 'Emission Strength').default_value = 0.
    links.new(shader.outputs[0], output.inputs[0])
    for channel, y in (('BaseColor', 260), ('Roughness', -20), ('Metallic', -300), ('Normal', -580)):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = images[channel]
        texture.label = channel
        texture.location = (-650, y)
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            normal.space = 'TANGENT'
            normal.location = (-170, -500)
            links.new(texture.outputs[0], normal.inputs[1])
            links.new(normal.outputs[0], input_socket(shader, 'Normal'))
        else:
            links.new(texture.outputs[0], input_socket(shader, {'BaseColor': 'Base Color',
                                                               'Roughness': 'Roughness',
                                                               'Metallic': 'Metallic'}[channel]))
    assert input_socket(shader, 'Metallic').is_linked, 'Baked metallic atlas is not connected'
    report['baked_material'] = {'name': material.name, 'emission_connected': False,
                               'emission_strength': 0., 'subsurface_weight': 0.,
                               'metallic_texture_connected': True,
                               'images': {key: image.name for key, image in images.items()}}
    return material


