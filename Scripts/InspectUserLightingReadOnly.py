"""Read persisted user lighting without saves, explicit compiles, or SCS mutation."""
import sys, json, hashlib, re, traceback
from pathlib import Path
from datetime import datetime, timezone
import unreal

R = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(R / 'Scripts'))
import InspectOldTownRealismInput as native

W = R / 'Saved/CodexOutputs/UserLightingReadOnly_20261016'
W.mkdir(parents=True, exist_ok=True)
MAIN = '/Game/Yastar/Maps/L_Main'
TOWN = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SWITCH = '/Game/Yastar/Blueprints/BP_LightSwitch'
BP_VARIABLES = {}

def content_hashes():
    roots = [R / 'Content', R / 'Config']
    return {str(p): native.sha(p) for root in roots for p in sorted(root.rglob('*')) if p.is_file()}

def export(obj, label):
    text, proof = native.native_text_export(obj, W / 'Native' / (label + '.t3d'))
    assert proof['passed'], label
    return proof

def material_summary(mat):
    ed = unreal.MaterialEditingLibrary
    row = dict(asset=mat.get_path_name(), class_path=mat.get_class().get_path_name())
    row['parameter_names'] = {}
    row['effective_parameters'] = {}
    for prefix in ('scalar', 'vector', 'texture', 'static_switch'):
        names = [str(x) for x in getattr(ed, 'get_' + prefix + '_parameter_names')(mat)]
        row['parameter_names'][prefix] = names
        if isinstance(mat, unreal.MaterialInstanceConstant):
            row['effective_parameters'][prefix] = {n: native.value(getattr(ed, 'get_material_instance_' + prefix + '_parameter_value')(mat, unreal.Name(n))) for n in names}
    if isinstance(mat, unreal.MaterialInstanceConstant):
        row['parent'] = native.path_of(mat.get_editor_property('parent'))
    return row

def scene_component(c):
    row = dict(name=c.get_name(), path=c.get_path_name(), class_path=c.get_class().get_path_name())
    if isinstance(c, unreal.SceneComponent):
        row['world_transform'] = native.value(c.get_world_transform())
        row['parent'] = native.path_of(c.get_attach_parent())
        row['properties'] = native.props(c, ['visible','hidden_in_game','mobility'])
    if isinstance(c, unreal.LightComponent):
        row['properties'] = native.reflect_editor_properties(c)
    if isinstance(c, unreal.StaticMeshComponent):
        row.update(mesh=native.path_of(c.static_mesh), materials=[native.path_of(c.get_material(i)) for i in range(c.get_num_materials())])
    return row

def blueprint(path):
    bp = unreal.load_asset(path)
    assert isinstance(bp, unreal.Blueprint), path
    # Never gather subobjects: UE can create inherited override templates while gathering.
    result = dict(asset=path, native=export(bp, bp.get_name()), properties=native.reflect_editor_properties(bp))
    raw = Path(result['native']['file']).read_bytes()
    txt = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')
    variable_names = sorted(set(re.findall(r'VarName="([^"]+)"', txt)))
    BP_VARIABLES[path] = variable_names
    result['variable_names'] = variable_names
    cls = bp.generated_class()
    if cls:
        cdo = unreal.get_default_object(cls)
        result['generated_class'] = cls.get_path_name()
        result['cdo_native'] = export(cdo, bp.get_name() + '_CDO')
        result['cdo_properties'] = native.reflect_editor_properties(cdo)
        result['explicit_variable_defaults'] = native.props(cdo, variable_names)
        result['python_members'] = [n for n in dir(cdo) if not n.startswith('_')]
    return result

def inspect_level(path):
    le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ae = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(path), path
    actors = list(ae.get_all_level_actors())
    result = dict(level=path, actor_count=len(actors), lighting_actors=[], materials={})
    light_classes = set()
    for actor in actors:
        lights = list(actor.get_components_by_class(unreal.LightComponent))
        name = actor.get_actor_label()
        is_switch = 'LightSwitch' in actor.get_class().get_path_name()
        relevant = bool(lights) or is_switch or bool(re.search(r'(lamp|light|tube|灯)', name, re.I))
        meshes = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        for c in meshes:
            for i in range(c.get_num_materials()):
                mat = c.get_material(i)
                if mat and mat.get_path_name() not in result['materials']:
                    result['materials'][mat.get_path_name()] = material_summary(mat)
        if not relevant:
            continue
        row = dict(label=name, name=actor.get_name(), path=actor.get_path_name(), class_path=actor.get_class().get_path_name(), folder=str(actor.get_folder_path()), transform=native.value(actor.get_actor_transform()), properties=native.reflect_editor_properties(actor))
        row['explicit_blueprint_variables'] = native.props(actor, BP_VARIABLES.get(actor.get_class().get_path_name().split('.')[0], []))
        row['components'] = [scene_component(c) for c in actor.get_components_by_class(unreal.SceneComponent)]
        safe = re.sub(r'[^\w-]', '_', name)
        row['native'] = export(actor, ('Main_' if path == MAIN else 'Town_') + safe + '_' + hashlib.sha256(actor.get_path_name().encode()).hexdigest()[:8])
        if actor.get_class().get_path_name().startswith('/Game/'):
            light_classes.add(actor.get_class().get_path_name().split('.')[0])
        result['lighting_actors'].append(row)
    result['lighting_blueprint_classes'] = sorted(light_classes)
    # Deep-read graphs only for material names or parameter names suggesting emission.
    for p, row in result['materials'].items():
        names = ' '.join(n for ns in row['parameter_names'].values() for n in ns)
        if re.search(r'(emiss|lamp|light|glow|tube|亮|发光)', p + ' ' + names, re.I):
            mat = unreal.load_asset(p)
            row['deep'] = native.material_record(mat)
            current = mat
            visited = set()
            while current and current.get_path_name() not in visited:
                visited.add(current.get_path_name())
                tag = 'Material_' + current.get_name() + '_' + hashlib.sha256(current.get_path_name().encode()).hexdigest()[:8]
                export(current, tag)
                current = current.get_editor_property('parent') if isinstance(current, unreal.MaterialInstanceConstant) else None
    return result

def main():
    before = content_hashes()
    native.write(W / 'ProtectedBefore.json', dict(file_sha256=before, timestamp_utc=datetime.now(timezone.utc).isoformat()))
    bps = {p: blueprint(p) for p in (SWITCH, '/Game/Yastar/Blueprints/BPI_Interact')}
    main_state = inspect_level(MAIN)
    town_state = inspect_level(TOWN)
    for p in sorted(set(main_state['lighting_blueprint_classes'] + town_state['lighting_blueprint_classes'])):
        if p not in bps:
            bps[p] = blueprint(p)
    after = content_hashes()
    changed = {p: [before.get(p), after.get(p)] for p in set(before) | set(after) if before.get(p) != after.get(p)}
    native.write(W / 'ReadOnly.json', dict(passed=not changed, no_save_or_explicit_compile_called=True, no_scs_gather_called=True, protected_file_count=len(before), changed_files=changed, blueprints=bps, main=main_state, town=town_state))
    assert not changed, changed
    unreal.log('USER_LIGHTING_READ_ONLY_PASS ' + json.dumps(dict(protected=len(before), main_actors=main_state['actor_count'], town_actors=town_state['actor_count'], blueprints=len(bps))))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        native.write(W / 'Failure.json', dict(passed=False, traceback=traceback.format_exc()))
        raise
