"""Read-only imported stair triangles and exact saved-world visual clearance.

Mesh copies are transient. No asset, actor, component, or map is modified/saved.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
WORK = ROOT/'Saved/CodexOutputs/DetailPolish_20261004'
OUT = ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP = ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TOL = .02
sys.path.insert(0,str(ROOT/'Scripts'))


def xyz(v): return [float(v.x),float(v.y),float(v.z)]
def near(a,b,tol=.1): return len(a)==len(b) and all(abs(x-y)<=tol for x,y in zip(a,b))


def source_position(p,axes):
    result = [0.,0.,0.]
    for i,axis in enumerate(axes['order']): result[axis] = p[i]/axes['signs'][i]
    return result


def source_to_local(p,axes):
    return [p[axes['order'][i]]*axes['signs'][i] for i in range(3)]


def sub(a,b): return [a[i]-b[i] for i in range(3)]
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def area3(t): return .5*math.sqrt(sum(v*v for v in cross(sub(t[1],t[0]),sub(t[2],t[0]))))
def signed_area2(p): return .5*sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))


def is_walking_surface(t):
    normal = cross(sub(t[1],t[0]),sub(t[2],t[0]))
    length = math.sqrt(sum(v*v for v in normal))
    # FBX end-face coordinates may differ by micrometres. Their projected
    # area is nonzero numerically but their nearly horizontal normal still
    # identifies the face as vertical. Nose facets have ample vertical normal.
    return length>1e-7 and abs(normal[2])/length>1e-5


def triangle_z(triangle,x,y):
    a,b,c = triangle
    det = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(det)<1e-9: return None
    u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det
    v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
    return u*a[2]+v*b[2]+(1-u-v)*c[2]


def contains_xy(triangle,x,y,tol=1e-7):
    a,b,c = triangle
    det = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(det)<1e-9: return False
    u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det
    v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
    return min(u,v,1-u-v)>=-tol


def clip_triangles(first,second):
    """Intersection in XY; linear-height extrema lie at its vertices."""
    polygon = [p[:2] for p in first]; clip = [p[:2] for p in second]
    if signed_area2(clip)<0: clip.reverse()
    for i,a in enumerate(clip):
        b = clip[(i+1)%3]
        def distance(p): return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        old,polygon = polygon,[]
        if not old: break
        previous,dp = old[-1],distance(old[-1])
        for current in old:
            dc = distance(current)
            if (dc>=-1e-7)!=(dp>=-1e-7):
                fraction = dp/(dp-dc)
                polygon.append([previous[j]+fraction*(current[j]-previous[j]) for j in range(2)])
            if dc>=-1e-7: polygon.append(current)
            previous,dp = current,dc
    return polygon


def probe_api():
    """Persist the real __doc__ contracts confirmed for this UE version."""
    docs = {}
    for cls_name,names in {
        'GeometryScript_AssetUtils':('copy_mesh_from_static_mesh',),
        'GeometryScript_MeshQueries':('get_all_triangle_i_ds','get_triangle_positions','get_is_closed_mesh','get_num_open_border_edges'),
        'GeometryScript_List':('convert_index_list_to_array',),
        'GeometryScriptMeshReadLOD':(),
        'GeometryScriptCopyMeshFromAssetOptions':(),
        'DynamicMesh':(),
    }.items():
        cls = getattr(unreal,cls_name,None)
        docs[cls_name] = {'exists':cls is not None,'doc':getattr(cls,'__doc__',None)}
        for name in names:
            method = getattr(cls,name,None) if cls else None
            docs[cls_name][name] = {'exists':method is not None,'doc':getattr(method,'__doc__',None)}
            assert method is not None,(cls_name,name)
    for enum in ('GeometryScriptLODType','GeometryScriptOutcomePins'):
        cls = getattr(unreal,enum)
        docs[enum] = {n:str(getattr(cls,n)) for n in dir(cls) if n.isupper()}
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'TriangleAPIDocs.json').write_text(json.dumps(docs,indent=2),encoding='utf-8')


def read_triangles(asset):
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property('apply_build_settings',True)
    options.set_editor_property('use_build_scale',True)
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.SOURCE_MODEL)
    lod.set_editor_property('lod_index',0)
    mesh,outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(asset,unreal.DynamicMesh(),options,lod)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS,asset.get_path_name()
    _,index_list,gaps = unreal.GeometryScript_MeshQueries.get_all_triangle_i_ds(mesh)
    ids = list(unreal.GeometryScript_List.convert_index_list_to_array(index_list))
    rows = []
    for triangle_id in ids:
        valid,a,b,c = unreal.GeometryScript_MeshQueries.get_triangle_positions(mesh,triangle_id)
        assert valid,triangle_id
        rows.append({'id':int(triangle_id),'local':[xyz(a),xyz(b),xyz(c)]})
    return {'triangles':rows,'closed':bool(unreal.GeometryScript_MeshQueries.get_is_closed_mesh(mesh)),
            'open_border_edges':int(unreal.GeometryScript_MeshQueries.get_num_open_border_edges(mesh)),
            'triangle_id_gaps':bool(gaps)}


def transformed(triangles,component):
    transform = component.get_world_transform()
    return [[xyz(transform.transform_location(unreal.Vector(*p))) for p in t] for t in triangles]


def clearance_geometry(lower_tops,upper_bottom):
    """Exact triangle-pair extrema, including the rounded nose surfaces."""
    minimum,at = float('inf'),None
    projected,covered = 0.,0.; incomplete = []
    for index,lower in enumerate(lower_tops):
        area = abs(signed_area2([p[:2] for p in lower]))
        if area<1e-7: continue
        projected += area; this_covered = 0.
        for upper in upper_bottom:
            polygon = clip_triangles(lower,upper)
            if len(polygon)<3: continue
            overlap = abs(signed_area2(polygon))
            if overlap<1e-8: continue
            this_covered += overlap
            for x,y in polygon:
                bottom_z,top_z = triangle_z(upper,x,y),triangle_z(lower,x,y)
                gap = bottom_z-top_z
                if gap<minimum: minimum,at = gap,[x,y,top_z,bottom_z]
        covered += this_covered
        if abs(this_covered-area)>.02:
            incomplete.append({'triangle':index,'area_cm2':area,'covered_cm2':this_covered})
    return {'minimum_cm':minimum if math.isfinite(minimum) else None,'minimum_at_cm':at,
            'projected_tread_area_cm2':projected,'covered_tread_area_cm2':covered,
            'incomplete_triangles':incomplete}


def inspect(build,plan,actors):
    from ConvertOldTownBuildings import plan_buildings
    report = {'passed':False,'checks':[],'errors':[],'statistics':{},'assets':[], 'stairs':[],
              'scope':'Actual UE LOD0 SourceModel triangles with build settings; exact world XY triangle intersections.',
              'limitations':['No runtime player walkthrough or render-LOD pixel inspection is performed.']}
    def check(name,passed,**details):
        report['checks'].append(dict(name=name,passed=bool(passed),**details))
        if not passed: report['errors'].append(name)
    spec = build['detail_polish']; axes = spec['axes']
    check('axis_transform_verified',axes['order']==[0,1,2] and axes['signs'][2]==1.)
    manifest = json.loads((ROOT/spec['manifest_path']).read_text(encoding='utf-8-sig'))
    flights = [r for r in manifest['assets'] if r['kind']=='flight']
    check('all_25_imported_flight_variants',len(flights)==25)
    imports = {r['asset'].split('.',1)[0].rsplit('/',1)[-1]:r for r in spec['imports']}
    data = {}
    for entry in flights:
        name = entry['name']; asset = unreal.load_asset(imports[name]['asset'])
        assert isinstance(asset,unreal.StaticMesh),name
        copied = read_triangles(asset)
        triangles = [r['local'] for r in copied['triangles']]
        source = [[source_position(p,axes) for p in t] for t in triangles]
        rise,n = float(entry['rise']),int(entry['steps']); run = n*28.
        bottom_ids = [i for i,t in enumerate(source) if all(abs(p[2]-rise/28.*p[1]+20.+rise)<=TOL for p in t)]
        bottom = [source[i] for i in bottom_ids]
        unique = {tuple(round(v,3) for v in p) for t in bottom for p in t}
        corners = [[x,y,z] for x in (-70.,70.) for y,z in ((0.,-20.-rise),(run,n*rise-20.-rise))]
        corner_match = len(unique)==4 and all(any(near(list(p),e) for e in corners) for p in unique)
        expected_area = 140.*run*math.sqrt(1.+(rise/28.)**2)
        actual_area = sum(area3(t) for t in bottom)
        shared = list(set(tuple(round(v,3) for v in p) for p in bottom[0]) &
                      set(tuple(round(v,3) for v in p) for p in bottom[1])) if len(bottom)==2 else []
        diagonal = len(shared)==2 and abs(abs(shared[0][0]-shared[1][0])-140.)<=.1 and abs(abs(shared[0][1]-shared[1][1])-run)<=.1
        check('imported_bottom_complete_quad:'+name,len(bottom)==2 and corner_match and diagonal
              and abs(actual_area-expected_area)<=max(.1,expected_area*1e-6),
              triangle_ids=[copied['triangles'][i]['id'] for i in bottom_ids],source_corners_cm=[list(p) for p in sorted(unique)],
              area_cm2=actual_area,expected_area_cm2=expected_area)
        check('imported_closed_mesh:'+name,copied['closed'] and copied['open_border_edges']==0,
              open_border_edges=copied['open_border_edges'],triangles=len(triangles))
        tops = [t for i,t in enumerate(source) if i not in bottom_ids and is_walking_surface(t)]
        samples,misses,max_error = 0,[],0.
        for step in range(n):
            for x in (-60.,0.,60.):
                for inset in (.26,14.,27.74):
                    y = step*28.+inset
                    heights = [triangle_z(t,x,y) for t in tops if contains_xy(t,x,y)]
                    error = abs(max(heights)-(step+1)*rise) if heights else float('inf')
                    samples += 1; max_error = max(max_error,error)
                    if error>TOL: misses.append({'step':step,'x':x,'y':y,'error_cm':error if math.isfinite(error) else None})
        bevels = []
        for t in tops:
            if max(p[2] for p in t)-min(p[2] for p in t)>TOL:
                bevels.extend(min(max(abs(p[1]-step*28.),abs(p[2]-(step+1)*rise)) for step in range(n)) for p in t)
        check('imported_28cm_treads_and_risers:'+name,not misses and max_error<=TOL,
              samples=samples,max_error_cm=max_error,failures=misses)
        check('imported_nose_bevel_at_most_025cm:'+name,bool(bevels) and max(bevels)<=.25+TOL,
              max_bevel_corner_distance_cm=max(bevels) if bevels else None)
        data[name] = {'entry':entry,'local_bottom':[triangles[i] for i in bottom_ids],
                      'local_tops':[[source_to_local(p,axes) for p in t] for t in tops],'asset':asset}
        report['assets'].append({'asset':asset.get_path_name(),'triangles':len(triangles),
                                'bottom_triangles':len(bottom),'closed':copied['closed'],'open_border_edges':copied['open_border_edges'],
                                'tread_sample_count':samples,'maximum_tread_error_cm':max_error})
    by = {a.get_actor_label():a for a in actors}
    visual_by = {r['actor']:r for r in spec['visuals']}
    geometry = {b.label:b for b in plan_buildings([],plan)}
    connections = {(r['building'],r['from_floor']):r for r in spec['stairs']}
    expected = {(b.label,f) for b in geometry.values() for f in range(b.count-1)}
    check('all_81_saved_stair_connections',set(connections)==expected and len(spec['stairs'])==81)
    roof_data = {}; no_collision = {}; minima = []; pair_count = 0
    for row in spec['stairs']:
        b = geometry[row['building']]; level = row['from_floor']; result = {'building':b.label,'from_floor':level,'flights':[]}
        for index,label in enumerate(row['flight_visual_actors']):
            components = [c for c in by[label].get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]
            assert len(components)==1,label
            component = components[0]; no_collision[label] = component.get_collision_enabled().value
            check('saved_visual_nocollision:'+label,no_collision[label]==unreal.CollisionEnabled.NO_COLLISION.value
                  and component.get_editor_property('visible'),collision=str(component.get_collision_enabled()))
            name = visual_by[label]['asset'].split('.',1)[0].rsplit('/',1)[-1]
            check('saved_visual_actual_asset:'+label,component.static_mesh==data[name]['asset'],
                  actual_asset=component.static_mesh.get_path_name(),expected_asset=data[name]['asset'].get_path_name())
            actual_bottom = transformed(data[name]['local_bottom'],component)
            actual_tops = transformed(data[name]['local_tops'],component)
            lower = b.floors[level]; middle = lower+b.n1*b.rise
            if index==0:
                u,ends = b.core_u-80.,((b.core_v,lower-20.-b.rise),(b.core_v+b.n1*28.,middle-20.-b.rise))
            else:
                u,ends = b.core_u+80.,((b.core_v+b.n1*28.,middle-20.-b.rise),
                                      (b.core_v+(b.n1-b.n2)*28.,b.floors[level+1]-20.-b.rise))
            expected_corners = [b.world(u+side,v,z) for side in (-70.,70.) for v,z in ends]
            actual_corners = {tuple(round(v,4) for v in p) for t in actual_bottom for p in t}
            check('actual_imported_soffit_world_placement:'+label,len(actual_corners)==4
                  and all(any(near(list(p),e) for e in expected_corners) for p in actual_corners),
                  imported_corners_cm=[list(p) for p in sorted(actual_corners)],expected_corners_cm=expected_corners)
            above = connections.get((b.label,level+1))
            if above:
                ceiling_label = above['flight_visual_actors'][index]
                ceiling_component = by[ceiling_label].get_component_by_class(unreal.StaticMeshComponent)
                ceiling_name = visual_by[ceiling_label]['asset'].split('.',1)[0].rsplit('/',1)[-1]
                ceiling = transformed(data[ceiling_name]['local_bottom'],ceiling_component)
                ceiling_kind = 'next_floor_imported_soffit'
            else:
                if b.label not in roof_data:
                    records = [r for r in build['buildings']['structural_boxes'] if r['building']==b.label and r['role']=='RoofSlab']
                    assert len(records)==1,(b.label,records)
                    ceiling_label = records[0]['actor']
                    ceiling_component = by[ceiling_label].get_component_by_class(unreal.StaticMeshComponent)
                    raw = read_triangles(ceiling_component.static_mesh)
                    world_triangles = transformed([r['local'] for r in raw['triangles']],ceiling_component)
                    roof_bottom = [t for t in world_triangles if all(abs(p[2]-(b.high[2]-20.))<=TOL for p in t)]
                    check('actual_roof_bottom_plane:'+b.label,len(roof_bottom)==2,
                          triangles=len(roof_bottom),expected_z_cm=b.high[2]-20.)
                    roof_data[b.label] = (ceiling_label,roof_bottom)
                ceiling_label,ceiling = roof_data[b.label]; ceiling_kind = 'actual_roof_slab_triangles'
            gap = clearance_geometry(actual_tops,ceiling)
            passed = gap['minimum_cm'] is not None and gap['minimum_cm']>225. and not gap['incomplete_triangles']
            check('actual_imported_triangle_clearance:'+label,passed,ceiling_actor=ceiling_label,
                  ceiling_kind=ceiling_kind,required_cm=225.,**gap)
            if gap['minimum_cm'] is not None: minima.append(gap['minimum_cm'])
            pair_count += 1
            result['flights'].append(dict(actor=label,ceiling_actor=ceiling_label,ceiling_kind=ceiling_kind,**gap))
        report['stairs'].append(result)
    check('visual_collision_unchanged',all(by[label].get_component_by_class(unreal.StaticMeshComponent).get_collision_enabled().value==value
                                         for label,value in no_collision.items()))
    report['statistics'] = {'imported_flight_variants':len(data),'stair_connections':len(connections),
                            'placed_flights':pair_count,'actual_roof_slabs':len(roof_data),
                            'minimum_actual_vertical_clearance_cm':min(minima) if minima else None,
                            'checks':len(report['checks']),'failed_checks':len(report['errors'])}
    report['passed'] = not report['errors']
    return report


def main():
    result = {'passed':False,'checks':[],'errors':[],'statistics':{}}
    try:
        probe_api()
        build = json.loads((OUT/'BuildReport.json').read_text(encoding='utf-8-sig'))
        plan = json.loads((OUT/'RevisionPlan.json').read_text(encoding='utf-8-sig'))
        expected_hash = hashlib.sha256(MAP.read_bytes()).hexdigest()
        assert expected_hash==build['map_sha256']==build['detail_polish']['map_sha256']
        protected = build['protected_map_sha256']
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
        owned_assets = [ROOT/'Content'/Path(r['asset'].split('.',1)[0].removeprefix('/Game/')).with_suffix('.uasset')
                        for r in build['detail_polish']['imports']]
        asset_hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in owned_assets}
        assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        result = inspect(build,plan,actors)
        result['map_sha256'] = expected_hash
        assert hashlib.sha256(MAP.read_bytes()).hexdigest()==expected_hash,'Target map changed during read-only inspection'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items()),'Protected map changed'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in asset_hashes.items()),'Imported asset changed'
        result['read_only_evidence'] = {'target_map_unchanged':True,'protected_maps_unchanged':True,
                                      'all_imported_assets_unchanged':True,'imported_asset_count':len(asset_hashes)}
    except Exception:
        result['passed'] = False
        result['errors'].append('inspection_exception')
        result['traceback'] = traceback.format_exc()
    finally:
        for folder in (OUT,WORK):
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'DetailTriangleAudit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if not result['passed']:
        unreal.log_error('OTS_DETAIL_TRIANGLE_AUDIT_FAILED '+','.join(result['errors']))
        raise RuntimeError('Actual imported triangle audit failed; see DetailTriangleAudit.json')
    unreal.log('OTS_DETAIL_TRIANGLE_AUDIT_SUCCESS '+json.dumps(result['statistics']))
    return result


if __name__=='__main__':
    main()
