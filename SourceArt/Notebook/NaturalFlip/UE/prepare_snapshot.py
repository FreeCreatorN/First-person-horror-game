"""Copy a verified original Notebook baseline; never overwrite a prior snapshot."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

UE = Path(__file__).resolve().parent
REV = UE.parent
OUT = REV.parent
PROJECT = OUT.parents[1]
BEFORE = REV/'Before'
ROOT = '/Game/Yastars/Mesh/Notebook'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


old = json.loads((OUT/'UE'/'ue_import_report.json').read_text(encoding='utf-8-sig'))
assert old['success'] and old['new_package_count'] == 76
assert not BEFORE.exists(), 'A previous snapshot exists; preserve it instead of overwriting.'
names = {'A_Notebook_FullCycle','A_Notebook_Open','A_Notebook_CloseLast'} | {f'A_Notebook_Turn{i:02d}' for i in range(1,17)}
manifest = {'created_utc':datetime.now(timezone.utc).isoformat(),'target_root':ROOT,'packages':{},'source_files':{},'protected_files':{}}
for package, info in old['new_packages_on_disk'].items():
    assert Path(info['file']).is_file() and sha(info['file']) == info['sha256'], ('Asset changed since verified import; do not overwrite',package)
    record = dict(info)
    record['replace_allowed'] = package.rsplit('/',1)[-1] in names
    manifest['packages'][package] = record
target = PROJECT/'Content'/'Yastars'/'Mesh'/'Notebook'
assert {Path(i['file']).resolve() for i in manifest['packages'].values()} == {p.resolve() for p in target.rglob('*.uasset')}
for source, digest in old['source_files_sha256'].items():
    assert Path(source).is_file() and sha(source) == digest, ('Original source changed before backup',source)
for package, info in manifest['packages'].items():
    if info['replace_allowed']:
        backup = BEFORE/'Packages'/Path(info['file']).relative_to(PROJECT/'Content')
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(info['file'],backup)
        assert sha(backup) == info['sha256']
        info['backup'] = str(backup)
sources = {Path(p) for p in old['source_files_sha256']}
sources.update(p for p in OUT.glob('*.py') if p.is_file())
sources.update(p for p in (OUT/'README.md',OUT/'CONTINUE.md') if p.is_file())
for source in sources:
    backup = BEFORE/'Source'/source.relative_to(OUT)
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,backup)
    manifest['source_files'][str(source)] = {'sha256':sha(source),'backup':str(backup)}
for path in (OUT/'UE').glob('*'):
    if path.is_file() and path.suffix in ('.py','.ps1','.json'):
        backup = BEFORE/'Evidence'/path.name
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,backup)
protected = set((PROJECT/'Content').rglob('*.umap'))
for directory in (PROJECT/'Config',PROJECT/'Content'/'Yastar'/'UI',PROJECT/'Content'/'Yastar'/'Items'):
    protected.update(p for p in directory.rglob('*') if p.is_file())
manifest['protected_files'] = {str(p.resolve()):sha(p) for p in protected}
(BEFORE/'state_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('NOTEBOOK_NATURAL_FLIP_BASELINE_COPIED',sum(i['replace_allowed'] for i in manifest['packages'].values()),len(manifest['source_files']))
