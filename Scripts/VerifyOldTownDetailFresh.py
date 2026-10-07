"""Read-only independent reload of every architectural/detail/lighting audit."""
import hashlib,json,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from ValidateEnterableStreet import refresh_world_collision
from AuditOldTownRevision import audit_revision
from AuditOldTownLightingCleanup import audit_cleanup
from AuditOldTownArchitectureSeal import audit_architecture
from AuditOldTownDetailPolish import audit_details
OUT=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
WORK=ROOT/'Saved/CodexOutputs/DetailPolish_20261004'
b=json.loads((OUT/'BuildReport.json').read_text(encoding='utf-8-sig'))
p=json.loads((OUT/'RevisionPlan.json').read_text(encoding='utf-8-sig'))
path=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
h=hashlib.sha256(path.read_bytes()).hexdigest()
assert h==b['map_sha256']==b['architecture_seal']['map_sha256']==b['detail_polish']['map_sha256']
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==expected for f,expected in b['protected_map_sha256'].items())
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(b['target_level'])
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
refresh_world_collision(actors)
from VerifySavedEnterableOldTown import main as verify_saved
saved=verify_saved();assert saved['passed'],saved['errors']
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
refresh_world_collision(actors)
for name,fn in [('RevisionAudit.json',lambda:audit_revision(w,actors,b,p)),
                ('LightingCleanupAudit.json',lambda:audit_cleanup(w,actors,b)),
                ('ArchitectureSealAudit.json',lambda:audit_architecture(w,actors,b,p)),
                ('DetailPolishAudit.json',lambda:audit_details(w,actors,b,p))]:
    report=fn();report['map_sha256']=h;report['independent_saved_reload']=True
    for folder in (OUT,WORK):(folder/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report['passed'],report['errors']
    unreal.log('OTS_DETAIL_FRESH_AUDIT '+name+' '+json.dumps(report['statistics']))
assert hashlib.sha256(path.read_bytes()).hexdigest()==h
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==expected for f,expected in b['protected_map_sha256'].items())
unreal.log('OTS_DETAIL_FRESH_SUCCESS '+h)
