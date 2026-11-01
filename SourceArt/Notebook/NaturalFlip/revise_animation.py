"""A corner-led flexible sheet turn, retaining the shipped mesh and skeleton.

The 9 cross-sections follow an inextensible centerline with a delayed free edge.
Director twist lifts a corner first. Contact projects the actual weighted mesh,
including its thickness, above both existing paper stacks. This is authored
deformation baked to the existing bones, not a claim of live cloth simulation.
"""
import bpy,math,json,hashlib
import numpy as np
from mathutils import Vector
from pathlib import Path
HERE=Path(__file__).resolve().parent;OUT=HERE.parent
BEFORE=HERE/'Before'/'Source'
bpy.ops.wm.open_mainfile(filepath=str(BEFORE/'Notebook.blend'))
s=bpy.context.scene;rig=bpy.data.objects['Armature'];mesh=bpy.data.objects['SK_Notebook']
report=json.loads((BEFORE/'model_report.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometry_hash():
    blob=bytearray()
    for v in mesh.data.vertices:blob.extend(np.asarray(v.co,dtype=np.float32).tobytes())
    for p in mesh.data.polygons:blob.extend(np.asarray(list(p.vertices)+[p.material_index],dtype=np.int32).tobytes())
    for uv in mesh.data.uv_layers[0].data:blob.extend(np.asarray(uv.uv,dtype=np.float32).tobytes())
    return hashlib.sha256(blob).hexdigest()
geometry_before=geometry_hash()
old_action=rig.animation_data.action
endpoints={}
for page in range(16):
    names=[f'Page_{page+1:02d}_{j:02d}' for j in range(9)]
    item={'names':names,'heads':np.array([rig.data.bones[n].head_local[:] for n in names]),'poses':[]}
    for frame in (71+40*page,99+40*page):
        s.frame_set(frame);bpy.context.view_layer.update()
        item['poses'].append({n:(rig.pose.bones[n].location.copy(),rig.pose.bones[n].rotation_euler.copy()) for n in names})
    # Gather exactly the vertices affected by this leaf; each has at most 2 weights.
    gids={mesh.vertex_groups[n].index:j for j,n in enumerate(names)}
    vertices=[];weights=[]
    for v in mesh.data.vertices:
        ww=np.zeros(9)
        for g in v.groups:
            if g.group in gids:ww[gids[g.group]]=g.weight
        if ww.sum()>.99:vertices.append(v.co[:]);weights.append(ww)
    item['vertices']=np.asarray(vertices);item['weights']=np.asarray(weights)
    item['relative']=item['vertices'][:,None,:]-item['heads'][None,:,:]
    endpoints[page]=item
new_action=old_action.copy();new_action.name='A_Notebook_NaturalFlip'
rig.animation_data.action=new_action
rig.animation_data.action_slot=new_action.slots[0]
def S(t):
    t=max(0.,min(1.,t));return t*t*t*(10+t*(-15+6*t))
def bell(t,a,b):
    return math.sin(math.pi*(t-a)/(b-a))**2 if a<t<b else 0.
W=.142;THICK=.00028
def angles(u,t,page):
    variation=1+.045*math.sin(page*1.71)
    main=-math.pi*S((t-.10)/.78)
    # Edge curls first, lags the accelerated bound edge, then relaxes onto the stack.
    delta=variation*(-.70*bell(t,0,.34)+1.05*bell(t,.18,.94)+.045*bell(t,.88,1))
    theta=main+delta*u**1.6
    phi=(-.070*bell(t,0,.50)+.040*bell(t,.58,1))*u*u*(1+.06*math.sin(page*2.11))
    return theta,phi
def matrices(theta,phi):
    c=math.cos(theta);ss=math.sin(theta);p=math.cos(phi);q=math.sin(phi)
    return np.array([[c,ss*q,ss*p],[0,p,-q],[-ss,c*q,c*p]])
def deform(item,C,R):
    transformed=np.einsum('bkj,vbj->vbk',R,item['relative'])+C[None,:,:]
    return (transformed*item['weights'][:,:,None]).sum(axis=1)
def floors(page,xyz):
    # Only existing sheets are obstacles. The moving leaf is excluded.
    right=.0089-(page+1)*.00032+THICK/2 if page<15 else .00355
    left=.00395+(page-1)*.00032+THICK/2 if page>0 else .00355
    x=xyz[:,0];y=xyz[:,1]
    h=np.where(x>=0,right,left)
    h=np.where(np.abs(x)>.1435,.00355,h)
    valid=(np.abs(x)>.004)&(np.abs(x)<.15)&(np.abs(y)<.106)
    return h,valid
records=[]
def sheet_pose(page,t):
    item=endpoints[page];heads=item['heads']
    zstart=heads[0,2];zend=.00395+page*.00032
    base=zstart+(zend-zstart)*S((t-.23)/.54)
    root_angle,_=angles(0,t,page)
    x=.0015*math.cos(root_angle);z=base-.0015*math.sin(root_angle)
    C=[];R=[];eulers=[]
    for j in range(9):
        u=j/8
        if j:
            for sub in range(24):
                q=((j-1)+(sub+.5)/24)/8;theta,_=angles(q,t,page)
                ds=W/8/24;x+=ds*math.cos(theta);z-=ds*math.sin(theta)
        theta,phi=angles(u,t,page);C.append([x,0,z]);R.append(matrices(theta,phi));eulers.append((phi,theta,0))
    C=np.asarray(C);R=np.asarray(R)
    xyz=deform(item,C,R);h,valid=floors(page,xyz)
    deficits=np.where(valid,np.maximum(0,h+.000005-xyz[:,2]),0)
    largest=float(deficits.max())
    if largest>0:
        ww=item['weights'];norm=(ww*ww).sum(axis=1)
        lift=(ww*(deficits/np.maximum(norm,1e-9))[:,None]).max(axis=0)
        # Spread local contact adjustments upward, without lowering any safe point.
        for _ in range(2):
            lift=np.maximum(lift,np.r_[lift[1:]*.55,0]);lift=np.maximum(lift,np.r_[0,lift[:-1]*.55])
        C[:,2]+=lift
    xyz=deform(item,C,R);h,valid=floors(page,xyz)
    penetration=float(np.maximum(0,h[valid]-xyz[valid,2]).max(initial=0))
    records.append({'leaf':page+1,'phase':t,'contact_lift_mm':largest*1000,'penetration_mm':penetration*1000})
    assert penetration<.000002,(page,t,penetration)
    return C,R,eulers
# Preserve all cover/spine keys and all flat page keys outside the active turn.
bags=[bag for layer in new_action.layers for strip in layer.strips for bag in strip.channelbags]
for page in range(16):
    start=71+40*page;end=107+40*page;names=endpoints[page]['names']
    for bag in bags:
        for curve in bag.fcurves:
            if any(curve.data_path.startswith(f'pose.bones["{n}"]') for n in names):
                for k in reversed(list(curve.keyframe_points)):
                    if start<=k.co.x<=end:curve.keyframe_points.remove(k,fast=True)
                curve.update()
    for frame in range(start,end+1):
        t=(frame-start)/(end-start)
        if frame in (start,end):
            sample=endpoints[page]['poses'][0 if frame==start else 1]
            for n in names:rig.pose.bones[n].location=sample[n][0];rig.pose.bones[n].rotation_euler=sample[n][1]
        else:
            C,R,eulers=sheet_pose(page,t)
            for j,n in enumerate(names):
                pb=rig.pose.bones[n];pb.location=Vector(C[j]-endpoints[page]['heads'][j]);pb.rotation_euler=eulers[j]
        for n in names:
            pb=rig.pose.bones[n]
            pb.keyframe_insert(data_path='location',frame=frame,group=n)
            pb.keyframe_insert(data_path='rotation_euler',frame=frame,group=n)
for bag in bags:
    for curve in bag.fcurves:
        for k in curve.keyframe_points:k.interpolation='LINEAR'
if old_action.users==0:bpy.data.actions.remove(old_action)
new_action.name='A_Notebook_FullCycle'
# Add informative source checks at non-flat pickup, roll-over and landing phases.
for page in (0,7,15):
    for phase,offset in [('Pickup',6),('Rollover',20),('Landing',32)]:
        report['markers'][f'Natural_{page+1:02d}_{phase}']={'frame':71+40*page+offset,'bones':[f'Page_{page+1:02d}_{j:02d}' for j in (0,4,8)]}
report['source_marker_bone_locations_cm']={};report['source_marker_bone_normals']={}
for label,marker in report['markers'].items():
    s.frame_set(marker['frame']);bpy.context.view_layer.update();locs={};normals={}
    for n in marker['bones']:
        matrix=rig.pose.bones[n].matrix;v=matrix.translation;normal=(matrix.to_3x3()@Vector((0,0,1))).normalized()
        locs[n]=[v.x*100,-v.y*100,v.z*100];normals[n]=[normal.x,-normal.y,normal.z]
    report['source_marker_bone_locations_cm'][label]=locs;report['source_marker_bone_normals'][label]=normals
# Evaluate the actual saved LBS at half frames too, to catch interpolation clipping.
half_penetration=0.
for page,item in endpoints.items():
    for tick in range(73):
        frame=71+40*page+tick*.5;s.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update()
        C=np.array([rig.pose.bones[n].matrix.translation[:] for n in item['names']])
        R=np.array([np.array(rig.pose.bones[n].matrix.to_3x3()) for n in item['names']])
        xyz=deform(item,C,R);h,valid=floors(page,xyz)
        penetration=float(np.maximum(0,h[valid]-xyz[valid,2]).max(initial=0));half_penetration=max(half_penetration,penetration)
assert half_penetration<.00003,('LBS between-frame clipping',half_penetration)
assert geometry_hash()==geometry_before,'Geometry or UV changed'
report['animation_revision']='NaturalFlip v2: corner pickup, delayed flexible edge, contact-limited landing'
report['page_turn_frames']=36;report['max_vertex_influences']=2
for clip in report['clips']:
    if clip['name'].startswith('A_Notebook_Turn'):
        clip['frame_end']=clip['frame_start']+36;clip['seconds']=1.2
report['animation_validation']={'geometry_uv_hash':geometry_before,'geometry_unchanged':True,'max_contact_projection_mm':max(r['contact_lift_mm'] for r in records),'max_sampled_penetration_mm':half_penetration*1000,'turn_seconds':1.2,'same_skeleton_bones':len(rig.data.bones),'contact_samples':len(records),'half_frame_samples':16*73}
# Ensure texture references still point at the main source folder, not its backup.
for img in bpy.data.images:
    if img.source=='FILE' and img.filepath:
        name=Path(bpy.path.abspath(img.filepath)).name
        if (OUT/'Textures'/name).is_file():img.filepath='//Textures/'+name
s.frame_set(1);s.frame_start=1;s.frame_end=781
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Notebook.blend'),relative_remap=False)
report['files']['Notebook.blend']=sha(OUT/'Notebook.blend')
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(HERE/'motion_validation.json').write_text(json.dumps({'success':True,**report['animation_validation'],'per_frame_contact':records},indent=2),encoding='utf-8')
print('NOTEBOOK_NATURAL_MOTION_VERIFIED',report['animation_validation'],flush=True)
