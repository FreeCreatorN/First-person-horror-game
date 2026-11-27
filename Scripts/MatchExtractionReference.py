"""Match the existing extraction effect to the supplied portal reference."""
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import ExtractionMaterials as materials
import ExtractionNiagara as niagara
from ExtractionReferenceFloor import build_reference_floor

LEVEL = '/Game/Yastar/Maps/L_GreenPortal'
DIRECTORY = '/Game/Yastar/Materials/'
HEIGHT = 180.0
RADIUS = 62.0
PARTICLE_SPEED = 1.30
MOTE_MOTION = 'float rowPos = h*46.0-t*(0.50+q*0.68);'
SCALED_MOTE_MOTION = 'float rowPos = h*46.0-t*MoteSpeed*(0.50+q*0.68);'
REPORT = ROOT / 'Saved/GreenPortalReferenceReview.json'
report = {}

SIDE = r'''
float h = Relative.z/max(Height, 1.0) + 0.5;
float u = frac(atan2(Relative.y,Relative.x)/6.2831853+1.0);
float a = u*6.2831853;
float t = T*FlowSpeed;
// Differentiate the radial direction rather than the wrapped angle at the seam.
float2 radial = normalize(Relative.xy+float2(0.0001,0.0));
float angularSpan = length(ddx(radial))+length(ddy(radial));
float2 viewXY = normalize(View.xy+float2(0.00001,0.0));
float facing = dot(radial,viewXY);
// The ray's impact distance to the cylinder axis gives a smooth projected
// inset from the silhouette, even where angular UV derivatives get steep.
float inset = 1.0-sqrt(saturate(1.0-facing*facing));
float raySpan = max(length(ddx(viewXY)),length(ddy(viewXY)));
float pixelSpan = max(0.00005,raySpan*PixelDepthWS*length(View.xy)/max(length(Relative.xy),1.0));
float coverage = smoothstep(0.0,1.2*pixelSpan,inset);
float variation = (0.52*sin(5*a-t*0.55)+0.29*sin(13*a+t*0.43+1.6)
    +0.19*sin(27*a-t*0.89))*TopRipple/max(Height,1.0);
float vertical = 1.0-saturate(abs(N.z));
// Fade the whole upper volume over distance instead of tracing its outline.
float baseMask = vertical*coverage*smoothstep(-0.005,0.013,h);
float upperFade = 1.0-smoothstep(0.58+variation,0.99,h);
'''

BODY = SIDE + r'''
float grazing = 1.0 - abs(facing);
float foot = exp(-max(h,0.0)*5.0);
// Keep the highlight inside the silhouette and give it a stable width at
// distance, with smooth falloff on both sides of the bright band.
float wideWidth = max(0.0035,1.50*pixelSpan);
float coreWidth = max(0.0012,1.05*pixelSpan);
float widePos = inset/wideWidth;
float corePos = inset/coreWidth;
float lateral = 0.0080*widePos*exp(-widePos)/wideWidth;
float narrow = 0.0026*corePos*exp(-corePos)/coreWidth;
float micro = 0.5+0.5*sin(a*31.0+h*9.0-t*1.6);
float edge = (0.020*lateral+0.15*narrow)
    + (0.65*lateral+3.05*narrow)*pow(saturate(1.0-h),1.22);
float tint = BodyOpacity*(0.45+0.45*foot)*(0.80+0.20*micro);
float footGlow = exp(-max(h,0.0)*28.0)*(0.035+0.16*pow(saturate(grazing),5.0));
float power = (edge+tint+footGlow)*baseMask*upperFade*BodyEmission;
return float4(float3(0.055,1.0,0.255)*power, vertical);
'''

FILAMENTS = SIDE + r'''
float laneSpan = angularSpan*94.0/6.2831853;
float detailLod = 1.0-smoothstep(0.16,0.73,laneSpan);
float moteLod = detailLod*(1.0-smoothstep(0.18,0.65,fwidth(h)*46.0));
float lane = floor(u*94.0);
float localX = frac(u*94.0);
float p = frac(sin(lane*127.1+1.3)*43758.5453);
float q = frac(sin(lane*311.7+6.2)*43758.5453);
float v = frac(sin(lane*191.9+9.3)*43758.5453);
float center = 0.18+0.64*p+0.012*sin(h*31.0+p*9.0-t*0.4);
float width = lerp(0.095,0.31,q);
float delta = (localX-center)/width;
float core = exp(-3.7*delta*delta);
float glow = exp(-0.6*delta*delta);
float tip = lerp(0.53,0.992,p)+variation;
float tail = lerp(-0.03,0.27,q*q);
float envelope = smoothstep(tail-0.05,tail+0.12,h)
    *(1.0-smoothstep(tip-lerp(0.16,0.32,v),tip,h));
float pulse = 0.50+0.24*sin(h*(16.0+12.0*q)-t*(1.0+1.5*v)+p*37.0)
    +0.17*sin(h*46.0-t*3.3+q*11.0);
float cluster = 0.70+0.30*sin(a*8.0+p*0.6);
float shaft = (0.045*glow+0.080*core)*envelope*pulse*cluster
    *lerp(0.25,2.2,pow(v,2.9))*(0.43+0.57*exp(-h*3.1));

// Independently jittered, tiny stars travelling within the wall thickness.
float rowPos = h*46.0-t*(0.50+q*0.68);
float row = floor(rowPos);
float key = lane*127.1+row*311.7;
float r1 = frac(sin(key+3.2)*43758.5453);
float r2 = frac(sin(key+11.7)*19237.3823);
float r3 = frac(sin(key+73.4)*28193.3563);
float2 d = float2((localX-lerp(0.12,0.88,r2))*5.0,(frac(rowPos)-lerp(0.14,0.86,r3))*3.4);
float size = lerp(0.12,0.54,pow(r3,3.7));
float dd = dot(d,d)/(size*size);
float life = smoothstep(0.0,0.1,frac(rowPos))*(1.0-smoothstep(0.88,1.0,frac(rowPos)));
float mote = (exp(-dd*3.0)*0.78+exp(-dd*0.30)*0.075)
    *step(lerp(0.82,0.98,smoothstep(0.45,0.96,h)),r1)*life*(0.45+0.55*pow(r2,6.0));
float hot = step(0.925,r3)*mote*(0.7+1.65*pow(saturate(1.0-h),1.55))*moteLod;
float softShaft = (0.010+0.004*sin(a*9.0+h*9.0-t))*smoothstep(0.02,0.12,h);
float cool = lerp(softShaft,shaft*(1.0+0.92*exp(-h*7.0)),detailLod)+mote*moteLod;
float3 power = float3(0.095,1.0,0.35)*cool + float3(0.30,1.0,0.47)*hot;
return float4(power*baseMask*upperFade*FilamentIntensity,vertical);
'''
FILAMENTS = FILAMENTS.replace(MOTE_MOTION, SCALED_MOTE_MOTION)

RING = r'''
float2 p=UV*2.0-1.0;
float r=length(p), a=atan2(p.y,p.x);
float t=T*FlowSpeed;
float d=r-(75.0/100.0);
// Widen undersampled bands while preserving their integrated brightness.
float span=0.5*fwidth(r);
float4 widths=1.0/float4(188.0,54.0,133.0,255.0);
float4 sigma=sqrt(widths*widths+span*span);
float4 offsets=float4(d,d,d+0.025,r-0.83)/sigma;
float4 bands=exp(-offsets*offsets)*widths/sigma;
float outerWidth=1.0/270.0;
float outerSigma=sqrt(outerWidth*outerWidth+span*span);
float outerOffset=(r-0.925)/outerSigma;
float core=bands.x;
float bloom=bands.y;
float under=bands.z;
float etch=bands.w*0.084+exp(-outerOffset*outerOffset)*outerWidth/outerSigma*0.034;
float grain=pow(saturate(0.57+0.31*sin(a*59.0+t*2.1)+0.15*sin(a*97.0-t*1.7)),5.0);
float2 tangent=float2(-p.y,p.x)/max(dot(p,p),0.0001);
float angularSpan=abs(dot(tangent,ddx(p)))+abs(dot(tangent,ddy(p)));
grain=lerp(grain,0.11,smoothstep(0.35,1.9,angularSpan*97.0));
float strongArc=0.53+0.30*smoothstep(-0.15,0.95,-p.y/max(0.001,r))+0.15*sin(a*5.0+t*0.45);
float fringe=exp(-pow(d*19.0,2.0));
float3 energy=float3(0.26,1.0,0.44)*(core*(strongArc+0.80*grain))+
    float3(0.035,1.0,0.31)*(0.34*bloom+0.16*under+etch+0.018*fringe);
return float4(energy*RingEmission,1.0);
'''

PARTICLE = r'''
float2 p=(UV-0.5)*2.0;
float r2=dot(p,p);
float kernel=max(0.0,exp(-r2*5.0)-exp(-5.0));
float hot=exp(-r2*26.0);
float3 green=lerp(float3(0.055,1.0,0.32),float3(0.32,1.0,0.59),hot*0.7);
float strength=saturate(Color.g)*saturate(Alpha)*ParticleIntensity;
return float4(green*strength*(0.57*kernel+0.43*hot),1.0);
'''


def backup(assets, prefix='BeforeReference_'):
    for rel in assets:
        path = ROOT / 'Content' / 'Yastar' / rel
        dst = ROOT / 'Saved' / (prefix + path.name)
        if not dst.is_file():
            shutil.copy2(path, dst)


def configure_materials(side_only=False, keep_particle=False):
    values = materials.DEFAULTS
    values.update(Height=HEIGHT, BodyOpacity=0.019, BodyEmission=1.0,
                  FlowSpeed=1.0, TopRipple=2.2, RingEmission=9.1,
                  FilamentIntensity=1.70, ParticleIntensity=2.25, MoteSpeed=PARTICLE_SPEED)
    edit = materials.EDIT
    for parent, instance, shader, parameters, kind in [
        ('M_GreenPortal_Beam', 'Body', BODY,
         ['Height', 'BodyOpacity', 'BodyEmission','FlowSpeed','TopRipple'], 'side'),
        ('M_GreenExtraction_Filaments','Filaments',FILAMENTS,
         ['Height','FlowSpeed','TopRipple','FilamentIntensity','MoteSpeed'], 'side'),
        ('M_GreenPortal_Ring','Ring',RING, ['FlowSpeed','RingEmission'], 'ring'),
        ('M_GreenExtraction_Particle','Particle',PARTICLE, ['ParticleIntensity'], 'particle'),
    ]:
        if side_only and kind != 'side':
            continue
        if keep_particle and kind == 'particle':
            continue
        m = materials._material(parent)
        m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
        graph_inputs = ['Relative','N','T','View','PixelDepthWS'] if kind == 'side' else (
            ['UV','T'] if kind == 'ring' else ['UV','Color','Alpha'])
        node=materials._custom(m,shader,graph_inputs+parameters)
        if kind == 'side':
            materials._surface_inputs(m,node,parameters)
            materials._connect(materials._node(m,unreal.MaterialExpressionCameraVectorWS,-1000,200),node,'View')
            materials._connect(materials._node(m,unreal.MaterialExpressionPixelDepth,-1000,320),node,'PixelDepthWS')
        else:
            materials._connect(materials._node(m,unreal.MaterialExpressionTextureCoordinate,-950,-160),node,'UV')
            if kind == 'ring':
                materials._connect(materials._node(m,unreal.MaterialExpressionTime,-950,0),node,'T')
            else:
                color = materials._node(m, unreal.MaterialExpressionParticleColor, -950,0)
                materials._connect(color,node,'Color')
                materials._connect(color,node,'Alpha','A')
            for i,p in enumerate(parameters):
                materials._connect(materials._parameter(m,p,-950,180+i*135),node,p)
        materials._outputs(m,node)
        if kind == 'particle':
            try:
                edit.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES)
            except AttributeError:
                pass  # The existing Niagara renderer also requests this usage.
        materials._save(m)
        materials._instance('MI_GreenExtraction_'+instance,m,parameters)


def particle_system_and_modules():
    asset = unreal.load_asset(niagara.TARGET)
    emitter = next(o for o in niagara._objects_inside(asset)
                   if o.get_class().get_name() == 'NiagaraStatelessEmitter')
    mods = {o.get_class().get_name().split('_')[-1]:o for o in niagara._get(emitter,'modules')}
    return asset, emitter, mods


def configure_particles(height_only=False, fit_only=False):
    asset, emitter, mods = particle_system_and_modules()
    niagara._distribution(mods['ShapeLocation'],'cylinder_height',HEIGHT-40.0)
    niagara._distribution(mods['InitializeParticle'],'initial_position_distribution',(0.0,0.0,HEIGHT*0.46))
    if height_only:
        unreal.EditorAssetLibrary.save_loaded_asset(asset,False)
        return
    niagara._distribution(mods['ShapeLocation'],'cylinder_radius',57.0*RADIUS/75.0)
    niagara._distribution(mods['ShapeLocation'],'cylinder_surface_thickness',31.0*RADIUS/75.0)
    if fit_only:
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False)
        return
    niagara._distribution(mods['InitializeParticle'],'sprite_size_distribution',(0.32,0.32),(1.35,1.35))
    niagara._distribution(mods['AddVelocity'],'linear_velocity_distribution',(-0.35,-0.35,-0.8),(0.35,0.35,1.3))
    niagara._distribution(mods['AddVelocity'],'linear_velocity_scale',PARTICLE_SPEED)
    spawn = list(niagara._get(emitter,'spawn_infos'))
    niagara._distribution(spawn[0],'rate',30.0)
    niagara._set(emitter,'spawn_infos',spawn)
    niagara._set(emitter,'random_seed',1117)
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False)


def configure_particle_speed(actors):
    asset, _, mods = particle_system_and_modules()
    velocity = mods['AddVelocity']
    boundary_motes = unreal.load_asset(DIRECTORY+'M_GreenExtraction_Filaments')
    custom = next(node for node in unreal.ObjectIterator(unreal.MaterialExpressionCustom)
                  if node.get_path_name().startswith(boundary_motes.get_path_name()+':'))
    code = custom.get_editor_property('code')
    has_speed = SCALED_MOTE_MOTION in code
    assert has_speed or MOTE_MOTION in code, 'The surface mote motion was edited'
    backup(['Materials/M_GreenExtraction_Filaments.uasset',
            'Materials/NS_GreenExtractionParticles.uasset'], 'BeforeParticleSpeed_')

    if not has_speed:
        speed_input = unreal.CustomInput()
        speed_input.set_editor_property('input_name', 'MoteSpeed')
        custom.set_editor_property('inputs', [*custom.get_editor_property('inputs'), speed_input])
        custom.set_editor_property('code', code.replace(MOTE_MOTION, SCALED_MOTE_MOTION, 1))
        materials.DEFAULTS['MoteSpeed'] = PARTICLE_SPEED
        speed = materials._parameter(boundary_motes, 'MoteSpeed', -800, 940)
        materials._connect(speed, custom, 'MoteSpeed')
        materials._save(boundary_motes)

    instance = unreal.load_asset(DIRECTORY+'MI_GreenExtraction_Filaments')
    edit = materials.EDIT
    if abs(edit.get_material_instance_scalar_parameter_value(instance, 'MoteSpeed') - PARTICLE_SPEED) >= 0.001:
        backup(['Materials/MI_GreenExtraction_Filaments.uasset'], 'BeforeParticleSpeed_')
        edit.set_material_instance_scalar_parameter_value(instance, 'MoteSpeed', PARTICLE_SPEED)
        edit.update_material_instance(instance)
        assert unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    mote_speed = edit.get_material_instance_scalar_parameter_value(instance, 'MoteSpeed')
    assert abs(mote_speed - PARTICLE_SPEED) < 0.001

    niagara._distribution(velocity, 'linear_velocity_scale', PARTICLE_SPEED)
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
    speed_distribution = niagara._get(velocity, 'linear_velocity_scale')
    velocity_scale = list(niagara._get(speed_distribution, 'channel_constants_and_ranges'))[0]
    assert abs(velocity_scale - PARTICLE_SPEED) < 0.001
    component = actors['Green extraction point'].get_component_by_class(unreal.NiagaraComponent)
    component.reinitialize_system()
    report.update(applied=True, mote_speed=mote_speed, velocity_scale=velocity_scale)


def configure_scene(actors, levels, height_only=False, keep_preview_pose=False):
    bp=unreal.load_asset('/Game/Yastar/Blueprints/BP_GreenExtractionPoint')
    sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib=unreal.SubobjectDataBlueprintFunctionLibrary
    objects={}
    for handle in sub.k2_gather_subobject_data_for_blueprint(bp):
        data=lib.get_data(handle)
        if lib.is_scene_component(data):
            objects[str(lib.get_variable_name(data))]=lib.get_object_for_blueprint(data,bp)
    for name,radius in [('EnergyBoundary',RADIUS),('EnergyThreads',RADIUS-0.7)]:
        c=objects[name]
        c.set_editor_property('relative_location',unreal.Vector(0,0,HEIGHT/2.0))
        c.set_editor_property('relative_scale3d',unreal.Vector(radius/50.0,radius/50.0,HEIGHT/100.0))
    if not height_only:
        ring_scale=2.0*RADIUS/75.0
        objects['GroundRings'].set_editor_property('relative_scale3d',unreal.Vector(ring_scale,ring_scale,1))
        if not keep_preview_pose:
            green=objects['LocalizedGreenLight']
            green.set_editor_property('intensity',5.5)
            green.set_editor_property('attenuation_radius',178.0)
            green.set_editor_property('specular_scale',0.0)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    for fx in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if fx.get_actor_label()=='Green extraction point':
            fx.get_component_by_class(unreal.NiagaraComponent).reinitialize_system()
    if height_only:
        assert levels.save_current_level()
        return
    floor=actors['Preview floor']
    floor.static_mesh_component.set_material(0,build_reference_floor(95.0,RADIUS))
    if keep_preview_pose:
        assert levels.save_current_level()
        return
    reference=actors['Preview - 180cm reference']
    p=reference.get_actor_location()
    reference.set_actor_location(unreal.Vector(-157,-55,p.z),False,False)
    reference.set_actor_rotation(unreal.Rotator(yaw=-85),False)
    fill=actors['Extraction neutral fill']
    fill.set_actor_location(unreal.Vector(-189,-180,195),False,False)
    fill.get_component_by_class(unreal.PointLightComponent).set_editor_property('intensity',88.0)
    actors['Extraction neutral key'].get_component_by_class(unreal.DirectionalLightComponent).set_editor_property('intensity',0.5)
    pp=actors['Extraction exposure']
    settings=pp.get_editor_property('settings')
    settings.set_editor_property('bloom_intensity',0.61)
    pp.set_editor_property('settings',settings)
    camera=actors['Portal preview camera']
    camera.set_actor_location(unreal.Vector(-14,-610,135),False,False)
    camera.set_actor_rotation(unreal.Rotator(pitch=-10.3,yaw=90,roll=0),False)
    cc=camera.get_component_by_class(unreal.CameraComponent)
    cc.set_editor_property('field_of_view',37.5)
    cc.set_editor_property('aspect_ratio',1.0)
    cc.set_editor_property('constrain_aspect_ratio',True)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
        camera.get_actor_location(),camera.get_actor_rotation())
    assert levels.save_current_level()


def write():
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')


def main():
    global REPORT
    character_fit = '--character-fit' in sys.argv[1:]
    height_only = '--open-top-only' in sys.argv[1:]
    particle_speed_only = '--particle-speed' in sys.argv[1:]
    if particle_speed_only:
        REPORT = ROOT / 'Saved/GreenPortalParticleSpeedReview.json'
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.get_current_level().get_outermost().get_path_name()==LEVEL
    assert not levels.is_in_play_in_editor()
    ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors={a.get_actor_label():a for a in ae.get_all_level_actors()}
    if particle_speed_only:
        configure_particle_speed(actors)
        write()
        return
    owned = ['Maps/L_GreenPortal.umap','Blueprints/BP_GreenExtractionPoint.uasset']
    owned += ['Materials/'+name+'.uasset' for name in [
        'M_GreenPortal_Beam','M_GreenPortal_Ring','M_GreenExtraction_Filaments',
        'M_GreenExtraction_Particle','M_GreenExtraction_PreviewFloor',
        'NS_GreenExtractionParticles', 'MI_GreenExtraction_Body','MI_GreenExtraction_Ring',
        'MI_GreenExtraction_Filaments','MI_GreenExtraction_Particle']]
    if height_only:
        owned = [p for p in owned if any(s in p for s in ('Maps/','Blueprints/','Beam','Body','Filaments','NS_Green'))]
    if character_fit:
        owned = [p for p in owned if 'Extraction_Particle.uasset' not in p]
    prefix = 'BeforeCharacterFit_' if character_fit else ('BeforeOpenTop_' if height_only else 'BeforeReference_')
    backup(owned,prefix)
    configure_materials(side_only=height_only,keep_particle=character_fit)
    configure_particles(height_only=height_only,fit_only=character_fit)
    configure_scene(actors,levels,height_only=height_only,keep_preview_pose=character_fit)
    person=actors['Preview - 180cm reference']
    _, extent=person.get_actor_bounds(False)
    report.update(applied=True,height_cm=HEIGHT,radius_cm=RADIUS,particles_per_second=30,
                  open_top=True,height_only=height_only,reference_character_height_cm=2.0*extent.z)
    write()


try:
    main()
except Exception:
    report['error']=traceback.format_exc()
    write()
    unreal.log_error(report['error'])
    raise
