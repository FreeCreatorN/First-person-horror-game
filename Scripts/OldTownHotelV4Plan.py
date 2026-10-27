"""Approved V4 hotel geometry, in world centimetres; no Unreal dependency.

Plan axes are s along the 70 m facade and d inward from its street side.
World X=9000+100*d, Y=100*s-3500. Box bounds are actual finished geometry.
"""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
BUILDING = 'OTS_PerimeterBoundaryEast_01'
TAG = 'HotelV4_20261008'
FLOOR_Z = [11., 378.25, 745.5, 1112.75]
RISE = 367.25 / 24.
ROOF_Z = 1480.


def world(s, d, z):
    return [9000. + 100. * d, 100. * s - 3500., float(z)]


def bounds(rect, lo, hi):
    s0, d0, s1, d1 = rect
    return world(s0, d0, lo), world(s1, d1, hi)


def subtract(lo, hi, cut_lo, cut_hi):
    """Axis-aligned solid subtraction without introducing overlapping pieces."""
    if not all(min(hi[i], cut_hi[i]) > max(lo[i], cut_lo[i]) + .001 for i in range(3)):
        return [(list(lo), list(hi))]
    a = [max(lo[i], cut_lo[i]) for i in range(3)]
    b = [min(hi[i], cut_hi[i]) for i in range(3)]
    low, high, out = list(lo), list(hi), []
    for i in range(3):
        if a[i] > low[i] + .001:
            q = high[:]
            q[i] = a[i]
            out.append((low[:], q))
            low[i] = a[i]
        if b[i] < high[i] - .001:
            q = low[:]
            q[i] = b[i]
            out.append((q, high[:]))
            high[i] = b[i]
    return out


def build_plan(base=None):
    p = dict(schema_version=4, building=BUILDING, tag=TAG, hotel_name='老城旅馆',
             approved_review='ArchitectureRedesignReview_20261008_V4',
             coordinate_system='X=9000+100*d; Y=100*s-3500; metres s/d, world centimetres',
             floor_z_cm=FLOOR_Z[:], floor_z=FLOOR_Z[:],
             shell_bounds=[[9000., -3500., 0.], [10040., 3500., 1500.]],
             corridor_width_cm=220., boxes=[], doors=[], windows=[], props=[], rooms=[],
             routes=[], stair_routes=[], staircases=[], shafts=[], slab_voids=[],
             spatial_program=[], review_cameras=[], interior_lights=[], asset_catalog={},
             stair_geometry=[], design_intent=dict(main_axis_s_m=35., main_axis_world_y=0.,
                 lobby_segment_m=[23., 47.], ground_guest_rooms=0,
                 upper_rooms_per_floor=9, total_rooms=27, luggage_room=False,
                 office_side='left', public_wc_side='front_right',
                 lift_clear_global_sd_m=[33.2,7.2,36.2,10.2],
                 safety_stair_clear_global_sd_m=[40.72,7.,46.6,10.2],
                 main_clear_width_cm=200., waiting_seats=8, dining_seats=24,
                 structural_status='Concept transfer frame; no structural calculation claim'))
    walls = []

    def box(key, role, rect, z0, z1, mat='plaster', floor=None, collision=True, **extra):
        lo, hi = bounds(rect,z0,z1)
        return worldbox(key,role,lo,hi,mat,floor,collision,**extra)

    def worldbox(key,role,lo,hi,mat='plaster',floor=None,collision=True,**extra):
        assert all(hi[i]>lo[i] for i in range(3)), key
        row=dict(id=key,key=key,role=role,world_min=list(lo),world_max=list(hi),
                 material=mat,floor=floor,collision=collision,**extra)
        p['boxes'].append(row)
        return row

    def wall(key,rect,floor,mat='plaster',z0=None,z1=None):
        z0=FLOOR_Z[floor] if z0 is None else z0
        z1=(FLOOR_Z[floor+1]-20 if floor<3 else ROOF_Z) if z1 is None else z1
        lo,hi=bounds(rect,z0,z1)
        walls.append(dict(id=key,world_min=lo,world_max=hi,floor=floor,material=mat))

    def enclosure(key,rect,floor,role):
        s0,d0,s1,d1=rect
        wall(key+'_Left',(s0-.2,d0-.2,s0,d1+.2),floor)
        wall(key+'_Right',(s1,d0-.2,s1+.2,d1+.2),floor)
        wall(key+'_Front',(s0,d0-.2,s1,d0),floor)
        wall(key+'_Back',(s0,d1,s1,d1+.2),floor)
        lo,hi=bounds(rect,FLOOR_Z[floor],FLOOR_Z[floor]+210)
        row=dict(id=key,key=key,floor=floor,role=role,global_sd_m=list(rect),
                 clear_bounds=[lo,hi],world_min=lo,world_max=hi)
        p['spatial_program'].append(row)
        return row

    def door(key,floor,role,s,d,width=90.,normal=(1,0,0),kind='swing',
             room=None,height=220.,hinge=1,locked=False):
        # width is clear frame opening; structural hole is 8 cm wider.
        row=dict(id=key,key=key,floor=floor,role=role,kind=kind,room_id=room,
                 position_cm=world(s,d,FLOOR_Z[floor]),inward=list(normal),
                 width=float(width),height=float(height),depth=20.,
                 clear_width_cm=float(width),rough_width_cm=float(width+8.),
                 rough_height_cm=float(height+4.),hinge_side=hinge,
                 locked=locked,initial_state='closed' if locked else 'open',collision=True)
        p['doors'].append(row)
        return row

    def window(key,floor,s,d,normal,width=140.,height=140.,sill=100.,kind='guest'):
        row=dict(id=key,key=key,floor=floor,kind=kind,
                 position_cm=world(s,d,FLOOR_Z[floor]+sill),inward=list(normal),
                 width=float(width),height=float(height),depth=20.)
        p['windows'].append(row)
        return row

    def route(key,floor,kind,sd,room=None,z=None):
        z=FLOOR_Z[floor]+2 if z is None else z
        points=[world(s,d,z) for s,d in sd]
        row=dict(id=key,key=key,floor=floor,kind=kind,room_id=room,points=points,
                 foot_waypoints=points,foot_z_cm=z,capsule_radius_cm=34.,capsule_half_height_cm=90.)
        p['routes'].append(row)
        return row

    manifest_path=ROOT/'SourceArt/OldTownHotelArchitecture_20261005/ImportManifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    fixture_rows={a['key']:a for a in manifest['assets']}
    for key,a in fixture_rows.items():
        p['asset_catalog'][key]='/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005/'+a['name']

    def fixture(key,asset,s,d,z,floor,yaw=0.,scale=None,collision=True):
        a=fixture_rows[asset]
        scale=list(scale or [1.,1.,1.])
        pos=world(s,d,z)
        rad=math.radians(yaw)
        vertices=[]
        for x in (a['bounds_cm'][0][0],a['bounds_cm'][1][0]):
            for y in (a['bounds_cm'][0][1],a['bounds_cm'][1][1]):
                for zz in (a['bounds_cm'][0][2],a['bounds_cm'][1][2]):
                    xx,yy=x*scale[0],y*scale[1]
                    vertices.append([pos[0]+xx*math.cos(rad)-yy*math.sin(rad),
                                     pos[1]+xx*math.sin(rad)+yy*math.cos(rad),pos[2]+zz*scale[2]])
        low=[min(v[i] for v in vertices) for i in range(3)]
        high=[max(v[i] for v in vertices) for i in range(3)]
        row=dict(id=key,key=key,asset_key=asset,asset=p['asset_catalog'][asset],
                 source_family='architecture',position_cm=pos,yaw=yaw,
                 rotation=[0.,yaw,0.],scale=scale,floor=floor,
                 collision=False,world_min=low,world_max=high,bounds=[low,high],
                 collision_boxes=[[low,high]] if collision else [])
        p['props'].append(row)
        return row

    def basin_box(key,rect,floor):
        s0,d0,s1,d1=rect
        return fixture(key,'Washbasin',(s0+s1)/2,(d0+d1)/2,FLOOR_Z[floor],floor,
                       scale=[(d1-d0)*100/45.,(s1-s0)*100/60.,1.])

    def table(key,rect,floor,height=75.,mat='wood'):
        s0,d0,s1,d1=rect; z=FLOOR_Z[floor]
        box(key+'_Top','table',rect,z+height-6,z+height,mat,floor)
        for i,ss in enumerate((s0+.07,s1-.07)):
            for j,dd in enumerate((d0+.07,d1-.07)):
                box(key+'_Leg%d%d'%(i,j),'table_leg',(ss-.025,dd-.025,ss+.025,dd+.025),z,z+height-6,'dark',floor)

    def seat(key,rect,floor,back='rear'):
        s0,d0,s1,d1=rect;z=FLOOR_Z[floor]
        box(key+'_Base','seat',rect,z+8,z+43,'linen',floor)
        if back=='rear': r=(s0,d1-.12,s1,d1)
        elif back=='front': r=(s0,d0,s1,d0+.12)
        elif back=='left': r=(s0,d0,s0+.12,d1)
        else:r=(s1-.12,d0,s1,d1)
        box(key+'_Back','seat',r,z+43,z+90,'linen',floor)

    def cabinet(key,rect,floor,height=185.):
        z=FLOOR_Z[floor]
        box(key,'shelf',rect,z,z+height,'wood',floor)
        s0,d0,s1,d1=rect
        box(key+'_DoorTrim','furniture_trim',(s0-.005,d0+.05,s0+.012,d1-.05),z+10,z+height-10,'dark',floor,False)

    # Shared shell, room partitions and actual openings on all four floors.
    for f,z in enumerate(FLOOR_Z):
        corridor_segments=[(.2,33.),(37.,69.8)] if f==0 else [(.2,69.8)]
        for j,(cs0,cs1) in enumerate(corridor_segments):
            clo,chi=bounds((cs0,.2,cs1,2.4),z,z+210)
            p['spatial_program'].append(dict(id='F%d_PublicCorridor%d'%(f,j),floor=f,role='public_corridor',
                global_sd_m=[cs0,.2,cs1,2.4],clear_bounds=[clo,chi],world_min=clo,world_max=chi))
        # Interior slabs end at the inside faces; envelope walls must also
        # span the 20cm slab edge band instead of leaving a horizontal slit.
        envelope_top=FLOOR_Z[f+1] if f<3 else ROOF_Z
        wall('F%d_StreetWall'%f,(0.,0.,70.,.2),f,z1=envelope_top)
        wall('F%d_RearWall'%f,(0.,10.2,70.,10.4),f,z1=envelope_top)
        wall('F%d_SouthEndWall'%f,(0.,.2,.2,10.2),f,z1=envelope_top)
        wall('F%d_NorthEndWall'%f,(69.8,.2,70.,10.2),f,z1=envelope_top)
        for s in (6.,64.): wall('F%d_EndStairBoundary_%g'%(f,s),(s-.1,2.4,s+.1,10.2),f)
        for s in (0.,64.):
            wall('F%d_EndStairFront_%g'%(f,s),(s+.2,2.4,s+5.8,2.6),f)
            door('F%d_%sStairDoor'%(f,'South' if s==0 else 'North'),f,'stair',s+3.,2.5,
                 140.,normal=(1,0,0),hinge=-1 if s==0 else 1)
            if f==0:
                door('%sFrontExit'%('South' if s==0 else 'North'),f,'exit',s+3.,.1,140.,normal=(-1,0,0))
                box('ExitThreshold_%g'%s,'floor',(s+2.1,-.3,s+3.9,.3),z-20,z,'concrete',0)
                route('%sFrontExitRoute'%('South' if s==0 else 'North'),0,'exit',
                      [(s+3.,4.5),(s+3.,3.1),(s+3.,1.3),(s+3.,-1.5)])
            window('F%d_EndStairRearWindow_%g'%(f,s),f,s+3.,10.3,(-1,0,0),180.,140.,110.,'stair')

        enclosure('F%d_LiftShaft'%f,(33.2,7.2,36.2,10.2),f,'lift_shaft')
        lift_door=door('F%d_LiftDoor'%f,f,'lift',36.3,8.7,140.,normal=(0,1,0),kind='slider',locked=True)
        lo,hi=bounds((33.2,7.2,36.2,10.2),z,(FLOOR_Z[f+1]-20 if f<3 else ROOF_Z))
        p['shafts'].append(dict(id='Lift_F%d'%f,key='Lift_F%d'%f,kind='lift',floor=f,
                                world_min=lo,world_max=hi,clear_bounds=[lo,hi],door_id=lift_door['id'],
                                wall_probe_points=[world(33.2,8.7,z+2),world(36.2,9.7,z+2),
                                                   world(34.7,7.2,z+2),world(34.7,10.2,z+2)]))
        enclosure('F%d_CentralSafetyStair'%f,(40.72,7.,46.6,10.2),f,'safety_stair')
        door('F%d_CentralStairDoor'%f,f,'stair',40.62,7.9,120.,normal=(0,1,0),hinge=-1)
        if f==0:
            door('CentralRearExit',0,'exit',41.42,10.3,120.,normal=(1,0,0))
            box('RearExitThreshold','floor',(40.74,10.15,42.1,10.7),z-20,z,'concrete',0)

        if f:
            # Five 4.8m left rooms; four 4.25m right rooms, all with private baths.
            number=0
            for start,bay,count in ((6.,4.8,5),(47.,4.25,4)):
                for j in range(count):
                    number+=1; s=start+j*bay; rid=str((f+1)*100+number)
                    key='Room'+rid
                    wall(key+'_Corridor',(s,2.4,s+bay,2.6),f)
                    wall(key+'_Left',(s-.1,2.6,s+.1,10.2),f)
                    wall(key+'_Right',(s+bay-.1,2.6,s+bay+.1,10.2),f)
                    did=door(key+'_Door',f,'guest',s+bay-1.1,2.5,100.,normal=(1,0,0),room=rid,hinge=-1)
                    number_s=did['position_cm'][1]/100+35.-.82
                    box(key+'_NumberPlaque','wayfinding',(number_s-.22,2.365,number_s+.22,2.395),z+159,z+183,'plaque',f,False)
                    fixture(key+'_Number','RoomNumber_'+rid,number_s,2.355,z+165,f,yaw=90.,collision=False)
                    # Bathroom perimeter, 12 cm walls, dry approach along its right side.
                    wall(key+'_BathFront',(s+.14,2.6,s+2.31,2.72),f)
                    wall(key+'_BathLeft',(s+.14,2.72,s+.26,5.06),f)
                    wall(key+'_BathRight',(s+2.19,2.72,s+2.31,5.06),f)
                    wall(key+'_BathRear',(s+.26,4.94,s+2.19,5.06),f)
                    bd=door(key+'_BathDoor',f,'bathroom',s+2.25,3.925,85.,normal=(0,-1,0),kind='slider',room=rid,height=205.)
                    bd['depth']=12.
                    box(key+'_WetRiser','wet_shaft',(s+1.8,4.5,s+2.19,4.94),z,z+250,'plaster',f)
                    fixture(key+'_Toilet','Toilet',s+.85,4.45,z,f,yaw=180.)
                    basin_box(key+'_Basin',(s+1.4,2.82,s+2.1,3.42),f)
                    fixture(key+'_ShowerTray','ShowerTray',s+.775,3.275,z,f,collision=False)
                    fixture(key+'_ShowerScreen','ShowerScreen',s+1.25,3.275,z,f,collision=True)
                    cabinet(key+'_Wardrobe',(s+bay-.7,3.85,s+bay-.1,5.65),f)
                    twin=(j%3!=2) if start==6 else (j%3!=1)
                    beds=[(s+.5,7.7,s+1.5,9.7),(s+bay-1.5,7.7,s+bay-.5,9.7)] if twin else [(s+1.,7.7,s+2.6,9.7)]
                    for k,br in enumerate(beds):
                        box(key+'_Bed%dBase'%k,'bed',br,z+5,z+34,'wood',f)
                        box(key+'_Bed%dMattress'%k,'bed',br,z+34,z+51,'linen',f)
                        bs0,bd0,bs1,bd1=br
                        box(key+'_Bed%dHead'%k,'bed_head',(bs0,bd1-.06,bs1,bd1+.03),z+10,z+105,'wood',f)
                        box(key+'_Bed%dPillow'%k,'bed_linen',(bs0+.08,bd1-.4,bs1-.08,bd1-.12),z+51,z+63,'linen',f,False)
                    dr=(s+1.75,9.5,s+2.65,10.1) if twin else (s+bay-1.25,9.5,s+bay-.35,10.1)
                    table(key+'_WindowDesk',dr,f)
                    seat(key+'_Armchair',(s+.4,5.45,s+1.2,6.8),f,back='left')
                    table(key+'_TeaTable',(s+1.55,5.65,s+2.65,6.3),f,height=55.)
                    win=window(key+'_RearWindow',f,s+bay/2,10.3,(-1,0,0),
                               width=(bay-2.5)*100,height=140.,sill=100.)
                    bedside=(s+bay/2,8.8) if twin else (s+bay-1.125,8.5)
                    rr=route(key+'_Access',f,'room',[(s+bay-1.1,1.3),(s+bay-1.1,2.5),
                              (s+bay-1.1,4.6),(s+bay-1.2,6.8),(bedside[0],7.0),bedside],rid)
                    br=route(key+'_BathroomAccess',f,'bathroom',[(s+bay-1.1,4.3),
                              (s+2.7,3.925),(s+1.7,3.925),(s+1.45,4.3)],rid)
                    low,high=bounds((s+.1,2.6,s+bay-.1,10.2),z,z+210)
                    blo,bhi=bounds((s+.26,2.72,s+2.19,4.94),z,z+210)
                    p['rooms'].append(dict(id=rid,key=key,floor=f,kind='twin' if twin else 'double',
                         door_id=did['id'],bath_door_id=bd['id'],window_id=win['id'],
                         route_ids=[rr['id'],br['id']],route=rr['points'],bathroom_route=br['points'],
                         global_sd_m=[s+.1,2.6,s+bay-.1,10.2],roomspan_cm=[(bay-.2)*100,760.],
                         world_min=low,world_max=high,clear_bounds=[low,high],bathroom_bounds=[blo,bhi],
                         area_m2=round((bay-.2)*7.6,2),bed_count=2 if twin else 1))
            for name,rect in [('Linen',(30.2,7.2,32.8,10.2)),('Cleaning',(30.2,3.,32.8,5.6))]:
                enclosure('F%d_%s'%(f,name),rect,f,'clean_linen' if name=='Linen' else 'cleaning')
                door('F%d_%sDoor'%(f,name),f,'service',32.9,rect[1]+.85,90.,normal=(0,-1,0))
                cabinet('F%d_%sShelf'%(f,name),(30.5,rect[1]+.4,31.1,rect[3]-.25),f)
            route('F%d_PublicGallery'%f,f,'public',[(3.,1.3),(67.,1.3)])
            route('F%d_CoreLiftApproach'%f,f,'public',[(38.5,1.3),(38.5,8.7),(36.8,8.7)])
            route('F%d_CoreStairApproach'%f,f,'public',[(38.5,7.9),(40.62,7.9),(41.4,7.9)])
        # Reused overhead fittings; route validation treats these above head height.
        ceil=FLOOR_Z[f+1]-20 if f<3 else ROOF_Z
        for j,s in enumerate((10.,18.,26.,44.,52.,60.)):
            fixture('F%d_GalleryTube%02d'%(f,j),'FluorescentFixture',s,1.3,ceil-13.,f,collision=False)
        for j,s in enumerate((18.,52.)):
            p['interior_lights'].append(dict(id='F%d_SurvivingTube%d'%(f,j),floor=f,
                 position_cm=world(s,1.3,ceil-18.),rotation=[-90.,0.,0.],intensity_lm=75.,
                 source_width_cm=10.,source_height_cm=90.,attenuation_radius_cm=650.))
        # Original period dado, segmented after real openings are cut.
        for a,b in ((6.,30.),(47.,64.)):
            box('F%d_Dado_%g'%(f,a),'wainscot',(a,2.385,b,2.4),z+12,z+95,'green',f,False)

    # Ground floor public and back-of-house program.
    z=FLOOR_Z[0]
    wall('GroundDiningFront',(6.,2.4,23.,2.6),0)
    wall('GroundDiningPantryDivider',(18.9,2.6,19.1,10.2),0)
    wall('GroundLeftLobbyBoundary',(22.9,2.4,23.1,10.2),0)
    door('BreakfastDoor',0,'public',11.,2.5,180.,normal=(1,0,0))
    door('PantryDoor',0,'service',19.,7.5,100.,normal=(0,-1,0),hinge=-1)
    p['spatial_program'].append(dict(id='Dining',floor=0,role='dining',global_sd_m=[6.2,2.6,18.8,10.2],seats=24))
    p['spatial_program'].append(dict(id='Pantry',floor=0,role='food_preparation',global_sd_m=[19.2,2.6,22.8,10.2]))
    for j,s in enumerate((8.,12.,16.)):
        for k,d in enumerate((4.1,7.4)):
            table('Breakfast%d%d'%(j,k),(s,d,s+1.3,d+.8),0)
            for n,ss in enumerate((s+.1,s+.75)):
                for m,dd in enumerate((d-.65,d+.9)):
                    seat('BreakfastChair%d%d%d%d'%(j,k,n,m),(ss,dd,ss+.45,dd+.45),0,
                         'rear' if dd>d else 'front')
    cabinet('PantryWorkStorage',(22.1,3.1,22.7,9.7),0,height=90.)
    for k,rect in enumerate(((23.2,2.6,27.4,4.8),(23.2,5.,27.4,7.2),(23.2,7.4,27.4,10.2))):
        e=enclosure('Office%d'%k,rect,0,'office')
        e['office_function']=('staff','management','reception')[k]
        mid=(rect[1]+rect[3])/2
        door('Office%dDoor'%k,0,'office',27.5,mid,90.,normal=(0,-1,0))
        table('Office%dDesk'%k,(23.5,rect[3]-.9,25.2,rect[3]-.25),0)
        route('Office%dAccess'%k,0,'service',[(28.3,6.3),(28.3,mid),(27.5,mid),(25.8,mid)])
    enclosure('Vestibule',(33.,.2,37.,2.4),0,'vestibule')
    door('MainEntry',0,'entry',35.,.1,200.,kind='slider',normal=(1,0,0),height=235.)
    door('VestibuleInnerDoor',0,'public',35.,2.5,200.,kind='slider',normal=(1,0,0),height=235.)
    box('MainEntryThreshold','floor',(33.95,-.3,36.05,.4),z-20,z,'concrete',0)
    box('ReceptionCounter','reception',(32.9,4.8,37.1,5.6),z,z+104,'wood',0)
    box('ReceptionCounterTop','reception_top',(32.86,4.76,37.14,5.64),z+104,z+109,'dark',0)
    for key,asset,ss,dd,zz in [('ReceptionPhone','RotaryPhone',34.3,5.2,z+109.2),
                               ('ReceptionLedger','Ledger',35.,5.2,z+109.2),
                               ('ReceptionBell','DeskBell',35.8,4.98,z+109.2),
                               ('StoppedClock','WallClock',34.7,6.98,z+244.)]:
        ap='/Game/Yastar/Meshes/hOUSE/HotelOperations_20261006/SM_OTS_Ops_'+asset
        p['asset_catalog'][asset]=ap
        p['props'].append(dict(id=key,key=key,asset_key=asset,asset=ap,source_family='operations',
            floor=0,position_cm=world(ss,dd,zz),rotation=[0.,0.,0.],yaw=0.,scale=[1.,-1.,1.],collision_boxes=[]))
    # Individual chairs remain outside the approach to the centre of the meeting group.
    for key,rect,back in [('WaitingSofaLeft',(29.2,7.7,30.,9.8),'left'),
                          ('WaitingSofaRight',(31.8,7.7,32.6,9.8),'right'),
                          ('WaitingChairLeft',(29.2,6.8,29.85,7.45),'front'),
                          ('WaitingChairRight',(32.,6.8,32.65,7.45),'front'),
                          ('LiftWaitingBench',(37.,9.3,39.2,10.1),'rear')]:seat(key,rect,0,back)
    table('WaitingTeaTable',(30.6,8.3,31.2,9.),0,height=55.)
    enclosure('PublicWC',(41.2,2.6,46.8,5.8),0,'public_wc')
    door('PublicWCDoor',0,'public_bath',41.1,3.6,120.,normal=(0,1,0),hinge=-1)
    wall('WCStallFront',(43.1,3.94,46.8,4.06),0)
    wall('WCStallLeft',(43.04,4.06,43.16,5.8),0)
    wall('WCStallMiddle',(44.84,4.06,44.96,5.8),0)
    for n,(ds,ts) in enumerate(((43.8,44.),(45.65,45.85))):
        door('PublicWCStall%dDoor'%n,0,'wc_stall',ds,4.,80.,normal=(1,0,0),height=205.)
        fixture('PublicWCStall%dToilet'%n,'Toilet',ts,5.15,z,0,yaw=180.)
        route('PublicWCStall%dAccess'%n,0,'bathroom',[(40.3,3.5),(41.1,3.5),(ds,3.5),(ds,4.42)])
    basin_box('PublicWCBasin0',(41.45,4.7,42.15,5.4),0)
    basin_box('PublicWCBasin1',(42.25,4.7,42.95,5.4),0)
    route('PublicWCWashAccess',0,'bathroom',[(40.3,3.5),(41.1,3.5),(42.2,3.5),(42.2,4.2)])
    wall('GroundRightLobbyBoundary',(46.9,2.4,47.1,10.2),0)
    wall('ServiceWingFront',(47.,2.4,64.,2.6),0)
    for key,rect,role in [('CleanLinen',(47.2,7.,51.,10.2),'clean_linen'),
                          ('DirtyLinen',(51.2,7.,55.,10.2),'dirty_linen'),
                          ('Changing',(55.2,7.,58.8,10.2),'changing'),
                          ('StaffWC',(59.,7.,61.2,10.2),'staff_wc'),
                          ('Equipment',(61.4,7.,63.8,10.2),'equipment')]:
        enclosure(key,rect,0,role)
        mid=(rect[0]+rect[2])/2
        door(key+'Door',0,'service',mid,6.9,90.,normal=(1,0,0))
        if key!='StaffWC':cabinet(key+'Shelf',(rect[0]+.3,9.,rect[2]-.3,9.7),0)
        route(key+'Access',0,'service',[(61.,5.2),(mid,5.2),(mid,6.9),(mid,8.2)])
    fixture('StaffWCToilet','Toilet',60.7,9.5,z,0,yaw=180.)
    basin_box('StaffWCBasin',(59.2,9.4,59.9,10.),0)
    door('ServiceEntry',0,'service_entry',61.,.1,140.,normal=(1,0,0),kind='slider')
    door('ServiceInnerDoor',0,'service',61.,2.5,140.,normal=(1,0,0))
    box('ServiceEntryThreshold','floor',(60.15,-.3,61.85,.4),z-20,z,'concrete',0)
    # The 80cm buffer behind the public WC is not a service passage.
    # Staff reach the service wing through its front door and shared gallery.
    route('ReceptionArrival',0,'public',[(35.,-1.5),(35.,.1),(35.,2.5),(35.,4.32)])
    route('LobbyLeftPublic',0,'public',[(34.,3.7),(31.5,3.7),(31.5,1.3),(3.,1.3)])
    route('LobbyRightPublic',0,'public',[(36.,3.7),(38.5,3.7),(38.5,1.3),(67.,1.3)])
    route('GroundLiftApproach',0,'public',[(38.5,3.7),(38.5,8.7),(36.8,8.7)])
    route('GroundSafetyStairApproach',0,'public',[(38.5,7.9),(40.62,7.9),(41.4,7.9)])
    route('WaitingAccess',0,'public',[(31.5,4.),(31.5,6.5),(30.9,7.0)])
    route('ReceptionStaffAccess',0,'service',[(28.3,8.2),(28.3,6.3),(34.4,6.3),(34.4,6.02)])
    route('BreakfastAccess',0,'public',[(11.,1.3),(11.,2.5),(11.,5.8)])
    route('PantryAccess',0,'service',[(17.8,5.8),(17.8,7.5),(19.,7.5),(20.3,7.5)])
    route('ServiceEntryAccess',0,'service',[(61.,-1.5),(61.,.1),(61.,2.5),(61.,5.2)])
    route('LobbyServiceRoute',0,'service',[(38.5,3.7),(38.5,1.3),(61.,1.3),(61.,2.5),(61.,5.2)])
    # Rear route has a single top datum of 11 cm: threshold and all three bands join.
    worldbox('RearEscapeBand','exterior_floor',[10040.,500.,-9.],[10340.,3800.,11.],'concrete',0)
    worldbox('NorthEscapeBand','exterior_floor',[8700.,3500.,-9.],[10340.,3800.,11.],'concrete',0)
    worldbox('FrontEscapeConnection','exterior_floor',[8700.,3200.,-9.],[9000.,3800.,11.],'concrete',0)
    p['rear_escape_route_id']='RearSafetyEscape'
    rear_points=[[9790.,642.,13.],[10190.,642.,13.],[10190.,3650.,13.],
                 [8850.,3650.,13.],[8850.,3350.,13.]]
    p['routes'].append(dict(id=p['rear_escape_route_id'],key=p['rear_escape_route_id'],floor=0,
                           kind='rear_escape',points=rear_points,foot_waypoints=rear_points,
                           foot_z_cm=13.,capsule_radius_cm=34.,capsule_half_height_cm=90.))
    # Ground transfer frame follows upper room axes, keeping piers off the public route.
    axes=sorted(set([6.+4.8*k for k in range(6)]+[47.+4.25*k for k in range(5)]))
    for i,s in enumerate(axes):
        for d in (2.5,10.1):
            pier_s=9.85 if d==2.5 and abs(s-10.8)<.01 else s
            pier_d=2.55 if d==2.5 else d
            box('GroundPier_%02d_%g'%(i,d),'column',(pier_s-.15,pier_d-.15,pier_s+.15,pier_d+.15),11.,FLOOR_Z[1]-60.,'concrete',0)
        box('GroundTransferBeam_%02d'%i,'beam',(s-.15,2.35,s+.15,10.25),FLOOR_Z[1]-60.,FLOOR_Z[1]-20.,'concrete',0)

    # Three stair families. Treads are 20 cm thick, not infilled to the floor below.
    # Infill would incorrectly crush the headroom above the previous second flight.
    families=[dict(id='South',axis='d',cross='s',cross0=1.4,long0=3.8),
              dict(id='North',axis='d',cross='s',cross0=65.4,long0=3.8),
              dict(id='Central',axis='s',cross='d',cross0=7.,long0=40.72)]

    def stair_rect(fam,l0,l1,c0,c1):
        return (l0,c0,l1,c1) if fam['axis']=='s' else (c0,l0,c1,l1)

    def stair_point(fam,long,cross,z):
        return world(long,cross,z) if fam['axis']=='s' else world(cross,long,z)

    for fam in families:
        name=fam['id'];c0=fam['cross0'];l0=fam['long0']
        run0=l0+1.4;run1=run0+3.08;end=run1+1.4
        voidrect=stair_rect(fam,run0,end,c0,c0+3.2)
        p['stair_geometry'].append(dict(id=name,axis=fam['axis'],clear_global_sd_m=list(stair_rect(fam,l0,end,c0,c0+3.2)),
             run_cm=308.,flight_clear_cm=140.,landing_depth_cm=140.,rises_per_flight=12,total_rises=24,
             rise_cm=RISE,same_floor_landing_global_sd_m=list(stair_rect(fam,l0,run0,c0,c0+3.2)),
             half_landing_global_sd_m=list(stair_rect(fam,run1,end,c0,c0+3.2))))
        for f in range(1,4):
            lo,hi=bounds(voidrect,FLOOR_Z[f]-21,FLOOR_Z[f]+1)
            p['slab_voids'].append(dict(id='F%d_%sStairVoid'%(f,name),floor=f,kind='stair',stair_id=name,world_min=lo,world_max=hi))
        for f in range(3):
            z=FLOOR_Z[f];mid=z+12*RISE
            for i in range(11):
                a=run0+i*.28;b=a+.28;top=z+(i+1)*RISE
                box('%s_F%d_FirstTread%02d'%(name,f,i),'stair_tread',stair_rect(fam,a,b,c0,c0+1.4),top-20,top,'concrete',f,
                    stair_id=name,flight=0,step=i+1,step_top_z_cm=top)
                a=run1-(i+1)*.28;b=a+.28;top=z+(13+i)*RISE
                box('%s_F%d_SecondTread%02d'%(name,f,i),'stair_tread',stair_rect(fam,a,b,c0+1.8,c0+3.2),top-20,top,'concrete',f,
                    stair_id=name,flight=1,step=i+13,step_top_z_cm=top)
            box('%s_F%d_HalfLanding'%(name,f),'landing',stair_rect(fam,run1,end,c0,c0+3.2),mid-20,mid,'concrete',f,stair_id=name)
            # The floor slab preserves the same-floor landing; add a flush visible slab.
            box('%s_F%d_LowerLanding'%(name,f),'landing',stair_rect(fam,l0,run0,c0,c0+3.2),z-20,z,'concrete',f,stair_id=name)
            if f==2:
                box('%s_F3_TopLanding'%name,'landing',stair_rect(fam,l0,run0,c0,c0+3.2),FLOOR_Z[3]-20,FLOOR_Z[3],'concrete',3,stair_id=name)
            pts=[stair_point(fam,l0+.7,c0+.7,z+2),stair_point(fam,run0-.20,c0+.7,z+2)]
            for i in range(11):pts.append(stair_point(fam,run0+(i+.5)*.28,c0+.7,z+(i+1)*RISE+2))
            pts.extend([stair_point(fam,run1+.2,c0+.7,mid+2),stair_point(fam,run1+.7,c0+.7,mid+2),
                        stair_point(fam,run1+.7,c0+2.5,mid+2),stair_point(fam,run1+.2,c0+2.5,mid+2)])
            for i in range(11):pts.append(stair_point(fam,run1-(i+.5)*.28,c0+2.5,z+(13+i)*RISE+2))
            pts.extend([stair_point(fam,run0-.2,c0+2.5,FLOOR_Z[f+1]+2),stair_point(fam,l0+.7,c0+2.5,FLOOR_Z[f+1]+2)])
            row=dict(id='%s_F%d_to_F%d'%(name,f,f+1),stair_id=name,from_floor=f,to_floor=f+1,
                     foot_waypoints=pts,points=pts,width=140.,rise=RISE,rise_cm=RISE,tread=28.,landing_depth=140.,
                     run_cm=308.,risers_per_flight=12,total_risers=24)
            p['stair_routes'].append(row);p['staircases'].append(dict(row))
            # Guardposts are inside the 40cm well, leaving full 140cm flight widths.
            for flight,c in ((0,c0+1.425),(1,c0+1.775)):
                for i in range(11):
                    lng=run0+(i+.5)*.28
                    top=z+(i+1)*RISE if flight==0 else z+(23-i)*RISE
                    r=stair_rect(fam,lng-.025,lng+.025,c-.025,c+.025)
                    box('%s_F%d_Guard%d_%02d'%(name,f,flight,i),'guard',r,top,top+105.,'dark',f)
                    rail=stair_rect(fam,lng-.15,lng+.15,c-.035,c+.035)
                    box('%s_F%d_Handrail%d_%02d'%(name,f,flight,i),'guard',rail,top+99.,top+105.,'green',f)
            # A railing across the open well at both landings prevents a direct drop.
            for k,lng,top in [(0,run0,z),(1,run1,mid)]:
                r=stair_rect(fam,lng-.025,lng+.025,c0+1.4,c0+1.8)
                box('%s_F%d_WellGuard%d'%(name,f,k),'guard',r,top,top+105.,'dark',f)
        # Dedicated approach routes connect public galleries to the first-flight centre.
        for f,z in enumerate(FLOOR_Z):
            if name=='Central':
                sd=[(38.5,7.9),(40.62,7.9),(41.42,7.9),(41.42,7.7)]
            else:
                s=3. if name=='South' else 67.
                sd=[(s,1.3),(s,2.5),(s,3.1),(s,4.5),(c0+.7,4.5)]
            route('F%d_%sFirstFlightApproach'%(f,name),f,'stair_approach',sd)

    # Slab solids are cut into disjoint boxes. Same-floor stair landings survive.
    for f,z in enumerate(FLOOR_Z):
        if f:
            lo,hi=bounds((33.2,7.2,36.2,10.2),z-21,z+1)
            p['slab_voids'].append(dict(id='F%d_LiftVoid'%f,floor=f,kind='lift',world_min=lo,world_max=hi))
        parts=[bounds((.2,.2,69.8,10.2),z-20,z)]
        for hole in [v for v in p['slab_voids'] if v['floor']==f]:
            parts=[q for lo,hi in parts for q in subtract(lo,hi,hole['world_min'],hole['world_max'])]
        for i,(lo,hi) in enumerate(parts):worldbox('F%d_FloorSlab%02d'%(f,i),'floor',lo,hi,'concrete',f)
    box('Roof','roof',(0.,0.,70.,10.4),1480.,1500.,'concrete')
    worldbox('MainEntryCanopy','canopy',[8750.,-150.,270.],[9000.,150.,280.],'concrete',0)
    worldbox('MainEntrySignBacking','sign',[8990.,-150.,300.],[8997.,150.,355.],'green',0,False)

    # Windows: rear rooms and service rooms, front common circulation, side stair light.
    for f in range(4):
        for s in ((8.,16.,24.,45.,53.,58.5) if f==0 else (8.,16.,24.,45.,53.,61.)):
            window('F%d_StreetWindow_%g'%(f,s),f,s,.1,(1,0,0),140.,140.,105.,'gallery')
        window('F%d_CentralStairRearWindow'%f,f,45.65,10.3,(-1,0,0),120.,125.,120.,'stair')
        if f==0:
            for s in (8.8,13.3,17.2,20.8,24.7,48.7,53.1,56.9,60.1,62.6):
                window('GroundRearWindow_%g'%s,0,s,10.3,(-1,0,0),120.,140.,105.,'service')

    # Cut the real wall and dado openings; no painted door or window rectangles.
    cuts=[]
    for row in p['doors']+p['windows']:
        x,y,zz=row['position_cm'];w=row.get('rough_width_cm',row['width']);h=row.get('rough_height_cm',row['height'])
        normal=row['inward'];halfdepth=max(14.,row.get('depth',20.)/2+2.)
        if abs(normal[0])>.5:lo,hi=[x-halfdepth,y-w/2,zz],[x+halfdepth,y+w/2,zz+h]
        else:lo,hi=[x-w/2,y-halfdepth,zz],[x+w/2,y+halfdepth,zz+h]
        row['opening_bounds']=[lo,hi]
        cuts.append((lo,hi))
    for wallrow in walls:
        parts=[(wallrow['world_min'],wallrow['world_max'])]
        for lo,hi in cuts:parts=[q for a,b in parts for q in subtract(a,b,lo,hi)]
        for j,(lo,hi) in enumerate(parts):worldbox(wallrow['id']+'_%02d'%j,'wall',lo,hi,wallrow['material'],wallrow['floor'])
    dados=[r for r in p['boxes'] if r['role']=='wainscot']
    p['boxes']=[r for r in p['boxes'] if r['role']!='wainscot']
    for r in dados:
        parts=[(r['world_min'],r['world_max'])]
        for lo,hi in cuts:parts=[q for a,b in parts for q in subtract(a,b,lo,hi)]
        for j,(lo,hi) in enumerate(parts):worldbox(r['id']+'_%02d'%j,'wainscot',lo,hi,r['material'],r['floor'],False)
    p['review_cameras']=[
        dict(camera='CAM_V4_Exterior',position=[8120.,-500.,330.],look_at=[9010.,0.,220.],fov=75.,lighting_mode='temporary'),
        dict(camera='CAM_V4_Reception',position=world(35.,3.0,175.),look_at=world(35.,7.0,160.),fov=85.,lighting_mode='temporary'),
        dict(camera='CAM_V4_LobbyWide',position=world(39.,3.3,195.),look_at=world(30.6,7.0,145.),fov=85.,lighting_mode='temporary'),
        dict(camera='CAM_V4_PublicWC',position=world(42.1,3.4,160.),look_at=world(44.,5.0,125.),fov=95.,lighting_mode='temporary'),
        dict(camera='CAM_V4_UpperCore',position=world(38.5,3.0,FLOOR_Z[1]+160.),look_at=world(40.5,8.6,FLOOR_Z[1]+150.),fov=90.,lighting_mode='temporary'),
        dict(camera='CAM_V4_TopGallery',position=world(8.,1.3,FLOOR_Z[3]+165.),look_at=world(28.,1.3,FLOOR_Z[3]+165.),fov=80.,lighting_mode='temporary'),
        dict(camera='CAM_V4_GuestTwin',position=world(50.15,4.9,FLOOR_Z[1]+160.),look_at=world(49.125,8.9,FLOOR_Z[1]+100.),fov=80.,lighting_mode='temporary'),
        dict(camera='CAM_V4_CentralStair',position=world(41.42,8.55,180.),look_at=world(44.2,8.5,225.),fov=90.,lighting_mode='temporary'),
        dict(camera='CAM_V4_RearEscape',position=[10580.,1000.,280.],look_at=[10030.,642.,160.],fov=80.,lighting_mode='temporary')]
    return p


def validate_plan(p,check_routes=True):
    errors=[];checks=0
    def check(value,label):
        nonlocal checks
        checks+=1
        if not value:errors.append(label)
    check(len(p['rooms'])==27,'room_count')
    check([sum(r['floor']==f for r in p['rooms']) for f in range(4)]==[0,9,9,9],'room_distribution')
    for field in ('boxes','doors','windows','props','rooms','routes','stair_routes'):
        ids=[r['id'] for r in p[field]]
        check(len(ids)==len(set(ids)),'duplicate_'+field)
    check(len(p['stair_routes'])==9,'stair_connections')
    for family in ('South','North','Central'):
        check(sorted((r['from_floor'],r['to_floor']) for r in p['stair_routes'] if r['stair_id']==family)==[(0,1),(1,2),(2,3)],'stair_continuity_'+family)
    check(len(p['shafts'])==4,'shaft_count')
    check(len(p['slab_voids'])==12,'slab_void_count')
    for hole in p['slab_voids']:
        for b in p['boxes']:
            if b['role']!='floor' or b['floor']!=hole['floor']:continue
            overlap=all(min(b['world_max'][i],hole['world_max'][i])-max(b['world_min'][i],hole['world_min'][i])>.001 for i in range(3))
            check(not overlap,'slab_void_filled:'+hole['id']+':'+b['id'])
    for row in p['boxes']:
        check(all(row['world_max'][i]>row['world_min'][i] for i in range(3)),'degenerate_box:'+row['id'])
    # Ordinary routes test actual fixed boxes and explicit fixture envelopes.
    if check_routes:
        obstacles=[b for b in p['boxes'] if b['collision'] and b['role'] not in ('floor','exterior_floor','roof','stair_tread','landing')]
        for prop in p['props']:
            obstacles.extend(dict(id=prop['id'],world_min=lo,world_max=hi) for lo,hi in prop['collision_boxes'])
        for row in p['routes']:
            for start,end in zip(row['points'],row['points'][1:]):
                n=max(1,math.ceil(math.dist(start,end)/15.))
                for step in range(n+1):
                    foot=[start[i]+(end[i]-start[i])*step/n for i in range(3)]
                    for b in obstacles:
                        lo,hi=b['world_min'],b['world_max']
                        if hi[2]<=foot[2] or lo[2]>=foot[2]+180.:continue
                        dx=max(lo[0]-foot[0],0.,foot[0]-hi[0]);dy=max(lo[1]-foot[1],0.,foot[1]-hi[1])
                        if dx>=34. or dy>=34.:continue
                        if math.hypot(dx,dy)<33.99:
                            e='route_obstruction:'+row['id']+':'+b['id']
                            if e not in errors:errors.append(e)
    return dict(passed=not errors,errors=errors,checks=checks,rooms=len(p['rooms']),
                boxes=len(p['boxes']),doors=len(p['doors']),windows=len(p['windows']),
                props=len(p['props']),routes=len(p['routes']),stair_connections=len(p['stair_routes']),
                scope='Pure geometry checks; saved Unreal support/collision and opening states require separate audit.')


if __name__=='__main__':
    plan=build_plan()
    report=validate_plan(plan)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
