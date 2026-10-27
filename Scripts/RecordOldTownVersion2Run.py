import argparse,re
from OldTownMainLightingCommon import R,read,write,ref
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016'
TOKENS={'CurrentInput':'USER_OLDTOWN_V2_INPUT_PASS','Create':'OLDTOWN_VERSION2_CREATED','Readback':'OLDTOWN_VERSION2_READBACK_PASS','PreviewCost':'INVENTORY_PREVIEW_COST_READONLY_PASS'}
def main(name):
    role=next(k for k in TOKENS if re.fullmatch(k+r'\d+',name));log=W/(name+'.log')
    text=log.read_text(encoding='utf-8-sig',errors='replace')
    assert TOKENS[role] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text
    p=W/'RunCompletion.json';d=read(p) if p.exists() else dict(runs=[])
    rows=[x for x in d['runs'] if x['role']!=role]
    rows.append(dict(role=role,name=name,exit_code=0,normal_exit_observed_by_root=True,forced_cleanup=False,log=ref(log),success_token=TOKENS[role]))
    write(p,dict(passed={'CurrentInput','Create','Readback'}.issubset({r['role'] for r in rows}),runs=rows))
    print('VERSION2_NORMAL_RUN_RECORDED',name)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');main(p.parse_args().name)
