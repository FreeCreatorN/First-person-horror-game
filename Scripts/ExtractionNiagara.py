"""Configure a copied lightweight Niagara system through generic reflection.

Call ``build_particle_system(material, diagnostics)`` in the live editor.
The function returns the NiagaraSystem and fills the supplied dictionary.
The caller must inspect ``diagnostics['success']`` before using the result.
No folders are created and the template asset is never edited.
"""
import unreal

SOURCE = '/Game/Variant_Horror/Blueprints/Light/Assets/NS_DustMote'
TARGET = '/Game/Yastar/Materials/NS_GreenExtractionParticles'


def _property_names(name):
    # Generic UObject wrappers do not apply Python's snake_case name mapping.
    cpp = ''.join(part[:1].upper() + part[1:] for part in name.split('_'))
    return list(dict.fromkeys((name, cpp, 'b' + cpp)))


def _get(obj, name):
    failures = []
    for candidate in _property_names(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception as exc:
            failures.append(candidate + ': ' + str(exc))
    raise RuntimeError('Read property ' + name + ' failed: ' + ' | '.join(failures))


def _set(obj, name, value):
    failures = []
    for candidate in _property_names(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as exc:
            failures.append(candidate + ': ' + str(exc))
    raise RuntimeError('Write property ' + name + ' failed: ' + ' | '.join(failures))


def _enum(current, member, *fallback_names):
    """Use the actual reflected enum class, avoiding generated-name assumptions."""
    cls = type(current)
    value = getattr(cls, member, None)
    if value is not None:
        return value
    for name in fallback_names:
        cls = getattr(unreal, name, None)
        value = getattr(cls, member, None) if cls else None
        if value is not None:
            return value
    raise RuntimeError('Cannot resolve enum member ' + member)


def _mode(dist, member):
    try:
        _set(dist, 'mode', _enum(_get(dist, 'mode'), member,
                               'NiagaraDistributionMode'))
    except Exception:
        # UENUMs without a Python wrapper can still be imported by native text.
        native = ''.join(p.title() for p in member.lower().split('_'))
        if not dist.import_text('(Mode=' + native + ')'):
            raise RuntimeError('Could not import distribution Mode=' + native)


def _set_enum_property(obj, name, member, *fallback_names):
    try:
        _set(obj, name, _enum(_get(obj, name), member, *fallback_names))
        return None
    except Exception:
        cpp = _property_names(name)[1]
        native = ''.join(p.title() for p in member.lower().split('_'))
        importer = getattr(obj, 'import_text', None)
        if importer:
            if not importer('(' + cpp + '=' + native + ')'):
                raise RuntimeError('Could not import ' + cpp + '=' + native)
            return {'enum_import_text': cpp + '=' + native}
        # SET targets this exact duplicated subobject, never a class/default/template.
        path = obj.get_path_name()
        if not path.startswith(TARGET + '.'):
            raise RuntimeError('Refusing SET outside duplicated target: ' + path)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        command = 'set "' + path + '" ' + cpp + ' ' + native
        unreal.SystemLibrary.execute_console_command(world, command)
        return {'enum_console_fallback': command,
                'verify': 'Native enum cannot be read through this Python build; inspect final scene/log.'}


def _vector_like(existing, values):
    """Preserve FVector2f/FVector3f versus FVector's actual reflected type."""
    result = type(existing)()
    for key, value in zip(('x', 'y', 'z', 'w'), values):
        try:
            result.set_editor_property(key, float(value))
        except Exception:
            setattr(result, key, float(value))
    return result


def _distribution(owner, property_name, lo, hi=None):
    """Edit both cooked values and editor channels so PostEdit won't undo them."""
    dist = _get(owner, property_name)
    hi = lo if hi is None else hi
    scalar = isinstance(lo, (int, float))
    low = [float(lo)] if scalar else [float(v) for v in lo]
    high = [float(hi)] if scalar else [float(v) for v in hi]
    constant = low == high
    _mode(dist, ('UNIFORM_CONSTANT' if constant else 'UNIFORM_RANGE') if scalar
          else ('NON_UNIFORM_CONSTANT' if constant else 'NON_UNIFORM_RANGE'))
    channels = low if constant else low + high
    _set(dist, 'channel_constants_and_ranges', channels)
    # Some distributions expose Min/Max, others expose an array of Values.
    try:
        old_min = _get(dist, 'min')
        if scalar:
            _set(dist, 'min', float(lo))
            _set(dist, 'max', float(hi))
        else:
            _set(dist, 'min', _vector_like(old_min, low))
            _set(dist, 'max', _vector_like(_get(dist, 'max'), high))
    except Exception:
        values = list(_get(dist, 'values'))
        if scalar:
            new_values = [float(lo), float(hi)]
        else:
            if not values:
                # InitialPositionDistribution is an FVector3f-valued distribution.
                value_type = getattr(unreal, 'Vector3f', unreal.Vector)
                prototype = value_type()
            else:
                prototype = values[0]
            new_values = [_vector_like(prototype, low), _vector_like(prototype, high)]
        _set(dist, 'values', new_values)
    _set(owner, property_name, dist)
    return dist


def _color_distribution(owner, property_name):
    dist = _get(owner, property_name)
    _mode(dist, 'NON_UNIFORM_RANGE')
    low = unreal.LinearColor(0.015, 0.65, 0.06, 0.65)
    high = unreal.LinearColor(0.12, 1.0, 0.45, 1.0)
    _set(dist, 'channel_constants_and_ranges',
                             [low.r, low.g, low.b, low.a, high.r, high.g, high.b, high.a])
    _set(dist, 'values', [low, high])
    # Random at birth, not an age-driven green-to-cyan transition.
    try:
        _set(dist, 'lookup_value_mode', 255)
    except Exception:
        pass
    _set(owner, property_name, dist)


def _objects_inside(system):
    prefix = system.get_path_name()
    result = []
    for obj in unreal.ObjectIterator(unreal.Object):
        try:
            path = obj.get_path_name()
            if path.startswith(prefix + ':') or path.startswith(prefix + '.'):
                # Iterator may also contain Python class wrappers in this build.
                obj.get_class().get_name()
                result.append(obj)
        except (TypeError, AttributeError):
            continue
    return result


def build_particle_system(particle_material, diagnostics=None):
    """Return configured system; all unsupported APIs are recorded in diagnostics.

    Spawn geometry is a 14 cm-thick cylindrical annulus inside radius 55 cm,
    centered at Z=72 cm and 110 cm high. With XY speed <=0.15 cm/s and a
    maximum 8 s lifetime, this remains comfortably inside a 75 cm boundary.
    The hollow annulus deliberately leaves the center clear.
    """
    diag = diagnostics if diagnostics is not None else {}
    diag.clear()
    diag.update(source=SOURCE, target=TARGET, success=False, created=False,
                objects=[], changes=[], errors=[], warnings=[], critical_failures=[])
    assert particle_material, 'A sprite particle material is required'
    assert unreal.EditorAssetLibrary.does_directory_exist('/Game/Yastar/Materials')
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET):
        system = unreal.load_asset(TARGET)
    else:
        system = unreal.EditorAssetLibrary.duplicate_asset(SOURCE, TARGET)
        diag['created'] = True
    if not system:
        raise RuntimeError('Could not duplicate/load Niagara system: ' + TARGET)

    def perform(label, action, critical=False):
        try:
            result = action()
            diag['changes'].append(label)
            if isinstance(result, dict):
                diag['warnings'].append(result)
            return True
        except Exception as exc:
            diag['errors'].append({'operation': label, 'error': str(exc)})
            if critical:
                diag['critical_failures'].append(label)
            return False

    def setprop(obj, name, value, critical=False):
        return perform(obj.get_name() + '.' + name,
                       lambda: _set(obj, name, value), critical)

    def dist(obj, prop, lo, hi=None, critical=False):
        return perform(obj.get_name() + '.' + prop,
                       lambda: _distribution(obj, prop, lo, hi), critical)

    objects = _objects_inside(system)
    diag['objects'] = [{'path': o.get_path_name(), 'class': o.get_class().get_name()}
                       for o in objects]
    emitters = [o for o in objects if o.get_class().get_name() == 'NiagaraStatelessEmitter']
    if not emitters:
        diag['critical_failures'].append('No reflected NiagaraStatelessEmitter found')
        return system

    configured = {'initialize': 0, 'shape': 0, 'velocity': 0, 'renderer': 0, 'spawn': 0}
    for emitter in emitters:
        try:
            modules = list(_get(emitter, 'modules'))
        except Exception:
            ep = emitter.get_path_name()
            modules = [o for o in objects if o.get_path_name().startswith(ep)
                       and o.get_class().get_name().startswith('NiagaraStatelessModule_')]
        for mod in modules:
            cls = mod.get_class().get_name()
            if cls.endswith('_InitializeParticle'):
                configured['initialize'] += 1
                setprop(mod, 'module_enabled', True, True)
                dist(mod, 'lifetime_distribution', 5.0, 8.0, True)
                dist(mod, 'sprite_size_distribution', (0.7, 0.7), (1.8, 1.8), True)
                dist(mod, 'initial_position_distribution', (0.0, 0.0, 72.0), critical=True)
                perform(mod.get_name() + '.color_distribution',
                        lambda m=mod: _color_distribution(m, 'color_distribution'), True)
            elif cls.endswith('_ShapeLocation'):
                configured['shape'] += 1
                setprop(mod, 'module_enabled', True, True)
                perform(mod.get_name() + '.shape_primitive', lambda m=mod:
                        _set_enum_property(m, 'shape_primitive', 'CYLINDER', 'NSMShapePrimitive'), True)
                dist(mod, 'cylinder_height', 110.0, critical=True)
                dist(mod, 'cylinder_radius', 55.0, critical=True)
                dist(mod, 'cylinder_height_midpoint', 0.5, critical=True)
                dist(mod, 'shape_scale', (1.0, 1.0, 1.0), critical=True)
                setprop(mod, 'cylinder_surface_only', True, True)
                setprop(mod, 'cylinder_surface_only_include_end_caps', False, True)
                perform(mod.get_name() + '.cylinder_surface_expansion', lambda m=mod:
                        _set_enum_property(m, 'cylinder_surface_expansion', 'INNER', 'NSMSurfaceExpansionMode'), True)
                dist(mod, 'cylinder_surface_thickness', 14.0, critical=True)
            elif cls.endswith('_AddVelocity'):
                configured['velocity'] += 1
                setprop(mod, 'module_enabled', True, True)
                perform(mod.get_name() + '.velocity_type', lambda m=mod:
                        _set_enum_property(m, 'velocity_type', 'LINEAR', 'NSMVelocityType'), True)
                dist(mod, 'linear_velocity_distribution', (-0.15, -0.15, -1.5), (0.15, 0.15, 2.0), True)
                dist(mod, 'linear_velocity_scale', 1.0, critical=True)
            elif cls.endswith('_CurlNoiseForce'):
                setprop(mod, 'module_enabled', True, True)
                setprop(mod, 'noise_strength', 0.12, True)
                setprop(mod, 'noise_frequency', 0.035, True)
            elif cls.endswith(('_GravityForce', '_AccelerationForce')):
                # Low curl and static drift preserve the annular distribution.
                setprop(mod, 'module_enabled', False, True)
            elif cls.endswith('_SolveVelocitiesAndForces'):
                setprop(mod, 'module_enabled', True, True)
            elif cls.endswith('_Drag'):
                setprop(mod, 'module_enabled', False)

        try:
            spawn_infos = list(_get(emitter, 'spawn_infos'))
            if not spawn_infos:
                raise RuntimeError('Template has no SpawnInfos to reconfigure')
            for index, info in enumerate(spawn_infos):
                _set(info, 'enabled', index == 0)
                if index == 0:
                    _set_enum_property(info, 'type', 'RATE', 'NiagaraStatelessSpawnInfoType')
                    _distribution(info, 'rate', 12.0)
                    _set(info, 'spawn_probability_enabled', False)
                    _set(info, 'loop_count_limit_enabled', False)
            if setprop(emitter, 'spawn_infos', spawn_infos, True):
                configured['spawn'] += 1
        except Exception as exc:
            diag['critical_failures'].append('spawn_infos')
            diag['errors'].append({'operation': 'spawn_infos', 'error': str(exc)})

        try:
            state = _get(emitter, 'emitter_state')
            _set_enum_property(state, 'loop_behavior', 'INFINITE', 'NiagaraLoopBehavior')
            _set(state, 'loop_delay_enabled', False)
            if setprop(emitter, 'emitter_state', state, True):
                diag['changes'].append('Continuous infinite emitter state')
        except Exception as exc:
            diag['critical_failures'].append('emitter_state')
            diag['errors'].append({'operation': 'emitter_state', 'error': str(exc)})
        # Native PostEditChangeProperty on emitter updates the owning system.
        setprop(emitter, 'random_seed', 913, True)

    renderers = [o for o in objects if o.get_class().get_name() == 'NiagaraSpriteRendererProperties']
    for renderer in renderers:
        if setprop(renderer, 'material', particle_material, True):
            configured['renderer'] += 1
    diag['configured'] = configured
    for key, count in configured.items():
        if count == 0:
            diag['critical_failures'].append('No configured ' + key)
    # Warm up particles so activation is populated, with no startup animation.
    setprop(system, 'warmup_time', 8.0)
    setprop(system, 'warmup_tick_delta', 0.1)
    def save_system():
        if not unreal.EditorAssetLibrary.save_loaded_asset(system, only_if_is_dirty=False):
            raise RuntimeError('save_loaded_asset returned False')
    saved = perform('save Niagara system', save_system, True)
    diag['success'] = saved and not diag['critical_failures']
    diag['estimated_alive_particles'] = 78
    diag['motion_bounds_cm'] = {'spawn_radius': 55, 'thickness_inward': 14,
                                'min_z': 17, 'max_z': 127,
                                'max_xy_lifetime_drift': 1.2,
                                'max_z_lifetime_drift': 16}
    return system
