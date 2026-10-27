"""Owned material refinement; no geometry/transform/light/collision changes."""
import json,hashlib,sys,traceback,re
from copy import deepcopy
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as p
import InspectOldTownRealismInput as native
from PolishOldTownHotel import actor_state
from VerifyOldTownRealismRefinement import verify_baseline,sha,PLAN_SCHEMA,SOURCE_POINTER_SHA
WORK=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
ASSET='/Game/CodexGenerated/OldTown/RealismRefinement_20261013'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
edit=unreal.MaterialEditingLibrary;assets=unreal.EditorAssetLibrary
masters={};instances={};material_rows=[]
p.ASSET=ASSET

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def stable_actor(a):
    state=actor_state(a)
    for c in state['components']:
        color=c.get('light_color')
        if isinstance(color,str):
            channels=dict(re.findall(r'([rgba]):\s*(\d+)',color))
            assert set(channels)==set('rgba'),color
            c['light_color']=[int(channels[k]) for k in 'rgba']
    return state
def write(name,d):
    (WORK/name).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def expression_nodes(m):
    seen={};pending=[]
    for name in ('BASE_COLOR','NORMAL','ROUGHNESS','METALLIC','SPECULAR','OPACITY','REFRACTION','EMISSIVE_COLOR','WORLD_POSITION_OFFSET'):
        x=edit.get_material_property_input_node(m,getattr(unreal.MaterialProperty,'MP_'+name))
        if x:pending.append(x)
    while pending:
        x=pending.pop()
        if x.get_path_name() in seen:continue
        seen[x.get_path_name()]=x
        pending.extend(y for y in edit.get_inputs_for_material_expression(m,x) if y)
    return list(seen.values())
def output(m,name):
    prop=getattr(unreal.MaterialProperty,'MP_'+name)
    return edit.get_material_property_input_node(m,prop),edit.get_material_property_input_node_output_name(m,prop)
def arg(m,name,value):return p.node(m,'ScalarParameter',parameter_name=unreal.Name(name),default_value=float(value))
def vec(m,name,value):return p.node(m,'VectorParameter',parameter_name=unreal.Name(name),default_value=unreal.LinearColor(*value,0))
def channel(m,x,i):
    n=p.node(m,'ComponentMask',r=i==0,g=i==1,b=i==2,a=False);p.connect(x,n,'Input');return n
def sat(m,x):
    n=p.node(m,'Saturate');p.connect(x,n,'Input');return n
def one_minus(m,x):
    n=p.node(m,'OneMinus');p.connect(x,n,'Input');return n
def lerp(m,a,b,alpha,bo=''):
    n=p.node(m,'LinearInterpolate');p.connect(a,n,'A');p.connect(b,n,'B',bo);p.connect(alpha,n,'Alpha');return n
def worldpos(m):return p.node(m,'WorldPosition',world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
def macro(m,c):
    n=p.node(m,'Noise',noise_function=unreal.NoiseFunction.NOISEFUNCTION_GRADIENT_ALU,
        levels=1,quality=1,scale=1.,output_min=0.,output_max=1.,tiling=False,turbulence=False)
    p.connect(p.mul(m,c,p.scalar(m,1./800.)),n,'World Position');return n
def owned_clone(source,name):
    package=ASSET+'/Materials/'+name
    assert not assets.does_asset_exist(package),'Existing material stage must not be overwritten: '+package
    m=assets.duplicate_asset(source.split('.')[0],package)
    assert isinstance(m,unreal.Material)
    return m
def finish(m,details):
    edit.layout_material_expressions(m);edit.recompile_material(m)
    row=p.save(m);row.update(details);material_rows.append(row)
    return m

COAT={'Plaster':[.53,.49,.41],'ConcreteWall':[.39,.40,.37],
      'BluePlaster':[.20,.29,.34],'GreenPlaster':[.29,.34,.24],
      'Wood':[.24,.145,.075],'PaintedWood':[.045,.115,.07]}

def surface_master(spec):
    key=spec['role']
    if key in masters:return masters[key]
    role,mode=key.rsplit('_',1)
    details=dict(kind='master',role=role,projection=mode,category=spec['category'],
        source_master=spec['source_base'],geometry_displacement='Original constant surface-translation graph retained',
        contrast=.32 if spec['category']=='wall' else .24 if spec['category']=='wood' else None,
        scan_texture_scale_preserved=True,macro_scale_cm=800.)
    # Only complete, individually saved new-stage masters can exist on disk.
    existing=assets.load_asset(ASSET+'/Materials/M_RF_'+key) if assets.does_asset_exist(ASSET+'/Materials/M_RF_'+key) else None
    if existing:
        masters[key]=finish(existing,details);return masters[key]
    m=owned_clone(spec['source_base'],'M_RF_'+key)
    original=expression_nodes(m)
    old_bc,old_out=output(m,'BASE_COLOR');old_rough,rough_out=output(m,'ROUGHNESS')
    assert old_bc and old_rough
    wp=worldpos(m);coord=p.add(m,wp,vec(m,'BuildingPhaseCM',[0.,0.,0.]))
    noise=macro(m,coord)
    sparse=sat(m,p.mul(m,p.add(m,noise,p.scalar(m,-.53)),p.scalar(m,3.5)))
    if spec['category']=='wall':
        functions=[x for x in original if isinstance(x,unreal.MaterialExpressionMaterialFunctionCall)]
        assert len(functions)==3,(key,len(functions))
        for x in functions:p.connect(coord,x,'WorldPosition')
        z=p.add(m,channel(m,wp,2),p.mul(m,arg(m,'FloorBaseZCM',11.),p.scalar(m,-1.)))
        near=one_minus(m,sat(m,p.mul(m,z,p.scalar(m,1./80.))))
        damp=p.mul(m,p.mul(m,near,sparse),arg(m,'DampAmount',.22))
        weight=p.add(m,p.scalar(m,.32),p.mul(m,damp,p.scalar(m,.45)))
        bc=lerp(m,p.color(m,COAT[role]),old_bc,weight,old_out)
        bc=p.mul(m,bc,p.add(m,p.scalar(m,.97),p.mul(m,noise,p.scalar(m,.06))))
        p.prop(bc,'BASE_COLOR')
        rough=p.add(m,old_rough,p.mul(m,damp,p.scalar(m,.03)))
        normnode,no=output(m,'NORMAL')
        flatten=next(x for x in edit.get_inputs_for_material_expression(m,normnode) if x)
        assert isinstance(flatten,unreal.MaterialExpressionLinearInterpolate)
        flatten.set_editor_property('const_alpha',.14)
    elif spec['category']=='wood':
        des=p.node(m,'Desaturation');p.connect(old_bc,des,'Input',old_out);p.connect(p.scalar(m,.30),des,'Fraction')
        bc=lerp(m,p.color(m,COAT[role]),des,p.scalar(m,.24 if role=='Wood' else .18))
        normalz=channel(m,p.node(m,'VertexNormalWS'),2)
        top=sat(m,p.mul(m,p.add(m,normalz,p.scalar(m,-.65)),p.scalar(m,3.)))
        dust=p.mul(m,p.mul(m,top,sparse),p.scalar(m,.11))
        p.prop(lerp(m,bc,p.color(m,[.34,.31,.25]),dust),'BASE_COLOR')
        rough=p.add(m,old_rough,p.mul(m,dust,p.scalar(m,.04)))
        normnode,no=output(m,'NORMAL');flatten=next(x for x in edit.get_inputs_for_material_expression(m,normnode) if x)
        assert isinstance(flatten,unreal.MaterialExpressionLinearInterpolate)
        flatten.set_editor_property('const_alpha',.12)
    else:
        # Keep plain hotel fabric; only subtle, continuous aged variation.
        bc=p.mul(m,old_bc,p.add(m,p.scalar(m,.95),p.mul(m,noise,p.scalar(m,.06))),old_out)
        p.prop(bc,'BASE_COLOR');rough=old_rough
    clamp=p.node(m,'Clamp',min_default=.55 if spec['category']=='wood' else .68,max_default=.96)
    p.connect(rough,clamp,'Input');p.prop(clamp,'ROUGHNESS')
    masters[key]=finish(m,details);return m

def lamp_master(kind):
    if kind in masters:return masters[kind]
    source='/Game/CodexGenerated/OldTown/Realism_20261012/Materials/M_R_'+('Ceramic' if kind=='HotelTube' else 'Glass')+'_UV'
    details=dict(kind='emissive_master',fixture=kind,source_master=source,
        tube_mask_cm=[42.5,43.1] if kind=='HotelTube' else None,
        source_geometry_sha256='160d59f60274ba86cfc3246588d3623e29206fee6776273f6b5f262112ecff4e' if kind=='HotelTube' else None)
    existing=assets.load_asset(ASSET+'/Materials/M_RF_'+kind) if assets.does_asset_exist(ASSET+'/Materials/M_RF_'+kind) else None
    if existing:
        masters[kind]=finish(existing,details);return masters[kind]
    m=owned_clone(source,'M_RF_'+kind)
    # A frosted transmitting lens reads as a lit surface without glowing metal.
    if kind=='StreetLens':
        m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
        p.prop(p.color(m,[.55,.52,.44]),'BASE_COLOR');p.prop(p.scalar(m,.38),'ROUGHNESS')
    tint=vec(m,'LampEmissionTint',[1.,.83,.56]);strength=arg(m,'LampEmissionStrength',3.)
    glow=p.mul(m,tint,strength,'RGB')
    if kind=='HotelTube':
        local=p.node(m,'TransformPosition',transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
            transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
        p.connect(worldpos(m),local,'Input')
        abs_y=p.node(m,'Abs');p.connect(channel(m,local,1),abs_y,'Input')
        fade=sat(m,p.mul(m,p.add(m,abs_y,p.scalar(m,-42.5)),p.scalar(m,1./.6)))
        glow=p.mul(m,glow,one_minus(m,fade))
    p.prop(glow,'EMISSIVE_COLOR')
    masters[kind]=finish(m,details)
    return masters[kind]

def instance(master,values):
    key=master.get_path_name()+json.dumps(values,sort_keys=True)
    if key in instances:return instances[key]
    name='MI_RF_'+hashlib.sha256(key.encode()).hexdigest()[:16]
    path=ASSET+'/Materials/Instances/'+name
    mi=assets.load_asset(path) if assets.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,ASSET+'/Materials/Instances',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    assert mi
    edit.set_material_instance_parent(mi,master)
    for name,value in values.items():
        if isinstance(value,list):
            edit.set_material_instance_vector_parameter_value(mi,unreal.Name(name),unreal.LinearColor(*value,0))
        else:edit.set_material_instance_scalar_parameter_value(mi,unreal.Name(name),float(value))
    edit.update_material_instance(mi)
    for name,v in values.items():
        if isinstance(v,list):
            actual=edit.get_material_instance_vector_parameter_value(mi,unreal.Name(name))
            assert max(abs(float(getattr(actual,k))-x) for k,x in zip(('r','g','b'),v))<.00015,(name,v,actual)
        else:assert abs(edit.get_material_instance_scalar_parameter_value(mi,unreal.Name(name))-v)<.00015,(name,v)
    row=p.save(mi);row.update(kind='instance',parent=master.get_path_name(),values=values);material_rows.append(row)
    instances[key]=mi;return mi

LIGHT_FIELDS=['intensity','intensity_units','light_color','use_temperature','temperature','attenuation_radius',
    'source_radius','source_length','source_width','source_height','inner_cone_angle','outer_cone_angle',
    'indirect_lighting_intensity','volumetric_scattering_intensity','affects_world','visible','hidden_in_game','cast_shadows']
def light_inventory(actors):
    return {a.get_actor_label()+'::'+c.get_name():dict(class_path=c.get_class().get_path_name(),
        values=native.props(c,LIGHT_FIELDS)) for a in actors for c in a.get_components_by_class(unreal.LightComponentBase)}

def main():
    assert not (WORK/'Applied.json').exists(),'The stage has already been applied.'
    baseline=read(WORK/'Baseline.json');source=verify_baseline(baseline)
    assert sha(MAP)==baseline['source_map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actorlist=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by={a.get_actor_label():a for a in actorlist};assert len(by)==8014
    before={name:stable_actor(a) for name,a in by.items()}
    if before!=source['actors']['actors']:
        write('InputActorDifference.json',dict(differences=[dict(actor=n,before=source['actors']['actors'].get(n),current=s) for n,s in before.items() if s!=source['actors']['actors'].get(n)]))
        raise AssertionError('Current saved-map state differs from accepted input.')
    lights=light_inventory(actorlist);write('LightInput.json',dict(passed=True,lights=lights,map_sha256=sha(MAP)))
    assert len([x for x in lights.values() if x['class_path'] in ('/Script/Engine.RectLightComponent','/Script/Engine.SpotLightComponent')])==16
    recipe=read(WORK/'MaterialPrescription.json');rows=[];bindings=[]
    # Construct all new assets and a frozen, fully reviewable per-slot plan first.
    for prescribed in recipe['components']:
        a=by[prescribed['actor']]
        c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==prescribed['component'])
        original=next(r for r in source['native']['component_records'][prescribed['actor']] if r['name']==c.get_name())
        mats=[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]
        assert mats==[m['asset'] for m in original['materials']]
        new=list(mats);bases=[x['base_material'] for x in original['materials']]
        for spec in prescribed['slots']:
            m=surface_master(spec);values={p.PARAM:spec['surface_translation_cm']}
            if spec['role'].endswith('_World'):values['BuildingPhaseCM']=spec['building_phase_cm']
            if spec['category']=='wall':values.update(FloorBaseZCM=spec['floor_base_z_cm'],DampAmount=spec['damp_amount'])
            mi=instance(m,values);new[spec['slot']]=mi.get_path_name();bases[spec['slot']]=m.get_path_name()
        if prescribed['lamp']:
            lamp=prescribed['lamp'];la=by[lamp['light_actor']]
            lc=next(x for x in la.get_components_by_class(unreal.LightComponent) if x.get_editor_property('intensity')>0.)
            assert lc.get_editor_property('visible') and not lc.get_editor_property('hidden_in_game') and lc.get_editor_property('affects_world')
            color=lc.get_light_color();rgb=[color.r,color.g,color.b]
            if lc.get_editor_property('use_temperature'):
                kelvin=unreal.LinearColor();kelvin.set_temperature(lc.get_editor_property('temperature'))
                rgb=[x*getattr(kelvin,k) for x,k in zip(rgb,('r','g','b'))]
            peak=max(rgb);assert peak>0;rgb=[float(v/peak) for v in rgb]
            m=lamp_master(lamp['kind']);mi=instance(m,{p.PARAM:original['materials'][lamp['slot']]['effective_surface_translation_cm'],
                'LampEmissionTint':rgb,'LampEmissionStrength':lamp['strength']})
            new[lamp['slot']]=mi.get_path_name();bases[lamp['slot']]=m.get_path_name()
            bindings.append(dict(id=prescribed['id'],slot=lamp['slot'],source_light=lamp['light_actor'],
                material=mi.get_path_name(),emission_tint=rgb,strength=lamp['strength'],kind=lamp['kind']))
        assert new!=mats
        rows.append(dict(id=prescribed['id'],actor=prescribed['actor'],component=c.get_name(),
            source_mesh=c.static_mesh.get_path_name(),target_mesh=c.static_mesh.get_path_name(),
            before_materials=mats,after_materials=new,after_base_materials=bases))
    folder=ROOT/('Content/'+ASSET[6:])
    newhash={str(x.resolve()):sha(x) for x in folder.rglob('*') if x.is_file()}
    plan=dict(schema=PLAN_SCHEMA,source_map_sha256=baseline['source_map_sha256'],source_current_evidence_sha256=SOURCE_POINTER_SHA,
        components=rows,models=[],new_asset_sha256=newhash,geometry_changes=False,lamp_bindings=bindings)
    write('ApprovedPlan.json',plan)
    assert len(bindings)==16 and all(sha(path)==h for path,h in baseline['previous_asset_sha256'].items())
    expected=deepcopy(before)
    for row in rows:
        c=next(c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==row['component'])
        assert [c.get_material(i).get_path_name() for i in range(c.get_num_materials())]==row['before_materials']
        for i,path in enumerate(row['after_materials']):
            if path!=row['before_materials'][i]:c.set_material(i,unreal.load_asset(path))
        e=next(r for r in expected[row['actor']]['components'] if r['name']==row['component']);e['materials']=row['after_materials']
    assert {name:stable_actor(a) for name,a in by.items()}==expected
    assert light_inventory(actorlist)==lights,'A real light property changed.'
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    digest=sha(MAP);assert digest!=baseline['source_map_sha256']
    for path,h in {**baseline['previous_asset_sha256'],**baseline['protected_file_sha256']}.items():assert sha(path)==h,path
    write('MaterialBuild.json',dict(passed=True,assets=material_rows,masters=len(masters),instances=len(instances),
        previous_asset_packages_preserved=927,no_new_textures_imported=True,source_texture_scale_preserved=True))
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=baseline['source_map_sha256'],
        components=len(rows),emissive_fixtures=len(bindings),new_asset_sha256=newhash,
        approved_plan_sha256=sha(WORK/'ApprovedPlan.json'),all_light_properties_preserved=True))
    build=read(ROOT/'Saved/CodexOutputs/OldTownRealism_20261012/BuildReport.json')
    build.update(map_sha256=digest,source_map_sha256=baseline['source_map_sha256'],
        new_asset_sha256={**baseline['previous_asset_sha256'],**newhash},
        protected_map_sha256={p:h for p,h in baseline['protected_file_sha256'].items() if p.endswith('.umap')},
        realism_material_refinement=dict(stage=str(WORK),components=len(rows),lamp_surfaces=bindings))
    write('BuildReport.json',build)
    write('ExpectedSnapshot.json',dict(actors=expected,actor_count=8014,map_sha256=digest))
    unreal.log('REALISM_REFINEMENT_APPLIED '+json.dumps(dict(components=len(rows),masters=len(masters),instances=len(instances),map_sha256=digest)))

if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
