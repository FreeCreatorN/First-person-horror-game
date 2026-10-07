"""Fresh saved-map audits; writes only the new phase's evidence bundle."""
import unreal,sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
WORK=ROOT/'Saved/CodexOutputs/HotelOpenings_20261004'
from ConvertOldTownBuildings import plan_buildings
from ValidateEnterableStreet import refresh_world_collision
from OldTownHotelValidation import route_probe
from AuditOldTownOpeningComponents import run
from PolishOldTownDetails import actor_bounds
import AuditOldTownRevision as revision
import AuditOldTownLightingCleanup as lighting
import AuditOldTownArchitectureSeal as architecture
import AuditOldTownDetailPolish as details
import VerifySavedEnterableOldTown as saved
import InspectOldTownDetailTriangles as triangles

def write(name,r):(WORK/name).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    build=json.loads((WORK/'BuildReport.json').read_text());plan=json.loads((WORK/'RevisionPlan.json').read_text())
    target=build['target_level'];mapfile=ROOT/('Content/'+target.removeprefix('/Game/')+'.umap');expected=sha(mapfile)
    import ConvertOldTownBuildings as conversion
    conversion.TARGET_LEVEL=target
    assert expected==build['map_sha256']
    saved.OUTPUT=WORK;saved.TARGET=target;saved.MAP_FILE=mapfile
    sr=saved.main();assert sr['passed'],sr['errors']
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors());by={a.get_actor_label():a for a in actors};refresh_world_collision(actors)
    for mod in (revision,lighting,details,triangles):mod.TARGET=target
    geometry=plan_buildings([],plan);results={}
    for name,fn in [('OpeningComponentsAudit.json',lambda:run(world,actors,geometry,build)),
                    ('RevisionAudit.json',lambda:revision.audit_revision(world,actors,build,plan)),
                    ('LightingCleanupAudit.json',lambda:lighting.audit_cleanup(world,actors,build)),
                    ('ArchitectureSealAudit.json',lambda:architecture.audit_architecture(world,actors,build,plan)),
                    ('DetailPolishAudit.json',lambda:details.audit_details(world,actors,build,plan)),
                    ('DetailTriangleAudit.json',lambda:triangles.inspect(build,plan,actors))]:
        r=fn();r['map_sha256']=expected;write(name,r);assert r['passed'],(name,r.get('failures',r.get('errors'))[:15]);results[name]=r
    h={'passed':True,'checks':[],'errors':[],'map_sha256':expected}
    def check(name,passed,**data):
        h['checks'].append(dict(data,name=name,passed=bool(passed)))
        if not passed:h['passed']=False;h['errors'].append(name)
    for row in build['hotel_plan']['placed_boxes']:
        a=by.get(row['actor']);box=actor_bounds(a) if a else None
        check('hotel_box:'+row['actor'],box is not None and all(abs(box[j][i]-row[['world_min','world_max'][j]][i])<.1 for j in range(2) for i in range(3)),actual=box)
    for r in build['roof_cap_repairs']:
        a=by[r['actor']];box=actor_bounds(a);b=next(b for b in geometry if b.label==r['building'])
        check('roof_eaves:'+r['actor'],all(abs(box[0][i]-(b.low[i]-10))<.1 and abs(box[1][i]-(b.high[i]+10))<.1 for i in (0,1)) and abs(box[0][2]-b.high[2])<.1,actual=box)
    routes=[]
    for route in build['hotel_plan']['routes']:
        result=route_probe(world,route['points']);routes.append(dict(route,result=result));check('hotel_route:'+route['name'],result['passed'],failures=result['failures'])
    h['routes']=routes;write('HotelLayoutAudit.json',h);assert h['passed'],h['errors']
    assert expected==sha(mapfile),'Review map changed during verification'
    assert all(sha(Path(p))==s for p,s in build['protected_map_sha256'].items()),'Protected map changed'
    write('FreshHotelVerification.json',{'passed':True,'map_sha256':expected,'actor_count':len(actors),'target_level':target,'protected_maps_unchanged':True,'audit_statistics':{n:r.get('statistics') for n,r in results.items()},'hotel_checks':len(h['checks'])})
    unreal.log('OLDTOWN_HOTEL_FRESH_VERIFICATION_PASS '+expected)

if __name__=='__main__':
    try:main()
    except Exception:
        write('FreshHotelFailure.json',{'passed':False,'traceback':traceback.format_exc()});raise
