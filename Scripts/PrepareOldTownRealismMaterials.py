import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import OldTownRealismMaterials as pbr
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def main():
    pbr.initialize()
    for role in pbr.SPEC:
        for mode in ('World','UV'):pbr.master(role,mode)
    (WORK/'MaterialBuild.json').write_text(json.dumps(pbr.report(),ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('REALISM_MATERIALS_PASS')
try:main()
except Exception:
    (WORK/'MaterialFailure.json').write_text(json.dumps(dict(passed=False,traceback=traceback.format_exc()),ensure_ascii=False,indent=2),encoding='utf-8');raise
