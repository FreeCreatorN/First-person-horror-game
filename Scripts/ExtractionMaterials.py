"""Editable materials for the existing green extraction-point level.

Import inside Unreal Editor and call build_materials().  All packages are saved
directly into the existing /Game/Yastar/Materials directory.
"""
import unreal


DIRECTORY = '/Game/Yastar/Materials'
EDIT = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary

DEFAULTS = {
    'Height': 155.0,
    'BodyOpacity': 0.055,
    'BodyEmission': 3.0,
    'FlowSpeed': 0.8,
    'TopRipple': 5.0,
    'RingEmission': 2.4,
    'FilamentIntensity': 3.0,
    'ParticleIntensity': 4.0,
}


BODY_CODE = r'''
float H=max(Height,1.0);
float h=(Relative.z+H*0.5)/H;
float u=frac(atan2(Relative.y,Relative.x)/6.28318530718+1.0);
float t=T*FlowSpeed;
float a=u*6.28318530718;
float ripple=(0.58*sin(a*4.0-t*0.92)+0.28*sin(a*7.0+t*0.57+1.3)+0.14*sin(a*11.0-t*1.19+0.5));
float top=0.963+ripple*clamp(TopRipple,0.0,10.0)/H;
float openEdge=1.0-smoothstep(top-0.035,top+0.006,h);
float base=smoothstep(0.0,0.025,h);
float side=1.0-saturate(abs(N.z));
float softFlow=0.5+0.23*sin(a*3.0+h*9.0-t*0.7)+0.16*sin(a*5.0-h*7.0+t*0.39+1.7);
softFlow=saturate(softFlow);
float lower=1.0-smoothstep(0.0,0.55,h);
float upper=smoothstep(0.48,0.96,h);
float3 middle=float3(0.012,0.26,0.055);
float3 tint=lerp(middle,float3(0.003,0.115,0.022),lower*0.85);
tint=lerp(tint,float3(0.055,0.38,0.17),upper*0.9);
float opacity=BodyOpacity*(0.78+0.40*softFlow+0.12*lower)*openEdge*base*side;
return float4(tint*BodyEmission*(0.84+0.20*softFlow+Facing*0.7),saturate(opacity*(1.0+Facing*0.5)));
'''


RING_CODE = r'''
float2 p=UV*2.0-1.0;
float r=length(p);
float a=atan2(p.y,p.x);
float t=T*FlowSpeed;
float outer=exp(-pow((r-0.78)*82.0,2.0));
float inner=exp(-pow((r-0.675)*105.0,2.0))*0.52;
float halo=exp(-pow((r-0.78)*19.0,2.0))*0.11;
float detail=0.92+0.08*sin(a*11.0-t*1.6)*sin(a*5.0+t*0.8);
float energy=(outer+inner+halo)*detail;
float3 tint=float3(0.035,0.80,0.15);
return float4(tint*RingEmission*energy,saturate(energy*0.78));
'''


FILAMENT_CODE = r'''
float H=max(Height,1.0);
float h=(Relative.z+H*0.5)/H;
float u=frac(atan2(Relative.y,Relative.x)/6.28318530718+1.0);
float t=T*FlowSpeed;
float lane=floor(u*18.0), x=frac(u*18.0);
float seed=frac(sin(lane*127.1+14.9)*43758.5453);
float seed2=frac(sin(lane*311.7+87.2)*43758.5453);
float cycle=floor(t*0.16+seed);
float phase=frac(t*0.16+seed);
float variation=frac(sin(lane*77.7+cycle*91.31+8.3)*43758.5453);
float head=0.10+0.76*phase;
float span=0.055+0.16*variation;
float segment=smoothstep(head-span-0.025,head-span,h)*(1.0-smoothstep(head,head+0.018,h));
float center=0.20+0.58*seed2+0.055*sin(h*53.0+seed*17.0)+0.025*sin(h*119.0-t*0.8+seed2*8.0);
float strand=exp(-pow((x-center)*48.0,2.0));
float branchCenter=center+(h-head+span*0.45)*(4.0+seed*4.0);
float branch=exp(-pow((x-branchCenter)*58.0,2.0))*(1.0-smoothstep(0.015,0.05,abs(h-head+span*0.45)))*0.65;
float active=(0.42+0.58*smoothstep(0.15,0.75,variation))*(0.62+0.38*sin(t*3.1+seed*31.0)*sin(t*1.7+seed2*19.0));
float a=u*6.28318530718;
float ripple=0.58*sin(a*4.0-t*0.92)+0.28*sin(a*7.0+t*0.57+1.3)+0.14*sin(a*11.0-t*1.19+0.5);
float top=0.963+ripple*clamp(TopRipple,0.0,10.0)/H;
float edge=(1.0-smoothstep(top-0.035,top+0.006,h))*smoothstep(0.0,0.025,h);
float side=1.0-saturate(abs(N.z));
float energy=(strand+branch)*segment*active*edge*side;
return float4(float3(0.028,0.85,0.14)*energy*FilamentIntensity,saturate(energy*0.60));
'''


PARTICLE_CODE = r'''
float2 p=(UV-0.5)*2.0;
float radius=length(p);
float soft=pow(saturate(1.0-radius),1.7);
float3 tint=max(Color,float3(0.0,0.0,0.0));
return float4(tint*ParticleIntensity, saturate(Alpha*soft));
'''


def _material(name):
    path = DIRECTORY + '/' + name
    material = unreal.load_asset(path) if ASSETS.does_asset_exist(path) else None
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DIRECTORY, unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(material, unreal.Material), path
    EDIT.delete_all_material_expressions(material)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    return material


def _node(material, cls, x, y):
    return EDIT.create_material_expression(material, cls, x, y)


def _parameter(material, name, x, y):
    node = _node(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', DEFAULTS[name])
    return node


def _custom(material, code, inputs, x=-400, y=0):
    node = _node(material, unreal.MaterialExpressionCustom, x, y)
    values = []
    for name in inputs:
        value = unreal.CustomInput()
        value.set_editor_property('input_name', name)
        values.append(value)
    node.set_editor_property('inputs', values)
    node.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    node.set_editor_property('code', code)
    return node


def _connect(source, target, input_name, output=''):
    assert EDIT.connect_material_expressions(source, output, target, input_name), input_name


def _outputs(material, custom):
    rgb = _node(material, unreal.MaterialExpressionComponentMask, -100, -80)
    alpha = _node(material, unreal.MaterialExpressionComponentMask, -100, 110)
    for key in ('r', 'g', 'b', 'a'):
        rgb.set_editor_property(key, key != 'a')
        alpha.set_editor_property(key, key == 'a')
    _connect(custom, rgb, '')
    _connect(custom, alpha, '')
    tint=_node(material,unreal.MaterialExpressionVectorParameter,-100,-260)
    tint.set_editor_property('parameter_name','Tint')
    tint.set_editor_property('default_value',unreal.LinearColor(1,1,1,1))
    multiply=_node(material,unreal.MaterialExpressionMultiply,100,-80)
    _connect(rgb,multiply,'A');_connect(tint,multiply,'B')
    assert EDIT.connect_material_property(multiply, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert EDIT.connect_material_property(alpha, '', unreal.MaterialProperty.MP_OPACITY)


def _surface_inputs(material, custom, parameters):
    world = _node(material, unreal.MaterialExpressionWorldPosition, -1200, -150)
    origin = _node(material, unreal.MaterialExpressionObjectPositionWS, -1200, 0)
    relative = _node(material, unreal.MaterialExpressionSubtract, -1000, -80)
    normal = _node(material, unreal.MaterialExpressionVertexNormalWS, -1000, 130)
    time_node = _node(material, unreal.MaterialExpressionTime, -1000, 280)
    _connect(world, relative, 'A')
    _connect(origin, relative, 'B')
    _connect(relative, custom, 'Relative')
    _connect(normal, custom, 'N')
    _connect(time_node, custom, 'T')
    for index, name in enumerate(parameters):
        _connect(_parameter(material, name, -800, 400 + 135 * index), custom, name)


def _save(material):
    EDIT.recompile_material(material)
    assert ASSETS.save_loaded_asset(material), material.get_path_name()


def _instance(name, parent, parameters):
    path = DIRECTORY + '/' + name
    instance = unreal.load_asset(path) if ASSETS.does_asset_exist(path) else None
    if instance is None:
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DIRECTORY, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    assert isinstance(instance, unreal.MaterialInstanceConstant), path
    EDIT.set_material_instance_parent(instance, parent)
    for name in parameters:
        EDIT.set_material_instance_scalar_parameter_value(instance, name, DEFAULTS[name])
    EDIT.update_material_instance(instance)
    assert ASSETS.save_loaded_asset(instance), path
    return instance


def build_materials(height=155.0):
    """Rebuild owned materials and return instance objects, parents, and paths."""
    assert ASSETS.does_directory_exist(DIRECTORY), 'Target material folder must already exist'
    DEFAULTS['Height'] = float(height)

    body = _material('M_GreenPortal_Beam')
    body_parameters = ['Height', 'BodyOpacity', 'BodyEmission', 'FlowSpeed', 'TopRipple']
    node = _custom(body, BODY_CODE, ['Relative', 'N', 'T','Facing'] + body_parameters)
    _surface_inputs(body, node, body_parameters)
    _connect(_node(body,unreal.MaterialExpressionFresnel,-900,100),node,'Facing')
    _outputs(body, node)
    _save(body)

    ring = _material('M_GreenPortal_Ring')
    node = _custom(ring, RING_CODE, ['UV', 'T', 'RingEmission', 'FlowSpeed'])
    _connect(_node(ring, unreal.MaterialExpressionTextureCoordinate, -950, -150), node, 'UV')
    _connect(_node(ring, unreal.MaterialExpressionTime, -950, 0), node, 'T')
    _connect(_parameter(ring, 'RingEmission', -950, 150), node, 'RingEmission')
    _connect(_parameter(ring, 'FlowSpeed', -950, 300), node, 'FlowSpeed')
    _outputs(ring, node)
    _save(ring)

    filaments = _material('M_GreenExtraction_Filaments')
    filament_parameters = ['Height', 'FlowSpeed', 'TopRipple', 'FilamentIntensity']
    node = _custom(filaments, FILAMENT_CODE, ['Relative', 'N', 'T'] + filament_parameters)
    _surface_inputs(filaments, node, filament_parameters)
    _outputs(filaments, node)
    _save(filaments)

    particle = _material('M_GreenExtraction_Particle')
    node = _custom(particle, PARTICLE_CODE, ['UV', 'Color', 'Alpha', 'ParticleIntensity'])
    uv = _node(particle, unreal.MaterialExpressionTextureCoordinate, -950, -150)
    color = _node(particle, unreal.MaterialExpressionParticleColor, -950, 50)
    _connect(uv, node, 'UV')
    _connect(color, node, 'Color')
    _connect(color, node, 'Alpha', 'A')
    _connect(_parameter(particle, 'ParticleIntensity', -950, 300), node, 'ParticleIntensity')
    _outputs(particle, node)
    try:
        EDIT.set_material_usage(particle, unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES)
    except Exception:
        # Some Python builds do not expose set_material_usage; the renderer will
        # request the sprite usage when this material is assigned to Niagara.
        pass
    _save(particle)

    parents = {'body': body, 'ring': ring, 'filaments': filaments, 'particle': particle}
    instances = {
        'body': _instance('MI_GreenExtraction_Body', body, body_parameters),
        'ring': _instance('MI_GreenExtraction_Ring', ring, ['RingEmission', 'FlowSpeed']),
        'filaments': _instance('MI_GreenExtraction_Filaments', filaments, filament_parameters),
        'particle': _instance('MI_GreenExtraction_Particle', particle, ['ParticleIntensity']),
    }
    result = dict(instances)
    result['materials'] = parents
    result['instances'] = instances
    result['paths'] = {
        'materials': {key: value.get_path_name() for key, value in parents.items()},
        'instances': {key: value.get_path_name() for key, value in instances.items()},
    }
    result['defaults'] = dict(DEFAULTS)
    return result
