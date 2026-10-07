"""Independent component parts, closed states and real hinge pivots, in cm."""
ASSET_ROOT='/Game/Yastar/Meshes/hOUSE/HotelOpenings_20261004'
CUBE='/Engine/BasicShapes/Cube.Cube'

def mesh_key(kind,w,h):
    return 'SM_OTS_'+kind+'_'+str(round(w*10))+'_'+str(round(h*10))

def component(name,parent,asset=None,location=None,rotation=None,scale=None,collision=False,hidden=False):
    row={'name':name,'parent':parent,'class':'StaticMeshComponent' if asset else 'SceneComponent',
         'asset':asset,'relative_location':location or [0.,0.,0.],
         'relative_rotation':rotation or [0.,0.,0.], 'relative_scale':scale or [1.,1.,1.],
         'mobility':'MOVABLE','collision':'QUERY_AND_PHYSICS' if collision else 'NO_COLLISION','hidden':hidden}
    return row

def collision_box(name,parent,center,size):
    return component(name,parent,CUBE,center,scale=[s/100. for s in size],collision=True,hidden=True)

def door_specs(width,height,side,depth=20.,center_depth=10.):
    rows=[component('OpeningRoot',None)]
    asset=lambda k:ASSET_ROOT+'/'+mesh_key(k,width,height)
    rows.append(component('FixedFrame','OpeningRoot',asset('DoorFrame'),[0,center_depth,0],scale=[1,depth/5.,1]))
    top_inset=2. if height<200 else 4.
    for name,x in (('FrameLeftCollision',-width/2+2),('FrameRightCollision',width/2-2)):
        rows.append(collision_box(name,'OpeningRoot',[x,center_depth,(height-top_inset)/2],[4,depth,height-top_inset]))
    rows.append(collision_box('FrameTopCollision','OpeningRoot',[0,center_depth,height-top_inset/2],[width,depth,top_inset]))
    edge=side*(width/2-4.4);length=width-8.8;direction=-side
    rows.append(component('DoorHinge','OpeningRoot',location=[edge,center_depth+depth/2-.5,0],rotation=[0,-side*90,0]))
    rows.append(component('DoorLeaf','DoorHinge',asset('DoorLeaf'),scale=[direction,1,1]))
    rows.append(component('Handle','DoorHinge',asset('DoorHandle'),scale=[direction,1,1]))
    rows.append(collision_box('LeafCollision','DoorHinge',[direction*length/2,0,(height-4)/2],[length,4,height-5.2]))
    for r in rows:
        if r['parent'] in (None,'OpeningRoot') and r['name']!='DoorHinge':r['mobility']='STATIC'
    return rows

def window_specs(width,height,depth=20.):
    rows=[component('OpeningRoot',None)]
    asset=lambda k:ASSET_ROOT+'/'+mesh_key(k,width,height)
    rows.append(component('FixedFrame','OpeningRoot',asset('WindowFrame'),[0,depth/2,0],scale=[1,depth/3.5,1]))
    for name,x in (('FrameLeftCollision',-width/2+2),('FrameRightCollision',width/2-2)):
        rows.append(collision_box(name,'OpeningRoot',[x,depth/2,height/2],[4,depth,height]))
    for name,z in (('FrameBottomCollision',2),('FrameTopCollision',height-2)):
        rows.append(collision_box(name,'OpeningRoot',[0,depth/2,z],[width-8,depth,4]))
    length=(width-8)/2-.5;edge=(width-8)/2-.3
    for name,side in (('Left',-1),('Right',1)):
        hinge=name+'Hinge';direction=-side
        rows.append(component(hinge,'OpeningRoot',location=[side*edge,depth-.5,0]))
        rows.append(component(name+'Sash',hinge,asset('WindowSash'),scale=[direction,1,1]))
        rows.append(component(name+'Glass',hinge,asset('WindowGlass'),scale=[direction,1,1]))
        rows.append(collision_box(name+'PaneCollision',hinge,[direction*length/2,0,height/2],[length,3.5,height-8.6]))
    for r in rows:
        if r['parent'] in (None,'OpeningRoot') and r['name'] not in ('LeftHinge','RightHinge'):r['mobility']='STATIC'
    return rows
