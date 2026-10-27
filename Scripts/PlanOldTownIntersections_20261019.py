"""Explicit placement plan from the fresh user-saved map, without editing Content."""
import json,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownIntersectionFix_20261019'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def rotate(v,q):
    x,y,z,w=q;vx,vy,vz=v;t=[2*(y*vz-z*vy),2*(z*vx-x*vz),2*(x*vy-y*vx)]
    return [vx+w*t[0]+y*t[2]-z*t[1],vy+w*t[1]+z*t[0]-x*t[2],vz+w*t[2]+x*t[1]-y*t[0]]
def main():
    assert not (W/'Plan.json').exists()
    data=read('Bounds.json');rows={a['label']:a for a in data['actors']};moves=[];wires=[]
    for label,a in rows.items():
        if label.startswith('OTS_UtilityPole_01_'):
            p=a['transform']['translation'];assert 'OldTownSchoolStreet_Generated' in a['tags']
            assert abs(p[0]-2200)<.01 and 430<p[1]<570
            new=[2200-(p[1]-500),385+(p[0]-2200),p[2]]
            moves.append(dict(label=label,before=a['transform'],position=new,yaw_delta=90.,kind='pole'))
    assert len(moves)==5
    for i,y in [(1,170.1),(4,198.),(7,225.9)]:
        label=f'OTS_OverheadWire_{i:02d}';a=rows[label];assert 'OldTownSchoolStreet_Generated' in a['tags']
        c=a['components'][0];t=c['world_transform'];s=t['scale'];q=t['rotation_quaternion_xyzw'];p=t['translation']
        ends=[]
        for x in (c['local_min'][0],c['local_max'][0]):
            d=rotate([x*s[0],0,0],q);ends.append([p[j]+d[j] for j in range(3)])
        assert abs(ends[0][0]-2200)<.05 and math.dist(ends[1],[3050,y,570])<.05
        new_start=[2200-(ends[0][1]-500),385+(ends[0][0]-2200),ends[0][2]]
        wires.append(dict(label=label,before=a['transform'],before_endpoints=ends,endpoints=[new_start,ends[1]],kind='wire'))
    cluster=[a for a in rows.values() if a['label'].startswith('OTS_P2Prop_WallUtilityCluster_05_') or a['label'] in [f'OTS_Enterable_OTS_PerimeterBoundaryEast_01_UtilityWallMount_{i}' for i in range(9030,9034)]]
    assert len(cluster)==9
    for a in cluster:
        expected_tag='OTS_Enterable_20261002' if 'UtilityWallMount_' in a['label'] else 'OldTownSchoolStreet_Generated'
        assert expected_tag in a['tags'];p=a['transform']['translation']
        assert 8970<p[0]<9002 and 3050<p[1]<3160
        moves.append(dict(label=a['label'],before=a['transform'],position=[p[0],p[1]-200,p[2]],yaw_delta=0.,kind='hotel_utility'))
    solid=rows['OTS_HotelV4_F0_StreetWall_21']['components'][0];o,e=solid['world_origin'],solid['world_extent']
    for a in cluster:
        for c in a['components']:
            cy,ey=c['world_origin'][1]-200,c['world_extent'][1]
            assert cy-ey>o[1]-e[1]+30 and cy+ey<o[1]+e[1]-100
    plan=dict(passed=True,source_map_sha256=data['map_sha256'],actor_count=data['actor_count'],moves=moves,wires=wires,
        allowed_labels=sorted([r['label'] for r in moves+wires]),hotel_group_move_cm=[0,-200,0],
        no_assets_modified=True,no_user_objects_modified=True,retain_user_door_material_and_open_angle=True,
        sidewalk_and_road_unchanged=True,hotel_solid_wall='OTS_HotelV4_F0_StreetWall_21',
        bounds_sha256=hashlib.sha256((W/'Bounds.json').read_bytes()).hexdigest())
    (W/'Plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print('INTERSECTION_PLAN_PASS',len(plan['allowed_labels']))
if __name__=='__main__':main()
