"""Adapt only assistant-made fixtures in the user's original town, using new assets."""
import sys, json, hashlib, shutil, traceback, re
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import unreal

R = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(R / 'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor, light_inventory
from OldTownMainLightingCommon import capture_geometry_state
W = R / 'Saved/CodexOutputs/OldTownCallableLighting_20261016'
READ = R / 'Saved/CodexOutputs/UserLightingReadOnly_20261016'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP = R / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSET = '/Game/CodexGenerated/OldTown/CallableLighting_20261016'
BP_PATH = ASSET + '/Blueprints/BP_OTS_LightCircuit'
NEW_FOLDER = R / ('Content/' + ASSET[6:])
TAG = 'OTS_CallableLighting_20261016'

def write(name, value):
    native.write(W / name, value)

def read(name):
    return json.loads((W / name).read_text(encoding='utf-8-sig'))

def files():
    return {str(p): native.sha(p) for root in (R/'Content', R/'Config') for p in sorted(root.rglob('*')) if p.is_file()}

def verify_protected(before, allow_map=False):
    current = files()
    changed = [p for p,h in before.items() if current.get(p) != h and not (allow_map and p == str(MAP))]
    new = sorted(set(current) - set(before))
    unexpected = [p for p in new if not Path(p).is_relative_to(NEW_FOLDER)]
    assert not changed and not unexpected, dict(changed=changed,unexpected=unexpected)
    return dict(passed=True, checked_existing_files=len(before)-(1 if allow_map else 0), changed_protected_files=changed, new_files=new)

def full_native_hashes(actors, phase):
    rows = {}
    # Every existing Actor gets full native serialization, including StaticMeshActors.
    for a in actors:
        if TAG in [str(t) for t in a.tags]:
            continue
        label = a.get_actor_label()
        file = W/'NativePreservation'/phase/(re.sub(r'[^\w-]','_',label)+'_'+hashlib.sha256(a.get_path_name().encode()).hexdigest()[:8]+'.t3d')
        text, proof = native.native_text_export(a,file)
        assert proof['passed'], label
        rows[label] = dict(native_text_sha256=hashlib.sha256(text.encode()).hexdigest(), file=str(file))
    return rows

def snapshot(actors, phase):
    labels = {a.get_actor_label():a for a in actors}
    assert len(labels)==len(actors), 'Duplicate actor labels'
    return dict(actor_count=len(actors), actors={n:stable_actor(a) for n,a in labels.items()},
        exact_scene_components=capture_geometry_state(actors), lights=light_inventory(actors),
        full_light_properties={a.get_actor_label()+'::'+c.get_name():native.reflect_editor_properties(c) for a in actors for c in a.get_components_by_class(unreal.LightComponentBase)},
        actor_properties={n:native.props(a,['hidden','is_editor_only_actor','actor_enable_collision','replicates','net_dormancy','owner','instigator']) for n,a in labels.items()},
        full_existing_actor_native=full_native_hashes(actors, phase))

def get_pairs(by):
    result=[]
    for floor in range(4):
        for i,slot in ((0,1),(1,4)):
            result.append((f'OTS_HotelV4_F{floor}_SurvivingTube{i}',f'OTS_HotelV4_F{floor}_GalleryTube{slot:02d}','HotelTube'))
    for i in (1,2,4,5,6,7,8,9):
        result.append((f'OTS_Light_StreetLamp{i:02d}',f'OTS_P2Prop_StreetLamp_{i:02d}','StreetLens'))
    rows=[]
    for light_label,mesh_label,kind in result:
        la,ma=by[light_label],by[mesh_label]
        assert isinstance(ma,unreal.StaticMeshActor)
        lc=list(la.get_components_by_class(unreal.LightComponent));assert len(lc)==1
        lc=lc[0]
        assert isinstance(lc,(unreal.RectLightComponent,unreal.SpotLightComponent))
        mc=ma.static_mesh_component;old=mc.get_material(2)
        assert isinstance(old,unreal.MaterialInstanceConstant)
        parent=old.get_editor_property('parent')
        assert parent.get_path_name().split('.')[0].endswith('/M_RF_'+kind)
        on=bool(lc.get_editor_property('visible')) and not lc.get_editor_property('hidden_in_game') and bool(lc.get_editor_property('affects_world')) and not la.get_editor_property('hidden') and float(lc.get_editor_property('intensity'))>0
        rows.append(dict(light_actor=light_label,lamp_actor=mesh_label,kind=kind,component=mc.get_name(),material_slot=2,
            original_material=old.get_path_name(),source_master=parent.get_path_name(),initially_on=on,
            base_intensity=float(lc.get_editor_property('intensity')),light_class=lc.get_class().get_path_name(),
            old_emission_strength=float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(old,'LampEmissionStrength')),
            original_effective_parameters=native.material_record(old)['effective_instance_parameters']))
    assert len(rows)==16 and sum(r['initially_on'] for r in rows)==13
    return rows

def new_master(source, kind):
    path=ASSET+'/Materials/M_OTS_Callable_'+kind
    edit=unreal.MaterialEditingLibrary
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        m=unreal.load_asset(path)
        assert 'LightStrength' in [str(n) for n in edit.get_scalar_parameter_names(m)]
        return m
    m=unreal.EditorAssetLibrary.duplicate_asset(source.split('.')[0],path)
    assert isinstance(m,unreal.Material)
    old=edit.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    old_out=edit.get_material_property_input_node_output_name(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert old and old.get_path_name().startswith(m.get_path_name()+':')
    switch=edit.create_material_expression(m,unreal.MaterialExpressionScalarParameter,800,-600)
    switch.set_editor_property('parameter_name',unreal.Name('LightStrength'))
    switch.set_editor_property('default_value',20.)
    switch.set_editor_property('desc','LightStrength: 20 on, 0 off')
    normalize=edit.create_material_expression(m,unreal.MaterialExpressionMultiply,1000,-600)
    normalize.set_editor_property('const_b',.05)
    assert edit.connect_material_expressions(switch,'',normalize,'A')
    emission=edit.create_material_expression(m,unreal.MaterialExpressionMultiply,1200,-400)
    assert edit.connect_material_expressions(old,old_out,emission,'A')
    assert edit.connect_material_expressions(normalize,'',emission,'B')
    assert edit.connect_material_property(emission,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    edit.recompile_material(m)
    assert unreal.EditorAssetLibrary.save_loaded_asset(m,False)
    # Parent graph and WPO are copied; only the new emission multiplier is introduced.
    return m

def private_instance(row, master):
    path=ASSET+'/Materials/Instances/MI_'+row['lamp_actor']
    edit=unreal.MaterialEditingLibrary
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi=unreal.load_asset(path)
    else:
        mi=unreal.EditorAssetLibrary.duplicate_asset(row['original_material'].split('.')[0],path)
    assert isinstance(mi,unreal.MaterialInstanceConstant)
    edit.set_material_instance_parent(mi,master)
    # UE5.7's setter updates the value but leaves its bool result false; verify the value itself.
    edit.set_material_instance_scalar_parameter_value(mi,'LightStrength',20. if row['initially_on'] else 0.)
    assert edit.get_material_instance_scalar_parameter_value(mi,'LightStrength')==(20. if row['initially_on'] else 0.)
    assert unreal.EditorAssetLibrary.save_loaded_asset(mi,False)
    effective=native.material_record(mi)['effective_instance_parameters']
    for typ,values in row['original_effective_parameters'].items():
        for n,v in values.items():
            assert effective[typ][n]==v,(path,n,v,effective)
    assert effective['scalar']['LightStrength']==(20. if row['initially_on'] else 0.)
    return mi

def apply():
    assert not (W/'Applied.json').exists(), 'Already applied; audit instead'
    proof=json.loads((READ/'ReadOnly.json').read_text(encoding='utf8'));assert proof['passed']
    old_files=json.loads((READ/'ProtectedBefore.json').read_text(encoding='utf8'))['file_sha256']
    unchanged=verify_protected(old_files)
    backup=R/'Saved/CodexBackups'/('OriginalTownBeforeCallableLights_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False)
    saved=backup/'L_OldTownSchoolStreet.umap';shutil.copy2(MAP,saved)
    assert native.sha(saved)==old_files[str(MAP)]
    write('Backup.json',dict(passed=True,source_map=str(MAP),source_sha256=old_files[str(MAP)],file=str(saved),sha256=native.sha(saved),created_before_any_map_or_material_write=True))
    write('ProtectedBefore.json',dict(file_sha256=old_files))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    if (W/'BeforeSnapshot.json').exists():
        # A failed pre-save attempt may leave only new private packages. All original input
        # bytes are verified unchanged above. The full post-edit Native compare below still
        # checks every existing Actor against this original captured state.
        before=read('BeforeSnapshot.json')
        write('PreSaveRetryProof.json',dict(passed=True,original_input_files_unchanged=True,
            original_snapshot_sha256=native.sha(W/'BeforeSnapshot.json'),protected=unchanged,
            fresh_after_edit_native_comparison_still_required=True))
    else:
        before=snapshot(actors,'Before');write('BeforeSnapshot.json',before)
    pairs=get_pairs(by);write('FixturePlan.json',dict(passed=True,pairs=pairs,existing_actor_count=len(actors),functional_fixtures=16,initially_on=13,initially_off=3,broken_decorative_fixtures_unchanged=17))
    masters={kind:new_master(next(r['source_master'] for r in pairs if r['kind']==kind),kind) for kind in ('HotelTube','StreetLens')}
    bp=unreal.OldTownLightCircuitEditorLibrary.create_circuit_blueprint(BP_PATH);assert bp
    cls=unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH);assert cls
    expected=deepcopy(before)
    for row in pairs:
        ma,la=by[row['lamp_actor']],by[row['light_actor']]
        mi=private_instance(row,masters[row['kind']])
        ma.static_mesh_component.set_material(2,mi)
        label='OTS_LightCircuit_'+row['lamp_actor'].removeprefix('OTS_')
        assert label not in by
        controller=ae.spawn_actor_from_class(cls,ma.get_actor_location(),unreal.Rotator(),False)
        assert controller
        controller.set_actor_label(label)
        controller.set_folder_path(unreal.Name('OldTownSchoolStreet/Lighting/CallableCircuits'))
        controller.set_editor_property('tags',[unreal.Name(TAG)])
        controller.set_editor_property('target_lamp_mesh',ma)
        controller.set_editor_property('emissive_material_slot',2)
        controller.set_editor_property('controlled_lights',[la])
        controller.set_editor_property('base_intensities',[row['base_intensity']])
        controller.set_editor_property('initially_on',row['initially_on'])
        row.update(material=mi.get_path_name(),controller_label=label,controller_path=controller.get_path_name())
        native_row=expected['full_existing_actor_native'][row['lamp_actor']]
        raw=Path(native_row['file']).read_bytes()
        txt=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
        assert row['original_material'] in txt
        expected_txt=txt.replace(row['original_material'],mi.get_path_name())
        native_row['native_text_sha256']=hashlib.sha256(expected_txt.encode()).hexdigest()
        c=next(c for c in expected['actors'][row['lamp_actor']]['components'] if c['name']==row['component'])
        c['materials'][2]=mi.get_path_name()
        key=row['lamp_actor']+'::'+row['component']
        after_geo=capture_geometry_state([ma])[key]
        old_geo=deepcopy(expected['exact_scene_components'][key]);new_geo=deepcopy(after_geo)
        assert [i for i,(a,b) in enumerate(zip(old_geo['materials'],new_geo['materials'])) if a!=b]==[2]
        old_geo.pop('materials');new_geo.pop('materials')
        old_geo['geometry_properties'].pop('override_materials');new_geo['geometry_properties'].pop('override_materials')
        assert old_geo==new_geo
        expected['exact_scene_components'][key]=after_geo
    existing_after=snapshot(actors,'BeforeSave')
    compare_snapshot(expected,existing_after)
    verify_protected(old_files)
    unreal.OldTownLightCircuitEditorLibrary.restore_all_editor_previews()
    assert le.save_current_level()
    newhashes={str(p):native.sha(p) for p in sorted(NEW_FOLDER.rglob('*')) if p.is_file()}
    assert len(newhashes)==19,len(newhashes)
    write('ExpectedExistingSnapshot.json',expected)
    write('Applied.json',dict(passed=True,target_level=TARGET,map_sha256=native.sha(MAP),source_map_sha256=old_files[str(MAP)],pairs=pairs,new_asset_sha256=newhashes,
        actor_count_before=len(actors),actor_count_after=len(actors)+16,main_and_user_assets_read_only=True,no_existing_actor_removed=True,geometry_unchanged=True,existing_light_source_properties_unchanged=True,
        intentionally_synchronized_initially_off_lampshade_count=3,
        protected_verification=verify_protected(old_files,True)))
    unreal.log('OLD_TOWN_CALLABLE_LIGHTS_APPLY_PASS '+native.sha(MAP))

def compare_snapshot(expected,current):
    for name in ('actor_count','actors','exact_scene_components','lights','full_light_properties','actor_properties'):
        assert current[name]==expected[name], 'Existing state changed: '+name
    e={n:x['native_text_sha256'] for n,x in expected['full_existing_actor_native'].items()}
    c={n:x['native_text_sha256'] for n,x in current['full_existing_actor_native'].items()}
    if e!=c:
        write('NativeDifference.json',dict(changed=[n for n in e if c.get(n)!=e[n]],phase=current['full_existing_actor_native']))
    assert e==c, 'Full existing Actor native state changed'

def audit():
    applied=read('Applied.json');assert applied['passed'] and native.sha(MAP)==applied['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());controllers=[a for a in actors if TAG in [str(t) for t in a.tags]]
    existing=[a for a in actors if a not in controllers]
    current=snapshot(existing,'Readback');write('ReadbackSnapshot.json',current)
    compare_snapshot(read('ExpectedExistingSnapshot.json'),current)
    assert len(controllers)==16 and len(actors)==applied['actor_count_after']
    by={a.get_actor_label():a for a in actors};rows=[]
    for p in applied['pairs']:
        c=by[p['controller_label']]
        row=json.loads(unreal.OldTownLightCircuitEditorLibrary.inspect_circuit(c))
        assert c.get_editor_property('target_lamp_mesh')==by[p['lamp_actor']]
        assert list(c.get_editor_property('controlled_lights'))==[by[p['light_actor']]]
        assert bool(c.get_editor_property('initially_on'))==p['initially_on']
        assert not c.has_initialized_light_circuit(), 'Editor load unexpectedly created MID'
        assert 'LightStrength' in [str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(by[p['lamp_actor']].static_mesh_component.get_material(2))]
        rows.append(row)
    protected=verify_protected(read('ProtectedBefore.json')['file_sha256'],True)
    assert all(native.sha(Path(p))==h for p,h in applied['new_asset_sha256'].items())
    material_proofs=[]
    for kind in ('HotelTube','StreetLens'):
        source=unreal.load_asset(next(p['source_master'] for p in applied['pairs'] if p['kind']==kind))
        clone=unreal.load_asset(ASSET+'/Materials/M_OTS_Callable_'+kind)
        original=native.material_record(source)['chain'][-1]
        copied=native.material_record(clone)['chain'][-1]
        srcpath=source.get_path_name();dstpath=clone.get_path_name()
        def norm(v):
            if isinstance(v,str):return v.replace(srcpath,dstpath)
            if isinstance(v,list):return [norm(x) for x in v]
            if isinstance(v,dict):return {norm(k):norm(x) for k,x in v.items()}
            return v
        assert original['properties']==copied['properties']
        for prop,value in original['property_inputs'].items():
            if prop!='MP_EMISSIVE_COLOR':assert norm(value)==copied['property_inputs'][prop],(kind,prop)
        oldnodes=norm(original['connected_graph_nodes']);newnodes=copied['connected_graph_nodes']
        assert all(newnodes.get(k)==v for k,v in oldnodes.items()),kind
        added=set(newnodes)-set(oldnodes)
        assert len(added)==3,(kind,len(added))
        material_proofs.append(dict(kind=kind,passed=True,source_master=srcpath,new_master=dstpath,
            original_connected_nodes_preserved=len(oldnodes),added_nodes=3,non_emission_outputs_identical=True,
            original_lamp_mask_and_world_position_offset_graph_identical=True,formula='OriginalEmissive * LightStrength * 0.05'))
    write('MaterialPreservation.json',dict(passed=True,masters=material_proofs,fixtures=16,initially_off_emission_zero=3))
    write('ReadbackAudit.json',dict(passed=True,map_sha256=native.sha(MAP),existing_actors_unchanged_except_16_lampshade_slots=True,existing_light_sources_all_properties_unchanged=True,
        old_actor_identity_preserved=True,existing_actor_count=len(existing),controllers=len(controllers),protected_verification=protected,circuits=rows))
    unreal.log('OLD_TOWN_CALLABLE_LIGHTS_READBACK_PASS')

if __name__=='__main__':
    try:
        if '-audit' in sys.argv:
            audit()
        else:
            apply()
    except Exception:
        write('Failure.json',dict(passed=False,traceback=traceback.format_exc()))
        raise
