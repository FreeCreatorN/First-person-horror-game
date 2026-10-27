def node(nodes, kind, name=None):
    n = nodes.new(kind)
    if name:
        n.name = name
        n.label = name
    return n
def vector_scale(nodes, links, source, scale):
    n = node(nodes, 'ShaderNodeVectorMath')
    n.operation = 'MULTIPLY'
    links.new(source, n.inputs[0])
    n.inputs[1].default_value = scale
    return n.outputs[0]
def math_node(nodes, links, operation, a, b):
    n = node(nodes, 'ShaderNodeMath')
    n.operation = operation
    for value, socket in [(a, n.inputs[0]), (b, n.inputs[1])]:
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            links.new(value, socket)
    return n.outputs[0]
def ramp(nodes, links, source, stops):
    n = node(nodes, 'ShaderNodeValToRGB')
    cr = n.color_ramp
    while len(cr.elements) > 2:
        cr.elements.remove(cr.elements[-1])
    for i, (position, color) in enumerate(stops):
        e = cr.elements[i] if i < 2 else cr.elements.new(position)
        e.position = position
        e.color = (*color, 1)
    links.new(source, n.inputs['Fac'])
    return n.outputs['Color']
def noise(nodes, links, source, scale=2, detail=3):
    n = node(nodes, 'ShaderNodeTexNoise')
    links.new(source, n.inputs['Vector'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = 0.7
    return n.outputs['Fac']
def wood(name, endgrain=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (0.16, 0.082, 0.031, 1)
    ns = m.node_tree.nodes
    ls = m.node_tree.links
    ns.clear()
    p = node(ns, 'ShaderNodeBsdfPrincipled', 'Wood surface')
    out = node(ns, 'ShaderNodeOutputMaterial')
    ls.new(p.outputs['BSDF'], out.inputs['Surface'])
    p.inputs['Roughness'].default_value = 0.66
    p.inputs['Metallic'].default_value = 0
    coord = node(ns, 'ShaderNodeAttribute', 'Local grain orientation')
    coord.attribute_name = 'WoodCoord'
    tone = node(ns, 'ShaderNodeAttribute', 'Individual board tone')
    tone.attribute_name = 'WoodTone'
    wear = node(ns, 'ShaderNodeAttribute', 'Wear amount')
    wear.attribute_name = 'Wear'
    stretched = vector_scale(ns, ls, coord.outputs['Vector'], (2.8, 95, 95))
    grain = noise(ns, ls, stretched, 2.2, 3.5)
    if endgrain:
        wave = node(ns, 'ShaderNodeTexWave')
        wave.wave_type = 'RINGS'
        wave.rings_direction = 'X'
        ls.new(coord.outputs['Vector'], wave.inputs['Vector'])
        wave.inputs['Scale'].default_value = 620
        wave.inputs['Distortion'].default_value = 5
        wave.inputs['Detail Scale'].default_value = 1.4
        grain = wave.outputs['Fac']
    color = ramp(ns, ls, grain, [(0.18, (0.041, 0.019, 0.008)), (0.42, (0.095, 0.043, 0.016)), (0.62, (0.162, 0.083, 0.032)), (0.82, (0.23, 0.138, 0.063))])
    broad = noise(ns, ls, coord.outputs['Vector'], 7, 4)
    tint = ramp(ns, ls, broad, [(0.12, (0.48, 0.39, 0.31)), (0.8, (1.0, 0.93, 0.83))])
    mix = node(ns, 'ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 0.48
    ls.new(color, mix.inputs[1])
    ls.new(tint, mix.inputs[2])
    scaled = node(ns, 'ShaderNodeVectorMath')
    scaled.operation = 'SCALE'
    ls.new(mix.outputs[0], scaled.inputs[0])
    ls.new(tone.outputs['Fac'], scaled.inputs['Scale'])
    scratches = noise(ns, ls, vector_scale(ns, ls, coord.outputs['Vector'], (32, 650, 47)), 2, 1)
    scratches = math_node(ns, ls, 'MULTIPLY', math_node(ns, ls, 'GREATER_THAN', scratches, 0.71), wear.outputs['Fac'])
    mix = node(ns, 'ShaderNodeMixRGB', 'Fine worn scratches')
    ls.new(scratches, mix.inputs[0])
    ls.new(scaled.outputs[0], mix.inputs[1])
    mix.inputs[2].default_value = (0.21, 0.12, 0.054, 1)
    geom = node(ns, 'ShaderNodeNewGeometry')
    edge = node(ns, 'ShaderNodeMapRange')
    ls.new(geom.outputs['Pointiness'], edge.inputs['Value'])
    edge.inputs['From Min'].default_value = 0.505
    edge.inputs['From Max'].default_value = 0.57
    edge.inputs['To Max'].default_value = 0.28
    worn = node(ns, 'ShaderNodeMixRGB', 'Soft edge wear')
    ls.new(math_node(ns, ls, 'MULTIPLY', edge.outputs[0], wear.outputs['Fac']), worn.inputs[0])
    ls.new(mix.outputs[0], worn.inputs[1])
    worn.inputs[2].default_value = (0.245, 0.15, 0.075, 1)
    distance = node(ns, 'ShaderNodeVectorMath')
    distance.operation = 'DISTANCE'
    ls.new(geom.outputs['Position'], distance.inputs[0])
    distance.inputs[1].default_value = (0.29, 0.075, 0.77)
    dist = math_node(ns, ls, 'ABSOLUTE', math_node(ns, ls, 'SUBTRACT', distance.outputs['Value'], 0.055), 0)
    ring = math_node(ns, ls, 'LESS_THAN', dist, 0.0022)
    xyz = node(ns, 'ShaderNodeSeparateXYZ')
    ls.new(geom.outputs['Position'], xyz.inputs[0])
    ring = math_node(ns, ls, 'MULTIPLY', ring, math_node(ns, ls, 'GREATER_THAN', xyz.outputs['Z'], 0.73))
    ring = math_node(ns, ls, 'MULTIPLY', ring, math_node(ns, ls, 'MULTIPLY', broad, 0.38))
    stain = node(ns, 'ShaderNodeMixRGB', 'Faded cup mark')
    ls.new(ring, stain.inputs[0])
    ls.new(worn.outputs[0], stain.inputs[1])
    stain.inputs[2].default_value = (0.04, 0.02, 0.009, 1)
    ls.new(stain.outputs[0], p.inputs['Base Color'])
    rough = math_node(ns, ls, 'ADD', math_node(ns, ls, 'MULTIPLY', broad, 0.23), 0.53)
    ls.new(rough, p.inputs['Roughness'])
    pores = noise(ns, ls, vector_scale(ns, ls, coord.outputs['Vector'], (3, 800, 800)), 1.8, 2)
    bump = node(ns, 'ShaderNodeBump', 'Fine wood pores')
    bump.inputs['Strength'].default_value = 0.23
    bump.inputs['Distance'].default_value = 0.00023
    ls.new(pores, bump.inputs['Height'])
    ls.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m
