"""Independent read-only audit of report-listed authored meshes.

Every geometric test is restricted to one product and uses world transforms
minus that product's display translation. No collection enumeration or saving.
"""
import bpy,bmesh,json,math,hashlib,itertools
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'SnackIceCreamSet.blend'
SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
REPORT=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8-sig'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.data.scenes[REPORT['source_scene']]
S.frame_set(1);bpy.context.view_layer.update()
EPS=2e-6
RESULT={'source':str(SOURCE),'source_sha256_before':SHA,'read_only':True,
 'selection':'Exact object names in model_report.parts[*].object',
 'coordinate_frame':'Object matrix_world minus product display translation; pivots and display roots included.',
 'tolerance_m':EPS,'parts':{},'products':{},'same_facing_coplanar_overlaps':[],
 'strict_surface_crossings':[], 'findings':[], 'notes':[
 'Vertex-to-surface distances are sampled upper bounds on exact component separation; cavity rays and strict triangle crossings provide independent physical checks.',
 'Embedded heat-seal/wrapper-tail/stick junctions are counted transparently and classified separately from neighboring product contents.']}
TRIS=[];SHELLS=defaultdict(list);PART_BVHS={}

def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def polyarea(p):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))*.5 if len(p)>2 else 0
def clip(subject,boundary):
 result=subject
 if cross(*boundary)<0:boundary=list(reversed(boundary))
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):
  old=result;result=[]
  if not old:break
  for p,q in zip(old,old[1:]+old[:1]):
   cp,cq=cross(a,b,p),cross(a,b,q);ip,iq=cp>=-1e-13,cq>=-1e-13
   if ip:result.append(p)
   if ip!=iq:
    t=cp/(cp-cq);result.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
 return result

def rayhits(bvh,origin,direction,limit=.4):
 origin=Vector(origin);direction=Vector(direction).normalized();out=[];total=0
 for _ in range(100):
  loc,n,idx,dist=bvh.ray_cast(origin,direction,limit-total)
  if loc is None:break
  out.append({'point_m':list(loc),'normal':list(n),'face':idx,'distance_m':total+dist})
  origin=loc+direction*1e-7;total+=dist+1e-7
  if total>=limit:break
 return out

def bbox(vs):return ([min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)])
def strict_intersection(a,b):
 # Test segment against the other triangle, excluding contact at triangle
 # vertices/edges and coplanar faces (the latter have their own area test).
 pts=[]
 for t,u in [(a,b),(b,a)]:
  v0,v1,v2=u;e1=v1-v0;e2=v2-v0
  for p,q in zip(t,t[1:]+t[:1]):
   delta=q-p;h=delta.cross(e2);det=e1.dot(h)
   if abs(det)<1e-14:continue
   inv=1/det;s=p-v0;uu=s.dot(h)*inv
   if uu<1e-6 or uu>1-1e-6:continue
   z=s.cross(e1);vv=delta.dot(z)*inv
   if vv<1e-6 or uu+vv>1-1e-6:continue
   frac=e2.dot(z)*inv
   if 1e-6<frac<1-1e-6:pts.append(p+delta*frac)
 if not pts:return None
 return list(sum(pts,Vector())/len(pts))

for key,row in REPORT['parts'].items():
 o=S.objects.get(row['object']);assert o and o.type=='MESH',row
 me=o.data;me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me)
 adj=defaultdict(set)
 for e in me.edges:
  a,b=e.vertices;adj[a].add(b);adj[b].add(a)
 comp={};shellids=[]
 for v in me.vertices:
  if v.index in comp:continue
  si=len(shellids);todo=[v.index];ids=[]
  while todo:
   j=todo.pop()
   if j in comp:continue
   comp[j]=si;ids.append(j);todo.extend(k for k in adj[j] if k not in comp)
  shellids.append(set(ids))
 product=row['product'];translation=Vector(REPORT['products'][product]['position_m'])
 coords=[o.matrix_world@v.co-translation for v in me.vertices]
 shells=[]
 for si,ids in enumerate(shellids):
  es=[e for e in me.edges if e.vertices[0] in ids];ps=[p for p in me.polygons if p.vertices[0] in ids]
  ts=[t for t in me.loop_triangles if t.vertices[0] in ids]
  volume=sum(coords[t.vertices[0]].dot(coords[t.vertices[1]].cross(coords[t.vertices[2]]))/6 for t in ts)
  vs=[coords[j] for j in ids];low,high=bbox(vs)
  sr={'index':si,'vertices':len(ids),'faces':len(ps),'triangles':len(ts),
      'signed_volume_m3':volume,'euler':len(ids)-len(es)+len(ps),'bounds_product_m':[low,high],
      'materials':sorted({me.materials[p.material_index].name for p in ps})}
  shells.append(sr)
  tv=[[coords[j] for j in t.vertices] for t in ts]
  flat=[p for t in tv for p in t]
  sh={'part':key,'part_type':row['part'],'shell':si,'triangles':tv,'indices':[(t.polygon_index,t.index) for t in ts],
      'bbox':(low,high),'bvh':BVHTree.FromPolygons(flat,[(3*i,3*i+1,3*i+2) for i in range(len(tv))],all_triangles=True),'summary':sr}
  SHELLS[product].append(sh)
 low,high=bbox(coords)
 RESULT['parts'][key]={'object':o.name,'product':product,'part':row['part'],'parent':o.parent.name if o.parent else None,
  'location_m':list(o.location),'report_pivot_m':row['pivot_m'],'bounds_product_m':[low,high],
  'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
  'boundary_edges':sum(e.is_boundary for e in bm.edges),'loose_edges':sum(e.is_wire for e in bm.edges),
  'zero_area_faces':sum(p.area<1e-12 for p in me.polygons),'shells':shells,
  'uv_layer':me.uv_layers.active.name if me.uv_layers.active else None,'material_slots':[m.name for m in me.materials]}
 PART_BVHS[key]=BVHTree.FromPolygons(coords,[list(t.vertices) for t in me.loop_triangles],all_triangles=True)
 for t in me.loop_triangles:
  pts=[coords[j] for j in t.vertices];n=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized();axis=max(range(3),key=lambda j:abs(n[j]));other=[j for j in range(3) if j!=axis]
  poly=[tuple(p[j] for j in other) for p in pts]
  TRIS.append({'product':product,'part':key,'shell':comp[t.vertices[0]],'polygon':t.polygon_index,'triangle':t.index,
   'normal':list(n),'plane':n.dot(pts[0]),'axis':axis,'poly':poly,
   'min':[min(p[j] for p in poly) for j in range(2)],'max':[max(p[j] for p in poly) for j in range(2)]})
 bm.free()

# Same-facing positive-area coplanar overlaps, product-local only.
groups=defaultdict(list)
for t in TRIS:groups[(t['product'],)+tuple(round(c,4) for c in t['normal'])].append(t)
for bucket in groups.values():
 bucket.sort(key=lambda a:a['plane'])
 for i,a in enumerate(bucket):
  for b in bucket[i+1:]:
   if b['plane']-a['plane']>EPS:break
   if a['part']==b['part'] and a['shell']==b['shell']:continue
   if sum(x*y for x,y in zip(a['normal'],b['normal']))<.999999:continue
   if any(min(a['max'][j],b['max'][j])-max(a['min'][j],b['min'][j])<=EPS for j in range(2)):continue
   ar=polyarea(clip(a['poly'],b['poly']))/max(abs(a['normal'][a['axis']]),1e-12)
   if ar<1e-10:continue
   RESULT['same_facing_coplanar_overlaps'].append({'product':a['product'],
    'a':{k:a[k] for k in ('part','shell','polygon','triangle')},'b':{k:b[k] for k in ('part','shell','polygon','triangle')},
    'normal':a['normal'],'plane_m':a['plane'],'overlap_area_m2':ar})

# Strict noncoplanar component intersections, including disconnected shells
# joined into one leaf mesh. Embedded seal/wrapper/head junctions are reported
# without claiming that all are visible defects.
for product,shells in SHELLS.items():
 for a,b in itertools.combinations(shells,2):
  if any(min(a['bbox'][1][j],b['bbox'][1][j])-max(a['bbox'][0][j],b['bbox'][0][j])<=EPS for j in range(3)):continue
  pairs=a['bvh'].overlap(b['bvh']);points=[]
  for ia,ib in pairs:
   p=strict_intersection(a['triangles'][ia],b['triangles'][ib])
   if p is not None:points.append(p)
  if not points:continue
  low,high=bbox([Vector(v) for v in points])
  category='unclassified'
  if REPORT['products'][product]['family'] in ('IcePop','ChocoBar','Chips','CandyBag','Bakery','Spicy','Nuts'):category='embedded heat seal into wrapper'
  elif product=='CandyJar_Fruit':category='wrapper tail inserted into same candy body'
  elif product=='CandyJar_Mint':
   if 'M_Goods_PaperInside' in a['summary']['materials'] or 'M_Goods_PaperInside' in b['summary']['materials']:category='lollipop stick inserted into head'
   else:category='unintended neighboring lollipop head intersection'
  elif REPORT['products'][product]['family']=='Biscuits':
   category='unintended tray corner intersection with rounded sleeve interior' if high[2]-low[2]>EPS else 'opposite-facing seated floor contact within numerical precision'
  RESULT['strict_surface_crossings'].append({'product':product,'classification':category,'a':{'part':a['part'],'shell':a['shell'],'materials':a['summary']['materials']},
    'b':{'part':b['part'],'shell':b['shell'],'materials':b['summary']['materials']},'crossing_triangle_pairs':len(points),
    'intersection_bounds_product_m':[low,high],'sample_points_product_m':points[:4]})

def nearest_distances(a,b):
 vals=[]
 for x,y in [(a,b),(b,a)]:
  ob=S.objects[REPORT['parts'][x]['object']];tr=Vector(REPORT['products'][REPORT['parts'][x]['product']]['position_m'])
  for v in ob.data.vertices:
   p=ob.matrix_world@v.co-tr;loc,n,idx,dist=PART_BVHS[y].find_nearest(p)
   if loc is not None:vals.append((dist,list(p),list(loc)))
 vals.sort(key=lambda x:x[0]);return {'minimum_vertex_to_surface_m':vals[0][0],'bvh_surface_overlap_triangle_pairs':len(PART_BVHS[a].overlap(PART_BVHS[b])),
  'closest_vertex_product_m':vals[0][1],'closest_surface_product_m':vals[0][2]}

for product,pr in REPORT['products'].items():
 parts=pr['parts'];family=pr['family'];out={'family':family,'parts':parts}
 if len(parts)>1:out['component_nearest_clearances']=[{'a':a,'b':b,**nearest_distances(a,b)} for a,b in itertools.combinations(parts,2)]
 if family=='CupIce':
  dome=next(p for p in parts if REPORT['parts'][p]['part']=='Dome');bv=PART_BVHS[dome]
  body=next(p for p in parts if REPORT['parts'][p]['part']=='Body')
  dome_min_z=RESULT['parts'][dome]['bounds_product_m'][0][2]
  cream_top_z=RESULT['parts'][body]['bounds_product_m'][1][2]
  center=rayhits(bv,(0,0,0),(0,0,1),.2)
  samples=[]
  for r in [0,.01,.02,.028,.032]:
   hh=rayhits(bv,(r,0,0),(0,0,1),.2)
   samples.append({'radius_m':r,'hits':hh})
  out['dome_cavity']={'center_vertical_hits':center,'radial_vertical_samples':samples,
   'center_first_surface_z_m':center[0]['point_m'][2] if center else None,
   'no_flat_bottom_disc_at_rim':len(center)==2 and center[0]['point_m'][2]>dome_min_z+.02,
   'central_shell_thickness_m':center[-1]['point_m'][2]-center[0]['point_m'][2] if len(center)==2 else None,
   'rim_z_m':dome_min_z,'cream_top_z_m':cream_top_z,
   'cream_to_dome_center_clearance_m':center[0]['point_m'][2]-cream_top_z if center else None}
 if family=='CandyJar':
  lid=next(p for p in parts if REPORT['parts'][p]['part']=='Lid');jar=next(p for p in parts if REPORT['parts'][p]['part']=='Jar')
  hh=rayhits(PART_BVHS[lid],(0,0,.12),(0,0,1),.10)
  mouth=rayhits(PART_BVHS[jar],(0,0,.12),(0,0,1),.10)
  out['cap_cavity']={'center_vertical_hits':hh,'open_jar_center_from_neck_hits':mouth,
   'no_bottom_disc_at_cap_lower_rim':len(hh)==2 and hh[0]['point_m'][2]>.15,
   'center_shell_thickness_m':hh[-1]['point_m'][2]-hh[0]['point_m'][2] if len(hh)==2 else None,
   'jar_neck_center_is_open':len(mouth)==0}
 if family=='Biscuits':
  body=next(p for p in parts if REPORT['parts'][p]['part']=='Body');tray=next(p for p in parts if REPORT['parts'][p]['part']=='Tray')
  tr=RESULT['parts'][tray]['bounds_product_m'];bb=RESULT['parts'][body]['bounds_product_m']
  # Rays at the horizontal axis verify an actual open +X sleeve mouth.
  hh=rayhits(PART_BVHS[body],(.09,0,.03),(-1,0,0),.2)
  fl=rayhits(PART_BVHS[body],(0,0,.03),(0,0,-1),.1)
  tf=rayhits(PART_BVHS[tray],(0,0,.03),(0,0,-1),.1)
  out['tray_placement']={'tray_bounds_m':tr,'sleeve_bounds_m':bb,'open_mouth_axis_ray_hits':hh,
   'tray_within_outer_sleeve_bbox':all(tr[0][j]>=bb[0][j]-EPS and tr[1][j]<=bb[1][j]+EPS for j in range(3)),
   'sleeve_floor_from_inside':fl,'tray_floor_from_above':tf,
   'tray_bottom_to_sleeve_interior_floor_m':tr[0][2]-fl[0]['point_m'][2] if fl else None,
   'central_tray_floor_seated_within_tolerance':abs(tr[0][2]-fl[0]['point_m'][2])<=EPS if fl else False}
 out['crossing_shell_pair_count']=sum(a['product']==product for a in RESULT['strict_surface_crossings'])
 out['same_facing_coplanar_pair_count']=sum(a['product']==product for a in RESULT['same_facing_coplanar_overlaps'])
 RESULT['products'][product]=out

for crossing in RESULT['strict_surface_crossings']:
 if crossing['classification']=='unintended neighboring lollipop head intersection':
  RESULT['findings'].append({'severity':'fix','product':crossing['product'],
   'issue':'Two distinct lollipop heads intersect inside the transparent jar',
   'shells':[crossing['a']['shell'],crossing['b']['shell']],
   'lollipop_indices':[crossing['a']['shell']//2,crossing['b']['shell']//2],
   'intersection_bounds_product_m':crossing['intersection_bounds_product_m']})
 elif crossing['classification']=='unintended tray corner intersection with rounded sleeve interior':
  RESULT['findings'].append({'severity':'fix','product':crossing['product'],
   'issue':'Tray lower long edges intersect rounded sleeve interior floor/side transitions',
   'intersection_bounds_product_m':crossing['intersection_bounds_product_m'],
   'maximum_crossing_height_above_flat_floor_m':crossing['intersection_bounds_product_m'][1][2]-.0012})
for product,p in RESULT['products'].items():
 if p['family'] in ('CupIce','FamilyTub','CandyJar'):
  fitting=[v for v in p.get('component_nearest_clearances',[]) if not v['a'].endswith('Contents') and not v['b'].endswith('Contents')]
  for f in fitting:
   fit_tolerance=.0001 if p['family']=='CandyJar' else EPS
   if f['minimum_vertex_to_surface_m']>fit_tolerance and f['bvh_surface_overlap_triangle_pairs']==0:
    RESULT['findings'].append({'severity':'assembly fit review','product':product,
     'issue':'Removable lid has no surface contact with the body in authored closed position',
     'sampled_minimum_vertex_to_surface_m':f['minimum_vertex_to_surface_m'],
     'surface_overlap_triangle_pairs':f['bvh_surface_overlap_triangle_pairs']})
 if p['family']=='Biscuits' and p['tray_placement']['tray_bottom_to_sleeve_interior_floor_m']>EPS:
  RESULT['findings'].append({'severity':'assembly fit review','product':product,
   'issue':'Tray fits inside the sleeve without crossing, but floats above interior floor',
   'vertical_floor_gap_m':p['tray_placement']['tray_bottom_to_sleeve_interior_floor_m']})

RESULT['summary']={'exact_report_meshes':len(RESULT['parts']),'products':len(RESULT['products']),
 'triangles':sum(p['triangles'] for p in RESULT['parts'].values()),
 'all_manifold':all(p['nonmanifold_edges']==0 for p in RESULT['parts'].values()),
 'all_shell_signed_volumes_positive':all(s['signed_volume_m3']>0 for p in RESULT['parts'].values() for s in p['shells']),
 'all_faces_nonzero_area':all(p['zero_area_faces']==0 for p in RESULT['parts'].values()),
 'coplanar_overlap_triangle_pairs':len(RESULT['same_facing_coplanar_overlaps']),
 'coplanar_overlap_area_m2':sum(p['overlap_area_m2'] for p in RESULT['same_facing_coplanar_overlaps']),
 'strict_crossing_shell_pairs':len(RESULT['strict_surface_crossings']),
 'unintended_intersecting_shell_pairs':sum(p['classification'].startswith('unintended') for p in RESULT['strict_surface_crossings']),
 'dome_cavities_open_below':all(p['dome_cavity']['no_flat_bottom_disc_at_rim'] for p in RESULT['products'].values() if 'dome_cavity' in p),
 'jar_caps_hollow':all(p['cap_cavity']['no_bottom_disc_at_cap_lower_rim'] for p in RESULT['products'].values() if 'cap_cavity' in p)}
RESULT['source_sha256_after']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert RESULT['source_sha256_after']==SHA,'Source unexpectedly changed during read-only audit'
(ROOT/'QA'/'goods_geometry_audit.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2),encoding='utf-8')
print('GOODS_GEOMETRY_AUDIT',json.dumps(RESULT['summary']),flush=True)
print('CROSSINGS_BY_PRODUCT',json.dumps({k:p['crossing_shell_pair_count'] for k,p in RESULT['products'].items() if p['crossing_shell_pair_count']}),flush=True)
print('COPLANAR_BY_PRODUCT',json.dumps({k:p['same_facing_coplanar_pair_count'] for k,p in RESULT['products'].items() if p['same_facing_coplanar_pair_count']}),flush=True)
print('PART_CLEARANCES',json.dumps({k:p.get('component_nearest_clearances') for k,p in RESULT['products'].items() if p.get('component_nearest_clearances')}),flush=True)
