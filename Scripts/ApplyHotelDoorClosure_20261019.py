import sys,shutil,traceback
from datetime import datetime,timezone
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from HotelDoorClosureCommon import *
from BuildOldTownOpeningBlueprints import _templates,_configure
from OldTownHotelDetailMeshes import _result
from HotelDoorClosureGeometry import geometry_for_door,validate_recipe

def mesh_asset(parts,kind,material):
    encoded=json.dumps(parts,sort_keys=True,separators=(',',':'));suffix=hashlib.sha256(encoded.encode()).hexdigest()[:12]
    path=ASSET+'/SM_Hotel_'+kind+'_'+suffix;assets=unreal.EditorAssetLibrary
    if assets.does_asset_exist(path):
        mesh=unreal.load_asset(path);assert assets.get_metadata_tag(mesh,'CodexDoorClosureRecipe')==encoded
    else:
        assets.make_directory(ASSET);dynamic=unreal.DynamicMesh();opt=unreal.GeometryScriptPrimitiveOptions();opt.set_editor_property('material_id',0)
        for p in parts:
            tf=unreal.Transform(location=unreal.Vector(*p['center']),rotation=unreal.Rotator(pitch=0,yaw=p.get('yaw_deg',0),roll=0),scale=unreal.Vector(1,1,1))
            if p['kind']=='box':dynamic=_result(unreal.GeometryScript_Primitives.append_box(dynamic,opt,tf,*p['size'],0,0,0,unreal.GeometryScriptPrimitiveOriginMode.CENTER))
            else:dynamic=_result(unreal.GeometryScript_Primitives.append_cylinder(dynamic,opt,tf,p['radius'],p['height'],24,1,True,unreal.GeometryScriptPrimitiveOriginMode.CENTER))
        create=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        for k,v in dict(enable_recompute_normals=True,enable_recompute_tangents=True,enable_nanite=False,enable_collision=False).items():create.set_editor_property(k,v)
        mesh=_result(unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,path,create))
        copy=unreal.GeometryScriptCopyMeshToAssetOptions()
        for k,v in dict(enable_recompute_normals=True,enable_recompute_tangents=True,replace_materials=True,new_materials=[material],new_material_slot_names=[unreal.Name('DoorHardware')],emit_transaction=False).items():copy.set_editor_property(k,v)
        lod=unreal.GeometryScriptMeshWriteLOD();lod.set_editor_property('lod_index',0)
        _result(unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,mesh,copy,lod,True))
        assets.set_metadata_tag(mesh,'CodexDoorClosureRecipe',encoded);assert assets.save_loaded_asset(mesh,False)
    return mesh

def main():
    assert not (W/'Applied.json').exists()
    plan=read('Plan.json');baseline=read('ProtectedBefore.json')['file_sha256'];expected=dict(baseline)
    if (W/'Recovery1.json').exists():expected.update(read('Recovery1.json')['new_assets'])
    assert files()==expected and native.sha(MAP)==plan['source_map_sha256']
    assert read('Inspect1.Completion.json')['normal_zero_exit']
    backup=R/'Saved/CodexBackups'/('HotelDoorClosureBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    changed_files=[MAP]+[R/('Content/'+p[6:]+'.uasset') for p in plan['blueprints']]
    manifest=[]
    for f in changed_files:
        target=backup/f.relative_to(R);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);assert native.sha(target)==baseline[str(f)]
        manifest.append(dict(source=str(f),backup=str(target),sha256=baseline[str(f)]))
    write('Backup.json',dict(passed=True,directory=str(backup),files=manifest,created_before_writes=True))
    # All eight private Blueprint classes are used only by hotel doors in this map.
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True)
    refs={p:[str(x) for x in registry.get_referencers(p,options)] for p in plan['blueprints']}
    assert all(set(v)<={TARGET} for v in refs.values()),refs
    inventory=read('Doors.json');source={r['label']:r for r in inventory['all_doors']};mesh_cache={};recipes=[]
    for row in plan['doors']:
        key=tuple(row[k] for k in ('width','height','depth','hinge_side'))
        if key not in mesh_cache:
            data=geometry_for_door(row);proof=validate_recipe(row,angles=tuple(i/10 for i in range(901)));assert proof['passed']
            cs={c['name']:c for c in source[row['label']]['components']};mat=unreal.load_asset(cs['FrameLeft']['materials'][0])
            stop=mesh_asset(data['recipe']['stops'],'DoorStop',mat);moving=None
            if row['kind']=='swing':
                attached=next(a for a in inventory['attached'] if a['door']==row['label'] and a['label'].endswith('_MovingHinges'))
                moving=mesh_asset(data['recipe']['moving'],'HingeMoving_CloseFit',unreal.load_asset(attached['component']['materials'][0]))
            mesh_cache[key]=(stop,moving);recipes.append(dict(dimensions=key,proof=proof))
        stop,moving=mesh_cache[key];row['stop_mesh']=stop.get_path_name()
        if moving:
            next(a for a in plan['moving_hinges'] if a['door']==row['label'])['mesh']=moving.get_path_name()
    write('GeometryRecipes.json',dict(passed=True,recipes=recipes))
    # Edit only named component templates, keeping user graphs/materials intact.
    sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);lib=unreal.SubobjectDataBlueprintFunctionLibrary;bp_proofs=[]
    for path,labels in plan['blueprints'].items():
        bp=unreal.load_asset(path);before_path=Path(inventory['blueprints'][path]['file']);raw=before_path.read_bytes();before_text=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
        templates=_templates(sub,bp);row=next(r for r in plan['doors'] if r['label']==labels[0])
        active={n:c for n,(_,c) in templates.items() if isinstance(c,unreal.StaticMeshComponent) and c.static_mesh}
        for n,c in active.items():
            if n in {'DoorLeaf','LeafCollision','Handle','LeftLeaf','RightLeaf','LeftLeafCollision','RightLeafCollision','LeftHandle','RightHandle','LeftGlassPanel','RightGlassPanel'}:
                p=c.get_editor_property('relative_location');c.set_editor_property('relative_location',unreal.Vector(p.x,p.y-5,p.z))
        if 'DoorHinge' in templates:templates['DoorHinge'][1].set_editor_property('relative_rotation',unreal.Rotator(0,0,0))
        for n in ('LeftSlider','RightSlider'):
            if n in templates:
                c=templates[n][1];p=c.get_editor_property('relative_location');c.set_editor_property('relative_location',unreal.Vector(0,p.y,p.z))
        assert 'DoorStops' not in templates
        handle,reason=sub.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=templates['OpeningRoot'][0],new_class=unreal.StaticMeshComponent,blueprint_context=bp,conform_transform_to_parent=False))
        assert lib.is_handle_valid(handle) and not str(reason);assert sub.rename_subobject(handle,'DoorStops');assert sub.attach_subobject(templates['OpeningRoot'][0],handle)
        stop_c=_templates(sub,bp)['DoorStops'][1]
        _configure(stop_c,dict(mobility='STATIC',asset=row['stop_mesh'],material=active['FrameLeft'].get_material(0).get_path_name(),collision='NO_COLLISION'))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
        after_text=export_text(bp,Path(path).name);assert graph_sections(before_text)==graph_sections(after_text),path
        bp_proofs.append(dict(blueprint=path,user_graphs_variables_and_interfaces_identical=True))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==plan['actor_count']
    for row in plan['doors']:
        a=by[row['label']];assert native.value(a.get_actor_transform())==source[row['label']]['actor_transform'];cs=components(a)
        for old in source[row['label']]['components']:
            c=cs[old['name']];props=old['local'];loc=list(props['relative_location'])
            if old['name'] in row['changed_components']:loc[1]-=5
            edited=False
            for n,raw in (('relative_location',loc),('relative_rotation',props['relative_rotation']),('relative_scale3d',props['relative_scale3d'])):
                if native.value(c.get_editor_property(n))==raw:continue
                value=unreal.Rotator(pitch=raw[0],yaw=raw[1],roll=raw[2]) if n=='relative_rotation' else unreal.Vector(*raw)
                c.set_editor_property(n,value,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER);edited=True
            if edited:c.set_absolute(c.get_editor_property('absolute_location'),c.get_editor_property('absolute_rotation'),c.get_editor_property('absolute_scale'))
        stop=cs['DoorStops'];stop.set_static_mesh(unreal.load_asset(row['stop_mesh']));stop.set_material(0,cs['FrameLeft'].get_material(0))
    for row in plan['moving_hinges']:
        c=by[row['label']].static_mesh_component;assert c.static_mesh.get_path_name()==row['source_mesh'];c.set_static_mesh(unreal.load_asset(row['mesh']))
    write('AppliedPlan.json',plan)
    closure=validate_closed(by,plan);write('BeforeSaveClosure.json',closure)
    from HotelDoorClosurePreservation import verify
    state=snap(actors,'BeforeSaveDoorClosure5');write('BeforeSaveScene.json',state);preservation=verify(read('BeforeScene.json'),state,plan);write('BeforeSavePreservation.json',preservation)
    assert le.save_current_level()
    current=files();allowed={str(f) for f in changed_files}
    assert all(current.get(p)==h for p,h in baseline.items() if p not in allowed)
    added=set(current)-set(baseline);assert added and all(Path(p).is_relative_to(R/('Content/'+ASSET[6:])) for p in added)
    write('Applied.json',dict(passed=True,map_sha256=native.sha(MAP),source_map_sha256=plan['source_map_sha256'],hotel_doors=96,moving_hinges=62,
        modified_existing_files={p:current[p] for p in allowed},new_assets={p:current[p] for p in sorted(added)},backup=str(backup),
        blueprint_graph_preservation=bp_proofs,before_save_preservation=preservation,all_other_files_unchanged=True))
    unreal.log('HOTEL_DOOR_CLOSURE_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
