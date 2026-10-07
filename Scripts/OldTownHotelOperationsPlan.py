"""Measured, additive furnishings for the former guesthouse's daily operation."""
import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelOperations_20261006'
SOURCE = ROOT / 'SourceArt/OldTownHotelOperations_20261006'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def world_bounds(row, bounds):
    theta = math.radians(row['yaw'])
    c, s = math.cos(theta), math.sin(theta)
    points = []
    for x in (bounds[0][0], bounds[1][0]):
        for y in (bounds[0][1], bounds[1][1]):
            for z in (bounds[0][2], bounds[1][2]):
                sx, sy, sz = x * row['scale'][0], y * row['scale'][1], z * row['scale'][2]
                points.append([row['position_cm'][0] + c*sx-s*sy,
                               row['position_cm'][1] + s*sx+c*sy,
                               row['position_cm'][2] + sz])
    return [[min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)]]


def build_plan():
    p = dict(theme='停业旧招待所：完整的营业设备留下，少量松动和积尘。',
             props=[], routes=[], review_cameras=[], source_directory=str(SOURCE))

    def prop(id, key, pos, yaw=0, role='reception', collision=False, scale=(1,1,1), support=None):
        p['props'].append(dict(id='Ops_'+id, asset_key=key, position_cm=list(pos), yaw=yaw,
                               role=role, scale=list(scale), collision=collision,
                               supported_by=support, collision_boxes=[]))

    prop('ReceptionPhone', 'RotaryPhone', [9730,-257,118], support='ReceptionTop')
    prop('ReceptionLedger', 'Ledger', [9730,-179,118], support='ReceptionTop')
    prop('ReceptionBell', 'DeskBell', [9703,-117,118], support='ReceptionTop')
    prop('ReceptionStaffChair', 'Chair', [9895,-200,11], collision=True)
    prop('StoppedClock', 'WallClock', [10016,-65,255])
    prop('LoungeSofaSouth', 'SofaTop', [9820,-2565,59], 180, 'lounge', True, scale=(1.015,1.05,1.03), support='LobbySeat0')
    prop('LoungeSofaNorth', 'SofaTop', [9820,-2115,59], 0, 'lounge', True, scale=(1.015,1.05,1.03), support='LobbySeat1')
    prop('LoungeCoffeeTable', 'CoffeeTable', [9820,-2350,11], role='lounge', collision=True)
    prop('LoungeAbandonedLedger', 'Ledger', [9820,-2350,59], 8, 'lounge', support='Ops_LoungeCoffeeTable')
    prop('LoungeLuggage', 'LuggageRack', [9760,-2740,11], role='lounge', collision=True)
    prop('BreakfastChairSouth', 'Chair', [9910,965,11], 270, 'breakfast', True)
    prop('BreakfastChairNorth', 'Chair', [9910,1300,11], 90, 'breakfast', True)
    prop('BreakfastKettle', 'Kettle', [9910,1120,86], role='breakfast', support='BreakfastTable')
    prop('PantrySink', 'PantrySink', [9930,1630,96], role='pantry', support='PantryWorktop')
    prop('PantryKettle', 'Kettle', [9930,1530,96], role='pantry', support='PantryWorktop')
    prop('OfficeDesk', 'CoffeeTable', [9910,2100,11], role='office', collision=True, scale=(1,1,1.5833333333))
    prop('OfficeChair', 'Chair', [9735,2100,11], 180, 'office', True)
    prop('OfficeLedger', 'Ledger', [9910,2100,87], role='office', support='Ops_OfficeDesk')
    prop('DirtyStoreCart', 'HousekeepingCart', [9515,2545,11], role='dirty_linen', collision=True)
    prop('DirtyStoreBag', 'LinenBag', [9500,2750,11], role='dirty_linen', collision=True)
    for n,x in enumerate((9830,9920)):
        prop('CleanStoreTowels%d'%n, 'TowelPile', [x,2460,201], role='clean_linen', support='CleanLinenShelves')
    floors = [11,378.25,745.5,1112.75]
    for f,z in enumerate(floors):
        prop('F%d_LiftFace'%f, 'LiftFace', [9595,210,z], role='lift_frontage', scale=(1,.875,1), support='F%d_LiftDoor'%f)
        prop('F%d_LiftCallPanel'%f, 'LiftCallPanel', [9593,105,z+110], role='lift_frontage')
        if f:
            prop('F%d_CleanTowels'%f, 'TowelPile', [9410,360,z+175], role='clean_linen', support='F%d_LinenShelf'%f)

    for id,kind,points in [
        ('ReceptionStaffUse','service',[[9520,158,11],[9520,-40,11],[9825,-40,11],[9825,-200,11]]),
        ('LoungeSouthSeatUse','public',[[9500,-2100,11],[9500,-2460,11],[9800,-2460,11]]),
        ('LoungeNorthSeatUse','public',[[9500,-2100,11],[9500,-2240,11],[9800,-2240,11]]),
        ('LuggageAccess','public',[[9500,-2460,11],[9500,-2740,11],[9660,-2740,11]]),
        ('PantrySinkUse','service',[[9790,1600,11],[9790,1630,11]]),
        ('OfficeWorkstation','service',[[9700,2200,11],[9800,2200,11],[9800,2100,11]]),
        ('DirtyStoreWork','service',[[9110,2600,11],[9400,2600,11],[9410,2545,11]]),
        ('DirtyBagAccess','service',[[9400,2600,11],[9400,2750,11],[9430,2750,11]]),
        ('CleanStoreShelfUse','service',[[9700,2600,11],[9880,2600,11]])]:
        p['routes'].append(dict(id='Ops_'+id,floor=0,kind=kind,points=points))
    p['review_cameras'] = [
        dict(camera='CAM_OpsHotel_Reception',position=[9470,-220,175],look_at=[9860,-175,155],fov=80,lighting_mode='temporary'),
        dict(camera='CAM_OpsHotel_Lounge',position=[9490,-2650,175],look_at=[9820,-2320,100],fov=95,lighting_mode='temporary'),
        dict(camera='CAM_OpsHotel_Pantry',position=[9650,1710,175],look_at=[9930,1605,115],fov=88,lighting_mode='temporary'),
        dict(camera='CAM_OpsHotel_Linen',position=[9360,2760,175],look_at=[9500,2530,100],fov=90,lighting_mode='temporary'),
        dict(camera='CAM_OpsHotel_Lift',position=[9370,180,538.25],look_at=[9595,210,518.25],fov=85,lighting_mode='temporary')]
    return p


def measured_plan():
    p = build_plan()
    manifest = read(SOURCE/'ImportManifest.json')
    assets = {r['key']:r for r in manifest['assets']}
    for row in p['props']:
        row['world_bounds_cm'] = world_bounds(row,assets[row['asset_key']]['bounds_cm'])
        if row['collision']:
            row['collision_boxes'] = [row['world_bounds_cm']]
    base = read(ROOT/'Saved/CodexOutputs/HotelArchitecture_20261005/BuildReport.json')
    a = deepcopy(base['hotel_architecture'])
    a['props'].extend(p['props'])
    a['routes'].extend(p['routes'])
    from OldTownHotelArchitecturePlan import validate_plan
    p['validation'] = validate_plan(a)
    errors=p['validation']['errors']
    supports={r['id']:[r['world_min'],r['world_max']] for r in a['boxes']}
    supports.update({r['id']:r['world_bounds_cm'] for r in p['props']})
    def overlaps(left,right):
        return all(min(left[1][i],right[1][i])-max(left[0][i],right[0][i])>.12 for i in range(3))
    for i,row in enumerate(p['props']):
        bounds=row['world_bounds_cm']
        for other in p['props'][i+1:]:
            if overlaps(bounds,other['world_bounds_cm']):
                errors.append('visible_prop_overlap:'+row['id']+':'+other['id'])
        for wall in [r for r in a['boxes'] if r['role'] in ('wall','column','wet_shaft','lift_door')]:
            if overlaps(bounds,[wall['world_min'],wall['world_max']]):
                errors.append('visible_structure_overlap:'+row['id']+':'+wall['id'])
        parent=row['supported_by']
        if parent and parent in supports and row['asset_key']!='LiftFace':
            lo,hi=supports[parent]
            if abs(bounds[0][2]-hi[2])>.15:
                errors.append('floating_or_embedded:'+row['id'])
            # Upholstery covers the old timber arms with a small intentional overhang.
            margin=2.6 if row['asset_key']=='SofaTop' else .2
            if any(bounds[0][j]<lo[j]-margin or bounds[1][j]>hi[j]+margin for j in (0,1)):
                errors.append('unsupported_overhang:'+row['id'])
    p['validation']['passed']=not errors
    assert p['validation']['passed'], p['validation']['errors']
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'OperationsPlan.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    return p


if __name__ == '__main__':
    p = measured_plan()
    print(json.dumps(dict(passed=True,props=len(p['props']),routes=len(p['routes']))))
