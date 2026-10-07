"""Centimetre geometry for sealed joints, rectangular stair skins and openings."""
import math

LAP = .5


def window_plan(building):
    """Windows fit between real slabs; ground windows avoid the sole entry."""
    narrow = building.width < 400.
    width, height = (90., 90.) if narrow else (125., 120.)
    columns = max(1, min(4, int(building.width // 450.)))
    span = building.width - 2.*20. - 70.
    coordinates = [span*((i+.5)/columns-.5) for i in range(columns)]
    rows = []
    for level, floor in enumerate(building.floors):
        ceiling = (building.floors[level+1] if level+1 < building.count else building.high[2])-20.
        center_z = floor+(ceiling-floor)*.55
        for column, u in enumerate(coordinates):
            if level == 0 and any(p['wall'] == 'Front' and
                    abs(u-p['coordinate']) < (width+building.door_width)*.5+25.
                    for p in building.portals):
                continue
            low = [u-width*.5, -.5, center_z-height*.5]
            high = [u+width*.5, 20.5, center_z+height*.5]
            assert low[2] > floor+35. and high[2] < ceiling-20.
            assert low[0] >= -building.width*.5+20. and high[0] <= building.width*.5-20.
            rows.append({'name':'{}_F{}_C{}'.format(building.label,level,column),
                         'building':building.label,'wall':'Front','floor':level,
                         'u':u,'v':0.,'z':center_z,'width':width,'height':height,
                         'local_min':low,'local_max':high,
                         'world_min':building.world_box(low,high)[0],
                         'world_max':building.world_box(low,high)[1]})
    if not rows:
        # A narrow one-storey shop still receives a rear window, clear of its
        # front entrance. The school guard's side door already leaves its front.
        floor = building.ground
        center_z = floor+(building.high[2]-20.-floor)*.55
        low = [-width*.5,building.depth-20.5,center_z-height*.5]
        high = [width*.5,building.depth+.5,center_z+height*.5]
        rows.append({'name':building.label+'_F0_Rear','building':building.label,
                     'wall':'Rear','floor':0,'u':0.,'v':building.depth,'z':center_z,
                     'width':width,'height':height,'local_min':low,'local_max':high,
                     'world_min':building.world_box(low,high)[0],
                     'world_max':building.world_box(low,high)[1]})
    return rows


def sealed_local_box(building, role, low, high):
    """Lap slabs/corners inside walls; keep the outer building silhouette exact."""
    low, high = list(low), list(high)
    if role in ('FloorSlab','RoofSlab'):
        targets = ((0,-building.width*.5+20.,building.width*.5-20.),
                   (1,20.,building.depth-20.))
        for axis,a,b in targets:
            if abs(low[axis]-a) < .01:
                low[axis] -= LAP
            if abs(high[axis]-b) < .01:
                high[axis] += LAP
    if role == 'WallPanel':
        on_side = high[0] <= -building.width*.5+20.01 or low[0] >= building.width*.5-20.01
        if on_side:
            if abs(low[1]-20.) < .01:
                low[1] -= LAP
            if abs(high[1]-(building.depth-20.)) < .01:
                high[1] += LAP
    return low,high


def sample_path(points, step=18.):
    for a,b in zip(points,points[1:]):
        count = max(1,int(math.ceil(math.dist(a,b)/step)))
        for i in range(count+1):
            yield [a[j]+(b[j]-a[j])*i/count for j in range(3)]


def distance_to_box_xy(point, low, high):
    return math.sqrt(sum(max(low[i]-point[i],0.,point[i]-high[i])**2 for i in (0,1)))


def door_coordinates(building, portal, a, n, z):
    """a runs across a door; n points inward, starting at its exterior face."""
    c = portal['coordinate']
    wall = portal['wall']
    if wall == 'Front':
        return building.world(c+a,n,z)
    if wall == 'Rear':
        return building.world(c+a,building.depth-n,z)
    if wall == 'Left':
        return building.world(-building.width*.5+n,c+a,z)
    return building.world(building.width*.5-n,c+a,z)


def door_world_box(building, portal, low, high):
    a,b = door_coordinates(building,portal,*low),door_coordinates(building,portal,*high)
    return [min(a[i],b[i]) for i in range(3)],[max(a[i],b[i]) for i in range(3)]


def door_leaf_plan(building, report):
    """A single visible leaf fixed open 90deg, on the safer hinge side."""
    portal = building.portals[0]
    width = building.door_width
    samples = list(sample_path(report['ground_route']))+list(sample_path(report['primary_entry_route']))
    choices = []
    for side in (-1.,1.):
        edge = side*(width*.5-4.)
        low = [edge-2.,20.,building.ground+1.]
        high = [edge+2.,20.+width-8.,building.ground+building.door_height-5.]
        world_low,world_high = door_world_box(building,portal,low,high)
        clearance = min(distance_to_box_xy(p,world_low,world_high) for p in samples)
        choices.append((clearance,side,low,high))
    clearance,side,low,high = max(choices)
    assert clearance >= 39., (building.label,clearance)
    return {'building':building.label,'hinge_side':side,'state':'fixed_open_90_degrees',
            'local_min':low,'local_max':high,'route_center_clearance_cm':clearance,
            'world_min':door_world_box(building,portal,low,high)[0],
            'world_max':door_world_box(building,portal,low,high)[1]}
