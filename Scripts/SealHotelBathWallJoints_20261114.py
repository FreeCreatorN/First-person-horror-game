"""Close the open slot beside each guest bath without moving its inside faces."""
import json
import copy
import shutil
import sys
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
import InspectOldTownStairTrim_20261113 as scene
import ApplyHotelBathCornerDoors_20261113 as bath
import MoveHotelBathSlidersInside_20261113 as slider
from AuditOldTownHotelV4 import refresh
from OldTownSurfaceMaterials import PARAMETER

OUT = ROOT/'Saved/CodexOutputs/HotelBathWallJoints_20261114'
LAP = .5
TOL = .02


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def state(a):
    c = a.static_mesh_component
    material = c.get_material(0)
    assert c.static_mesh and material,a.get_actor_label()
    offset = [0.,0.,0.]
    if c.get_editor_property('evaluate_world_position_offset'):
        if isinstance(material,unreal.MaterialInstanceConstant):
            names = [str(n) for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(material)]
            if PARAMETER in names:
                v = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material,unreal.Name(PARAMETER))
                offset = [float(v.r),float(v.g),float(v.b)]
    return dict(bounds=scene.bounds(c),offset=offset,material=material.get_path_name(),
                mesh=c.static_mesh.get_path_name(),profile=str(c.get_collision_profile_name()),
                collision=str(c.get_collision_enabled()),actor=a.get_path_name(),
                actor_collision=bool(a.get_actor_enable_collision()))


def close(a,b):
    return abs(a-b)<TOL


def rendered(bounds,offset):
    return [[p[i]+offset[i] for i in range(3)] for p in bounds]


def plan(by, openings):
    results = []
    for door in openings:
        stem = door['basin_label'].removesuffix('_Basin')
        labels = {key:stem+suffix for key,suffix in [('divider','_Left_00'),('left','_BathLeft_00'),
            ('front','_BathFront_00'),('rear','_BathRear_00'),('stow','_BathRight_01')]}
        old = {key:state(by[label]) for key,label in labels.items()}
        room = door['room_bounds']
        divider,left,front,rear = (old[key]['bounds'] for key in ('divider','left','front','rear'))
        assert close(left[1][1],room[0][1]) and close(front[1][0],room[0][0]) and close(rear[0][0],room[1][0]),door['room_id']
        assert close(left[0][0],front[1][0]) and close(left[1][0],rear[1][0]) and close(left[1][1],rear[0][1]),door['room_id']
        assert close(left[0][1],front[0][1]) and close(left[0][1]-divider[1][1],4.),door['room_id']
        assert all(close(old[k]['bounds'][j][2],room[j][2]) for k in old for j in (0,1)),door['room_id']
        assert divider[0][0]<=front[0][0]+TOL and divider[1][0]>=rear[1][0]-TOL,door['room_id']
        assert all(old[k]['mesh']=='/Engine/BasicShapes/Cube.Cube' and old[k]['actor_collision'] for k in old),door['room_id']
        assert all(max(map(abs,old[k]['offset']))<.2 for k in old),door['room_id']
        target = {}
        for k in ('left','front'):
            bb = [p[:] for p in old[k]['bounds']]
            # Keep the bathroom/bedroom exposed planes fixed; enlarge only toward the adjacent divider.
            bb[0][1] = min(divider[1][1],divider[1][1]+old['divider']['offset'][1]-old[k]['offset'][1])-LAP
            target[k] = bb
        old_gap = rendered(left,old['left']['offset'])[0][1]-rendered(divider,old['divider']['offset'])[1][1]
        assert 3.7<old_gap<4.3,door['room_id']
        results.append(dict(room=door['room_id'],labels=labels,before=old,targets=target,render_gap_before_cm=old_gap))
    return results


def resize(actor,target):
    assert actor.get_attach_parent_actor() is None and not actor.get_attached_actors()
    assert scene.xyz(actor.get_actor_right_vector()) == [0.,1.,0.]
    c = actor.static_mesh_component
    old = scene.bounds(c)
    position,scale = actor.get_actor_location(),actor.get_actor_scale3d()
    position.y += (target[0][1]+target[1][1]-old[0][1]-old[1][1])*.5
    scale.y *= (target[1][1]-target[0][1])/(old[1][1]-old[0][1])
    actor.modify()
    actor.set_actor_scale3d(scale)
    assert actor.set_actor_location(position,False,True)


def verify_joints(by,rows):
    proofs = []
    for row in rows:
        after = {key:state(by[label]) for key,label in row['labels'].items()}
        for key,old in row['before'].items():
            new = after[key]
            target = row['targets'].get(key,old['bounds'])
            assert all(close(new['bounds'][j][i],target[j][i]) for j in (0,1) for i in (0,1,2)),(row['room'],key,new['bounds'],target)
            assert all(new[k]==v for k,v in old.items() if k!='bounds'),(row['room'],key)
        edge = rendered(after['divider']['bounds'],after['divider']['offset'])[1][1]
        overlaps = {k:edge-rendered(after[k]['bounds'],after[k]['offset'])[0][1] for k in ('left','front')}
        assert all(value>=LAP-TOL for value in overlaps.values()), (row['room'],overlaps)
        proofs.append(dict(room=row['room'],render_gap_before_cm=row['render_gap_before_cm'],
                           render_overlap_after_cm=overlaps,inside_faces_unchanged=True))
    return proofs


def probe(world,rows,expect_closed):
    objects = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2]
    results=[]
    for row in rows:
        left = row['before']['left']['bounds']
        divider = row['before']['divider']['bounds']
        y = (left[0][1]+divider[1][1])*.5
        owners=[]
        for dz in (10.,100.,195.,300.):
            z=left[0][2]+dz
            start,end = (unreal.Vector(x,y,z) for x in (left[1][0]+3.,left[0][0]+5.))
            hit = unreal.SystemLibrary.line_trace_single_for_objects(world,start,end,objects,False,[],unreal.DrawDebugTrace.NONE)
            comp=hit.to_tuple()[10] if hit and hit.to_tuple()[0] else None
            owner=comp.get_owner().get_actor_label() if comp else None
            owners.append(owner)
            if expect_closed:
                assert owner==row['labels']['left'],(row['room'],dz,owner)
            else:
                assert owner is None,(row['room'],dz,owner)
        results.append(dict(room=row['room'],sample_owners=owners,closed=expect_closed))
    return results


def audit(ae,world,by,saved,rows):
    openings=copy.deepcopy(saved['openings'])
    for door,row in zip(openings,rows):
        assert door['room_id']==row['room']
        for key,target in row['targets'].items():
            door['wall_targets'][row['labels'][key]]=target
    refresh(ae.get_all_level_actors())
    joints=verify_joints(by,rows)
    ray_proof=probe(world,rows,True)
    walls=bath.verify_bathroom_walls(ae,openings)
    doors=bath.verify_doors(ae,world,openings)
    basins=bath.verify_guest_basins(ae,slider.basin_routes(saved['basins']),verify_approach=True)
    return dict(passed=True,joints=joints,ray_proof=ray_proof,wall_checks=walls['bathrooms'],door_checks=len(doors),
                basin_clearance_cm=basins['minimum_screen_clear_cm'])


def main():
    verify='-OTSJointVerify' in unreal.SystemLibrary.get_command_line()
    saved=bath.read('Applied.json')
    previous=read(slider.OUTPUT/'Readback.json')
    initial,alt=scene.sha(scene.MAP),scene.sha(scene.ALT)
    assert alt==saved['alt_sha256']==previous['alt_sha256']
    levels,ae,world=scene.load()
    by=bath.by_label(ae)
    if verify:
        applied=read(OUT/'Applied.json')
        assert initial==applied['map_sha256']
        report=audit(ae,world,by,saved,applied['plan'])
        assert scene.sha(scene.MAP)==initial and scene.sha(scene.ALT)==alt
        write('Readback.json',dict(report,map_sha256=initial,alt_sha256=alt))
        unreal.log('OTS_BATH_WALL_JOINTS_READBACK_PASS')
        return
    assert initial==previous['map_sha256'],'Original map changed since the last verified save'
    rows=plan(by,saved['openings'])
    assert len(rows)==27
    write('Plan.json',dict(source_sha256=initial,alt_sha256=alt,rooms=rows))
    refresh(ae.get_all_level_actors())
    before=probe(world,rows,False)
    backup=OUT/'Before_L_OldTownSchoolStreet.umap'
    if not backup.exists():shutil.copy2(scene.MAP,backup)
    assert scene.sha(backup)==initial
    for row in rows:
        for key,target in row['targets'].items():
            resize(by[row['labels'][key]],target)
    report=audit(ae,world,by,saved,rows)
    assert scene.sha(scene.MAP)==initial and scene.sha(scene.ALT)==alt
    assert levels.save_current_level()
    assert scene.sha(scene.ALT)==alt
    write('Applied.json',dict(report,plan=rows,open_before=before,map_sha256=scene.sha(scene.MAP),alt_sha256=alt))
    unreal.log('OTS_BATH_WALL_JOINTS_SAVED rooms=27')


if __name__=='__main__':
    main()
