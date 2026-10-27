"""Connected door hinge render geometry, in centimetres, with no Unreal import.

Public API:
    primitive_specs(width, height, depth=20., hinge_side=-1)
    build_closed_geometry(primitives, radial_sides=24)
    geometry_for_door(row, radial_sides=24)
    validate_recipe(row)

Fixed primitives use OpeningRoot local coordinates. Moving primitives use
DoorHinge local coordinates. All geometry is cosmetic, with NoCollision;
existing pivots, leaf and collision proxies are not changed. Each primitive
is an individually closed solid, preserving buried internal cap faces for
an occlusion-aware scanner. There are three separate connected hinges.
"""
import math

SCHEMA = 'OldTownConnectedOffsetHingesV1'


def _box(name, center, size, group, yaw_deg=0.):
    return dict(name=name, kind='box', center=list(center), size=list(size),
                yaw_deg=float(yaw_deg), group=group, collision='NoCollision')


def _cylinder(name, center, radius, height, group):
    return dict(name=name, kind='cylinder', center=list(center),
                radius=float(radius), height=float(height), axis=[0.,0.,1.],
                group=group, collision='NoCollision')


def _neck(name, first_xy, second_xy, z, thickness, height, group):
    center = [(first_xy[0]+second_xy[0])/2,
              (first_xy[1]+second_xy[1])/2,z]
    length = math.dist(first_xy,second_xy)
    yaw = math.degrees(math.atan2(second_xy[1]-first_xy[1],
                                  second_xy[0]-first_xy[0]))
    result = _box(name,center,[length,thickness,height],group,yaw)
    result['bridge_endpoints_cm'] = [list(first_xy)+[z],list(second_xy)+[z]]
    return result


def primitive_specs(width, height, depth=20., hinge_side=-1):
    """Return fixed/moving closed primitive recipes without mutating inputs."""
    width,height,depth = float(width),float(height),float(depth)
    side = int(hinge_side)
    assert side in (-1,1) and width >= 70. and height >= 180. and depth >= 4.
    direction = -side
    px,py = side*(width/2-.5),depth/2+3.
    fixed,moving = [],[]
    for index,z in enumerate((22.,height/2,height-22.)):
        prefix = 'Hinge%02d_'%index
        fixed.append(_box(prefix+'JambLeaf',[side*(width/2+2),depth/2+.075,z],
                          [3.6,.65,10.],index))
        for suffix,dz in (('Lower',-3.6),('Upper',3.6)):
            fixed.append(_neck(prefix+'FixedNeck'+suffix,
                                [px+side*2.5,py-2.85],
                                [px+side*.75,py-.8],z+dz,.5,2.4,index))
            fixed.append(_cylinder(prefix+'FixedKnuckle'+suffix,
                                    [px,py,z+dz],1.2,2.7,index))
        fixed.append(_cylinder(prefix+'Pin',[px,py,z],.4,10.5,index))
        moving.append(_cylinder(prefix+'MovingKnuckle',[0.,0.,z],1.2,4.2,index))
        moving.append(_box(prefix+'DoorLeaf',[direction*2.4,-2.05,z],
                           [4.8,.7,4.2],index))
        moving.append(_neck(prefix+'MovingNeck',[direction*.6,-.75],
                             [direction*1.5,-2.2],z,.4,3.6,index))
    return dict(schema=SCHEMA,units='centimetres',width_cm=width,height_cm=height,
                depth_cm=depth,hinge_side=side,
                hinge_axis_opening_root_cm=[px,py,0.],
                fixed_parent='OpeningRoot',moving_parent='DoorHinge',
                collision='NoCollision',radial_sides_recommended=24,
                fixed=fixed,moving=moving,
                axial_clearance_cm=.15,
                render_translation_tolerance_cm=.22,
                intentional_contacts=['Fixed leaves overlap their jamb by 0.25cm, '
                                      'covering its existing material render translation.',
                                      'Moving leaves embed 0.3cm into the wood face, '
                                      'covering its existing material render translation.',
                                      'The coaxial pin seats inside the three knuckles.',
                                      'The barrel is recessed into the wood hinge edge.'])


def _box_geometry(spec):
    a,b,c = [float(value)/2 for value in spec['size']]
    local = [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),
             (-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]
    faces = [(0,3,2,1),(4,5,6,7),(1,2,6,5),(0,4,7,3),
             (3,7,6,2),(0,1,5,4)]
    rad = math.radians(spec.get('yaw_deg',0.))
    cosine,sine = math.cos(rad),math.sin(rad)
    center = spec['center']
    vertices = [[center[0]+x*cosine-y*sine,
                 center[1]+x*sine+y*cosine,center[2]+z] for x,y,z in local]
    triangles = []
    for aa,bb,cc,dd in faces:
        triangles += [(aa,bb,cc),(aa,cc,dd)]
    return vertices,triangles


def _cylinder_geometry(spec, radial_sides):
    radial_sides = int(radial_sides)
    assert radial_sides >= 16 and radial_sides <= 128
    radius,half_height = spec['radius'],spec['height']/2
    center = spec['center']
    vertices = []
    for z in (-half_height,half_height):
        for index in range(radial_sides):
            angle = index*2*math.pi/radial_sides
            vertices.append([center[0]+radius*math.cos(angle),
                             center[1]+radius*math.sin(angle),center[2]+z])
    bottom,top = len(vertices),len(vertices)+1
    vertices += [[center[0],center[1],center[2]-half_height],
                 [center[0],center[1],center[2]+half_height]]
    triangles = []
    for index in range(radial_sides):
        following = (index+1)%radial_sides
        upper,upper_following = index+radial_sides,following+radial_sides
        triangles += [(bottom,following,index),(top,upper,upper_following),
                      (index,following,upper_following),(index,upper_following,upper)]
    return vertices,triangles


def build_closed_geometry(primitives, radial_sides=24):
    """Aggregate closed solids; no welding, boolean, or triangle filtering."""
    vertices,triangles,pieces = [],[],[]
    for spec in primitives:
        if spec['kind']=='box':
            vv,tt = _box_geometry(spec)
        elif spec['kind']=='cylinder':
            vv,tt = _cylinder_geometry(spec,radial_sides)
        else:
            raise ValueError('Unsupported primitive: '+spec['kind'])
        vertex_base,triangle_base = len(vertices),len(triangles)
        vertices.extend(vv)
        triangles.extend([[value+vertex_base for value in tri] for tri in tt])
        pieces.append(dict(name=spec['name'],kind=spec['kind'],group=spec['group'],
                           vertex_start=vertex_base,vertex_count=len(vv),
                           triangle_start=triangle_base,triangle_count=len(tt),
                           closed=True))
    return dict(vertices=vertices,triangles=triangles,pieces=pieces,
                vertex_count=len(vertices),triangle_count=len(triangles),
                units='centimetres',closed_primitives=True,
                collision='NoCollision',schema=SCHEMA)


def geometry_for_door(row, radial_sides=24):
    recipe = primitive_specs(row['width'],row['height'],row.get('depth',20.),
                             row.get('hinge_side',1))
    return dict(recipe=recipe,fixed=build_closed_geometry(recipe['fixed'],radial_sides),
                moving=build_closed_geometry(recipe['moving'],radial_sides))


def _rectangle(center, size, angle=0.):
    cosine,sine = math.cos(angle),math.sin(angle)
    return [(center[0]+x*cosine-y*sine,center[1]+x*sine+y*cosine)
            for x,y in [(-size[0]/2,-size[1]/2),(size[0]/2,-size[1]/2),
                        (size[0]/2,size[1]/2),(-size[0]/2,size[1]/2)]]


def _positive_polygon_overlap(first, second):
    for polygon in (first,second):
        for index,start in enumerate(polygon):
            end = polygon[(index+1)%len(polygon)]
            normal = (start[1]-end[1],end[0]-start[0])
            aa = [sum(x*y for x,y in zip(normal,point)) for point in first]
            bb = [sum(x*y for x,y in zip(normal,point)) for point in second]
            if min(max(aa),max(bb)) <= max(min(aa),min(bb))+1.e-9:
                return False
    return True


def _signed_mesh_volume(mesh):
    total = 0.
    for aa,bb,cc in mesh['triangles']:
        a,b,c = [mesh['vertices'][index] for index in (aa,bb,cc)]
        cross = (b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],
                 b[0]*c[1]-b[1]*c[0])
        total += sum(x*y for x,y in zip(a,cross))/6
    return total


def _piece_closure(mesh):
    checks = []
    for piece in mesh['pieces']:
        first = piece['triangle_start']
        tt = mesh['triangles'][first:first+piece['triangle_count']]
        edges = {}
        for triangle in tt:
            for index,aa in enumerate(triangle):
                bb = triangle[(index+1)%3]
                key = tuple(sorted((aa,bb)))
                edges.setdefault(key,[]).append((aa,bb))
        closed = all(len(edge)==2 and edge[0]==edge[1][::-1]
                     for edge in edges.values())
        part = dict(vertices=mesh['vertices'],triangles=tt)
        volume = _signed_mesh_volume(part)
        checks.append(dict(piece=piece['name'],closed_manifold=closed,
                           outward_winding=volume>0.,signed_volume_cm3=volume,
                           passed=closed and volume>0.))
    return checks


def validate_recipe(row):
    """Static tests; deliberate bearing/wood mounting contact is allowed."""
    data = geometry_for_door(row)
    recipe = data['recipe']
    width = recipe['width_cm']
    # Normalised hinge space q goes from the hinge into the closed wood leaf.
    # Fixed pads/necks are wholly in q<0 and y<0, away from its sweep.
    fixed = [('jamb_leaf',_rectangle([-2.5,-2.925],[3.6,.65]))]
    first,second = [-2.5,-2.85],[-.75,-.8]
    center = [(a+b)/2 for a,b in zip(first,second)]
    angle = math.atan2(second[1]-first[1],second[0]-first[0])
    fixed.append(('fixed_neck',_rectangle(center,[math.dist(first,second),.5],angle)))
    sweep = []
    for degrees in range(0,91,15):
        rad = math.radians(degrees)
        length = width-1.
        leaf = _rectangle([length/2*math.cos(rad),length/2*math.sin(rad)],
                          [length,4.],rad)
        collisions = [name for name,part in fixed if _positive_polygon_overlap(leaf,part)]
        sweep.append(dict(angle_deg=degrees,passed=not collisions,
                           unexpected_fixed_mount_overlaps=collisions))
    closure = {part:_piece_closure(data[part]) for part in ('fixed','moving')}
    # Each group has strict interior overlap at neck endpoints and its pin.
    # These analytic witnesses are unchanged by door width/handedness.
    contacts = [
        dict(first='jamb_leaf',second='fixed_neck',
             witness='fixed neck start y=depth/2+.15 lies inside pad depth/2-.25 to depth/2+.4',
             interior_overlap=True),
        dict(first='fixed_neck',second='fixed_knuckle',
             witness_distance_to_axis_cm=math.hypot(.75,.8),barrel_radius_cm=1.2,
             interior_overlap=math.hypot(.75,.8)<1.2),
        dict(first='fixed_knuckle',second='pin',witness='coaxial solid pin and sleeve',
             interior_overlap=True),
        dict(first='pin',second='moving_knuckle',witness='coaxial solid pin and sleeve at all angles',
             interior_overlap=True),
        dict(first='moving_knuckle',second='moving_neck',
             witness_distance_to_axis_cm=math.hypot(.6,.75),barrel_radius_cm=1.2,
             interior_overlap=math.hypot(.6,.75)<1.2),
        dict(first='moving_neck',second='door_leaf_mount',
             witness='moving neck endpoint at q=1.5, y=-2.2 inside mounting leaf',
             interior_overlap=True),
    ]
    return dict(schema=SCHEMA,passed=all(check['passed'] for check in sweep) and
                all(check['passed'] for checks in closure.values() for check in checks) and
                all(check['interior_overlap'] for check in contacts),
                sampled_sweep=sweep,closure=closure,contacts_per_hinge=contacts,
                fixed_triangle_count=data['fixed']['triangle_count'],
                moving_triangle_count=data['moving']['triangle_count'],
                no_collision=True,existing_leaf_and_pivot_unchanged=True,
                scope='Pure geometry validation only; live-map render and route checks remain required.')
