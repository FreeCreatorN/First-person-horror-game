"""Carry the verified material-only revision into the model's current reports."""
import json,hashlib,runpy
from pathlib import Path
TASK=Path(__file__).resolve().parent;OUT=TASK.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
source=read(TASK/'update_report.json');ue=read(TASK/'ue_update_report.json')
assert source['success'] and ue['success']
assert source['geometry_before']==source['geometry_after']
for path,expected in source['untouched_source_files'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected,path
validation=read(OUT/'validation_report.json')
validation['bakes']['T_ClipboardPaper_BaseColor']=source['bakes']['T_ClipboardPaper_BaseColor']
for current,key in [('Clipboard_Preview.png','overall'),('Clipboard_ClipDetail.png','clip_detail')]:
    validation['renders'][current].update(source['renders'][key])
validation['paper_material_revision']={'path':str(TASK/'update_report.json'),'style':source['paper_style'],'geometry_unchanged':True}
(OUT/'validation_report.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
runpy.run_path(str(OUT/'verify_final.py'),run_name='__main__')
