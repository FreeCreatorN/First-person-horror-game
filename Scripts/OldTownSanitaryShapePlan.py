"""Closed sanitary fixture shape replacements, centimetres, no UE dependency.

The saved Functional mesh is the input. Remove ONLY the four bounding-box
identified disconnected components; all other source render faces, sections,
actor transforms and external collision actors must be retained exactly.
Triangles use outward winding. ``smooth_groups`` parallels ``triangles``;
separate caps/rim bands from curved sides when constructing normal overlays.
"""
from __future__ import annotations
import math
from collections import Counter

SCHEMA = 'OldTownSanitaryShapesV1'
TOILET_SOURCE = '/Game/CodexGenerated/OldTown/Meshes/SanitaryFixtures_20261011/SM_OTS_Arch_Toilet_Functional'
BASIN_SOURCE = '/Game/CodexGenerated/OldTown/Meshes/SanitaryFixtures_20261011/SM_OTS_Arch_Washbasin_Functional'
TOILET_ENVELOPE = [[-32.01, -17.7, 0.], [33., 17.7, 78.]]
BASIN_ENVELOPE = [[-22.5, -30., 0.], [22.5, 30., 96.05]]
RADIAL_SIDES = 64
EPS = .0002

def source_removal_specs():
    """Identify complete position-welded components, never triangle centroids."""
    return [
        dict(fixture='Toilet', name='Bowl', triangles=92, material_id=0,
             bounds_cm=[[-30.76,-17.,25.],[12.76,17.,40.7]]),
        dict(fixture='Toilet', name='RearCeramicShoulder', triangles=144, material_id=0,
             bounds_cm=[[-3.,-12.,29.5],[29.,12.,46.]]),
        dict(fixture='Washbasin', name='FaucetSpout', triangles=144, material_id=0,
             bounds_cm=[[4.,-1.05,91.35],[16.,1.05,93.45]]),
        dict(fixture='Washbasin', name='FaucetDownspout', triangles=144, material_id=0,
             bounds_cm=[[3.05,-.95,89.3],[4.95,.95,92.5]]),
    ]

def _ring(cx, cy, z, rx, ry, n=RADIAL_SIDES):
    return [[cx+rx*math.cos(2*math.pi*i/n),cy+ry*math.sin(2*math.pi*i/n),z]
            for i in range(n)]

def _loft(name, fixture, rings, side_groups, first_cap_group, last_cap_group):
    n=len(rings[0]); vertices=[p for r in rings for p in r]
    triangles=[]; groups=[]
    for k,sg in enumerate(side_groups):
        a,b=k*n,(k+1)*n
        for i in range(n):
            j=(i+1)%n
            triangles += [[a+i,a+j,b+j],[a+i,b+j,b+i]]
            groups += [sg,sg]
    for k,sg,reverse in ((0,first_cap_group,True),(len(rings)-1,last_cap_group,False)):
        center=len(vertices)
        vertices.append([sum(p[a] for p in rings[k])/n for a in range(3)])
        for i in range(n):
            j=(i+1)%n; base=k*n
            triangles.append([center,base+j,base+i] if reverse else [center,base+i,base+j])
            groups.append(sg)
    return dict(name=name,fixture=fixture,material_id=0,vertices=vertices,
                triangles=triangles,smooth_groups=groups,closed=True,units='cm',
                collision='NoCollision')

# x center, z, outer x radius, outer y radius. Multiple rings give the foot-to-
# lip contour a rounded profile while retaining the original exact envelope.
BOWL_OUTER = [(-9.,25.,17.2,12.6),(-9.,26.,18.0,13.2),
              (-9.,28.,19.4,14.3),(-9.,31.,20.5,15.4),
              (-9.,34.,21.3,16.3),(-9.,37.,21.68,16.86),
              (-9.,39.,21.76,17.),(-9.,40.7,21.76,17.)]
# Inner cup closes 8.5 cm above the outside bottom. Its floor sits above both
# old pedestal top (32 cm) and rear foot (31 cm), so they cannot fill the cup.
BOWL_INNER = [(-9.,40.7,18.6,14.3),(-9.,39.,18.0,13.8),
              (-9.,38.,17.5,13.2),(-9.,36.3,15.,11.3),
              (-9.,35.,11.6,8.8),(-9.,34.,6.6,5.),
              (-9.,33.5,4.2,3.)]

def bowl_piece():
    profiles=BOWL_OUTER+BOWL_INNER
    rings=[_ring(cx,0.,z,rx,ry) for cx,z,rx,ry in profiles]
    side_groups=[1]*(len(BOWL_OUTER)-1)+[2]+[3]*(len(BOWL_INNER)-1)
    result=_loft('HollowCeramicBowl','Toilet',rings,side_groups,4,5)
    result['profiles_cm']=dict(outer=BOWL_OUTER,inner=BOWL_INNER)
    result['labels']=dict(outer=1,top_rim=2,inner_cup=3,outer_bottom=4,inner_floor=5)
    return result

SHOULDER = [(13.,29.5,16.,12.),(13.,32.,16.,12.),
            (19.5,34.,9.5,12.),(19.8125,36.5,9.1875,12.),
            (20.125,39.,8.875,12.),(20.5,42.,8.5,12.),(21.,46.,8.,12.)]

def shoulder_piece():
    result=_loft('TaperedRearCeramicShoulder','Toilet',
                 [_ring(cx,0.,z,rx,ry) for cx,z,rx,ry in SHOULDER],
                 [6]*(len(SHOULDER)-1),7,8)
    result['profiles_cm']=SHOULDER
    result['labels']=dict(curved_support=6,bottom=7,top=8)
    return result

def faucet_piece():
    """A single closed straight/bend/drop tube; preserve the old mouth cap.

    The 2.8 cm bend radius exceeds 1.05 cm tube radius. Its upper tangent is
    z92.4; downward tangent is x4.0. It ends at z89.4, embedded 0.575 cm into
    the retained aerator, and begins x15.9 inside the retained vertical sleeve.
    """
    path=[([x,0.,92.4],[-1.,0.,0.]) for x in (15.9,13.,10.,6.8)]
    for i in range(1,17):
        a=(math.pi/2)*i/16
        path.append(([6.8-2.8*math.sin(a),0.,89.6+2.8*math.cos(a)],
                     [-math.cos(a),0.,-math.sin(a)]))
    path.append(([4.,0.,89.4],[0.,0.,-1.]))
    rings=[]
    for center,tangent in path:
        # u cross v = tangent, v is the shared lateral Y axis.
        u=[tangent[2],0.,-tangent[0]]; v=[0.,1.,0.]
        rings.append([[center[a]+1.05*(u[a]*math.cos(2*math.pi*i/RADIAL_SIDES)+
                                  v[a]*math.sin(2*math.pi*i/RADIAL_SIDES))
                       for a in range(3)] for i in range(RADIAL_SIDES)])
    result=_loft('ContinuousRoundedFaucetSpout','Washbasin',rings,
                 [9]*(len(rings)-1),10,11)
    result['centerline_cm']=[p for p,t in path]
    result['bend_radius_cm']=2.8; result['tube_radius_cm']=1.05
    result['labels']=dict(curved_tube=9,inlet_cap=10,outlet_cap=11)
    return result

def build_pieces():
    return [bowl_piece(),shoulder_piece(),faucet_piece()]

CONNECTION_WITNESSES = [
    dict(name='SeatLeftIntoNewBowl',point=[-9.,16.5,40.5],parts=['Seat','HollowCeramicBowl']),
    dict(name='SeatRightIntoNewBowl',point=[-9.,-16.5,40.5],parts=['Seat','HollowCeramicBowl']),
    dict(name='SeatFrontIntoNewBowl',point=[-30.,0.,40.5],parts=['Seat','HollowCeramicBowl']),
    dict(name='FrontPedestalIntoNewBowl',point=[-6.,0.,31.],parts=['Pedestal','HollowCeramicBowl']),
    dict(name='RearFootIntoNewBowl',point=[4.,0.,28.],parts=['RearCeramicPedestal','HollowCeramicBowl']),
    dict(name='RearFootIntoTaperedShoulder',point=[13.,0.,30.25],parts=['RearCeramicPedestal','TaperedRearCeramicShoulder']),
    dict(name='NewBowlIntoTaperedShoulder',point=[12.2,0.,40.5],parts=['HollowCeramicBowl','TaperedRearCeramicShoulder']),
    dict(name='TaperedShoulderIntoCistern',point=[20.,0.,45.5],parts=['Cistern','TaperedRearCeramicShoulder']),
    dict(name='SleeveIntoRoundedSpout',point=[15.5,0.,92.4],parts=['FaucetSleeve','ContinuousRoundedFaucetSpout']),
    dict(name='RoundedSpoutIntoAerator',point=[4.,0.,89.6],parts=['FaucetAerator','ContinuousRoundedFaucetSpout']),
]
CAVITY_EMPTY_WITNESSES = [[-9.,0.,34.],[-9.,0.,35.],[-9.,0.,38.],[-9.,0.,40.5],
                          [-17.,0.,38.],[-1.,0.,38.],[-9.,7.,38.],[-9.,-7.,38.]]

def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]

def inside(point, vertices, triangles):
    """Winding/solid-angle test against the actual closed surface."""
    total=0.
    for t in triangles:
        a,b,c=[[vertices[j][k]-point[k] for k in range(3)] for j in t]
        la,lb,lc=[math.sqrt(_dot(q,q)) for q in (a,b,c)]
        if min(la,lb,lc)<1.e-9:return True
        total+=2*math.atan2(_dot(a,_cross(b,c)),la*lb*lc+_dot(a,b)*lc+_dot(b,c)*la+_dot(c,a)*lb)
    return abs(total)>2*math.pi

def bounds(vertices):
    return [[min(p[a] for p in vertices) for a in range(3)],
            [max(p[a] for p in vertices) for a in range(3)]]

def audit_closed_piece(piece):
    vv,tt=piece['vertices'],piece['triangles']; edges=Counter(); directions=Counter()
    volume=0.; degenerate=[]
    for ti,t in enumerate(tt):
        p=[vv[i] for i in t]
        area=_cross([p[1][a]-p[0][a] for a in range(3)],[p[2][a]-p[0][a] for a in range(3)])
        if _dot(area,area)<1.e-14:degenerate.append(ti)
        volume+=_dot(p[0],_cross(p[1],p[2]))/6
        for i in range(3):
            a,b=t[i],t[(i+1)%3];edges[tuple(sorted((a,b)))]+=1;directions[a,b]+=1
    closed=all(n==2 for n in edges.values())
    winding=all(directions[a,b]==directions[b,a] for a,b in edges)
    used={i for t in tt for i in t}; euler=len(used)-len(edges)+len(tt)
    return dict(name=piece['name'],passed=closed and winding and euler==2 and volume>0 and not degenerate,
                closed=closed,winding=winding,euler=euler,signed_volume_cm3=volume,
                degenerate_triangles=degenerate,bounds_cm=bounds(vv),
                vertex_count=len(vv),triangle_count=len(tt))

def audit_recipe():
    pieces=build_pieces(); rows=[audit_closed_piece(p) for p in pieces]
    by_name={p['name']:p for p in pieces}; cavity=[]
    for point in CAVITY_EMPTY_WITNESSES:
        hits={name:inside(point,p['vertices'],p['triangles']) for name,p in by_name.items() if p['fixture']=='Toilet'}
        cavity.append(dict(point=point,passed=not any(hits.values()),inside=hits))
    joins=[]
    for w in CONNECTION_WITNESSES:
        existing=[n for n in w['parts'] if n in by_name]
        tests={n:inside(w['point'],by_name[n]['vertices'],by_name[n]['triangles']) for n in existing}
        joins.append(dict(name=w['name'],passed=all(tests.values()),point=w['point'],new_part_inside=tests))
    return dict(schema=SCHEMA,passed=all(r['passed'] for r in rows+cavity+joins),
                pieces=rows,cavity_checks=cavity,connection_checks=joins,
                source_removals=source_removal_specs(),
                notes=['Actual saved audit must also prove retained source faces and old-part solid intersections.',
                       'Preserve all old actor transforms, old material slots and independent collision actors.'])

if __name__=='__main__':
    import json
    print(json.dumps(audit_recipe(),indent=2))
