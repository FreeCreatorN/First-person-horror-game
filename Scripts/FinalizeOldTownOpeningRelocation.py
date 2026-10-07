"""Publish location/reference evidence; previous rendered images stay historical."""
import json
import shutil
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Saved/CodexOutputs/OpeningRelocation_20261007'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    b=read(WORK/'BuildReport.json');audit=read(WORK/'RelocationValidation.json')
    assert audit['passed'] and not (ROOT/'Content/Yastar/Blueprints/OldTownOpenings_20261004').exists()
    mapfile=ROOT/('Content/'+b['target_level'].removeprefix('/Game/')+'.umap');assert sha(mapfile)==b['map_sha256']
    assert all(sha(Path(p))==h for p,h in b['protected_map_sha256'].items())
    result=dict(passed=True,status='PASS',target_level=b['target_level'],map_sha256=b['map_sha256'],
        actor_count=b['actor_count'],moved_blueprints=11,old_folder_removed=True,
        old_folder=audit['old_folder'],new_folder=audit['new_folder'],reference_maps=audit['maps'],
        statistics=audit['statistics'],other_saved_content_changes=audit['other_saved_content_changes'],
        previous_evidence=b['previous_evidence'],previous_renders_status='historical_map_hash',
        changes='Opening blueprint folder and map references only; generation paths updated.',
        limitations=['Door/window player interaction and functioning lift remain pending.'])
    write(WORK/'FinalReview.json',result)
    shutil.copy2(WORK/'Inventory.json',WORK/'RelocationInventory.json')
    reports=['BuildReport.json','RelocationInventory.json','RelocationValidation.json','ArchitectureAudit.json','OperationsAudit.json','FinalReview.json']
    old=read(CANON/'CurrentEvidence.json');before=WORK/'BeforeCanonicalPublish';before.mkdir(exist_ok=True)
    for name in sorted(set(reports+old['current_reports']+['CurrentEvidence.json'])):
        f=CANON/name
        if f.exists() and not (before/name).exists():shutil.copy2(f,before/name)
    for name in reports:shutil.copy2(WORK/name,CANON/name)
    write(CANON/'CurrentEvidence.json',dict(target_level=b['target_level'],map_sha256=b['map_sha256'],
        source_bundle=str(WORK),source_directory=str(WORK),current_reports=reports,
        current_renders=None,current_render_cameras=[],current_render_lighting_modes={},
        previous_evidence_bundle=old['source_bundle'],previous_evidence_status='historical',
        previous_renders=old['current_renders'],previous_render_status='historical_map_hash',
        historical_report_backup=str(before),historical_reports_not_current=sorted(set(old['current_reports'])-set(reports)),
        note='Blueprint location/ref migration. Actor geometry/components were compared after fresh loads; previous images were not relabeled as new captures.',
        external_user_light_deletion_preserved=True,preserved_external_deletions=['PointLight']))
    print(json.dumps(dict(passed=True,moved=11,new_folder=audit['new_folder'],map_sha256=b['map_sha256'])))


if __name__=='__main__':main()
