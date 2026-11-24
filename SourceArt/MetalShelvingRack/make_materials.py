"""Meter-scale procedural metal finishes for the shelving rack."""

import bpy


def _linear_rgba(rgb):
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb) + (1.0,)


class _Surface:
    def __init__(self, name, color, roughness, metallic):
        self.material = bpy.data.materials.new(name)
        self.material.use_nodes = True
        self.material.diffuse_color = _linear_rgba(color)
        self.material.roughness = roughness
        self.material.metallic = metallic
        tree = self.material.node_tree
        self.nodes = tree.nodes
        self.links = tree.links
        self.nodes.clear()
        self.bsdf = self.node("ShaderNodeBsdfPrincipled", "Surface finish", 880, 100)
        self.bsdf.inputs["Base Color"].default_value = _linear_rgba(color)
        self.bsdf.inputs["Roughness"].default_value = roughness
        self.bsdf.inputs["Metallic"].default_value = metallic
        output = self.node("ShaderNodeOutputMaterial", "Material Output", 1190, 100)
        self.links.new(self.bsdf.outputs["BSDF"], output.inputs["Surface"])
        # Position in meters keeps the powder grain consistent across the rack.
        coords = self.node("ShaderNodeNewGeometry", "Position in scene units (m)", -1130, 180)
        self.position = coords.outputs["Position"]

    def node(self, type_name, label, x, y):
        node = self.nodes.new(type_name)
        node.label = label
        node.location = (x, y)
        return node

    def connect(self, value, socket):
        if isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, socket)
        else:
            socket.default_value = value

    def noise(self, name, scale, detail, x, y):
        node = self.node("ShaderNodeTexNoise", name, x, y)
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = 0.66
        self.links.new(self.position, node.inputs["Vector"])
        return node.outputs["Fac"]

    def math(self, name, op, first, second, x, y):
        node = self.node("ShaderNodeMath", name, x, y)
        node.operation = op
        self.connect(first, node.inputs[0])
        self.connect(second, node.inputs[1])
        return node.outputs[0]

    def remap(self, name, value, source, target, x, y):
        node = self.node("ShaderNodeMapRange", name, x, y)
        node.interpolation_type = "SMOOTHSTEP"
        node.clamp = True
        self.connect(value, node.inputs["Value"])
        for label, limit in zip(("From Min", "From Max", "To Min", "To Max"), source + target):
            node.inputs[label].default_value = limit
        return node.outputs["Result"]

    def tint(self, name, factor, first, second, x, y):
        node = self.node("ShaderNodeMixRGB", name, x, y)
        self.connect(factor, node.inputs[0])
        self.connect(first, node.inputs[1])
        self.connect(second, node.inputs[2])
        return node.outputs[0]

    def bump(self, name, height, strength, distance, x, y):
        node = self.node("ShaderNodeBump", name, x, y)
        node.inputs["Strength"].default_value = strength
        node.inputs["Distance"].default_value = distance
        self.links.new(height, node.inputs["Height"])
        self.links.new(node.outputs["Normal"], self.bsdf.inputs["Normal"])


def _paint(name, palette, chip_multiplier):
    surface = _Surface(name, palette[1], 0.62, 0.06)
    tonal = surface.noise("Soft patches in the old paint", 11, 3, -900, 310)
    patches = surface.noise("Scattered chips", 76, 2, -900, 40)
    flecks = surface.noise("Broken chip outlines", 260, 3, -900, -235)
    grain = surface.noise("Fine powder coat grain", 1850, 2, -900, -520)

    attr = surface.node("ShaderNodeVertexColor", "Wear R: face 0, exposed rim 1", -1130, -850)
    attr.layer_name = "Wear"
    channels = surface.node("ShaderNodeSeparateColor", "Edge exposure mask", -900, -850)
    surface.links.new(attr.outputs["Color"], channels.inputs["Color"])
    edge = channels.outputs["Red"]

    patch_part = surface.math("Chip clustering", "MULTIPLY", patches, 0.72, -675, 40)
    fleck_part = surface.math("Chip edge breakup", "MULTIPLY", flecks, 0.28, -675, -160)
    breakup = surface.math("Irregular paint loss", "ADD", patch_part, fleck_part, -475, 40)
    edge_chips = surface.remap("Chips at bends and lips", breakup, (0.61, 0.70), (0.0, 1.0), -260, 25)
    edge_chips = surface.math("Keep wear on exposed steel", "MULTIPLY", edge_chips, edge, -40, 10)
    face_pins = surface.remap("A few pinpricks on broad faces", breakup, (0.77, 0.82), (0.0, 0.56), -260, -260)
    wear = surface.math("Combined sparse paint loss", "MAXIMUM", edge_chips, face_pins, 150, 0)
    wear = surface.math("Wear amount", "MULTIPLY", wear, chip_multiplier, 335, 0)

    paint = surface.tint("Warm gray paint", tonal, _linear_rgba(palette[0]), _linear_rgba(palette[1]), -260, 320)
    rust = surface.tint("Brown oxide and darker bare steel", flecks, _linear_rgba((0.26, 0.17, 0.12)),
                        _linear_rgba((0.52, 0.32, 0.19)), 110, 315)
    color = surface.tint("Paint and small oxidized edges", wear, paint, rust, 600, 300)
    surface.links.new(color, surface.bsdf.inputs["Base Color"])
    worn_roughness = surface.math("Rougher oxide", "MULTIPLY_ADD", wear, 0.18, 605, 5)
    worn_roughness.node.inputs[2].default_value = 0.60
    surface.links.new(worn_roughness, surface.bsdf.inputs["Roughness"])
    chip_depth = surface.math("Recess where paint has chipped", "MULTIPLY", wear, -0.24, 365, -250)
    height = surface.math("Grain and chip depth", "ADD", grain, chip_depth, 560, -275)
    surface.bump("Microscopic paint texture", height, 0.24, 0.00024, 780, -280)
    return surface.material


def _plain(name, colors, metallic, roughness, texture_scale, bump_depth):
    surface = _Surface(name, colors[1], roughness, metallic)
    tonal = surface.noise("Finish variation", 46, 2, -860, 225)
    grain = surface.noise("Fine surface grain", texture_scale, 2, -860, -120)
    tint = surface.tint("Subtle material variation", tonal, _linear_rgba(colors[0]), _linear_rgba(colors[1]), -405, 220)
    surface.links.new(tint, surface.bsdf.inputs["Base Color"])
    rough = surface.remap("Small roughness variation", grain, (0.24, 0.76),
                          (roughness - 0.055, roughness + 0.065), -405, -50)
    surface.links.new(rough, surface.bsdf.inputs["Roughness"])
    surface.bump("Fine surface grain", grain, 0.2, bump_depth, 565, -130)
    return surface.material


def create_rack_materials():
    """Return paint, inner paint, fastener zinc, and rubber foot materials.

    On painted meshes, use a color attribute named Wear. Use red=0 on flat
    panels and red=1 only on exposed bends, chamfers, and slot rims.
    """
    return {
        "painted": _paint("M_Rack_WarmGrayPowderCoat", ((0.66, 0.64, 0.61), (0.80, 0.77, 0.73)), 0.95),
        "inner": _paint("M_Rack_ShadowedInteriorMetal", ((0.46, 0.45, 0.43), (0.59, 0.57, 0.54)), 0.70),
        "zinc": _plain("M_Rack_WeatheredZincFasteners", ((0.33, 0.34, 0.33), (0.54, 0.54, 0.51)),
                       0.79, 0.49, 820, 0.00014),
        "rubber": _plain("M_Rack_CharcoalRubberFeet", ((0.105, 0.104, 0.101), (0.19, 0.185, 0.175)),
                         0.0, 0.81, 920, 0.00023),
    }
