import json,re
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
d=read('Doors.json');assert d['passed'] and read('Inspection.json')['passed'] and read('Inspect1.Completion.json')['normal_zero_exit']
rows=[];moving=[];groups={}
for a in d['all_doors']:
    if not a['is_hotel']:continue
    cs={c['name']:c for c in a['components']};bp=a['class_path'].split('.')[0]
    w,h,depth=map(float,re.search(r'_W(\d+)_H(\d+)_D(\d+)',bp).groups())
    swing=bool(cs.get('DoorLeaf',{}).get('mesh'))
    parents={'DoorHinge'} if swing else {'LeftSlider','RightSlider'}
    side=(1 if cs['DoorHinge']['local']['relative_location'][0]>0 else -1) if swing else 0
    changed=sorted(c['name'] for c in a['components'] if c['parent'] in parents and c.get('mesh'))
    assert set(changed)>={'DoorLeaf','LeafCollision','Handle'} if swing else set(changed)>={'LeftLeaf','RightLeaf','LeftLeafCollision','RightLeafCollision'}
    row=dict(label=a['label'],blueprint=bp,kind='swing' if swing else 'slider',width=w,height=h,depth=depth,hinge_side=side,leaf_depth_offset=-5.,changed_components=changed)
    rows.append(row);groups.setdefault(bp,[]).append(a['label'])
    if swing:
        matches=[v for v in d['attached'] if v['door']==a['label'] and v['label'].endswith('_MovingHinges')]
        assert len(matches)==1
        moving.append(dict(label=matches[0]['label'],door=a['label'],source_mesh=matches[0]['component']['mesh']))
assert len(rows)==96 and len(moving)==62 and len(groups)==8
assert all(a['is_hotel'] for a in d['all_doors'] if a['class_path'].split('.')[0] in groups)
plan=dict(passed=True,source_map_sha256=d['map_sha256'],actor_count=d['actor_count'],doors=rows,moving_hinges=moving,blueprints=groups,
    scope='96 assistant hotel doors and their 62 moving hinge meshes; other map actors and all user assets preserved')
(W/'Plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,doors=len(rows),swing=len(moving),slider=len(rows)-len(moving),blueprints=len(groups))))
