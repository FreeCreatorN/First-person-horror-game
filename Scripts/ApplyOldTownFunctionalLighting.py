"""Turn the 17 remaining assistant-made decorative fixtures into callable real lights."""
import sys,json,hashlib,shutil,traceback
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import ApplyOldTownCallableLighting as prior
import InspectOldTownRealismInput as native
from OldTownMainLightingCommon import capture_geometry_state
import OldTownRealismMaterials as graph
W=R/'Saved/CodexOutputs/OldTownFunctionalLighting_20261017'
ASSET='/Game/CodexGenerated/OldTown/FunctionalLighting_20261017'
NEW_FOLDER=R/('Content/'+ASSET[6:])
MAP=prior.MAP;TARGET=prior.TARGET
TAG='OTS_FunctionalLighting_20261017'
BP='/Game/CodexGenerated/OldTown/CallableLighting_20261016/Blueprints/BP_OTS_LightCircuit'
prior.W=W;prior.TAG=TAG;prior.NEW_FOLDER=NEW_FOLDER
edit=unreal.MaterialEditingLibrary;assets=unreal.EditorAssetLibrary

def write(name,d):native.write(W/name,d)
def read(name):return json.loads((W/name).read_text(encoding='utf-8-sig'))

def reset_export_marks():
    # UE's ObjectExporterT3D keeps global TagImp/TagExp marks between calls.
    # The native read-only OBJ COMPONENTS handler clears these marks. The base
    # UObject CDO has no components to re-mark; no asset properties are changed.
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')

def snapshot(actors,phase):
    reset_export_marks()
    result=prior.snapshot(actors,phase)
    record=result['full_existing_actor_native']['PostProcessVolume']
    raw=Path(record['file']).read_bytes()
    text=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
    assert text.count('Begin Polygon')==6,'Native export omitted existing PostProcess brush geometry'
    return result

def recipes(by):
    rows=[]
    for floor in range(4):
        for i in (0,2,3,5):
            rows.append(dict(lamp_actor=f'OTS_HotelV4_F{floor}_GalleryTube{i:02d}',
                light_actor=f'OTS_Enabled_HotelV4_F{floor}_GalleryTube{i:02d}',kind='HotelTube',
                template_lamp=f'OTS_HotelV4_F{floor}_GalleryTube01',template_light=f'OTS_HotelV4_F{floor}_SurvivingTube0'))
    rows.append(dict(lamp_actor='OTS_P2Prop_StreetLamp_03',light_actor='OTS_Light_StreetLamp03',kind='StreetLens',
        template_lamp='OTS_P2Prop_StreetLamp_02',template_light='OTS_Light_StreetLamp02'))
    for row in rows:
        assert row['light_actor'] not in by
        a=by[row['lamp_actor']];assert isinstance(a,unreal.StaticMeshActor)
        mat=a.static_mesh_component.get_material(2);assert mat
        assert mat.get_path_name().split('.')[0].endswith('/M_R_'+('Ceramic' if row['kind']=='HotelTube' else 'Glass')+'_UV')
        row.update(component=a.static_mesh_component.get_name(),original_material=mat.get_path_name(),
            original_material_record=native.material_record(mat),controller_label='OTS_LightCircuit_'+row['lamp_actor'].removeprefix('OTS_'))
        assert row['controller_label'] not in by
    assert len(rows)==17
    return rows

def new_street_master(source):
    package=ASSET+'/Materials/M_OTS_Street03_GlassCallable'
    if assets.does_asset_exist(package):return unreal.load_asset(package)
    m=assets.duplicate_asset(source.split('.')[0],package);assert isinstance(m,unreal.Material)
    original_emission=edit.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    original_output=edit.get_material_property_input_node_output_name(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    # Preserve the original translucent glass, opacity and surface offsets; add emission only.
    tint=graph.node(m,'VectorParameter',parameter_name=unreal.Name('LampEmissionTint'),default_value=unreal.LinearColor(1.,.57056278,.25911239,0.))
    power=graph.node(m,'ScalarParameter',parameter_name=unreal.Name('LampEmissionStrength'),default_value=4.)
    state=graph.node(m,'ScalarParameter',parameter_name=unreal.Name('LightStrength'),default_value=0.)
    norm=graph.mul(m,state,graph.scalar(m,.05))
    emission=graph.mul(m,graph.mul(m,tint,power,'RGB'),norm)
    if original_emission:
        combined=graph.node(m,'Add')
        assert edit.connect_material_expressions(original_emission,original_output,combined,'A')
        assert edit.connect_material_expressions(emission,'',combined,'B')
        emission=combined
    graph.prop(emission,'EMISSIVE_COLOR');edit.recompile_material(m)
    assert assets.save_loaded_asset(m,False)
    return m

def create_instance(row,by,street_master):
    template=by[row['template_lamp']].static_mesh_component.get_material(2)
    master=template.get_editor_property('parent') if row['kind']=='HotelTube' else street_master
    package=ASSET+'/Materials/Instances/MI_'+row['lamp_actor']
    if assets.does_asset_exist(package):mi=unreal.load_asset(package)
    else:
        mi=unreal.AssetToolsHelpers.get_asset_tools().create_asset(package.rsplit('/',1)[1],package.rsplit('/',1)[0],unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    assert mi
    edit.set_material_instance_parent(mi,master)
    for p,v in {'LightStrength':0.,'LampEmissionStrength':3. if row['kind']=='HotelTube' else 4.}.items():
        edit.set_material_instance_scalar_parameter_value(mi,p,v)
        assert edit.get_material_instance_scalar_parameter_value(mi,p)==v
    tint=edit.get_material_instance_vector_parameter_value(template,'LampEmissionTint')
    edit.set_material_instance_vector_parameter_value(mi,'LampEmissionTint',tint)
    offset=row['original_material_record']['effective_surface_translation_cm']
    edit.set_material_instance_vector_parameter_value(mi,'CodexSurfaceTranslationCM_20261009',unreal.LinearColor(*offset,0.))
    assert assets.save_loaded_asset(mi,False)
    row['material']=mi.get_path_name();row['master']=master.get_path_name()
    return mi

def bind_light(row,by,ae,world):
    source,template,target=(by[row[k]] for k in ('template_light','template_lamp','lamp_actor'))
    local_pos=unreal.MathLibrary.inverse_transform_location(template.get_actor_transform(),source.get_actor_location())
    pos=unreal.MathLibrary.transform_location(target.get_actor_transform(),local_pos)
    local_rot=unreal.MathLibrary.inverse_transform_rotation(template.get_actor_transform(),source.get_actor_rotation())
    rot=unreal.MathLibrary.transform_rotation(target.get_actor_transform(),local_rot)
    unreal.log('FUNCTIONAL_LIGHT_CREATE '+row['light_actor'])
    clone=ae.spawn_actor_from_class(source.get_class(),pos,rot,False);assert clone
    clone.set_actor_label(row['light_actor'])
    clone.set_folder_path(unreal.Name('OldTownSchoolStreet/Lighting/EnabledDecorativeFixtures'))
    clone.set_editor_property('tags',[unreal.Name(TAG)])
    lc=clone.get_component_by_class(unreal.LightComponent);sc=source.get_component_by_class(unreal.LightComponent)
    assert lc and sc
    excluded={'relative_location','relative_translation','relative_rotation','relative_scale3d','visible','hidden_in_game','component_tags','on_component_activated','on_component_deactivated'}
    source_props=native.reflect_editor_properties(sc)
    copy_errors={}
    for name in source_props:
        if name in excluded:continue
        try:lc.set_editor_property(name,sc.get_editor_property(name))
        except Exception as error:copy_errors[name]=str(error)
    # Saved off-state keeps the existing photometric base value for future switching.
    for name in ('visible','hidden_in_game'):lc.set_editor_property(name,False)
    clone_props=native.reflect_editor_properties(lc)
    def norm(v):
        if isinstance(v,str):return v.replace(source.get_path_name(),clone.get_path_name())
        if isinstance(v,list):return [norm(x) for x in v]
        if isinstance(v,dict):return {k:norm(x) for k,x in v.items()}
        return v
    mismatches={k:dict(source=norm(v),new=clone_props.get(k),copy_error=copy_errors.get(k)) for k,v in source_props.items() if k not in excluded and norm(v)!=clone_props.get(k)}
    assert not mismatches,(row['light_actor'],mismatches)
    row.update(base_intensity=float(lc.get_editor_property('intensity')),initially_on=False,
        light_class=lc.get_class().get_path_name(),light_world_transform=native.value(lc.get_world_transform()),
        source_local_position=native.value(local_pos),template_light_properties=source_props,
        new_light_properties=clone_props,light_actor_path=clone.get_path_name(),creation_method='spawn_actor_and_copy_all_editor_properties',read_only_property_copy_errors=copy_errors)
    return clone

def apply():
    assert not (W/'Applied.json').exists(),'Already applied'
    assert not [p for p in NEW_FOLDER.rglob('*') if p.is_file()],'New-stage asset directory must start empty'
    baseline=prior.files()
    assert native.sha(MAP)=='d907f4dfff07ec83011337b34107427b61d39efd1479134035ed749d73a8a8c7','User saved map changed; inspect the new input before applying'
    backup=R/'Saved/CodexBackups'/('OriginalTownBeforeFunctionalLights_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False);file=backup/'L_OldTownSchoolStreet.umap';shutil.copy2(MAP,file)
    assert native.sha(file)==baseline[str(MAP)]
    write('Backup.json',dict(passed=True,file=str(file),sha256=native.sha(file),source_sha256=baseline[str(MAP)],created_before_map_write=True))
    write('ProtectedBefore.json',dict(file_sha256=baseline))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(by)==7952
    before=snapshot(actors,'Before');write('BeforeSnapshot.json',before)
    rows=recipes(by);write('FixturePlan.json',dict(passed=True,rows=rows,new_lights=17,new_controllers=17,initially_off=True,other_fixtures_unchanged=16))
    street=new_street_master(rows[-1]['original_material'])
    cls=unreal.EditorAssetLibrary.load_blueprint_class(BP);assert cls
    expected=deepcopy(before)
    for row in rows:
        mi=create_instance(row,by,street)
        ma=by[row['lamp_actor']];ma.static_mesh_component.set_material(2,mi)
        light=bind_light(row,by,ae,world)
        controller=ae.spawn_actor_from_class(cls,ma.get_actor_location(),unreal.Rotator(),False);assert controller
        controller.set_actor_label(row['controller_label']);controller.set_folder_path(unreal.Name('OldTownSchoolStreet/Lighting/CallableCircuits'))
        controller.set_editor_property('tags',[unreal.Name(TAG)])
        for k,v in dict(target_lamp_mesh=ma,emissive_material_slot=2,controlled_lights=[light],base_intensities=[row['base_intensity']],initially_on=False).items():controller.set_editor_property(k,v)
        row['controller_path']=controller.get_path_name()
        rec=expected['full_existing_actor_native'][row['lamp_actor']]
        raw=Path(rec['file']).read_bytes();txt=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
        old_ref="/Script/Engine.Material'"+row['original_material']+"'"
        new_ref="/Script/Engine.MaterialInstanceConstant'"+mi.get_path_name()+"'"
        assert txt.count(old_ref)==1,(row['lamp_actor'],txt.count(old_ref))
        rec['native_text_sha256']=hashlib.sha256(txt.replace(old_ref,new_ref).encode()).hexdigest()
        next(c for c in expected['actors'][row['lamp_actor']]['components'] if c['name']==row['component'])['materials'][2]=mi.get_path_name()
        key=row['lamp_actor']+'::'+row['component'];old=deepcopy(expected['exact_scene_components'][key]);new=capture_geometry_state([ma])[key]
        a,b=deepcopy(old),deepcopy(new)
        assert [i for i,(x,y) in enumerate(zip(a['materials'],b['materials'])) if x!=y]==[2]
        for g in (a,b):g.pop('materials');g['geometry_properties'].pop('override_materials')
        assert a==b
        expected['exact_scene_components'][key]=new
    prior.compare_snapshot(expected,snapshot(actors,'BeforeSave'))
    prior.verify_protected(baseline)
    unreal.OldTownLightCircuitEditorLibrary.restore_all_editor_previews()
    assert le.save_current_level()
    assets_added={str(p):native.sha(p) for p in sorted(NEW_FOLDER.rglob('*')) if p.is_file()};assert len(assets_added)==18
    write('ExpectedExistingSnapshot.json',expected)
    write('Applied.json',dict(passed=True,target_level=TARGET,map_sha256=native.sha(MAP),source_map_sha256=baseline[str(MAP)],
        pairs=rows,new_asset_sha256=assets_added,actor_count_before=7952,actor_count_after=7986,new_real_lights=17,new_controllers=17,
        expected_circuit_count=33,expected_initially_on=13,expected_initially_off=20,geometry_unchanged=True,
        protected_verification=prior.verify_protected(baseline,True)))
    unreal.log('OLD_TOWN_FUNCTIONAL_LIGHTING_APPLY_PASS '+native.sha(MAP))

def audit():
    plan=read('Applied.json');assert plan['passed'] and native.sha(MAP)==plan['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET);actors=list(ae.get_all_level_actors());assert len(actors)==7986
    existing=[a for a in actors if TAG not in [str(t) for t in a.tags]]
    assert len(existing)==7952
    snap=snapshot(existing,'Readback');write('ReadbackSnapshot.json',snap);prior.compare_snapshot(read('ExpectedExistingSnapshot.json'),snap)
    by={a.get_actor_label():a for a in actors};circuits=[a for a in actors if isinstance(a,unreal.OldTownLightCircuitActor)];assert len(circuits)==33
    bindings=[]
    for c in circuits:
        p=json.loads(unreal.OldTownLightCircuitEditorLibrary.inspect_circuit(c));assert not p['configuration_error'] and not p['initialized']
        ma=c.get_editor_property('target_lamp_mesh');mat=ma.static_mesh_component.get_material(2)
        assert 'LightStrength' in [str(n) for n in edit.get_scalar_parameter_names(mat)]
        on=bool(c.get_editor_property('initially_on'));assert edit.get_material_instance_scalar_parameter_value(mat,'LightStrength')==(20. if on else 0.)
        assert len(c.get_editor_property('controlled_lights'))==1
        bindings.append(dict(controller=c.get_actor_label(),lamp=ma.get_actor_label(),material=mat.get_path_name(),initially_on=on,diagnostics=p))
    assert sum(b['initially_on'] for b in bindings)==13
    for row in plan['pairs']:
        la=by[row['light_actor']];lc=la.get_component_by_class(unreal.LightComponent)
        assert native.reflect_editor_properties(lc)==row['new_light_properties']
        assert native.value(lc.get_world_transform())==row['light_world_transform']
    assert all(native.sha(Path(p))==h for p,h in plan['new_asset_sha256'].items())
    materials=[]
    for kind in ('HotelTube','StreetLens'):
        row=next(x for x in plan['pairs'] if x['kind']==kind)
        src=unreal.load_asset(row['original_material']);dst=unreal.load_asset(row['master'])
        original=native.material_record(src)['chain'][-1];copied=native.material_record(dst)['chain'][-1]
        sp,dp=src.get_path_name(),dst.get_path_name()
        def norm(v):
            if isinstance(v,str):return v.replace(sp,dp)
            if isinstance(v,list):return [norm(x) for x in v]
            if isinstance(v,dict):return {norm(k):norm(x) for k,x in v.items()}
            return v
        assert original['properties']==copied['properties']
        for k,v in original['property_inputs'].items():
            if k!='MP_EMISSIVE_COLOR':assert norm(v)==copied['property_inputs'][k],(kind,k)
        assert all(copied['connected_graph_nodes'].get(k)==v for k,v in norm(original['connected_graph_nodes']).items()),kind
        materials.append(dict(kind=kind,passed=True,non_emission_properties_and_original_nodes_unchanged=True,source=sp,destination=dp))
    write('MaterialPreservation.json',dict(passed=True,masters=materials,all_33_have_LightStrength=True))
    write('ReadbackAudit.json',dict(passed=True,map_sha256=native.sha(MAP),existing_actor_count=7952,actor_count=7986,
        all_33_callable_real_lights=True,bindings=bindings,new_real_lights=17,new_controllers=17,initially_on=13,initially_off=20,
        protected_verification=prior.verify_protected(read('ProtectedBefore.json')['file_sha256'],True)))
    unreal.log('OLD_TOWN_FUNCTIONAL_LIGHTING_READBACK_PASS')

if __name__=='__main__':
    try:apply()
    except Exception:
        write('Failure.json',dict(passed=False,traceback=traceback.format_exc()));raise
