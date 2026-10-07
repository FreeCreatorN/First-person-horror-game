"""Build reusable Actor blueprints with named components and correct roots.

Only this phase's own asset directory can be edited. Parent component names
must appear earlier in ``specs``; rotations use [pitch, yaw, roll]. Existing
owned blueprints may be reused only when their component names match exactly.
"""
import unreal

ROOT='/Game/CodexGenerated/OldTown/Blueprints/Openings/'

def _templates(subsystem,bp):
    result={}
    library=unreal.SubobjectDataBlueprintFunctionLibrary
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data=library.get_data(handle)
        if not library.is_scene_component(data):continue
        obj=library.get_object_for_blueprint(data,bp)
        if obj is None:continue
        name=str(library.get_variable_name(data))
        result[name]=(handle,obj)
    return result

def _configure(obj,row):
    obj.set_editor_property('mobility',getattr(unreal.ComponentMobility,row.get('mobility','STATIC' if row.get('parent') is None else 'MOVABLE')))
    obj.set_editor_property('relative_location',unreal.Vector(*row.get('relative_location',[0,0,0])))
    rotation=row.get('relative_rotation',[0,0,0])
    obj.set_editor_property('relative_rotation',unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))
    obj.set_editor_property('relative_scale3d',unreal.Vector(*row.get('relative_scale',[1,1,1])))
    if isinstance(obj,unreal.StaticMeshComponent):
        mesh=unreal.load_asset(row['asset']);assert mesh,row['asset']
        obj.set_static_mesh(mesh)
        if row.get('material'):
            material=unreal.load_asset(row['material']);assert material,row['material']
            obj.set_material(0,material)
    if isinstance(obj,unreal.BoxComponent):
        obj.set_editor_property('box_extent',unreal.Vector(*row['box_extent']))
    if isinstance(obj,unreal.PrimitiveComponent):
        collision=row.get('collision','NO_COLLISION')
        obj.set_collision_profile_name('NoCollision' if collision=='NO_COLLISION' else 'BlockAll')
        obj.set_collision_enabled(getattr(unreal.CollisionEnabled,collision))
        hidden=bool(row.get('hidden',False))
        obj.set_editor_property('visible',not hidden)
        obj.set_editor_property('hidden_in_game',hidden)
        obj.set_editor_property('cast_shadow',not hidden)
        obj.set_editor_property('generate_overlap_events',False)

def create_blueprint(path,specs):
    assert path.startswith(ROOT),path
    assert specs and len({r['name'] for r in specs})==len(specs),'Duplicate component names'
    assert specs[0]['name']=='OpeningRoot' and specs[0].get('parent') is None,'OpeningRoot must be the first, unparented component'
    assert sum(r.get('parent') is None for r in specs)==1,'Exactly one scene root required'
    # Loading a nonexistent path allocates an empty UPackage. The creation
    # API then sees that package and refuses to create the Blueprint.
    exists=unreal.EditorAssetLibrary.does_asset_exist(path)
    if exists:
        bp=unreal.load_asset(path);assert isinstance(bp,unreal.Blueprint),path
    else:
        unreal.EditorAssetLibrary.make_directory(path.rsplit('/',1)[0])
        bp=unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(path,unreal.Actor)
        assert bp,path
    subsystem=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library=unreal.SubobjectDataBlueprintFunctionLibrary
    if not exists:
        handles=subsystem.k2_gather_subobject_data_for_blueprint(bp)
        actor_handles=[h for h in handles if library.is_actor(library.get_data(h))]
        assert len(actor_handles)==1,'Actor context missing'
        root=actor_handles[0];named={}
        for row in specs:
            parent=row.get('parent')
            assert parent is None or parent in named,'Parent must precede child: '+row['name']
            handle,reason=subsystem.add_new_subobject(unreal.AddNewSubobjectParams(
                parent_handle=named[parent] if parent else root,new_class=getattr(unreal,row['class']),
                blueprint_context=bp,conform_transform_to_parent=False))
            assert library.is_handle_valid(handle),(row['name'],str(reason))
            assert not str(reason),str(reason)
            assert subsystem.rename_subobject(handle,row['name']),row['name']
            if parent is None:
                data=library.get_data(handle)
                if not library.is_root_component(data):
                    assert subsystem.make_new_scene_root(root,handle,bp),'Failed to replace DefaultSceneRoot'
            else:
                assert subsystem.attach_subobject(named[parent],handle),'Failed component parenting: '+row['name']
            named[row['name']]=handle
    templates=_templates(subsystem,bp)
    assert set(templates)=={r['name'] for r in specs},(path,sorted(templates))
    for row in specs:
        _configure(templates[row['name']][1],row)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False),path
    cls=unreal.EditorAssetLibrary.load_blueprint_class(path)
    assert cls,path
    return bp,cls
