"""Fresh saved-map verification of passage, door approach and directional lamps."""
import sys
import traceback
from pathlib import Path
import unreal
ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import ImproveOldTownStreetAccessLighting as phase
WORK = phase.WORK


def main():
    build = phase.read(WORK / 'BuildReport.json')
    plan = phase.read(WORK / 'RevisionPlan.json')
    target = build['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    current = phase.sha(mapfile)
    assert current == build['map_sha256'] == build['street_access_lighting']['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    phase.verify_preservation(actors, build)
    import VerifyOldTownHotelReview as base
    base.WORK = WORK
    base.main()
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    from AuditOldTownStreetAccessLighting import audit
    result = audit(world, actors, build, plan)
    result['map_sha256'] = current
    phase.write('StreetAccessLightingAudit.json', result)
    assert result['passed'], 'Street access/light verification failed; see report.'
    assert phase.sha(mapfile) == current
    assert all(phase.sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    applied = phase.read(WORK / 'AccessLightingApplied.json')
    assert applied['map_sha256'] == current and applied['passed']
    applied['fresh_audits_pending'] = False
    phase.write('AccessLightingApplied.json', applied)
    unreal.log('STREET_ACCESS_LIGHTING_FRESH_PASS ' + current)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        phase.write('AccessFreshFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
