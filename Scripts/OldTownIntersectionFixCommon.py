import sys,json,re,math,hashlib
from copy import deepcopy
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/OldTownIntersectionFix_20261019';base.W=W;base.TAG='IntersectionFix_DoNotExcludeAnyExistingActor'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def text(rec):
    b=Path(rec['file']).read_bytes();s=b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
    assert hashlib.sha256(s.encode()).hexdigest()==rec['native_text_sha256'];return s
def pose(a):return native.value(a.get_actor_transform())
def endpoints(a):
    c=a.static_mesh_component;e=c.static_mesh.get_bounds().box_extent.x;p=a.get_actor_location();v=a.get_actor_forward_vector()*e*a.get_actor_scale3d().x
    return [native.value(p-v),native.value(p+v)]
def validate_geometry(by,plan):
    for row in plan['moves']:
        a=by[row['label']];p=pose(a);assert math.dist(p['translation'],row['position'])<1e-6
        assert p['scale']==row['before']['scale']
        q=row['before']['rotation_quaternion_xyzw'];half=math.radians(row['yaw_delta'])/2;c=math.cos(half);s=math.sin(half)
        expected=[c*q[0]-s*q[1],c*q[1]+s*q[0],c*q[2]+s*q[3],c*q[3]-s*q[2]]
        actual=p['rotation_quaternion_xyzw']
        assert min(math.dist(actual,expected),math.dist(actual,[-v for v in expected]))<1e-8,row['label']
    for row in plan['wires']:
        actual=endpoints(by[row['label']]);assert all(math.dist(a,b)<.001 for a,b in zip(actual,row['endpoints']))
        s=pose(by[row['label']])['scale'];assert s[1:]==row['before']['scale'][1:]
    cross=by['OTS_UtilityPole_01_Crossarm_01'].static_mesh_component
    origin,extent,_=unreal.SystemLibrary.get_component_bounds(cross)
    assert origin.y+extent.y<=400.001 and 520-(origin.y+extent.y)>=119.999
    pole=by['OTS_UtilityPole_01_01'].static_mesh_component;o,e,_=unreal.SystemLibrary.get_component_bounds(pole)
    assert o.y-e.y-350>=22.999
    solid=by['OTS_HotelV4_F0_StreetWall_21'].static_mesh_component;so,se,_=unreal.SystemLibrary.get_component_bounds(solid)
    hotel=[]
    for row in plan['moves']:
        if row['kind']!='hotel_utility':continue
        o,e,_=unreal.SystemLibrary.get_component_bounds(by[row['label']].static_mesh_component)
        assert o.y-e.y>so.y-se.y+30 and o.y+e.y<so.y+se.y-100
        hotel.append(dict(actor=row['label'],min_y=o.y-e.y,max_y=o.y+e.y,door_clearance=3126-(o.y+e.y)))
    return dict(passed=True,crossarm_facade_clearance_cm=520-(origin.y+extent.y),pole_road_clearance_cm=by['OTS_UtilityPole_01_01'].get_actor_location().y-12-350,
        hotel_wall_placements=hotel,wire_opposite_endpoints_preserved=True)
def verify(before,after,plan):
    allowed=set(plan['allowed_labels']);assert before['actor_count']==after['actor_count']==plan['actor_count']
    assert set(before['actors'])==set(after['actors'])
    for key in ('lights','full_light_properties','actor_properties'):assert before[key]==after[key],key
    for n,a in before['actors'].items():
        b=after['actors'][n]
        if n not in allowed:assert a==b,n;continue
        a=deepcopy(a);b=deepcopy(b)
        for r in (a,b):
            assert len(r['components'])==1 and r['components'][0]['parent'] is None
            for k in ('location','rotation','scale'):r.pop(k);r['components'][0].pop(k)
        assert a==b,n
    assert set(before['exact_scene_components'])==set(after['exact_scene_components'])
    for n,a in before['exact_scene_components'].items():
        b=after['exact_scene_components'][n]
        if n.split('::')[0] in allowed:
            a=deepcopy(a);b=deepcopy(b)
            for r in (a,b):
                r.pop('world_transform')
                for k in ('relative_location','relative_rotation','relative_scale3d'):r['local'].pop(k)
        assert a==b,n
    assert set(before['full_existing_actor_native'])==set(after['full_existing_actor_native'])
    for n,a in before['full_existing_actor_native'].items():
        b=after['full_existing_actor_native'][n]
        if n not in allowed:assert a['native_text_sha256']==b['native_text_sha256'],n;continue
        aa,bb=text(a),text(b)
        clean=lambda s:re.sub(r'(?m)^\s*(?:RelativeLocation|RelativeRotation|RelativeScale3D)=.*\n','',s)
        assert clean(aa)==clean(bb),dict(actor=n,before=a['file'],after=b['file'])
    return dict(passed=True,actor_count=before['actor_count'],changed_actors=len(allowed),other_actors_exact=before['actor_count']-len(allowed),
        all_unchanged_actor_native_exact=True,changed_actor_native_only_root_transforms=True,all_materials_collision_lights_tags_names_folders_preserved=True)
