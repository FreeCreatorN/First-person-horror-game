"""Meter-scale finishes for the wooden display counter and its glass leaves.

The opaque materials use standard Principled inputs so Base Color, Roughness
and Metallic can be baked before the sliding leaves are moved to local origins.
The Wear color attribute uses red = 0 on broad faces and red = 1 at exposed
edges. The chips are procedural. The cabinet needs no external texture files.
"""

import bpy


def linear_color(rgb):
    return tuple(
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in rgb
    ) + (1.0,)


class Surface:
    def __init__(self, name, color, roughness, metallic=0.0):
        self.material = bpy.data.materials.new(name)
        self.material.use_nodes = True
        self.material.diffuse_color = linear_color(color)
        self.material.roughness = roughness
        self.material.metallic = metallic
        self.tree = self.material.node_tree
        self.tree.nodes.clear()
        self.shader = self.node('ShaderNodeBsdfPrincipled', 'Principled BSDF', 1160, 200)
        self.shader.inputs['Base Color'].default_value = linear_color(color)
        self.shader.inputs['Roughness'].default_value = roughness
        self.shader.inputs['Metallic'].default_value = metallic
        output = self.node('ShaderNodeOutputMaterial', 'Material Output', 1480, 200)
        self.connect(self.shader.outputs['BSDF'], output.inputs['Surface'])
        geometry = self.node('ShaderNodeNewGeometry', 'World position in meters', -1450, 300)
        self.position = geometry.outputs['Position']

    def node(self, kind, title, x, y):
        node = self.tree.nodes.new(kind)
        node.label = title
        node.location = (x, y)
        return node

    def connect(self, value, input_socket):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, input_socket)
        else:
            input_socket.default_value = value

    def coordinate_scale(self, title, scale, x, y):
        node = self.node('ShaderNodeVectorMath', title, x, y)
        node.operation = 'MULTIPLY'
        self.connect(self.position, node.inputs[0])
        node.inputs[1].default_value = scale
        return node.outputs['Vector']

    def noise(self, title, scale, detail, x, y, position=None, distortion=0.0):
        node = self.node('ShaderNodeTexNoise', title, x, y)
        node.inputs['Scale'].default_value = scale
        node.inputs['Detail'].default_value = detail
        node.inputs['Roughness'].default_value = 0.62
        node.inputs['Distortion'].default_value = distortion
        self.connect(self.position if position is None else position, node.inputs['Vector'])
        return node.outputs['Fac']

    def math(self, title, operation, a, b, x, y, c=None):
        node = self.node('ShaderNodeMath', title, x, y)
        node.operation = operation
        self.connect(a, node.inputs[0])
        self.connect(b, node.inputs[1])
        if c is not None:
            self.connect(c, node.inputs[2])
        return node.outputs[0]

    def remap(self, title, value, before, after, x, y):
        node = self.node('ShaderNodeMapRange', title, x, y)
        node.clamp = True
        node.interpolation_type = 'SMOOTHSTEP'
        self.connect(value, node.inputs['Value'])
        for name, amount in zip(('From Min', 'From Max', 'To Min', 'To Max'), before + after):
            node.inputs[name].default_value = amount
        return node.outputs['Result']

    def blend(self, title, factor, first, second, x, y):
        node = self.node('ShaderNodeMixRGB', title, x, y)
        self.connect(factor, node.inputs[0])
        self.connect(first, node.inputs[1])
        self.connect(second, node.inputs[2])
        return node.outputs[0]

    def bump(self, title, height, strength, distance, x, y):
        node = self.node('ShaderNodeBump', title, x, y)
        node.inputs['Strength'].default_value = strength
        node.inputs['Distance'].default_value = distance
        self.connect(height, node.inputs['Height'])
        self.connect(node.outputs['Normal'], self.shader.inputs['Normal'])

    def edge_wear(self):
        attribute = self.node('ShaderNodeVertexColor', 'Wear red channel', -1430, -830)
        attribute.layer_name = 'Wear'
        channels = self.node('ShaderNodeSeparateColor', 'Edge exposure from mesh', -1220, -830)
        self.connect(attribute.outputs['Color'], channels.inputs['Color'])
        return channels.outputs['Red']


def stained_wood(name, palette, chip_color, strength, *, interior=False, dark=False):
    surface = Surface(name, palette[1], .69 if interior else .53)
    surface.shader.inputs['IOR'].default_value = 1.46
    surface.shader.inputs['Specular IOR Level'].default_value = .33
    surface.shader.inputs['Coat Weight'].default_value = .06 if interior else .19
    surface.shader.inputs['Coat Roughness'].default_value = .44

    # Small Z scale makes grain vertical across both the front and the sides.
    # The cabinet bed and the storage shelf run the fibers along the width.
    grain_vector = surface.coordinate_scale('Long wood fibers', (.075, 1., 1.) if interior else (1., 1., .067), -1230, 520)
    wide_grain = surface.noise('Broad streaks under the stain', 38, 2.6, -1000, 570, grain_vector, .44)
    fine_grain = surface.noise('Thin cross-contrast fibers', 245, 2., -1000, 295, grain_vector, .18)
    dark_fibers = surface.remap('Individual dark pores', fine_grain, (.23, .49), (.0, 1.), -775, 325)
    grain_factor = surface.math('Variegated straight grain', 'MULTIPLY_ADD', dark_fibers, .29, -550, 530, wide_grain)
    grain_factor = surface.remap('Grain tonal range', grain_factor, (.32, .96), (.08, .91), -330, 530)
    grain_color = surface.blend('Red brown stained veneer', grain_factor, linear_color(palette[0]),
                                linear_color(palette[1]), -105, 555)

    blotches = surface.noise('Broad polish and age variation', 5.5, 2.4, -1000, -30)
    stain = surface.remap('Small muted patches', blotches, (.37, .72), (.025, .24), -570, 180)
    aged_color = surface.blend('Faded stain over the wood', stain, grain_color, linear_color(palette[2]), 145, 520)

    scratch_vector = surface.coordinate_scale('Thin linear scratches', (1., 1., .235), -1230, -395)
    scratch_noise = surface.noise('Fine scored varnish', 358, 1.7, -1000, -325, scratch_vector)
    scratches = surface.remap('Scattered fine marks', scratch_noise, (.70, .78), (0., .43), -560, -50)
    chips = surface.noise('Interrupted wear flakes', 92, 2.2, -1000, -610, distortion=.17)
    specks = surface.noise('Broken edges to the flakes', 350, 1.6, -1000, -880)
    chip_field = surface.math('Fragmented chip boundaries', 'MULTIPLY_ADD', specks, .24, -780, -540, chips)
    chip_mask = surface.remap('Paint loss near exposed edges', chip_field, (.68, .85), (0., 1.), -560, -390)
    exposure = surface.edge_wear()
    z_axis = surface.node('ShaderNodeSeparateXYZ', 'Height from the floor', -1210, -1120)
    surface.connect(surface.position, z_axis.inputs['Vector'])
    foot_multiplier = .42 if dark else (.05 if interior else .30)
    floorwear = surface.remap('More wear near the plinth', z_axis.outputs['Z'], (.025, .24), (foot_multiplier, 0.), -990, -1170)
    exposure = surface.math('Edge and plinth exposure', 'MAXIMUM', exposure, floorwear, -550, -740)
    wear = surface.math('Local finish loss', 'MULTIPLY', chip_mask, exposure, -315, -410)
    abrasion = surface.math('Varnish damage', 'MAXIMUM', scratches, wear, -95, -120)
    abrasion = surface.math('Wear strength', 'MULTIPLY', abrasion, strength, 100, -100)
    rubbed_wood = surface.blend('Pale exposed veneer', specks, linear_color(chip_color[0]),
                                linear_color(chip_color[1]), 80, 200)
    color = surface.blend('Aged varnish and exposed grain', abrasion, aged_color, rubbed_wood, 600, 480)
    surface.connect(color, surface.shader.inputs['Base Color'])

    roughness_limits = (.52, .70) if interior else (.43, .62)
    roughness = surface.remap('Varnish roughness variation', blotches, (.20, .82), roughness_limits, 400, 120)
    roughness = surface.math('Wear is rougher than varnish', 'MULTIPLY_ADD', abrasion, .19, 780, 140, roughness)
    surface.connect(roughness, surface.shader.inputs['Roughness'])
    fiber_height = surface.math('Scored varnish over wood pores', 'MULTIPLY_ADD', abrasion, -.29, 520, -190, fine_grain)
    surface.bump('Fine wood fiber relief', fiber_height, .20, .00037, 850, -200)
    return surface.material


def weathered_alloy(name, brass=False):
    if brass:
        palette = ((.27, .22, .16), (.52, .43, .30), (.66, .61, .49))
    else:
        palette = ((.26, .231, .196), (.46, .425, .37), (.66, .66, .635))
    surface = Surface(name, palette[1], .48, .72)
    mottling = surface.noise('Shadowed patina in the metal', 20, 3, -1200, 560, distortion=.14)
    granules = surface.noise('Fine oxidation', 260, 2.4, -1200, 295)
    pitting = surface.noise('Tiny stippled corrosion', 950, 2, -1200, 30)
    weathering = surface.math('Broken patina texture', 'MULTIPLY_ADD', granules, .29, -950, 420, mottling)
    oxide = surface.remap('Patina tonal range', weathering, (.46, .86), (.08, .86), -730, 485)
    patina_color = surface.blend('Warm bronze and dark oxide', oxide, linear_color(palette[1]),
                                 linear_color(palette[0]), -450, 510)

    edge = surface.edge_wear()
    flakes = surface.noise('Rubbing along the exposed lip', 118, 3, -1200, -330)
    bright_mask = surface.remap('Small bright chips', flakes, (.52, .78), (.065, .91), -940, -220)
    polish = surface.math('Exposed corners take the rub', 'MULTIPLY', bright_mask, edge, -690, -220)
    line_coords = surface.coordinate_scale('Longer sanding marks', (1., 1., .27), -1260, -575)
    lines = surface.noise('Fine scratches in the alloy', 475, 1.4, -1010, -580, line_coords)
    lines = surface.remap('Infrequent sanding marks', lines, (.75, .83), (0., .23), -760, -555)
    polish = surface.math('Receives light on the rubbed parts', 'MAXIMUM', polish, lines, -450, -165)
    color = surface.blend('Bronze with rubbed silver edges', polish, patina_color, linear_color(palette[2]), 500, 490)
    surface.connect(color, surface.shader.inputs['Base Color'])

    roughness = surface.remap('Oxidized areas scatter more light', oxide, (.0, 1.), (.37, .68), -200, 130)
    roughness = surface.math('Polished edges settle the roughness', 'MULTIPLY_ADD', polish, -.17, 575, 155, roughness)
    surface.connect(roughness, surface.shader.inputs['Roughness'])
    metallic = surface.remap('Oxide has lower metal response', oxide, (0., 1.), (.79, .44), 320, -105)
    metallic = surface.math('Exposed substrate is more metallic', 'MULTIPLY_ADD', polish, .12, 795, -80, metallic)
    surface.connect(metallic, surface.shader.inputs['Metallic'])
    surface.bump('Tiny oxidation pits', pitting, .17, .00018, 860, -320)
    return surface.material


def feet_rubber():
    surface = Surface('M_Counter_CharcoalRubberFeet', (.14, .12, .106), .81)
    speckle = surface.noise('Unevenly worn dark rubber', 81, 2.4, -1000, 360)
    color = surface.blend('Rubber color variation', speckle, linear_color((.09, .079, .068)),
                          linear_color((.19, .169, .144)), 470, 400)
    surface.connect(color, surface.shader.inputs['Base Color'])
    pores = surface.noise('Tiny rubber pores', 800, 2, -1000, -70)
    surface.bump('Fine rubber pores', pores, .19, .00025, 825, -110)
    return surface.material


def clear_glass(edge=False):
    name = 'M_Counter_GlassPolishedEdge' if edge else 'M_Counter_ClearDisplayGlass'
    # Principled transmission and the mesh's thickness produce reflections and
    # refraction in Cycles. The subdued tint leaves small merchandise legible.
    tone = (.75, .91, .84) if edge else (.945, .981, .962)
    base_roughness = .054 if edge else .037
    surface = Surface(name, tone, base_roughness)
    surface.material.diffuse_color = (*linear_color(tone)[:3], .22 if edge else .13)
    surface.shader.inputs['Transmission Weight'].default_value = 1.0
    surface.shader.inputs['IOR'].default_value = 1.45
    wipe_coords = surface.coordinate_scale('Faint old wipe direction', (1., .95, .18), -1200, 465)
    wiped = surface.noise('Faint handling and wiping variation', 94, 2, -955, 465, wipe_coords)
    fine_wear = surface.remap('Occasional mellow scratch highlights', wiped, (.65, .79),
                              (base_roughness, .125 if edge else .086), -550, 480)
    surface.connect(fine_wear, surface.shader.inputs['Roughness'])
    if hasattr(surface.material, 'use_raytrace_refraction'):
        surface.material.use_raytrace_refraction = True
    return surface.material


def create_counter_materials():
    """Return wood, hardware and clear glass using the project material keys."""
    return {
        'wood_red': stained_wood('M_Counter_RedBrownVarnishedVeneer',
                                 ((.326, .152, .096), (.584, .307, .194), (.407, .254, .168)),
                                 ((.510, .357, .243), (.670, .552, .413)), .95),
        'wood_dark': stained_wood('M_Counter_DarkWornWoodTrim',
                                  ((.221, .105, .068), (.438, .222, .140), (.305, .228, .168)),
                                  ((.393, .305, .218), (.653, .536, .401)), 1., dark=True),
        'wood_inside': stained_wood('M_Counter_DustyPaleInterior',
                                    ((.419, .353, .269), (.704, .631, .529), (.570, .482, .365)),
                                    ((.497, .387, .270), (.744, .650, .525)), .68, interior=True),
        'metal': weathered_alloy('M_Counter_WeatheredBronzeFrame'),
        'brass': weathered_alloy('M_Counter_OldBrassHardware', brass=True),
        'rubber': feet_rubber(),
        'glass': clear_glass(),
        'glass_edge': clear_glass(edge=True),
    }
