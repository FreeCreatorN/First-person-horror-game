"""Bound preservation and directional-light proofs for the Main-light copy."""
import json,hashlib,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
W=R/'Saved/CodexOutputs/OldTownMainLighting_20261015'
S=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
CANON=R/'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SOURCE='/Game/Yastar/Maps/L_Main'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
MAIN=R/'Content/Yastar/Maps/L_Main.umap'
FOLDER='OldTownSchoolStreet/Lighting/FromMain_20261015'
LABELS={'DirectionalLight':'OTS_MainDirectional_Sun','MoonDirectionalLight':'OTS_MainDirectional_Moon'}
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def ref(p):return dict(file=str(Path(p).resolve()),sha256=sha(p))
def frozen():
    pointer=read(CANON/'CurrentEvidence.json');final=read(S/'FinalReview.json')
    assert pointer['source_bundle_name']==S.name and final['passed'] and final['published']
    assert sha(S/'FinalReview.json')==pointer['current_final_review_sha256']
    for n,h in pointer['current_report_sha256'].items():assert sha(S/n)==h,n
    assets=pointer['current_asset_sha256'];assert len(assets)==1206
    files={**assets,**read(S/'Baseline.json')['protected_file_sha256']}
    assert str(MAIN) not in files,'Main is independently user edited.'
    return pointer,files
def verify_files(files):
    for p,h in files.items():assert sha(p)==h,'Protected file changed: '+p
def verify_backup(digest):
    proof=read(W/'BackupBeforeLighting.json');assert proof['passed'] and proof['oldtown_map_sha256']==digest
    manifest=read(proof['manifest_file']);assert sha(proof['manifest_file'])==proof['manifest_sha256']
    assert manifest['passed'] and manifest['completed_before_lighting_write'] and manifest['oldtown_map_sha256']==digest
    base=Path(manifest['backup_directory']).resolve();assert base.is_relative_to((R/'Saved/CodexBackups').resolve())
    rows={}
    for row in manifest['files']:
        p=(base/row['relative_path']).resolve();assert p.is_relative_to(base)
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],str(p)
        assert row['source'] not in rows,'Duplicate backup source: '+row['source']
        rows[row['source']]=row
    assert manifest['file_count']==len(manifest['files']) and manifest['current_asset_packages']==1206
    _,protected=frozen()
    expected={**protected,str(MAP):digest}
    for source,expected_sha in expected.items():
        source_path=Path(source).resolve()
        if source_path.is_relative_to(R):
            assert source in rows and rows[source]['sha256']==expected_sha,'Backup omitted current protected source: '+source
            assert rows[source]['relative_path']==source_path.relative_to(R).as_posix(),source
        else:
            assert manifest['engine_dependencies_not_copied'][source]==expected_sha,source
    reference=manifest['main_reference_only'];reference_file=Path(reference['file']).resolve()
    assert reference_file.is_relative_to(base/'ReferenceMain') and not reference['restore_to_main_automatically']
    assert sha(reference_file)==reference['sha256'],'Reference Main backup changed.'
    return ref(W/'BackupBeforeLighting.json')
def level_package(level):
    # ULevel's outer is a UWorld (Package.Map:PersistentLevel), not its package.
    return level.get_outermost().get_path_name()
def verify_target_only_world(world,persistent):
    import unreal
    assert level_package(world)==level_package(persistent)==TARGET
    levels=list(unreal.EditorLevelUtils.get_levels(world))
    assert len(levels)==1 and levels[0]==persistent,'Unexpected remaining loaded level.'
    # StreamingLevels is a private, non-editor-visible UPROPERTY in UE5.7;
    # querying it through get_editor_property is forbidden. This public lookup
    # also rejects a Main streaming entry which remains while unloaded.
    assert unreal.GameplayStatics.get_streaming_level(world,unreal.Name(SOURCE)) is None,'Main streaming entry remains.'
    return dict(passed=True,loaded_level_count=1,loaded_level_packages=[level_package(x) for x in levels],
        source_main_streaming_entry_absent=True)
def capture_geometry_state(actors):
    import unreal
    import InspectOldTownRealismInput as native
    result={}
    for a in actors:
        for c in a.get_components_by_class(unreal.SceneComponent):
            parent=c.get_attach_parent()
            row=dict(class_path=c.get_class().get_path_name(),parent=parent.get_path_name() if parent else None,
                world_transform=native.value(c.get_world_transform()),
                local=native.props(c,['relative_location','relative_rotation','relative_scale3d','absolute_location','absolute_rotation','absolute_scale','visible','hidden_in_game','mobility']))
            if isinstance(c,unreal.StaticMeshComponent):
                row.update(mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
                    materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())],
                    collision=str(c.get_collision_enabled()),collision_profile=str(c.get_collision_profile_name()),
                    geometry_properties=native.props(c,['override_materials','cast_shadow','reverse_culling','evaluate_world_position_offset','world_position_offset_disable_distance','receives_decals','custom_primitive_data']))
            result[a.get_actor_label()+'::'+c.get_name()]=row
    return result
def directional_record(a):
    import unreal
    import InspectOldTownRealismInput as native
    from ApplyOldTownRealismRefinement import stable_actor
    components=list(a.get_components_by_class(unreal.DirectionalLightComponent));assert len(components)==1
    c=components[0]
    component_records={}
    for component in a.get_components_by_class(unreal.ActorComponent):
        record=dict(class_path=component.get_class().get_path_name(),properties=native.reflect_editor_properties(component))
        if isinstance(component,unreal.SceneComponent):
            parent=component.get_attach_parent()
            record.update(world_transform=native.value(component.get_world_transform()),parent=parent.get_name() if parent else None)
        assert component.get_name() not in component_records
        component_records[component.get_name()]=record
    return dict(label=a.get_actor_label(),actor_path=a.get_path_name(),class_path=a.get_class().get_path_name(),actor_state=stable_actor(a),
        actor_properties=native.props(a,['hidden','is_editor_only_actor','actor_enable_collision','replicates']),
        world_transform=native.value(c.get_world_transform()),component_name=c.get_name(),
        properties=native.reflect_editor_properties(c),component_records=component_records,owner_level=a.get_outer().get_path_name())
def normalized_references(value,source_actor_path,target_actor_path):
    if isinstance(value,str):return value.replace(source_actor_path,target_actor_path)
    if isinstance(value,list):return [normalized_references(x,source_actor_path,target_actor_path) for x in value]
    if isinstance(value,dict):return {k:normalized_references(v,source_actor_path,target_actor_path) for k,v in value.items()}
    return value
def compare_world_transform(st,ct):
    for key in ('translation','scale'):
        assert len(st[key])==len(ct[key])==3
        assert max(abs(a-b) for a,b in zip(st[key],ct[key]))<1e-6,(key,st,ct)
    q1,q2=st['rotation_quaternion_xyzw'],ct['rotation_quaternion_xyzw']
    assert len(q1)==len(q2)==4 and all(math.isfinite(x) for x in q1+q2)
    assert abs(sum(x*x for x in q1)-1)<1e-7 and abs(sum(x*x for x in q2)-1)<1e-7
    error=min(max(abs(a-b) for a,b in zip(q1,q2)),max(abs(a+b) for a,b in zip(q1,q2)))
    assert error<1e-7,(q1,q2,error)
    return error
def compare_light(source,clone):
    assert source['class_path']==clone['class_path']=='/Script/Engine.DirectionalLight'
    assert source['owner_level'].split('.')[0]==SOURCE and source['actor_path'].startswith(SOURCE+'.')
    assert clone['owner_level'].split('.')[0]==TARGET and clone['actor_path'].startswith(TARGET+'.')
    assert source['actor_properties']==clone['actor_properties']
    assert source['component_name']==clone['component_name']
    transforms={'relative_location','relative_translation','relative_rotation','relative_scale3d'}
    sp={k:v for k,v in source['properties'].items() if k not in transforms}
    cp={k:v for k,v in clone['properties'].items() if k not in transforms}
    sp=normalized_references(sp,source['actor_path'],clone['actor_path'])
    assert sp==cp,{k:(sp.get(k),cp.get(k)) for k in set(sp)|set(cp) if sp.get(k)!=cp.get(k)}
    error=compare_world_transform(source['world_transform'],clone['world_transform'])
    assert source['actor_state']['tags']==clone['actor_state']['tags']
    sc,cc=source['component_records'],clone['component_records'];assert set(sc)==set(cc)
    for name,srecord in sc.items():
        crecord=cc[name];assert srecord['class_path']==crecord['class_path']
        expected=normalized_references({k:v for k,v in srecord['properties'].items() if k not in transforms},source['actor_path'],clone['actor_path'])
        actual={k:v for k,v in crecord['properties'].items() if k not in transforms}
        assert expected==actual,('Component properties differ',name,{k:(expected.get(k),actual.get(k)) for k in set(expected)|set(actual) if expected.get(k)!=actual.get(k)})
        if 'world_transform' in srecord:
            assert srecord['parent']==crecord['parent'],name
            compare_world_transform(srecord['world_transform'],crecord['world_transform'])
    assert SOURCE not in json.dumps(clone,ensure_ascii=False),'Copied actor retains a source Main object reference.'
    return dict(passed=True,source_label=source['label'],target_label=clone['label'],
        reflected_properties_compared=len(sp),full_property_names=sorted(sp),
        all_actor_components_compared=len(sc),source_actor_object_references_remapped=True,no_source_main_object_references=True,
        transform_fields_compared_as_world_transform=sorted(transforms),quaternion_max_abs_error=error,
        complete_photometry_shadow_mobility_atmosphere_and_visibility_preserved=True)
