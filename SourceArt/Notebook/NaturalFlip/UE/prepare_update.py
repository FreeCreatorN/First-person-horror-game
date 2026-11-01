"""Validate original packages and build an animation-only update plan. No UE launch."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fbx_semantics import animation_semantic

UE = Path(__file__).resolve().parent
REV = UE.parent
OUT = REV.parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT/'Content'
TARGET = CONTENT/'Yastars'/'Mesh'/'Notebook'
BEFORE = REV/'Before'
ROOT = '/Game/Yastars/Mesh/Notebook'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_files():
    files = set(CONTENT.rglob('*.umap'))
    for directory in (PROJECT/'Config',CONTENT/'Yastar'/'UI',CONTENT/'Yastar'/'Items'):
        files.update(path for path in directory.rglob('*') if path.is_file())
    return {str(path.resolve()) for path in files}


def prepare():
    before = json.loads((BEFORE/'state_manifest.json').read_text(encoding='utf-8-sig'))
    report = {'success':False,'checked_utc':datetime.now(timezone.utc).isoformat(),'target_root':ROOT,
              'unexpected_changes':[],'animations':{},'sources_sha256':{}}
    try:
        for package, item in before['packages'].items():
            if not Path(item['file']).is_file() or sha(item['file']) != item['sha256']:
                report['unexpected_changes'].append(package)
            if item['replace_allowed']:
                assert Path(item['backup']).is_file() and sha(item['backup']) == item['sha256'], ('Original animation backup differs',package)
        current = {p.resolve() for p in TARGET.rglob('*.uasset')}
        expected = {Path(item['file']).resolve() for item in before['packages'].values()}
        assert current == expected, ('Notebook package set changed',sorted(map(str,current^expected)))
        assert not report['unexpected_changes'], ('User assets changed; do not overwrite',report['unexpected_changes'])
        assert protected_files() == set(before['protected_files']), 'Protected file set changed'
        assert all(sha(path)==digest for path,digest in before['protected_files'].items()), 'Protected project files changed; review before updating'
        old = json.loads((BEFORE/'Source'/'model_report.json').read_text(encoding='utf-8-sig'))
        model = json.loads((OUT/'model_report.json').read_text(encoding='utf-8-sig'))
        for key in ('bones','triangles','vertices','material_slots','materials','bounds_min_m','bounds_max_m'):
            assert model[key] == old[key], ('Animation-only revision changed the model contract',key)
        assert model['fbx_unit']=='centimeter' and model['fbx_armature_scale']==model['ue_import_uniform_scale']==1
        assert model['fps']==30 and len(model['clips'])==18
        sources = {OUT/'Notebook.blend',OUT/'model_report.json',OUT/'Exports'/'SK_Notebook.fbx'}
        specs = [{'name':'A_Notebook_FullCycle','file':'Exports/A_Notebook_FullCycle.fbx',
                  'frame_start':model['frame_start'],'frame_end':model['frame_end'],
                  'seconds':(model['frame_end']-model['frame_start'])/model['fps']}] + model['clips']
        expected_names = {'A_Notebook_FullCycle','A_Notebook_Open','A_Notebook_CloseLast'} | {f'A_Notebook_Turn{i:02d}' for i in range(1,17)}
        assert {spec['name'] for spec in specs}==expected_names
        for spec in specs:
            package = ROOT+'/'+spec['name']
            item = before['packages'][package]
            assert item['replace_allowed']
            path = (OUT/spec['file']).resolve()
            assert path.is_relative_to(OUT) and path.is_file()
            old_path = BEFORE/'Source'/path.relative_to(OUT)
            old_hash, new_hash = animation_semantic(old_path),animation_semantic(path)
            sources.add(path)
            report['animations'][spec['name']] = {**spec,'package':package,'source_sha256':sha(path),
                'original_package_sha256':item['sha256'],'old_semantic':old_hash,'new_semantic':new_hash,
                'replace':old_hash['sha256']!=new_hash['sha256']}
        assert report['animations']['A_Notebook_FullCycle']['replace'], 'The full-cycle animation has no semantic change'
        for path in sources:
            assert path.is_file()
            report['sources_sha256'][str(path.resolve())]=sha(path)
        for path,item in before['source_files'].items():
            if Path(path).parent.name == 'Textures':
                assert sha(path)==item['sha256'], ('Texture source changed in an animation-only revision',path)
        report['before_manifest_sha256']=sha(BEFORE/'state_manifest.json')
        report['preflight_scripts_sha256']={str(path):sha(path) for path in (UE/'prepare_update.py',UE/'fbx_semantics.py')}
        report['replace_names']=[name for name,spec in report['animations'].items() if spec['replace']]
        report['preserve_names']=[name for name,spec in report['animations'].items() if not spec['replace']]
        report['success']=True
    except Exception as error:
        report['error']=str(error)
    (UE/'update_plan.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('NOTEBOOK_NATURAL_UPDATE_PLAN',report['success'])
    if not report['success']:
        print(report['error'])
        raise SystemExit(1)


if __name__=='__main__':
    prepare()
