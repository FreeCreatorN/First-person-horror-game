"""Record a helper whose actual normal zero exit was observed by the caller."""
import argparse,json,re
from pathlib import Path
from VerifyOldTownSoftGoodsRefinement import reference,read
W=Path(__file__).resolve().parents[1]/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
TOKENS={'InputExport':'SOFT_GOODS_INPUT_EXPORT_PASS','BuildApply':'SOFT_GOODS_APPLIED','SavedAudit':'SOFT_GOODS_SAVED_AUDIT_PASS',
        'OverlapCorrection':'SOFT_GOODS_OVERLAP_CORRECTION_PASS'}
def main(name):
    role=next(r for r in TOKENS if re.fullmatch(r+'\\d*',name));log=W/(name+'.log')
    text=log.read_text(encoding='utf-8-sig',errors='replace')
    assert TOKENS[role] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text
    p=W/'RunCompletion.json';d=read(p) if p.exists() else {'runs':[]}
    rows=[r for r in d['runs'] if not re.fullmatch(role+'\\d*',r['name'])]
    rows.append(dict(name=name,exit_code=0,normal_exit_observed_by_root=True,forced_cleanup=False,reused=False,
        success_token=TOKENS[role],log=reference(log)))
    seen={next(k for k in TOKENS if re.fullmatch(k+'\\d*',r['name'])) for r in rows}
    d=dict(passed=seen==set(TOKENS),stage=W.name,runs=rows,required_runs_remaining=sorted(set(TOKENS)-seen))
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('NORMAL_HELPER_EXIT_RECORDED '+name+' all_required='+str(d['passed']))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('name');main(a.parse_args().name)
