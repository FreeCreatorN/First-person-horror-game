"""Rounded old-hotel cistern and lid, centimetres, no Unreal dependency.

Input is the saved Shaped toilet from SanitaryShapes_20261011. Replace fourteen
complete position-welded ceramic islands (215 faces). Keep every other source
face, including the 108-face metal flush lever, hollow bowl, seat and feet.
The two new pieces are closed, mathematically outward surfaces. The producer
must reverse their triangle indices for UE clockwise RenderData and prove that
the final stored normals agree with each pure outward cross product.
"""
from __future__ import annotations
import math
from collections import Counter

SCHEMA = 'OldTownSanitaryFinishV1'
TOILET_SOURCE = '/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011/SM_OTS_Arch_Toilet_Shaped'
SOURCE_MAP_SHA256 = '96a927f42d52477d371665aad35ac8fdd85406eb42a91940cf047213cde8c44d'
TANK_ENVELOPE = [[13., -17.5, 45.], [33., 17.5, 78.]]
BODY_ENVELOPE = [[13., -17.5, 45.], [33., 17.5, 75.7]]
LID_ENVELOPE = [[13., -17.5, 75.4], [33., 17.5, 78.]]
TOILET_ENVELOPE = [[-32.01, -17.7, 0.], [33., 17.7, 78.]]
CORNER_SEGMENTS = 16
EDGE_SEGMENTS = 5
SOURCE_GROUP_BOUNDS_EPS_CM = .0002
BODY_CORNER_RADIUS_CM = 1.8
BODY_EDGE_RADIUS_CM = .6
LID_CORNER_RADIUS_CM = 2.2
LID_EDGE_RADIUS_CM = .25
LID_EMBED_CM = .3
COPLANAR_PLANE_TOLERANCE_CM = .03


def source_removal_specs():
    """Exact whole-island matches; a bounding-region face filter is forbidden.

    The retained rear support's upper cap is inside the aggregate tank bounds.
    The thirteen source lid patches were separated in the earlier surface
    repair and must all be removed exactly once alongside the main 190 faces.
    """
    rows = [
        ('CisternAndLidMain',190,[[13.,-17.5,45.],[33.,17.5,78.]]),
        ('CisternLidPatch01',2,[[13.6,-17.3113,77.7928],[32.4,-16.887,77.9686]]),
        ('CisternLidPatch02',2,[[13.6,16.887,77.7928],[32.4,17.3113,77.9686]]),
        ('CisternLidPatch03',2,[[13.1887,-16.9,77.7928],[13.613,16.9,77.9686]]),
        ('CisternLidPatch04',2,[[13.6,-17.4686,77.387],[32.4,-17.2929,77.8113]]),
        ('CisternLidPatch05',2,[[13.6,17.2928,77.387],[32.4,17.4686,77.8113]]),
        ('CisternLidPatch06',1,[[13.6,-16.9,77.966],[32.4,16.9,77.966]]),
        ('CisternLidPatch07',2,[[32.387,-16.9,77.7928],[32.8113,16.9,77.9686]]),
        ('CisternLidPatch08',2,[[13.034,-16.9,76.],[13.034,16.9,77.4]]),
        ('CisternLidPatch09',2,[[13.6,17.466,76.],[32.4,17.466,77.4]]),
        ('CisternLidPatch10',2,[[13.6,-17.466,76.],[32.4,-17.466,77.4]]),
        ('CisternLidPatch11',2,[[32.966,-16.9,76.],[32.966,16.9,77.4]]),
        ('CisternLidPatch12',2,[[32.7929,-16.9,77.387],[32.9686,16.9,77.8113]]),
        ('CisternLidPatch13',2,[[13.0314,-16.9,77.387],[13.2071,16.9,77.8113]]),
    ]
    return [dict(fixture='Toilet',name=name,triangles=count,material_id=0,bounds_cm=box)
            for name,count,box in rows]


def _rounded_rectangle_ring(z, inset, corner_radius):
    """Parallel inward outline at a bevel height, CCW as seen from above."""
    cx, cy, hx, hy = 23., 0., 10.-inset, 17.5-inset
    radius = corner_radius-inset
    if not 0 < radius < min(hx,hy):
        raise ValueError('Invalid rounded rectangle radius/inset')
    centers = [(cx+hx-radius,cy+hy-radius,0.),
               (cx-hx+radius,cy+hy-radius,math.pi/2),
               (cx-hx+radius,cy-hy+radius,math.pi),
               (cx+hx-radius,cy-hy+radius,3*math.pi/2)]
    ring = []
    for x,y,start in centers:
        for i in range(CORNER_SEGMENTS+1):
            angle = start+(math.pi/2)*i/CORNER_SEGMENTS
            ring.append([x+radius*math.cos(angle),y+radius*math.sin(angle),z])
    return ring


def _profiles(zmin,zmax,edge_radius):
    """Quarter-circle vertical bevels; straight-wall endpoints are explicit."""
    rows=[]
    for i in range(EDGE_SEGMENTS+1):
        angle=(math.pi/2)*i/EDGE_SEGMENTS
        rows.append((zmin+edge_radius*(1-math.cos(angle)),
                     edge_radius*(1-math.sin(angle))))
    rows.append((zmax-edge_radius,0.))
    for i in range(1,EDGE_SEGMENTS+1):
        angle=(math.pi/2)*i/EDGE_SEGMENTS
        rows.append((zmax-edge_radius+edge_radius*math.sin(angle),
                     edge_radius*(1-math.cos(angle))))
    return rows


def _piece(name,zmin,zmax,corner_radius,edge_radius,side_group,bottom_group,top_group):
    profiles=_profiles(zmin,zmax,edge_radius)
    rings=[_rounded_rectangle_ring(z,inset,corner_radius) for z,inset in profiles]
    n=len(rings[0]); vertices=[p for ring in rings for p in ring]
    triangles=[]; smooth=[]
    for k in range(len(rings)-1):
        a,b=k*n,(k+1)*n
        for i in range(n):
            j=(i+1)%n
            triangles.extend([[a+i,a+j,b+j],[a+i,b+j,b+i]])
            smooth.extend([side_group,side_group])
    for k,group,reverse in ((0,bottom_group,True),(len(rings)-1,top_group,False)):
        center=len(vertices)
        vertices.append([23.,0.,profiles[k][0]])
        for i in range(n):
            j=(i+1)%n; base=k*n
            triangles.append([center,base+j,base+i] if reverse else [center,base+i,base+j])
            smooth.append(group)
    return dict(name=name,fixture='Toilet',material_id=0,vertices=vertices,
                triangles=triangles,smooth_groups=smooth,closed=True,units='cm',
                collision='NoCollision',expected_euler=2,
                bounds_cm=[[13.,-17.5,zmin],[33.,17.5,zmax]],
                corner_radius_cm=corner_radius,edge_radius_cm=edge_radius,
                corner_segments=CORNER_SEGMENTS,edge_segments=EDGE_SEGMENTS,
                profile_z_and_inset_cm=[list(p) for p in profiles],
                smoothing_labels=dict(curved_sides_and_bevel=side_group,bottom=bottom_group,top=top_group))


def build_pieces():
    return [_piece('RoundedCisternBody',45.,75.7,BODY_CORNER_RADIUS_CM,BODY_EDGE_RADIUS_CM,1,2,3),
            _piece('RoundedCisternLid',75.4,78.,LID_CORNER_RADIUS_CM,LID_EDGE_RADIUS_CM,4,5,6)]


CONNECTION_WITNESSES = [
    dict(name='RearShoulderIntoRoundedCistern',point=[20.,0.,45.5],
         parts=['TaperedRearCeramicShoulder','RoundedCisternBody']),
    dict(name='ExistingFlushLeverIntoRoundedCistern',point=[32.5,0.,68.],
         parts=['FlushLever','RoundedCisternBody']),
    dict(name='RoundedBodyIntoLidCenter',point=[23.,0.,75.55],
         parts=['RoundedCisternBody','RoundedCisternLid']),
    dict(name='RoundedBodyIntoLidLeft',point=[15.,-14.,75.55],
         parts=['RoundedCisternBody','RoundedCisternLid']),
    dict(name='RoundedBodyIntoLidRight',point=[15.,14.,75.55],
         parts=['RoundedCisternBody','RoundedCisternLid']),
]

# The bevel creates a recessed seam rather than a through gap. The same-facing
# straight side-wall planes stop at 75.1 and start again at 75.65, so they have
# no overlapping area. The contacting cap planes at 75.7/75.4 face oppositely.
SEAM_GEOMETRY = dict(body_straight_wall_top_z_cm=75.1,lid_straight_wall_bottom_z_cm=75.65,
                     same_facing_outer_flat_planes_vertical_clearance_cm=.55,
                     central_solid_embed_cm=.3,body_top_cap_z_cm=75.7,lid_bottom_cap_z_cm=75.4,
                     lowest_new_geometry_z_cm=45.,old_cup_top_z_cm=40.7,
                     new_geometry_to_old_cup_vertical_gap_cm=4.3,
                     full_map_same_facing_plane_tolerance_cm=.03)


def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def inside(point,vertices,triangles):
    total=0.
    for t in triangles:
        a,b,c=[[vertices[j][k]-point[k] for k in range(3)] for j in t]
        la,lb,lc=[math.sqrt(_dot(q,q)) for q in (a,b,c)]
        if min(la,lb,lc)<1.e-9:return True
        total+=2*math.atan2(_dot(a,_cross(b,c)),la*lb*lc+_dot(a,b)*lc+_dot(b,c)*la+_dot(c,a)*lb)
    return abs(total)>2*math.pi


def bounds(vertices):
    return [[min(v[a] for v in vertices) for a in range(3)],
            [max(v[a] for v in vertices) for a in range(3)]]


def audit_closed_piece(piece):
    vertices,triangles=piece['vertices'],piece['triangles']
    edges=Counter();directions=Counter();volume=0.;degen=[]
    for ti,t in enumerate(triangles):
        pp=[vertices[i] for i in t]
        area=_cross([pp[1][a]-pp[0][a] for a in range(3)],[pp[2][a]-pp[0][a] for a in range(3)])
        if _dot(area,area)<1.e-14:degen.append(ti)
        volume+=_dot(pp[0],_cross(pp[1],pp[2]))/6
        for i in range(3):
            a,b=t[i],t[(i+1)%3];edges[tuple(sorted((a,b)))]+=1;directions[a,b]+=1
    closed=all(n==2 for n in edges.values())
    winding=all(directions[a,b]==directions[b,a] for a,b in edges)
    euler=len({i for t in triangles for i in t})-len(edges)+len(triangles)
    actual=bounds(vertices)
    envelope=all(abs(a-b)<1.e-10 for aa,bb in zip(actual,piece['bounds_cm']) for a,b in zip(aa,bb))
    return dict(name=piece['name'],passed=closed and winding and euler==2 and volume>0 and not degen and envelope,
                closed=closed,winding=winding,euler=euler,signed_volume_cm3=volume,
                degenerate_triangles=degen,expected_bounds_preserved=envelope,
                bounds_cm=actual,vertex_count=len(vertices),triangle_count=len(triangles))


def audit_recipe():
    pieces=build_pieces();by_name={p['name']:p for p in pieces}
    topology=[audit_closed_piece(p) for p in pieces]
    joins=[]
    for witness in CONNECTION_WITNESSES:
        tests={n:inside(witness['point'],by_name[n]['vertices'],by_name[n]['triangles'])
               for n in witness['parts'] if n in by_name}
        joins.append(dict(name=witness['name'],passed=all(tests.values()),
                          point=witness['point'],new_part_inside=tests))
    removal=source_removal_specs()
    seam_pass=(SEAM_GEOMETRY['same_facing_outer_flat_planes_vertical_clearance_cm']
               >COPLANAR_PLANE_TOLERANCE_CM and
               SEAM_GEOMETRY['central_solid_embed_cm']>.01 and
               SEAM_GEOMETRY['new_geometry_to_old_cup_vertical_gap_cm']>0.)
    return dict(schema=SCHEMA,passed=all(p['passed'] for p in topology+joins) and seam_pass
                and len(removal)==14 and sum(r['triangles'] for r in removal)==215,
                pieces=topology,connection_checks=joins,seam_geometry=SEAM_GEOMETRY,
                source_islands_removed=14,source_triangles_removed=215,
                retained_source_triangles=3672,source_triangle_count=3887,
                mathematical_winding='outward_counter_clockwise',
                UE_render_indices_must_be_reversed=True,
                notes=['Saved audit must match all new faces to this recipe and retain all 3672 other source faces.',
                       'Actual old rear-shoulder and flush-lever solid tests are additionally required.',
                       'All new material IDs are zero. Source material slots and all external collision actors remain unchanged.',
                       'Fresh full-map coplanar scanning must independently verify the recessed seam and retained flush lever.'])


if __name__=='__main__':
    import json
    print(json.dumps(audit_recipe(),indent=2))
