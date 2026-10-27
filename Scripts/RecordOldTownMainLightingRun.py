"""Record a Main-light helper only after its zero exit is observed."""
import argparse,re
from datetime import datetime,timezone
from OldTownMainLightingCommon import *
TOKENS={'Apply':'OLDTOWN_MAIN_DIRECTIONAL_APPLIED','Audit':'OLDTOWN_MAIN_DIRECTIONAL_READBACK_PASS'}
def main(name):
    role=next(k for k in TOKENS if re.fullmatch(k+r'\d+',name))
    log=W/(name+'.log');text=log.read_text(encoding='utf-8-sig',errors='replace')
    assert TOKENS[role] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text
    report=W/('Applied.json' if role=='Apply' else 'ReadbackAudit.json');output=read(report)
    digest=sha(MAP);assert output['passed'] and output['map_sha256']==digest
    assert re.search(re.escape(TOKENS[role])+r'\s+'+re.escape(digest)+r'\b',text),'Helper log is not bound to this saved map.'
    path=W/'RunCompletion.json';doc=read(path) if path.exists() else dict(runs=[])
    rows=[r for r in doc['runs'] if r['role']!=role]
    rows.append(dict(role=role,name=name,exit_code=0,normal_exit_observed_by_root=True,forced_cleanup=False,reused=False,
        map_sha256=digest,output_report=ref(report),success_token=TOKENS[role],log=ref(log),observed_utc=datetime.now(timezone.utc).isoformat()))
    write(path,dict(passed={r['role'] for r in rows}==set(TOKENS),stage=W.name,runs=rows))
    print('MAIN_LIGHTING_NORMAL_EXIT_RECORDED',name)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');main(p.parse_args().name)
