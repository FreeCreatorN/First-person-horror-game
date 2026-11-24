"""Reopen the saved original map and verify the narrow trim and lighting."""
import json
from pathlib import Path
import sys
import unreal

sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from ApplyOldTownStairTrim_20261113 import ALT, MAP, OUTPUT, by_label, load, read, sha, verify_geometry, write
from OldTownNonLightEmission import verify_non_light_emission


def main():
    applied = read('Applied.json')
    assert applied['passed'] and sha(MAP)==applied['saved_sha256'] and sha(ALT)==applied['version2_sha256']
    _, ae, _ = load()
    kept = {label:[tuple(row) for row in rows] for label,rows in applied['kept'].items()}
    verify_geometry(by_label(ae), kept)
    report = verify_non_light_emission(ae, applied['emission'])
    assert report['passed']
    write('Readback.json', {'passed':True,'map_sha256':sha(MAP),'version2_sha256':sha(ALT),
        'removed_bounds':applied['removed_bounds'],'kept':list(kept),
        'non_light_slots_remaining':len(report['candidates']),'emitter_slots':len(report['preserved']),
        'lights':len(report['light_components']),'controllers':len(report['controllers'])})
    unreal.log('OLDTOWN_STAIR_TRIM_READBACK_PASS')


if __name__ == '__main__':
    main()
