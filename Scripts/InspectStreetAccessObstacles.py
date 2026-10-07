"""Inspect approach obstacles without saving the level."""
import sys
from pathlib import Path
import unreal
ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import ImproveOldTownStreetAccessLighting as phase
from PolishOldTownDetails import actor_bounds
from AuditOldTownLightingCleanup import _bounds, _xyz
build = phase.read(phase.BASE / 'BuildReport.json')
mapfile = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
before = phase.sha(mapfile)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rows = []
for actor in sub.get_all_level_actors():
    name = actor.get_actor_label()
    if not any(c.static_mesh for c in actor.get_components_by_class(unreal.StaticMeshComponent)):
        continue
    low, high = actor_bounds(actor)
    if ('UtilityPole_02' in name or 'WallUtilityCluster_03' in name
            or (low[0] < 4700 < high[0] and low[1] < -500 < high[1] and low[2] > 400)
            or (low[0] < 1450 and high[0] > 1000 and low[1] < 600 and high[1] > 350)):
        rows.append({'actor': name, 'location': _xyz(actor.get_actor_location()),
                     'bounds': [low, high], 'state': phase.actor_state(actor),
                     'component_bounds': [{'name': c.get_name(), 'bounds': _bounds(c)}
                                          for c in actor.get_components_by_class(unreal.PrimitiveComponent)]})
assert phase.sha(mapfile) == before
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
from ValidateEnterableStreet import refresh_world_collision
refresh_world_collision(list(sub.get_all_level_actors()))
hits = unreal.SystemLibrary.line_trace_multi_for_objects(world, unreal.Vector(1169,435,56), unreal.Vector(1169,435,-34),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2], False, [], unreal.DrawDebugTrace.NONE)
trace_rows = []
for hit in hits or []:
    trace_rows.append([{'index': i, 'type': type(v).__name__, 'value': str(v)} for i,v in enumerate(hit.to_tuple())])
phase.write('ApproachObstacles.json', {'map_sha256': before, 'actors': rows, 'map_unchanged': True,
                                      'trace_tuple_rows': trace_rows,
                                      'hit_doc': unreal.HitResult.__doc__})
unreal.log('STREET_OBSTACLES_INSPECTED actors={}'.format(len(rows)))
