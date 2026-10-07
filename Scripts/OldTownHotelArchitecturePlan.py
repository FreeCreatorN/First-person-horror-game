"""A four-storey former guesthouse: measured architecture, independent of UE."""
import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelArchitecture_20261005'
BUILDING = 'OTS_PerimeterBoundaryEast_01'
PITCH = 5700. / 14


def subtract(low, high, cl, ch):
    if not all(min(high[i], ch[i]) > max(low[i], cl[i]) + .01 for i in range(3)):
        return [(list(low), list(high))]
    a, b = [max(low[i], cl[i]) for i in range(3)], [min(high[i], ch[i]) for i in range(3)]
    l, h, out = list(low), list(high), []
    for i in range(3):
        if a[i] > l[i] + .01:
            q = h[:]; q[i] = a[i]; out.append((l[:], q)); l[i] = a[i]
        if b[i] < h[i] - .01:
            q = l[:]; q[i] = b[i]; out.append((q, h[:])); h[i] = b[i]
    return out


def build_plan(base):
    old = next(b for b in base['buildings']['buildings'] if b['label'] == BUILDING)
    floors = old['floor_z']
    p = dict(schema_version=1, building=BUILDING, hotel_name='老城酒店',
             narrative='原单位招待所改造旅馆，停业后的旧楼；空间先完整成立，再呈现破败。',
             shell_bounds=[[9000., -3500., 0.], [10040., 3500., 1500.]], floor_z_cm=floors,
             corridor_width_cm=180., boxes=[], doors=[], windows=[], rooms=[], props=[],
             routes=[], staircases=[], shafts=[], spatial_program=[], review_cameras=[], interior_lights=[],
             structural_grid={'bay_pitch_cm': PITCH, 'bay_y_cm': [-2850 + i * PITCH for i in range(15)],
                              'upper_partition_thickness_cm': 20., 'ground_transfer_frame': True,
                              'description': 'Upper transverse partitions align; visible ground beams and piers carry their axes. Architectural load-path concept; no structural load calculation.'})
    walls = []
    def box(id, role, lo, hi, mat='plaster', floor=None, collision=True):
        assert all(hi[i] > lo[i] for i in range(3)), id
        row = dict(id=id, role=role, world_min=list(lo), world_max=list(hi), material=mat,
                   floor=floor, collision=collision)
        p['boxes'].append(row)
        return row
    def wall(id, lo, hi, floor, mat='plaster'):
        walls.append(dict(id=id, world_min=lo, world_max=hi, floor=floor, material=mat))
    def route(id, floor, kind, points):
        p['routes'].append(dict(id=id, floor=floor, kind=kind, points=points))
        return points
    def door(id, floor, kind, x, y, width=90, inward=(1,0,0), room=None, height=None):
        z = floors[floor]
        row = dict(id=id, floor=floor, kind=kind, room_id=room, position_cm=[x,y,z],
                   inward=list(inward), width=float(width), height=float(height or (230 if width==140 else 200)), depth=20.)
        p['doors'].append(row); return row
    def prop(id, key, pos, yaw=0, scale=None, colliders=None):
        row = dict(id=id, asset_key=key, position_cm=pos, yaw=yaw,
                   scale=scale or [1,1,1], collision_boxes=colliders or [])
        p['props'].append(row); return row
    def window(id, floor, x, y, bottom, inward, kind='guest'):
        p['windows'].append(dict(id=id, floor=floor, kind=kind, position_cm=[x,y,bottom],
                                 inward=list(inward), width=125., height=120.))
    # A continuous, properly opened shell; all four levels have the same datum.
    for f,z in enumerate(floors):
        ceil = floors[f+1]-20 if f<3 else 1480.
        wall('F%d_ExternalWest'%f, [9000,-3500,z], [9020,3500,ceil], f)
        wall('F%d_ExternalEast'%f, [10020,-3500,z], [10040,3500,ceil], f)
        wall('F%d_ExternalSouth'%f, [9020,-3500,z], [10020,-3480,ceil], f)
        wall('F%d_ExternalNorth'%f, [9020,3480,z], [10020,3500,ceil], f)
        wall('F%d_CorridorWall'%f, [9200,-2850,z], [9220,2850,ceil], f)
        # Stair compartments open into the west gallery, never through rooms.
        for sign in (-1,1):
            y0,y1 = sorted((sign*2870, sign*3480))
            wall('F%d_StairWest_%d'%(f,sign),[9220,y0,z],[9240,y1,ceil],f)
            # Separate the staircase from the adjacent accommodation.
            boundary = sign*2860
            wall('F%d_StairCross_%d'%(f,sign),[9220,boundary-10,z],[10020,boundary+10,ceil],f)
            sd=door('F%d_StairDoor_%d'%(f,sign),f,'stair',9230,sign*3225,140)
            sd['hinge_side']=-1 if sign<0 else 1
            if f==0:
                door('Exit_%s'%('North' if sign>0 else 'South'),0,'exit',9010,sign*3225,140,(-1,0,0))
                box('ExitThreshold_%d'%sign,'floor',[8970,sign*3225-85,-1],[9030,sign*3225+85,z],'concrete',0)
                route('Exit_%d'%sign,0,'exit',[[9462,sign*3305,z],[9350,sign*3305,z],
                       [9350,sign*3225,z],[9110,sign*3225,z],[8800,sign*3225,z]])
        # Real slab holes at both U stairs and the stacked lift shaft.
        parts = [([9020,-3480,z-20],[10020,3480,z])]
        if f>0:
            for sign in (-1,1):
                yl,yh = sorted((sign*3155,sign*3455))
                parts = [q for lo,hi in parts for q in subtract(lo,hi,[9547,yl,z-21],[9995,yh,z+1])]
            parts = [q for lo,hi in parts for q in subtract(lo,hi,[9620,70,z-21],[9900,350,z+1])]
        for i,(lo,hi) in enumerate(parts): box('F%d_Floor_%02d'%(f,i),'floor',lo,hi,'concrete',f)
        # A material datum reinforces the period without obstructing circulation.
        box('F%d_Wainscot'%f,'wainscot',[9198,-2840,z+12],[9200,2840,z+95],'green',f,False)
        route('F%d_LongGallery'%f,f,'corridor',[[9110,-3225,z],[9110,3225,z]])
        for sign in (-1,1):
            route('F%d_StairApproach_%d'%(f,sign),f,'corridor',
                  [[9110,sign*3225,z],[9350,sign*3225,z],[9350,sign*3305,z],[9462,sign*3305,z]])
        # Lift walls are continuous; doors are closed at upper floors, never an open drop.
        wall('F%d_LiftNorth'%f,[9600,350,z],[9920,370,ceil],f)
        wall('F%d_LiftSouth'%f,[9600,50,z],[9920,70,ceil],f)
        wall('F%d_LiftEast'%f,[9900,70,z],[9920,350,ceil],f)
        wall('F%d_LiftWest'%f,[9600,70,z],[9620,350,ceil],f)
        # A closed modeled landing door protects the shaft. Not a working game lift.
        box('F%d_LiftDoor'%f,'lift_door',[9595,130,z],[9600,290,z+220],'dark',f)
        box('F%d_LiftArchitrave'%f,'lift_head',[9593,125,z+220],[9600,295,z+235],'green',f)
        p['shafts'].append(dict(id='Lift_F%d'%f,kind='lift',floor=f,world_min=[9620,70,z],world_max=[9900,350,ceil]))
        if f:
            # Central shared landing, clean linen enclosed and separate from rooms.
            wall('F%d_CoreSouth'%f,[9220,-10,z],[10020,10,ceil],f)
            wall('F%d_CoreNorth'%f,[9220,PITCH-10,z],[10020,PITCH+10,ceil],f)
            door('F%d_CoreDoor'%f,f,'service',9210,180,140)
            wall('F%d_LinenFront'%f,[9250,280,z],[9600,290,ceil],f)
            wall('F%d_LinenWest'%f,[9240,280,z],[9250,PITCH-10,ceil],f)
            door('F%d_LinenDoor'%f,f,'service',9420,285,90,(0,1,0))
            box('F%d_LinenShelf'%f,'shelf',[9260,330,z],[9550,390,z+175],'wood',f)
            p['spatial_program'].append(dict(id='F%d_LiftLinen'%f,floor=f,role='lift_lobby_and_clean_linen',
                                            rect=[9220,0,10020,PITCH]))
        # A few surviving fluorescent fittings; most are failed fixtures.
        for n,y in enumerate(range(-2600,2800,700)):
            prop('F%d_Fluorescent_%02d'%(f,n),'FluorescentFixture',[9110,y,ceil-12])
            if (f==1 and n in (1,4,6)) or (f==0 and n==4):
                p['interior_lights'].append(dict(id='F%d_SurvivingTube_%02d'%(f,n),
                    position_cm=[9110,y,ceil-17],rotation=[-90,0,0],intensity_lm=75,
                    source_width_cm=10,source_height_cm=90,attenuation_radius_cm=650))
        for n,y in enumerate((-2360,-1180,820,2240)):
            box('F%d_PeelingDado_%d'%(f,n),'paint_loss',[9196.5,y,z+25],[9198,y+38,z+66],'plaster',f,False)
        for sign in (-1,1):
            p['windows'].append(dict(id='StairWindow_F%d_%d'%(f,sign),floor=f,kind='stair',
                   position_cm=[9820,sign*3490,z+125],inward=[0,-sign,0],width=125.,height=120.))
    box('Roof','roof',[9000,-3500,1480],[10040,3500,1500],'concrete')
    # Preserve the old west gallery's fenestration while genuinely opening all new rear windows.
    for row in base['opening_components']['windows']:
        if row['building']==BUILDING and row['kind']=='building_window':
            c=row['world_center']; f=min(range(4),key=lambda k:abs((c[2]-190)-floors[k]))
            window('Original_'+row['window_id'],f,9010,c[1],c[2]-row['height']/2,[1,0,0],'gallery')
    door('MainEntry',0,'entry',9010,158,140,(-1,0,0))
    door('EntryFoyer',0,'public',9210,158,140)
    door('LoungeDoor',0,'public',9210,-2100,140)
    door('ServiceEntry',0,'service_entry',9010,2300,140,(-1,0,0))
    route('MainEntryReception',0,'entry',[[8800,158,11],[9110,158,11],[9520,158,11],[9520,-220,11],[9600,-220,11]])
    route('LobbyLounge',0,'public',[[9110,-2100,11],[9500,-2100,11],[9600,-2100,11]])
    route('TeaBreakfast',0,'public',[[9520,700,11],[9670,700,11],[9670,1100,11]])
    route('TeaPantry',0,'service',[[9670,1100,11],[9790,1100,11],[9790,1600,11]])
    # Reuse the verified U stair geometry, then mirror it for the independent south exit.
    for row in base['buildings']['structural_boxes']:
        if row['building']==BUILDING and row['role'] in ('StairTread','StairLanding'):
            lo,hi=row['min'],row['max']
            for sign in (-1,1):
                a,b=lo[:],hi[:]
                if sign<0: a[1],b[1]=-hi[1],-lo[1]
                box('Stair_%d_'%sign+row['actor'],'stair_tread' if row['role']=='StairTread' else 'landing',a,b,'concrete')
    for row in old['stairs']:
        for sign in (-1,1):
            points=[[q[0],q[1]*sign,q[2]] for q in row['foot_waypoints']]
            p['staircases'].append(dict(id='Stair_%d_F%d'%(sign,row['from_floor']),
                 from_floor=row['from_floor'],to_floor=row['to_floor'],foot_waypoints=points,
                 rise=row['rise_cm'],tread=28.,width=140.,landing_depth=140.))
    for sign in (-1,1):
        for label,yl,yh in [('Divider',3295,3315),('OuterA',3135,3155),('OuterB',3455,3475)]:
            a,b=sorted((sign*yl,sign*yh))
            box('StairGuard_%s_%d'%(label,sign),'stair_enclosure',[9547,a,11],[9855,b,1480],'plaster')
    # Each guest room has a private wet room, wardrobe, work surface and actual sleeping clearances.
    def guest(id,f,y0,y1,kind='twin',accessible=False):
        z=floors[f]; ceil=floors[f+1]-20 if f<3 else 1480
        wall('Room'+id+'_South',[9220,y0-10,z],[10020,y0,ceil],f)
        wall('Room'+id+'_North',[9220,y1,z],[10020,y1+10,ceil],f)
        d_y=y0+(310 if accessible else 300)
        d=door('Room'+id,f,'guest',9210,d_y,140 if accessible else 90,room=id)
        bx=9520 if accessible else 9450; by=y0+(260 if accessible else 220)
        wall('Bath'+id+'_East',[bx,y0,z],[bx+12,by,ceil],f)
        wall('Bath'+id+'_North',[9220,by,z],[bx+12,by+12,ceil],f)
        bd=door('Bath'+id,f,'bath',bx+6,y0+(145 if accessible else 95),140 if accessible else 90,
                (1,0,0) if accessible else (-1,0,0),id)
        box('Bath'+id+'_Tiles','bath_floor',[9220,y0,z],[bx,by,z+1],'ceramic',f)
        sh=[9470,y0+100,z+1] if accessible else [9285,y0+55,z+1]
        prop('Room'+id+'_Shower','ShowerTray',sh,scale=[1,1,.25] if accessible else None)
        if not accessible:
            prop('Room'+id+'_Screen','ShowerScreen',[9285,y0+10,z+1])
            prop('Room'+id+'_ScreenReturn','ShowerScreen',[9330,y0+55,z+1],90)
        wc=[9480,y0+220,z+1] if accessible else [9400,y0+170,z+1]
        sink=[9245,y0+220,z+1] if accessible else [9260,y0+160,z+1]
        prop('Room'+id+'_Toilet','Toilet',wc,colliders=[[[wc[0]-33,wc[1]-19,z+1],[wc[0]+33,wc[1]+19,z+79]]])
        prop('Room'+id+'_Basin','Washbasin',sink,180,colliders=[[[sink[0]-22.5,sink[1]-30,z+1],[sink[0]+22.5,sink[1]+30,z+86]]])
        wardrobe_x=9720 if accessible else 9680
        prop('Room'+id+'_Wardrobe','Wardrobe',[wardrobe_x,y0+75,z],colliders=[[[wardrobe_x-30,y0+15,z],[wardrobe_x+30,y0+135,z+210]]])
        # Window and bed are separated so neither blocks the other.
        window('Room'+id+'_Rear',f,10030,(y0+y1)/2,z+110,[-1,0,0])
        ys=([y0+20,y0+270] if kind=='twin' else [y0+20,y0+275] if kind=='family' else [y0+120])
        widths=([95,95] if kind=='twin' else [150,95] if kind=='family' else [150])
        for i,(yy,w) in enumerate(zip(ys,widths)):
            box('Room'+id+'_Bed%d'%i,'bed',[9750,yy,z+5],[9960,yy+w,z+35],'wood',f)
            box('Room'+id+'_Mattress%d'%i,'mattress',[9750,yy,z+35],[9960,yy+w,z+55],'linen',f)
            box('Room'+id+'_Pillow%d'%i,'pillow',[9910,yy+15,z+55],[9950,yy+w-15,z+65],'linen',f,False)
            box('Room'+id+'_Headboard%d'%i,'headboard',[9960,yy,z+5],[9970,yy+w,z+98],'wood',f)
        desk_y=y0+(290 if kind=='double' else 180)
        desk_x=9900 if kind=='double' else 9800
        desk_length=100 if kind=='double' else 120
        desk_width=80 if kind=='double' else 70
        box('Room'+id+'_DeskTop','desk',[desk_x,desk_y,z+72],[desk_x+desk_length,desk_y+desk_width,z+78],'wood',f)
        for index,xx in enumerate((desk_x+10,desk_x+desk_length-20)):
            box('Room'+id+'_DeskLeg'+str((9810,9900)[index]),'desk_leg',[xx,desk_y+5,z],[xx+8,desk_y+desk_width-5,z+72],'dark',f)
        r=route('Room'+id+'_Approach',f,'room',[[9110,d_y,z],[9600,d_y,z],[9680,d_y,z]])
        br=route('Room'+id+'_Bathroom',f,'bath',[[9600,d_y,z],[9600,bd['position_cm'][1],z],
                           [9330 if accessible else 9380,bd['position_cm'][1],z+1]])
        if kind=='double':
            route('Room'+id+'_Bedside',f,'room_use',[[9680,d_y,z],[9720,y0+315,z],[9810,y0+315,z]])
            route('Room'+id+'_DeskUse',f,'room_use',[[9720,y0+315,z],[9810,y0+335,z]])
        else:
            route('Room'+id+'_Bedside',f,'room_use',[[9680,d_y,z],[9720,y0+215,z],[9760,y0+(215 if kind=='family' else 150),z]])
            route('Room'+id+'_DeskUse',f,'room_use',[[9720,y0+215,z],[9750,y0+215,z]])
        p['rooms'].append(dict(id=id,floor=f,room_type='accessible_double' if accessible else kind,
                    world_min=[9220,y0,z],world_max=[10020,y1,ceil],bathroom_bounds=[[9220,y0,z],[bx,by,ceil]],
                    door_id=d['id'],window_id='Room'+id+'_Rear',route=r,bathroom_route=br,
                    area_m2=800*(y1-y0)/10000,accessible=accessible))
        p['shafts'].append(dict(id='Wet_'+id,kind='wet_stack',floor=f,
                     world_min=[9400,y0+10,z],world_max=[9450,y0+50,ceil]))
        box('WetShaft_'+id,'wet_shaft',[9400,y0+10,z],[9450,y0+50,ceil],'plaster',f)
        prop('BathVent_'+id,'WallVent',[9397,y0+32,z+240])
    for f in (1,2,3):
        count=0
        for slot in range(14):
            if slot==7: continue
            count+=1; y0=-2850+slot*PITCH+10; y1=-2850+(slot+1)*PITCH-10
            guest(str((f+1)*100+count),f,y0,y1,'double' if count in (4,8,12) else 'family' if count==13 else 'twin')
    guest('101',0,-2850+4*PITCH+10,-2850+5*PITCH-10,'double',True)
    guest('102',0,-2850+5*PITCH+10,-2850+6*PITCH-10,'double',True)
    # Ground floor: west service band under bathrooms; food only in the east dry band.
    programs=[('FrontDesk',[-300,900],'reception'),('Lounge',[-2850,-1500],'guest_lounge'),
              ('TeaBreakfast',[900,1390],'tea_breakfast'),('Office',[1800,2400],'office')]
    for id,ys,role in programs:
        p['spatial_program'].append(dict(id=id,floor=0,role=role,rect=[9570 if id=='TeaBreakfast' else 9220,ys[0],10020,ys[1]]))
    wall('OfficeSouth',[9220,1790,floors[0]],[10020,1810,floors[1]-20],0)
    wall('StoresSouth',[9220,2390,floors[0]],[10020,2410,floors[1]-20],0)
    door('OfficeDoor',0,'service',9210,2200)
    door('DirtyLinenDoor',0,'service',9210,2600)
    wall('LinenSeparation',[9590,2410,11],[9610,2850,floors[1]-20],0)
    door('CleanLinenDoor',0,'service',9700,2400,90,(0,1,0))
    box('DirtyLinenBin','linen_bin',[9280,2440,11],[9380,2520,111],'dark',0)
    box('CleanLinenShelves','shelf',[9780,2425,11],[9980,2500,201],'wood',0)
    p['spatial_program'].extend([
        dict(id='DirtyLinenStore',floor=0,role='dirty_linen',rect=[9220,2410,9590,2850]),
        dict(id='CleanLinenStore',floor=0,role='clean_linen',rect=[9610,2410,10020,2850])])
    route('CleanLinenAccess',0,'service',[[9110,2200,11],[9700,2200,11],[9700,2600,11]])
    # Pantry separated from all upper bathroom projections, with service access.
    wall('PantryWest',[9530,900,11],[9550,1790,floors[1]-20],0)
    wall('TeaPantryDivision',[9550,1390,11],[10020,1410,floors[1]-20],0)
    door('PantryDoor',0,'service',9790,1400,90,(0,1,0))
    box('PantryWorktop','worktop',[9880,1500,11],[9980,1740,96],'wood',0)
    box('BreakfastTable','table',[9840,1020,11],[9990,1230,86],'wood',0)
    p['spatial_program'].append(dict(id='DryPantry',floor=0,role='food_preparation',rect=[9570,1410,10020,1790]))
    for key,yl,yh,door_y in [('PublicWC',900,1340,1140),('StaffWC',1360,1790,1570)]:
        wall(key+'_South',[9220,yl-10,11],[9530,yl+10,floors[1]-20],0)
        wall(key+'_North',[9220,yh-10,11],[9530,yh+10,floors[1]-20],0)
        door(key+'_Door',0,'public_bath' if key=='PublicWC' else 'staff_bath',9210,door_y)
        prop(key+'_Basin','Washbasin',[9250,yl+100,12],180,
             colliders=[[[9227.5,yl+70,12],[9272.5,yl+130,97]]])
        toilet_y=1200 if key=='PublicWC' else 1740
        prop(key+'_Toilet','Toilet',[9488,toilet_y,12],
             colliders=[[[9455,toilet_y-19,12],[9521,toilet_y+19,90]]])
        p['spatial_program'].append(dict(id=key,floor=0,role='public_toilet' if key=='PublicWC' else 'staff_toilet',rect=[9220,yl,9530,yh]))
        route(key+'_Access',0,'bath',[[9110,door_y,11],[9400,door_y,11]])
        route(key+'_ToiletUse',0,'bath',[[9400,door_y,11],[9360,door_y,11],[9360,toilet_y,11],[9400,toilet_y,11]])
    # Wet-service risers continue through the ground service band, outside food areas.
    for slot in range(14):
        if slot==7 or slot in (4,5):continue
        y0=-2850+slot*PITCH+10
        box('GroundWetShaft_%02d'%slot,'wet_shaft',[9400,y0+10,11],[9450,y0+50,floors[1]-20],'plaster',0)
    for i,y in enumerate((-2600,-2150)):
        box('LobbySeat%d'%i,'seat',[9680,y,11],[9960,y+70,59],'wood',0)
        box('LobbySeatBack%d'%i,'seat_back',[9950,y,59],[9960,y+70,106],'wood',0)
    box('ReceptionCounter','reception',[9690,-300,11],[9770,-100,113],'wood',0)
    box('ReceptionTop','reception_top',[9685,-305,113],[9775,-95,118],'dark',0)
    prop('ReceptionKeys','KeyRack',[10008,-195,116])
    # Ground transfer beams are visible, not unsupported room walls above an empty lobby.
    for i,y in enumerate(p['structural_grid']['bay_y_cm']):
        for x in (9210,10010):
            box('Pier_%02d_%d'%(i,x),'column',[x-15,y-15,11],[x+15,y+15,floors[1]-70],'concrete',0)
        box('TransferBeam%02d'%i,'beam',[9195,y-15,floors[1]-70],[10025,y+15,floors[1]-20],'concrete',0)
    # Cut every real opening into structural boxes; moving parts remain independent.
    cuts=[]
    for d in p['doors']:
        x,y,z=d['position_cm']; w=d['width']; h=d['height']; n=d['inward']
        cuts.append(([x-40,y-w/2,z],[x+40,y+w/2,z+h]) if abs(n[0])>.5 else
                    ([x-w/2,y-40,z],[x+w/2,y+40,z+h]))
    for w in p['windows']:
        x,y,z=w['position_cm']; width=w['width']; height=w['height']
        cuts.append(([x-40,y-width/2,z],[x+40,y+width/2,z+height]) if abs(w['inward'][0])>.5 else
                    ([x-width/2,y-40,z],[x+width/2,y+40,z+height]))
    for row in walls:
        parts=[(row['world_min'],row['world_max'])]
        for cl,ch in cuts: parts=[q for lo,hi in parts for q in subtract(lo,hi,cl,ch)]
        for i,(lo,hi) in enumerate(parts): box(row['id']+'_%02d'%i,'wall',lo,hi,row['material'],row['floor'])
    # Painted dado panels must stop at openings too, despite being nonblocking.
    old_dados=[b for b in p['boxes'] if b['role']=='wainscot']
    p['boxes']=[b for b in p['boxes'] if b['role']!='wainscot']
    for row in old_dados:
        parts=[(row['world_min'],row['world_max'])]
        for cl,ch in cuts: parts=[q for lo,hi in parts for q in subtract(lo,hi,cl,ch)]
        for i,(lo,hi) in enumerate(parts): box(row['id']+'_%02d'%i,'wainscot',lo,hi,row['material'],row['floor'],False)
    p['review_cameras']=[
        dict(camera='CAM_ArchHotel_Exterior',position=[8100,-100,350],look_at=[9010,158,380],fov=75,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_Reception',position=[9470,-250,180],look_at=[9860,-180,160],fov=85,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_Gallery',position=[9110,-2750,floors[1]+165],look_at=[9110,2400,floors[1]+165],fov=75,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_TwinRoom',position=[9500,-2515,floors[1]+165],look_at=[9920,-2660,floors[1]+120],fov=85,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_Bathroom',position=[9380,-2715,floors[1]+150],look_at=[9310,-2735,floors[1]+75],fov=105,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_SouthStair',position=[9350,-3040,floors[1]+155],look_at=[9850,-3300,floors[1]+200],fov=85,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_LiftLobby',position=[9300,180,floors[1]+160],look_at=[9600,210,floors[1]+145],fov=85,lighting_mode='temporary'),
        dict(camera='CAM_ArchHotel_NightGallery',position=[9110,-2700,floors[1]+160],look_at=[9110,2200,floors[1]+160],fov=80,lighting_mode='street_only')]
    return p


def validate_plan(p):
    errors=[]
    ids=[r['id'] for r in p['rooms']]
    if len(ids)!=len(set(ids)) or len(ids)!=41: errors.append('room_count_or_ids')
    if [sum(r['floor']==f for r in p['rooms']) for f in range(4)] != [2,13,13,13]: errors.append('floor_distribution')
    if len(p['staircases'])!=6 or any(s['width']<140 or s['rise']>18 for s in p['staircases']): errors.append('stairs')
    exits=[d for d in p['doors'] if d['kind']=='exit']
    if len(exits)!=2 or abs(exits[0]['position_cm'][1]-exits[1]['position_cm'][1])<6000: errors.append('independent_exits')
    for a in [s for s in p['spatial_program'] if s['role']=='food_preparation']:
        for r in p['rooms']:
            if r['floor']==0:continue
            lo,hi=r['bathroom_bounds']; q=a['rect']
            if min(q[2],hi[0])>max(q[0],lo[0]) and min(q[3],hi[1])>max(q[1],lo[1]): errors.append('food_below_bath_'+r['id'])
    checks=0
    obstacles=[b for b in p['boxes'] if b['collision'] and b['role'] not in ('floor','bath_floor','stair_tread','landing')]
    for prop in p['props']:
        obstacles.extend(dict(id=prop['id'],world_min=lo,world_max=hi) for lo,hi in prop['collision_boxes'])
    furniture=[b for b in p['boxes'] if b['collision'] and b['role'] in
               ('bed','desk','reception','shelf','seat','worktop','linen_bin','table')]
    furniture.extend(dict(id=prop['id'],world_min=lo,world_max=hi) for prop in p['props'] for lo,hi in prop['collision_boxes'])
    fixed=[b for b in p['boxes'] if b['role'] in ('wall','wet_shaft','column','lift_door','stair_enclosure')]
    for a in furniture:
        for b in fixed:
            if all(min(a['world_max'][i],b['world_max'][i])-max(a['world_min'][i],b['world_min'][i])>.1 for i in range(3)):
                errors.append('furniture_structure_overlap:'+a['id']+':'+b['id'])
    for route in p['routes']:
        for start,end in zip(route['points'],route['points'][1:]):
            n=max(1,math.ceil(math.dist(start,end)/20))
            for k in range(n+1):
                foot=[start[i]+(end[i]-start[i])*k/n for i in range(3)]
                for b in obstacles:
                    lo,hi=b['world_min'],b['world_max']
                    if hi[2]<=foot[2]+2 or lo[2]>=foot[2]+182:continue
                    checks+=1
                    distance=math.hypot(max(lo[0]-foot[0],0,foot[0]-hi[0]),max(lo[1]-foot[1],0,foot[1]-hi[1]))
                    if distance<33.99:
                        error='fixed_route_blocked:'+route['id']+':'+b['id']
                        if error not in errors: errors.append(error)
    return dict(passed=not errors,errors=errors,room_count=len(ids),staircase_connections=6,
                fixed_route_geometry_checks=checks,
                scope='Planning checks; saved UE bodies and door states require separate physical verification.')


if __name__=='__main__':
    base=json.loads((ROOT/'Saved/CodexOutputs/StreetAccessLighting_20261005/BuildReport.json').read_text(encoding='utf-8-sig'))
    plan=build_plan(base); plan['validation']=validate_plan(plan)
    assert plan['validation']['passed'],plan['validation']
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'ArchitecturePlan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,rooms=len(plan['rooms']),boxes=len(plan['boxes']),doors=len(plan['doors']),windows=len(plan['windows']))))
