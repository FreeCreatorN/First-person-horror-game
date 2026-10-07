"""Physical-dimension mesh profiles for the current saved street refinement."""
import json
from pathlib import Path
from ConvertOldTownBuildings import plan_buildings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'SourceArt/OldTownDetailPolish_20261004'

def key(prefix, *values):
    return 'SM_OTS_Polish_'+prefix+'_'+'_'.join(('{:.6f}'.format(v).rstrip('0').rstrip('.')).replace('.','p') for v in values)

def profiles(plan, build):
    result = {}
    for b in plan_buildings([],plan):
        if b.count > 1:
            for n in (b.n1,b.n2):
                name=key('Flight',n,b.rise)
                result[name]={'name':name,'kind':'flight','steps':n,'rise':b.rise,'width':140.,'tread':28.}
            name=key('Landing',300,140,20+b.rise)
            result[name]={'name':name,'kind':'landing','size':[300.,140.,20.+b.rise]}
        name=key('Door',b.door_width-8,b.door_height-6)
        result[name]={'name':name,'kind':'door','size':[4.,b.door_width-8.,b.door_height-6.]}
    for w in build['architecture_seal']['windows']:
        name=key('InnerTrim',w['width'],w['height'])
        result[name]={'name':name,'kind':'trim','width':w['width'],'height':w['height']}
    return list(result.values())

if __name__=='__main__':
    plan=json.loads((ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/RevisionPlan.json').read_text(encoding='utf-8-sig'))
    build=json.loads((ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json').read_text(encoding='utf-8-sig'))
    OUT.mkdir(parents=True,exist_ok=True)
    data=profiles(plan,build)
    (OUT/'Profiles.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Physical profiles:',len(data), 'Flights:',sum(p['kind']=='flight' for p in data))
