"""Validate fresh Unreal evidence and all asset files on disk."""
from pathlib import Path

from rack_manifest import HERE, TARGET, digest, packages, read, read_export, verify_protected, write


def verify():
    completion = read(HERE / 'completion.json')
    assert completion['success'] and completion['target_root'] == TARGET
    assert [run['mode'] for run in completion['runs']] == ['import', 'reload']
    assert len({run['editor_pid'] for run in completion['runs']}) == 2
    _, expected, source_hashes = read_export()
    assert completion['script_sha256'] == digest(HERE / 'import_ue.py')
    baseline = HERE / 'protected_content_sha256.json'
    assert completion['baseline_sha256'] == digest(baseline)
    actual = packages()
    assert set(actual) == expected
    reports = []
    for run in completion['runs']:
        assert run['normal_zero_exit'] and run['exit_code'] == 0
        path = Path(run['report'])
        assert path.is_relative_to(HERE) and digest(path) == run['report_sha256']
        report = read(path)
        assert report['success'] and report['editor_pid'] == run['editor_pid']
        assert report['source_hashes'] == source_hashes and report['packages'] == actual
        for key in ('run_id', 'target_root', 'script_sha256', 'baseline_sha256', 'manifest_sha256'):
            assert report[key] == completion[key]
        reports.append(report)
    assert reports[0]['meshes'] == reports[1]['meshes'] and reports[0]['parent'] == reports[1]['parent']
    return {'success': True, 'target_root': TARGET, 'mesh_count': len(reports[1]['meshes']),
            'package_count': len(actual), 'verified_in_fresh_editor': True, 'meshes': reports[1]['meshes'],
            'protected_files_checked': verify_protected(read(baseline)), 'packages': actual}


if __name__ == '__main__':
    result = verify()
    write(HERE / 'final_verification.json', result)
    print('RACK_FINAL_VERIFIED', result['success'], result['mesh_count'], result['package_count'])
