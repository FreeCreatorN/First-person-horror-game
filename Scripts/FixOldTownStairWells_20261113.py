"""Crop floor intrusions only inside measured stair voids in the original map."""
import json
import re
import shutil
import sys
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT/'Scripts'))
import InspectOldTownStairTrim_20261113 as base
from ApplyOldTownStairTrim_20261113 import by_label, nearly
from OldTownHotelV4Plan import subtract

OUT = ROOT/'Saved/CodexOutputs/OldTownStairWells_20261113'
TOL = .05


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf-8')


def overlap(a,b):
    return all(min(a[1][i],b[1][i])-max(a[0][i],b[0][i])>TOL for i in range(3))


def box_volume(a):
    return (a[1][0]-a[0][0])*(a[1][1]-a[0][1])*(a[1][2]-a[0][2])


def original_plan():
    out = ROOT/'Saved/CodexOutputs'
    hotel = read(out/'HotelRedesign_20261008_V4/ArchitecturePlan.json')
    town = read(out/'EnterableStreet_20261002/BuildingReport.json')
    return hotel,town


def well_inventory(by, hotel, town):
    wells, routes, missing = [], [], []
    for hole in hotel['slab_voids']:
        if hole['kind'] != 'stair':
            continue
        lo,hi = list(hole['world_min']),list(hole['world_max'])
        f = hole['floor']
        side = hole['stair_id']
        lo[2],hi[2] = hotel['floor_z'][f]-20.,hotel['floor_z'][f]
        if side in ('North','South'):
            label = 'OTS_HotelV4_Revision%s_F%d_LandingExtension' % (side, f-1)
            bb = base.bounds(by[label].static_mesh_component)
            assert abs(bb[0][0]-hi[0])<TOL and abs(bb[0][1]-lo[1])<TOL and abs(bb[1][1]-hi[1])<TOL,(label,bb,lo,hi)
            hi[0] = bb[1][0]
        wells.append({'id':hole['id'],'group':'hotel','building':'Hotel','floor':f,'bounds':[lo,hi]})
    for route in hotel['stair_routes']:
        routes.append((route['id'],route['foot_waypoints']))
    for building in town['buildings']:
        if not building['stairs'] or building['label']=='OTS_PerimeterBoundaryEast_01':
            continue
        name = building['label']
        sides = {r['coverage']['part']:r['actor'] for r in building['stair_side_panels']}
        left,right = (sides.get('FullHeight'+k) for k in ('Left','Right'))
        if left not in by or right not in by:
            missing.append({'building':name,'left':left,'right':right})
            continue
        b0,b1 = (base.bounds(by[label].static_mesh_component) for label in (left,right))
        cross = min(range(2),key=lambda i:b0[1][i]-b0[0][i])
        along = 1-cross
        near,far = sorted((b0,b1),key=lambda b:b[0][cross])
        lo,hi = [0.,0.,0.],[0.,0.,0.]
        lo[cross],hi[cross] = near[1][cross],far[0][cross]
        lo[along],hi[along] = max(b0[0][along],b1[0][along]),min(b0[1][along],b1[1][along])
        assert 299.9<hi[cross]-lo[cross]<300.1 and hi[along]-lo[along]>=300., (name,b0,b1)
        for index,z in enumerate(building['floor_z'][1:],1):
            wells.append({'id':name+':F'+str(index),'group':'town','building':name,'floor':index,
                          'bounds':[lo[:2]+[z-20.],hi[:2]+[z]]})
        for stair in building['stairs']:
            routes.append((name+':'+str(stair['from_floor']),stair['foot_waypoints']))
    return wells,routes,missing


def floor_rows(by,town):
    old = {row['actor']:row['building'] for row in town['structural_boxes'] if row['role']=='FloorSlab'}
    rows = []
    for label,actor in by.items():
        hotel = re.match(r'OTS_HotelV4_F([1-3])_FloorSlab\d\d(?:_|$)',label)
        if not hotel and label not in old and not re.match(r'OTS_Enterable_.+_FloorSlab_',label):
            continue
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        assert component and component.static_mesh,label
        rows.append({'label':label,'bounds':base.bounds(component),'floor':int(hotel[1]) if hotel else None,
                     'group':'hotel' if hotel else 'town','building':'Hotel' if hotel else old.get(label),
                     'mesh':component.static_mesh.get_path_name()})
    return rows


def plan_crops(wells,rows):
    plan = []
    for row in rows:
        cuts = [well for well in wells if well['group']==row['group'] and
                (row['floor']==well['floor'] if row['group']=='hotel' else row['building']==well['building'])
                and overlap(row['bounds'],well['bounds'])]
        if not cuts:
            continue
        parts = [row['bounds']]
        for cut in cuts:
            parts = [part for lo,hi in parts for part in subtract(lo,hi,*cut['bounds'])]
        assert parts and sum(box_volume(p) for p in parts) < box_volume(row['bounds']),row
        plan.append(dict(row,cuts=[c['id'] for c in cuts],parts=parts))
    return plan


def resize(actor, target):
    component = actor.static_mesh_component
    current = base.bounds(component)
    axes = [actor.get_actor_forward_vector(), actor.get_actor_right_vector(), actor.get_actor_up_vector()]
    scale = actor.get_actor_scale3d()
    position = actor.get_actor_location()
    for i, world_axis in enumerate('xyz'):
        j = max(range(3),key=lambda index:abs(getattr(axes[index],world_axis)))
        assert abs(getattr(axes[j],world_axis))>.99999, actor.get_actor_label()
        local_axis = 'xyz'[j]
        factor = (target[1][i]-target[0][i])/(current[1][i]-current[0][i])
        setattr(scale,local_axis,getattr(scale,local_axis)*factor)
        setattr(position,world_axis,getattr(position,world_axis)+(target[0][i]+target[1][i]-current[0][i]-current[1][i])*.5)
    actor.modify()
    actor.set_actor_scale3d(scale)
    assert actor.set_actor_location(position,False,True)
    assert nearly(base.bounds(component),target),actor.get_actor_label()


def edge(ae, actor, label):
    source = actor.static_mesh_component
    assert source.get_num_materials()==1 and not actor.get_attached_actors() and actor.get_attach_parent_actor() is None
    a = ae.spawn_actor_from_class(unreal.StaticMeshActor,actor.get_actor_location(),actor.get_actor_rotation(),False)
    assert a
    a.set_actor_label(label)
    a.set_folder_path(actor.get_folder_path())
    a.set_editor_property('tags',list(actor.tags))
    a.set_actor_scale3d(actor.get_actor_scale3d())
    c = a.static_mesh_component
    c.set_static_mesh(source.static_mesh)
    c.set_material(0,source.get_material(0))
    c.set_mobility(source.get_editor_property('mobility'))
    c.set_collision_profile_name(source.get_collision_profile_name())
    c.set_collision_enabled(source.get_collision_enabled())
    for prop in ('cast_shadow','receives_decals'):
        c.set_editor_property(prop,source.get_editor_property(prop))
    return a


def crop(ae,by,plan):
    result = {}
    for row in plan:
        actor = by[row['label']]
        assert isinstance(actor,unreal.StaticMeshActor) and row['mesh']=='/Engine/BasicShapes/Cube.Cube',row
        parts = sorted(row['parts'], key=box_volume, reverse=True)
        for index, part in enumerate(parts[1:],1):
            label = row['label']+'_WellEdge_%02d_20261113' % index
            assert label not in by,label
            new_actor = edge(ae,actor,label)
            resize(new_actor,part)
            result[label] = part
        resize(actor,parts[0])
        result[row['label']] = parts[0]
    return result


def probe(world, ae, routes):
    from AuditOldTownHotelV4 import refresh, route_probe
    refresh(ae.get_all_level_actors())
    records = {}
    for label,points in routes:
        if not re.fullmatch(r'(North|South|Central)_F\d_to_F\d',label):
            continue
        result = route_probe(world,points,stairs=True)
        records[label] = {k:result[k] for k in ('passed','sample_count','failures')}
    assert len(records)==9,records.keys()
    return records


def verify_movement(records, baseline):
    assert set(records)==set(baseline)
    for label,row in records.items():
        before = baseline[label]
        assert row['sample_count']==before['sample_count'],label
        if label.startswith(('South_','North_')):
            assert before['passed'] and row['passed'], (label,row['failures'][:2])
            continue
        # The central shaft is not cropped. Its saved closed doors intentionally
        # block the approach, so require the exact same probe results.
        assert row==before,(label,row['failures'][:2],before['failures'][:2])
        for fault in row['failures']:
            blockers = fault.get('probe',{}).get('blockers',[])
            assert any('CentralStairDoor:LeafCollision' in key for key in blockers), (label,fault)


def verify_no_remaining(by,hotel,town,expected=None):
    wells,routes,missing = well_inventory(by,hotel,town)
    assert not missing,missing
    floor = floor_rows(by,town)
    plan = plan_crops(wells,floor)
    if expected is not None:
        assert not plan,plan
        assert all(nearly(base.bounds(by[label].static_mesh_component),bb) for label,bb in expected.items())
    return wells,routes,floor,plan


def main():
    from AuditOldTownEmissionCoverage import audit_old_town_emission_coverage
    from OldTownNonLightEmission import apply_non_light_emission, verify_non_light_emission
    mode = 'verify' if '-OTSWellVerify' in unreal.SystemLibrary.get_command_line() else ('apply' if '-OTSWellApply' in unreal.SystemLibrary.get_command_line() else 'inspect')
    map_sha,alt_sha = base.sha(base.MAP),base.sha(base.ALT)
    hotel,town = original_plan()
    le,ae,world = base.load()
    by = by_label(ae)
    wells,routes,floor,plan = verify_no_remaining(by,hotel,town)
    if '-OTSWellProbe' in unreal.SystemLibrary.get_command_line():
        write('BeforeMovement.json',probe(world,ae,routes))
        unreal.log('OLDTOWN_STAIR_MOVEMENT_BASELINE_WRITTEN')
        return
    emission = audit_old_town_emission_coverage(ae)
    write(mode.title()+'EmissionCoverage.json',emission)
    if mode=='inspect':
        write('Plan.json',{'map_sha256':map_sha,'alt_sha256':alt_sha,'wells':wells,'floor_count':len(floor),'crops':plan})
        assert base.sha(base.MAP)==map_sha and base.sha(base.ALT)==alt_sha
        unreal.log('OLDTOWN_ALL_STAIR_WELLS_PLAN_OK wells={} cuts={}'.format(len(wells),len(plan)))
        return
    if mode=='verify':
        applied = read(OUT/'Applied.json')
        assert map_sha==applied['saved_sha256'] and alt_sha==applied['alt_sha256']
        verify_no_remaining(by,hotel,town,applied['retained'])
        assert emission['passed'], 'Expanded material audit did not pass'
        verify_non_light_emission(ae,applied['emission'])
        movement = probe(world,ae,routes)
        verify_movement(movement,read(OUT/'BeforeMovement.json'))
        write('Readback.json',{'passed':True,'wells':len(wells),'floor_count':len(floor),'remaining_cuts':len(plan),
            'stairs':movement,'saved_sha256':map_sha,'version2_sha256':alt_sha})
        unreal.log('OLDTOWN_ALL_STAIR_WELLS_READBACK_PASS')
        return
    reviewed = read(OUT/'Plan.json')
    assert reviewed['map_sha256']==map_sha and reviewed['alt_sha256']==alt_sha
    assert reviewed['crops']==json.loads(json.dumps(plan)), 'The crop plan changed since inspection'
    before = probe(world,ae,routes)
    write('BeforeMovement.json',before)
    verify_movement(before,before)
    backup = OUT/'Before_L_OldTownSchoolStreet.umap'
    if not backup.exists():shutil.copy2(base.MAP,backup)
    assert base.sha(backup)==map_sha
    retained = crop(ae,by,plan)
    updated = by_label(ae)
    assert set(updated)-set(by)==set(retained)-set(by) and not(set(by)-set(updated))
    verify_no_remaining(updated,hotel,town,retained)
    emission_result = apply_non_light_emission(ae)
    assert verify_non_light_emission(ae,emission_result)['passed']
    complete_emission = audit_old_town_emission_coverage(ae)
    write('AfterEmissionCoverage.json',complete_emission)
    assert complete_emission['passed'], 'Expanded material audit did not pass'
    movement = probe(world,ae,routes)
    write('AfterMovement.json',movement)
    verify_movement(movement,before)
    assert base.sha(base.MAP)==map_sha and base.sha(base.ALT)==alt_sha
    assert le.save_current_level()
    assert base.sha(base.ALT)==alt_sha
    write('Applied.json',{'passed':True,'saved_sha256':base.sha(base.MAP),'alt_sha256':alt_sha,
        'crops':plan,'retained':retained,'emission':emission_result})
    unreal.log('OLDTOWN_ALL_STAIR_WELLS_APPLIED')


if __name__=='__main__':
    main()
