"""Independent material clones for millimetre-scale world translations.

Only new assets below ``assetroot`` are mutated or saved. Original material
graphs, textures, static switches, instance parameters and parent chains remain
unchanged. A whole component is translated uniformly; hard mesh edges do not
split as they would with a VertexNormalWS displacement.
"""
import hashlib
import json
import math
import re
from pathlib import Path

import unreal

DEFAULT_ROOT = '/Game/CodexGenerated/OldTown/Materials/SurfaceSeparation_20261009'
PARAMETER = 'CodexSurfaceTranslationCM_20261009'
VERSION = 'constant-world-translation-v1'
_parents = {}
_instances = {}
_created = {}
_original_hashes = {}
_visiting = set()
_edit = unreal.MaterialEditingLibrary
_assets = unreal.EditorAssetLibrary


def _package(obj):
    return obj.get_path_name().split('.')[0]


def _asset_file(obj):
    package = _package(obj)
    if package.startswith('/Game/'):
        return Path(unreal.Paths.project_dir()).resolve() / ('Content/' + package[6:] + '.uasset')
    if package.startswith('/Engine/'):
        return Path(unreal.Paths.engine_content_dir()).resolve() / (package[8:] + '.uasset')
    return None


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _remember_original(obj):
    path = _asset_file(obj)
    if path and path.is_file():
        value = _sha(path)
        previous = _original_hashes.setdefault(str(path), value)
        assert previous == value, 'Original material file changed: ' + str(path)


def _name(obj, prefix):
    readable = re.sub('[^A-Za-z0-9_]+', '_', obj.get_name())[:64]
    identity = hashlib.sha256(obj.get_path_name().encode('utf-8')).hexdigest()[:12]
    return prefix + readable + '_' + identity


def _metadata(obj, source, kind):
    _assets.set_metadata_tag(obj, 'CodexSurfaceSeparationSource', source.get_path_name())
    _assets.set_metadata_tag(obj, 'CodexSurfaceSeparationVersion', VERSION)
    _assets.set_metadata_tag(obj, 'CodexSurfaceSeparationKind', kind)
    _assets.set_metadata_tag(obj, 'CodexSurfaceSeparationReady', '1')


def _existing(package, source, kind):
    obj = unreal.load_asset(package)
    if not obj:
        return None
    assert _assets.get_metadata_tag(obj, 'CodexSurfaceSeparationSource') == source.get_path_name(), package
    assert _assets.get_metadata_tag(obj, 'CodexSurfaceSeparationVersion') == VERSION, package
    assert _assets.get_metadata_tag(obj, 'CodexSurfaceSeparationKind') == kind, package
    assert _assets.get_metadata_tag(obj, 'CodexSurfaceSeparationReady') == '1', 'Incomplete generated material: ' + package
    return obj


def _save(obj, root, source, kind, **extra):
    assert _package(obj).startswith(root + '/'), 'Refusing to save a shared material.'
    _metadata(obj, source, kind)
    assert _assets.save_loaded_asset(obj, False), obj.get_path_name()
    path = _asset_file(obj)
    assert path and path.is_file(), obj.get_path_name()
    _created[obj.get_path_name()] = dict(asset=obj.get_path_name(), file=str(path),
        sha256=_sha(path), source=source.get_path_name(), kind=kind, **extra)


def _record_existing(obj, source, kind, **extra):
    path = _asset_file(obj)
    assert path and path.is_file(), obj.get_path_name()
    _created[obj.get_path_name()] = dict(asset=obj.get_path_name(), file=str(path),
        sha256=_sha(path), source=source.get_path_name(), kind=kind, reused=True, **extra)


def _parent_clone(original, root):
    """Clone a complete parameter inheritance chain once per original asset."""
    key = (root, original.get_path_name())
    if key in _parents:
        return _parents[key]
    assert key not in _visiting, 'Material inheritance cycle: ' + original.get_path_name()
    _visiting.add(key)
    _remember_original(original)
    try:
        if isinstance(original, unreal.Material):
            clone = _clone_master(original, root)
        elif isinstance(original, unreal.MaterialInstanceConstant):
            parent = original.get_editor_property('parent')
            assert parent, 'Missing material parent: ' + original.get_path_name()
            new_parent = _parent_clone(parent, root)
            package = root + '/Parents/' + _name(original, 'MI_Parent_')
            clone = _existing(package, original, 'parent_instance')
            if clone:
                _record_existing(clone, original, 'parent_instance', parent=new_parent.get_path_name())
            else:
                _assets.make_directory(root + '/Parents')
                clone = _assets.duplicate_asset(_package(original), package)
                assert isinstance(clone, unreal.MaterialInstanceConstant), package
                # Duplicate the entire object instead of copying a hand-picked
                # parameter list: texture/vector/scalar/static/layer overrides,
                # physical material and base-property overrides are retained.
                _edit.set_material_instance_parent(clone, new_parent)
                _edit.update_material_instance(clone)
                _save(clone, root, original, 'parent_instance', parent=new_parent.get_path_name())
        else:
            raise AssertionError('Unsupported material interface: ' + original.get_class().get_path_name())
        _parents[key] = clone
        return clone
    finally:
        _visiting.remove(key)


def _clone_master(original, root):
    package = root + '/Masters/' + _name(original, 'M_Master_')
    clone = _existing(package, original, 'master')
    if clone:
        _record_existing(clone, original, 'master')
        return clone
    # A separate attributes chain must be edited through SetMaterialAttributes;
    # a direct WPO pin would be ignored. Fail explicitly instead of claiming the
    # surfaces moved when this unsupported graph type is encountered.
    assert not original.get_editor_property('use_material_attributes'), 'Material attributes graph requires a separate adapter: ' + original.get_path_name()
    existing_parameters = [str(n) for n in _edit.get_vector_parameter_names(original)]
    assert PARAMETER not in existing_parameters, 'Offset parameter name collision.'
    _assets.make_directory(root + '/Masters')
    clone = _assets.duplicate_asset(_package(original), package)
    assert isinstance(clone, unreal.Material), package
    wpo = unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET
    old_node = _edit.get_material_property_input_node(clone, wpo)
    old_output = _edit.get_material_property_input_node_output_name(clone, wpo)
    parameter = _edit.create_material_expression(clone, unreal.MaterialExpressionVectorParameter, -560, 740)
    assert parameter
    parameter.set_editor_property('parameter_name', unreal.Name(PARAMETER))
    parameter.set_editor_property('default_value', unreal.LinearColor(0., 0., 0., 0.))
    result, output = parameter, 'RGB'
    if old_node:
        result = _edit.create_material_expression(clone, unreal.MaterialExpressionAdd, -300, 740)
        assert result
        assert _edit.connect_material_expressions(old_node, old_output, result, 'A'), 'Unable to preserve existing WPO pin.'
        assert _edit.connect_material_expressions(parameter, 'RGB', result, 'B')
        output = ''
    assert _edit.connect_material_property(result, output, wpo)
    # Both properties are present in this installation's Material.h. Avoid
    # clamping an existing unlimited WPO; existing animations remain intact.
    old_limit = float(clone.get_editor_property('max_world_position_offset_displacement'))
    clone.set_editor_property('max_world_position_offset_displacement',
        0. if old_node and old_limit == 0. else max(1., old_limit + 1.))
    clone.set_editor_property('always_evaluate_world_position_offset', True)
    _edit.recompile_material(clone)
    _save(clone, root, original, 'master', had_original_wpo=bool(old_node),
        original_wpo_output=old_output, original_wpo_limit_cm=old_limit,
        offset_parameter=PARAMETER)
    return clone


def make_offset_material(original, offset, assetroot=DEFAULT_ROOT):
    """Return a generated MIC whose WPO adds ``offset`` in world centimetres.

    Reuses each (original asset, rounded offset) pair. Offset length is limited
    to 1 cm so this module cannot accidentally move geometry substantially.
    Root must enable component WPO evaluation and handle any required bounds.
    """
    assert isinstance(original, unreal.MaterialInterface), original
    assert assetroot.startswith('/Game/CodexGenerated/') and '..' not in assetroot
    root = assetroot.rstrip('/')
    values = tuple(round(float(x), 6) for x in offset)
    assert len(values) == 3 and all(math.isfinite(x) for x in values)
    assert math.sqrt(sum(x*x for x in values)) <= 1., values
    key = (root, original.get_path_name(), values)
    if key in _instances:
        return _instances[key]
    parent = _parent_clone(original, root)
    encoded = json.dumps([original.get_path_name(), values], separators=(',', ':')).encode('utf-8')
    suffix = hashlib.sha256(encoded).hexdigest()[:16]
    package = root + '/Instances/MI_Offset_' + suffix
    instance = _existing(package, original, 'offset_instance')
    if instance:
        actual = _edit.get_material_instance_vector_parameter_value(instance, unreal.Name(PARAMETER))
        assert all(abs(float(getattr(actual, k))-v) < 0.000002 for k,v in zip(('r','g','b'),values)), package
        _record_existing(instance, original, 'offset_instance', offset_cm=list(values), parent=parent.get_path_name())
    else:
        folder, name = package.rsplit('/', 1)
        _assets.make_directory(folder)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder,
            unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        assert isinstance(instance, unreal.MaterialInstanceConstant), package
        _edit.set_material_instance_parent(instance, parent)
        # UE 5.7 MaterialEditingLibrary.cpp initializes bResult=false and never
        # changes it in this setter, even though the parameter is applied. Check
        # the effective value instead of trusting that defective return flag.
        _edit.set_material_instance_vector_parameter_value(instance, unreal.Name(PARAMETER), unreal.LinearColor(*values, 0.))
        _edit.update_material_instance(instance)
        actual = _edit.get_material_instance_vector_parameter_value(instance, unreal.Name(PARAMETER))
        assert all(abs(float(getattr(actual, k))-v) < 0.000002 for k,v in zip(('r','g','b'),values)), 'New material offset parameter did not take effect: ' + package
        _save(instance, root, original, 'offset_instance', offset_cm=list(values), parent=parent.get_path_name())
    _instances[key] = instance
    return instance


def get_report():
    """Fresh hashes and source-preservation checks for the caller's report."""
    changed = [p for p,h in _original_hashes.items() if _sha(Path(p)) != h]
    rows = []
    for row in _created.values():
        fresh = dict(row)
        fresh['sha256'] = _sha(Path(row['file']))
        rows.append(fresh)
    return dict(passed=not changed, version=VERSION, offset_parameter=PARAMETER,
        assets=sorted(rows, key=lambda r:r['asset']), created_or_reused_assets=len(rows),
        original_asset_sha256=dict(_original_hashes), changed_original_files=changed)


def asset_hashes():
    report = get_report()
    assert report['passed'], report['changed_original_files']
    return {r['file']:r['sha256'] for r in report['assets']}
