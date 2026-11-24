"""Crop one exposed strip above the photographed north stair window."""
import json
import math
import shutil
import sys
from pathlib import Path
import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'Scripts'))
from InspectOldTownStairTrim_20261113 import ALT, MAP, OUTPUT, TARGET, bounds, load, sha, write

LABEL = 'OTS_HotelV4_F3_FloorSlab03'
EDGE = LABEL + '_NorthEdge_20261113'
BEFORE = [[9968., 1160., 1092.75], [10020., 3480., 1112.75]]
LEFT = [BEFORE[0], [10020., 3040., 1112.75]]
RIGHT = [[9968., 3360., 1092.75], BEFORE[1]]
WINDOW = 'OTS_HotelV4_Window_F2_EndStairRearWindow_64'
KEEP = ('OTS_HotelV4_North_F2_HalfLanding', 'OTS_HotelV4_RevisionNorth_F2_LandingExtension',
        'OTS_HotelV4_F3_FloorSlab01', 'OTS_HotelV4_F2_FloorSlab03', 'OTS_HotelV4_F1_FloorSlab03', WINDOW)


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding='utf-8'))


def nearly(actual, target):
    return all(abs(actual[j][i]-target[j][i]) < .02 for j in (0,1) for i in range(3))


def record(actor):
    return [(c.get_name(), c.static_mesh.get_path_name(), bounds(c), str(c.get_collision_enabled()),
             str(c.get_collision_profile_name()))
            for c in actor.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]


def resize_y(actor, target):
    component = actor.static_mesh_component
    previous = bounds(component)
    axes = [actor.get_actor_forward_vector(), actor.get_actor_right_vector(), actor.get_actor_up_vector()]
    index = max(range(3), key=lambda i: abs(axes[i].y))
    assert abs(axes[index].y) > .99999, 'Slab is not aligned to world Y'
    scale = actor.get_actor_scale3d()
    name = ('x','y','z')[index]
    setattr(scale, name, getattr(scale,name)*(target[1][1]-target[0][1])/(previous[1][1]-previous[0][1]))
    loc = actor.get_actor_location()
    loc.y += (sum(r[1] for r in target)-sum(r[1] for r in previous))*.5
    actor.modify()
    actor.set_actor_scale3d(scale)
    assert actor.set_actor_location(loc, False, True)
    assert nearly(bounds(component),target), bounds(component)


def by_label(ae):
    actors = list(ae.get_all_level_actors())
    return {a.get_actor_label():a for a in actors}


def make_retained_edge(ae, original):
    # DuplicateActor relies on editor viewport/selection state unavailable in
    # the unattended commandlet. This source is a single unparented cube.
    source = original.static_mesh_component
    assert source.get_num_materials()==1
    assert not original.get_attached_actors()
    actor = ae.spawn_actor_from_class(unreal.StaticMeshActor, original.get_actor_location(), original.get_actor_rotation(), False)
    assert actor
    actor.set_actor_label(EDGE)
    actor.set_folder_path(original.get_folder_path())
    actor.set_editor_property('tags',list(original.tags))
    actor.set_actor_scale3d(original.get_actor_scale3d())
    c = actor.static_mesh_component
    c.set_static_mesh(source.static_mesh)
    c.set_material(0,source.get_material(0))
    c.set_mobility(source.get_editor_property('mobility'))
    c.set_collision_profile_name(source.get_collision_profile_name())
    c.set_collision_enabled(source.get_collision_enabled())
    for prop in ('cast_shadow','receives_decals'):
        c.set_editor_property(prop,source.get_editor_property(prop))
    assert nearly(bounds(c), BEFORE)
    return actor


def verify_geometry(by, kept):
    assert nearly(bounds(by[LABEL].static_mesh_component),LEFT)
    assert nearly(bounds(by[EDGE].static_mesh_component),RIGHT)
    assert all(record(by[n]) == r for n,r in kept.items()), 'Neighbor stair/floor/window changed'
    assert by[LABEL].static_mesh_component.get_material(0) == by[EDGE].static_mesh_component.get_material(0)


def main():
    from OldTownNonLightEmission import apply_non_light_emission, verify_non_light_emission
    inspection = read('Inspection.json')
    assert inspection['target'] == TARGET and sha(MAP) == inspection['map_sha256']
    assert sha(ALT) == inspection['version2_sha256']
    camera = inspection['viewport'][0]
    x,y,z = camera['position']
    pitch,yaw,_ = [math.radians(v) for v in camera['rotation']]
    assert 9800.<x<9968. and 3040.<y<3360. and 1112.75<z<1480., camera
    assert 3040.<y+(10020.-x)*math.tan(yaw)<3360. and pitch<0., camera
    le,ae,world = load()
    by = by_label(ae)
    assert LABEL in by and EDGE not in by and len(by)==inspection['actors']
    actor = by[LABEL]
    assert isinstance(actor,unreal.StaticMeshActor) and actor.get_attach_parent_actor() is None
    assert actor.static_mesh_component.static_mesh.get_path_name() == '/Engine/BasicShapes/Cube.Cube'
    assert nearly(bounds(actor.static_mesh_component), BEFORE), bounds(actor.static_mesh_component)
    kept = {n:record(by[n]) for n in KEEP}
    backup = OUTPUT/'Before_L_OldTownSchoolStreet.umap'
    if not backup.exists(): shutil.copy2(MAP, backup)
    assert sha(backup)==inspection['map_sha256']
    unreal.log('OLDTOWN_STAIR_TRIM_BEGIN')
    extra = make_retained_edge(ae,actor)
    resize_y(actor,LEFT)
    resize_y(extra,RIGHT)
    updated = by_label(ae)
    assert set(updated)-set(by)=={EDGE} and not(set(by)-set(updated))
    verify_geometry(updated,kept)
    unreal.log('OLDTOWN_STAIR_TRIM_GEOMETRY_OK')
    emission = apply_non_light_emission(ae)
    verify_geometry(updated,kept)
    audit = verify_non_light_emission(ae, emission)
    assert audit['passed'], audit
    assert sha(MAP)==inspection['map_sha256'] and sha(ALT)==inspection['version2_sha256']
    assert le.save_current_level()
    assert sha(ALT)==inspection['version2_sha256']
    write('Applied.json', {'passed':True,'target':TARGET,'original_sha256':inspection['map_sha256'],
        'saved_sha256':sha(MAP),'version2_sha256':sha(ALT),'actor':LABEL,'retained_edge':EDGE,
        'removed_bounds':[[9968.,3040.,1092.75],[10020.,3360.,1112.75]],
        'retained_bounds':[LEFT,RIGHT],'kept':kept,'emission':emission,'emission_audit':audit})
    unreal.log('OLDTOWN_STAIR_TRIM_AND_EMISSION_SAVED')


if __name__ == '__main__':
    main()
