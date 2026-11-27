"""Build wet ground lighting in the extraction preview's existing floor material."""

import unreal

from ExtractionMaterials import ASSETS, EDIT, _connect, _custom, _node


FLOOR_PATH = '/Game/Yastar/Materials/M_GreenExtraction_PreviewFloor'

FLOOR_SURFACE = r'''
float2 p = Relative.xy;
float2 cell = floor(p * 1.85);
float grit = frac(sin(dot(cell, float2(127.1, 311.7))) * 43758.5453);
float2 stones = floor(p * 0.76);
float aggregate = frac(sin(dot(stones, float2(269.5, 183.3))) * 43758.5453);
float wet = smoothstep(0.07, 0.70, 0.43 + 0.29 * sin(p.x * 0.028 + sin(p.y * 0.047))
    + 0.22 * sin(p.y * 0.036 - p.x * 0.052));
float albedo = (0.007 + 0.010 * aggregate + 0.003 * grit) * lerp(1.0, 0.54, wet);
float roughness = lerp(0.54, 0.16, wet) + 0.06 * grit;
return float4(float3(0.76, 0.90, 1.0) * albedo, roughness);
'''

FLOOR_REFLECTION = r'''
float2 p = Relative.xy;
float distanceToPortal = length(p);
float radius = max(Radius, 1.0);
float wet = smoothstep(0.07, 0.70, 0.43 + 0.29 * sin(p.x * 0.028 + sin(p.y * 0.047))
    + 0.22 * sin(p.y * 0.036 - p.x * 0.052));
float grain = frac(sin(dot(floor(p * 1.05), float2(127.1, 311.7))) * 43758.5453);
float detail = 1.0-smoothstep(0.45,2.0,length(ddx(p))+length(ddy(p)));
grain = lerp(0.5,grain,detail);

// Trace an eye ray into a reflected cylinder below the ground plane.
float3 view = normalize(View);
float2 side = float2(-view.y, view.x);
float disturbance = 0.012 * sin(dot(p, float2(0.37, 0.23)) + T * 2.1)
    + 0.008 * sin(dot(p, float2(-0.91, 0.55)) - T * 1.7);
float2 ray = -view.xy + side * disturbance * 2.4;
float slope = max(0.015, view.z + disturbance);
float a = max(0.0001, dot(ray, ray));
float b = dot(p, ray);
float c = dot(p, p) - radius * radius;
float discriminant = b * b - a * c;
float nearHit = (-b - sqrt(max(0.0, discriminant))) / a;
float farHit = (-b + sqrt(max(0.0, discriminant))) / a;
float range = nearHit > 0.0 ? nearHit : farHit;
float depth = max(0.0, range * slope);
float2 hit = p + ray * max(0.0, range);
float azimuth = atan2(hit.y, hit.x);
float valid = smoothstep(0.0,max(fwidth(discriminant),1.0),discriminant) * step(0.0, range);

float2 cells = floor(p * 0.036);
float2 rippleOrigin = (cells + 0.5) / 0.036;
float ripplePhase = frac(T * 0.58 + frac(sin(dot(cells, float2(72.3, 219.9))) * 17431.781));
float rippleDistance = length(p - rippleOrigin) - ripplePhase * 11.0;
float ripple = exp(-0.52 * rippleDistance * rippleDistance);
float puddle = (0.28 + 0.72 * wet) * (0.21 + 0.79 * grain);
float glints = 0.45 + 0.55 * sin(dot(p, float2(0.33, 0.94)) + ripple * 3.4 + T * 0.75);
float edge = saturate(1.0 - depth / max(0.70 * Height, 1.0));
float streak = pow(saturate(0.51 + 0.28 * sin(azimuth * 17.0 + 0.4)
    + 0.21 * sin(azimuth * 29.0 - 1.4)), 3.3);
float reflectedEdge=pow(saturate(1.0-abs(dot(normalize(hit+0.0001),normalize(ray)))),8.0);
float projected = valid * edge * edge * (0.026 + 0.23 * streak + 0.30*reflectedEdge);
float ringDistance = distanceToPortal - radius;
float glowingBase = exp(-0.0028 * ringDistance * ringDistance) * 0.032;
float splash = valid * edge * 0.036 * ripple * (1.0 - ripplePhase) * detail;
float reflection = (projected + glowingBase + splash) * puddle * (0.33 + 0.67 * glints);
reflection *= 1.0 - smoothstep(radius * 1.30, radius * 4.4, distanceToPortal);

// A small unlit contribution retains wet texture in shadowed reference shots.
float coolAmbient = 0.00055 + (0.0013 * glints + 0.0008 * grain) * wet;
return float4(float3(0.53, 0.74, 1.0) * coolAmbient
    + float3(0.055, 1.0, 0.26) * reflection * ReflectionStrength, 1.0);
'''


def _scalar(material, name, value, y):
    node = _node(material, unreal.MaterialExpressionScalarParameter, -1050, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', float(value))
    return node


def _mask(material, source, rgb, y):
    node = _node(material, unreal.MaterialExpressionComponentMask, 50, y)
    for channel in ('r', 'g', 'b', 'a'):
        node.set_editor_property(channel, (channel != 'a') == rgb)
    _connect(source, node, '')
    return node


def build_reference_floor(height, radius=75.0):
    """Update the original preview floor material and return the saved asset."""
    material = unreal.load_asset(FLOOR_PATH)
    assert isinstance(material, unreal.Material), FLOOR_PATH
    EDIT.delete_all_material_expressions(material)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('two_sided', False)
    world = _node(material, unreal.MaterialExpressionWorldPosition, -1400, -300)
    origin = _node(material, unreal.MaterialExpressionObjectPositionWS, -1400, -130)
    relative = _node(material, unreal.MaterialExpressionSubtract, -1100, -240)
    _connect(world, relative, 'A')
    _connect(origin, relative, 'B')

    surface = _custom(material, FLOOR_SURFACE, ['Relative'], -550, -205)
    _connect(relative, surface, 'Relative')
    assert EDIT.connect_material_property(_mask(material, surface, True, -270), '', unreal.MaterialProperty.MP_BASE_COLOR)
    assert EDIT.connect_material_property(_mask(material, surface, False, -100), '', unreal.MaterialProperty.MP_ROUGHNESS)

    reflection = _custom(material, FLOOR_REFLECTION, ['Relative', 'View', 'T', 'Height', 'Radius', 'ReflectionStrength'], -550, 280)
    _connect(relative, reflection, 'Relative')
    _connect(_node(material, unreal.MaterialExpressionCameraVectorWS, -1050, 0), reflection, 'View')
    _connect(_node(material, unreal.MaterialExpressionTime, -1050, 135), reflection, 'T')
    _connect(_scalar(material, 'Height', height, 280), reflection, 'Height')
    _connect(_scalar(material, 'Radius', radius, 425), reflection, 'Radius')
    _connect(_scalar(material, 'ReflectionStrength', 1.0, 570), reflection, 'ReflectionStrength')
    assert EDIT.connect_material_property(_mask(material, reflection, True, 240), '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    EDIT.recompile_material(material)
    assert ASSETS.save_loaded_asset(material), FLOOR_PATH
    return material
