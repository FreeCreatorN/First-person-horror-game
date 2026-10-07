import bpy, math, os, json
from mathutils import Vector, Quaternion
__file__=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword\create_reference_sword.py'
OUT=os.path.dirname(__file__)
# Reuse only the materials and primitive helpers; build an entirely new sword.
src=open(os.path.join(OUT,'create_sword.py'),encoding='utf-8-sig').read()
exec(src.split('# Diamond cross section:')[0])
root.name='SWORD_CONTROL | reference design'; root.location=(0,0,.79)
wood.diffuse_color=(.23,.082,.035,1)
ramp=next(n for n in wood.node_tree.nodes if n.type=='VALTORGB')
ramp.color_ramp.elements[0].color=(.028,.007,.003,1)
ramp.color_ramp.elements[1].color=(.28,.105,.042,1)
carving=mat('Carved warm wood relief',(.21,.081,.033),0,.5)
groove=mat('Recessed carving shadow',(.035,.010,.004),0,.7)
cord=mat('Dark brown woven grip',(.034,.017,.011),0,.84)
nt=cord.node_tree; pp=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
no=nt.nodes.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value=180; no.inputs['Detail'].default_value=2
bu=nt.nodes.new('ShaderNodeBump'); bu.inputs['Strength'].default_value=.5; bu.inputs['Distance'].default_value=.0007
nt.links.new(no.outputs['Fac'],bu.inputs['Height']); nt.links.new(bu.outputs[0],pp.inputs['Normal'])
red.node_tree.nodes
next(n for n in red.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(.24,.005,.009,1)
def cylinder(name,loc,radius,depth,material,vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc,rotation=(math.pi/2,0,0))
    o=bpy.context.object; o.name=name; o.parent=root; o.data.materials.append(material); bevel(o,.0005); return o
def ring(name,x,z,r,y,material,width=.0008,n=96):
    return curve(name,[(x+r*math.cos(i*math.tau/n),y,z+r*math.sin(i*math.tau/n)) for i in range(n+1)],width,material)
def smooth_outline(points,steps=6):
    result=[]
    for i in range(len(points)):
        p0,p1,p2,p3=[Vector(points[j%len(points)]) for j in [i-1,i,i+1,i+2]]
        for s in range(steps):
            t=s/steps
            p=.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
            result.append(tuple(p))
    return result
def extrude_outline(name,outline,depth,material):
    count=len(outline); vs=[(x,y,z) for y in [-depth/2,depth/2] for x,z in outline]
    fs=[tuple(range(count-1,-1,-1)),tuple(range(count,count*2))]+[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    ob=mesh(name,vs,fs,material); bevel(ob,.0015); return ob
# Broad flat faces and beveled wood edges. Tip to pommel measures 1.015 m.
v=[]
for z,w,t in [(-.735,.0005,.001),(-.692,.021,.005),(-.13,.027,.007),(-.018,.029,.008)]:
    v.extend([(-w,0,z),(-w*.76,-t,z),(w*.76,-t,z),(w,0,z),(w*.76,t,z),(-w*.76,t,z)])
f=[tuple(range(5,-1,-1))]
for row in range(3):
    for j in range(6):f.append((row*6+j,row*6+(j+1)%6,(row+1)*6+(j+1)%6,(row+1)*6+j))
f.append(tuple(range(18,24)))
blade=mesh('Peachwood blade | broad engraved face',v,f,wood); bevel(blade,.0006)
# Scalloped cloud guard, continuous center and matching wooden pommel.
outline=smooth_outline([(-.024,.024),(-.040,.016),(-.068,.024),(-.084,.017),(-.087,-.001),(-.075,-.016),(-.058,-.009),(-.036,-.013),(-.019,-.026),(0,-.029),(.019,-.026),(.036,-.013),(.058,-.009),(.075,-.016),(.087,-.001),(.084,.017),(.068,.024),(.040,.016),(.024,.024),(0,.032)])
guard=extrude_outline('Cloud silhouette carved crossguard',outline,.031,wood)
cube('Handle wood core',(0,0,.123),(.029,.024,.202),wood)
for z in [.03,.211]:
    cylinder('Wood handle collar',(0,0,z),.018,.029,wood).rotation_euler=(0,0,0)
    # Cylinder height must follow the grip axis.
    o=bpy.context.object; o.scale.z=.19
sphere('Round cloud-carved pommel',(0,0,.249),(.031,.018,.031),wood)
for side in [-1,1]:
    y=side*.0167
    curve('Guard inset outline',[(x*.944,y,z*.83) for x,z in outline]+[(outline[0][0]*.944,y,outline[0][1]*.83)],.00065,carving)
    ring('Pommel carved border',0,.249,.025,side*.015,carving,.001)
def spiral(cx,cz,scale,y,mirror=1):
    pts=[]
    for i in range(100):
        t=i/99; a=t*math.pi*3.4; r=scale*(1-.87*t)
        pts.append((cx+mirror*r*math.cos(a),y,cz+r*math.sin(a)))
    curve('Cloud scroll recessed line',pts,.00105,groove)
    curve('Cloud scroll raised edge',[(x,y-.00025 if y<0 else y+.00025,z+.0015) for x,y,z in pts],.00065,carving)
for side in [-1,1]:
    for sign in [-1,1]:
        spiral(sign*.064,.003,.010,side*.017,sign)
        spiral(sign*.038,.006,.007,side*.017,sign)
        spiral(sign*.013,.254,.009,side*.018,sign)
    spiral(0,.238,.007,side*.019)
def bagua(cx,cz,r,y):
    side=1 if y>0 else -1
    cylinder('Bagua recessed medallion',(cx,y-side*.001,cz),r,.0015,groove,8)
    ring('Bagua octagonal rim',cx,cz,r,y,carving,.00075,8)
    ring('Bagua inner octagon',cx,cz,r*.66,y,carving,.0005,8)
    ring('Taiji round border',cx,cz,r*.49,y,carving,.0006)
    # Yin-yang half: right outer semicircle and alternating inner semicircles.
    rr=r*.455
    pts=[]
    for i in range(41):
        a=math.pi/2-i*math.pi/40; pts.append((cx+rr*math.cos(a),y,cz+rr*math.sin(a)))
    for i in range(31):
        a=-math.pi/2-i*math.pi/30; pts.append((cx+rr/2*math.cos(a),y,cz-rr/2+rr/2*math.sin(a)))
    for i in range(31):
        a=-math.pi/2+i*math.pi/30; pts.append((cx+rr/2*math.cos(a),y,cz+rr/2+rr/2*math.sin(a)))
    mesh('Taiji light lobe',pts,[tuple(range(len(pts)))],carving)
    cylinder('Yin eye',(cx,y+side*.0006,cz+rr/2),rr*.16,.0008,groove,24)
    cylinder('Yang eye',(cx,y+side*.0006,cz-rr/2),rr*.16,.0008,carving,24)
    patterns=[(1,1,1),(0,1,1),(0,1,0),(0,0,1),(0,0,0),(1,0,0),(1,0,1),(1,1,0)]
    for k,bits in enumerate(patterns):
        a=k*math.tau/8; radial=Vector((math.sin(a),math.cos(a))); tangent=Vector((math.cos(a),-math.sin(a)))
        for j,bit in enumerate(bits):
            center=Vector((cx,cz))+radial*r*(.72+.09*j)
            segments=[(-.24,.24)] if bit else [(-.24,-.065),(.065,.24)]
            for lo,hi in segments:
                p=center+tangent*r*lo; q=center+tangent*r*hi
                curve('Bagua trigram cut',[(p.x,y,p.y),(q.x,y,q.y)],r*.020,carving)
for side in [-1,1]:
    bagua(0,.001,.025,side*.0185)
    bagua(0,-.126,.012,side*.0082)
    # Flowing cloud engravings beneath the small blade medallion.
    for cx,cz,sz in [(-.003,-.078,.008),(.003,-.17,.009),(-.002,-.205,.007)]:spiral(cx,cz,sz,side*.0079)
    for s in [-1,1]:curve('Long cloud engraving',[(s*(.003+.003*math.sin(i/50*math.pi*3)),side*.0075,-.206-i/50*.062) for i in range(51)],.00065,groove)
# Wide criss-cross winding, plus fine thread ridges following each strip.
for sign in [-1,1]:
    verts=[]; faces=[]; turns=10.5; count=840
    for i in range(count+1):
        t=i/count; a=sign*t*math.tau*turns
        rr=.0006*math.sin(a*2)
        for w in [-.0039,.0039]:verts.append(((.017+rr)*math.cos(a),(.014+rr)*math.sin(a),.043+t*.155+w))
        if i<count:faces.append((2*i,2*i+1,2*i+3,2*i+2))
    ob=mesh('Cross woven grip wrap',verts,faces,cord); so=ob.modifiers.new('Cord band body','SOLIDIFY'); so.thickness=.0008
    for offset in [-.0028,-.0014,0,.0014,.0028]:
        curve('Grip thread ridge',[((.0177+.0006*math.sin(sign*i/count*math.tau*turns*2))*math.cos(sign*i/count*math.tau*turns),(.0147+.0006*math.sin(sign*i/count*math.tau*turns*2))*math.sin(sign*i/count*math.tau*turns),.043+i/count*.155+offset) for i in range(count+1)],.00022,cord)
# Side-hanging braided cord and woven auspicious knot.
def braid(name,path,r=.0018):
    curve(name,path,r,red)
    for strand in range(3):
        curve(name+' twist',[(x+r*.72*math.cos(i*.72+strand*math.tau/3),y+r*.72*math.sin(i*.72+strand*math.tau/3),z) for i,(x,y,z) in enumerate(path)],r*.32,red)
braid('Pommel suspension cord',[(.008+.070*t/100,-.002,.273-.084*t/100+.025*math.sin(math.pi*t/100)) for t in range(101)],.002)
kx=.080; kz=.158
for j in range(4):
    for sign in [-1,1]:
        path=[]
        for i in range(80):
            t=i/79; u=-.014+t*.028; zz=(j-1.5)*.006
            x=(u+zz)*.707; z=(u-zz)*.707*sign
            path.append((kx+x,-.006+.002*math.sin(t*math.pi*7+j*math.pi),kz+z))
        braid('Chinese knot interlace',path,.0017)
for a in [0,math.pi/2,math.pi,math.pi*1.5]:
    for shift in [-.25,.25]:
        aa=a+shift
        path=[]
        for i in range(81):
            t=i/80*math.tau
            u=.014+.010*(1-math.cos(t)); w=.005*math.sin(t)
            path.append((kx+u*math.sin(aa)+w*math.cos(aa),-.004,kz+u*math.cos(aa)-w*math.sin(aa)))
        braid('Chinese knot outer loop',path,.0016)
braid('Knot lower tie',[(kx,-.005,kz-.023-i*.0005) for i in range(31)],.002)
sphere('Polished redwood bead',(kx,-.005,.109),(.009,.009,.010),dark)
sphere('Bound tassel crown',(kx,-.005,.089),(.009,.008,.012),red)
for z in [.083+i*.0014 for i in range(8)]:
    curve('Tassel wound collar',[(kx+.009*math.cos(i*math.tau/64),-.005+.008*math.sin(i*math.tau/64),z) for i in range(65)],.0008,red)
v=[]; f=[]; pins=[]
for k in range(96):
    a=k*math.tau/96; radius=.003+(k%5)*.0014; length=.29+.01*math.sin(k*2.399); base=len(v)
    for row in range(25):
        t=row/24; rr=radius+.007*t
        for s in [-1,1]:v.append((kx+rr*math.cos(a)+s*.00042*math.cos(a+.6),-.005+rr*math.sin(a)+s*.00042*math.sin(a+.6),.081-length*t))
        if row<2:pins.extend([base+row*2,base+row*2+1])
        if row<24:f.append((base+row*2,base+row*2+1,base+row*2+3,base+row*2+2))
tassel=mesh('TASSEL | 96 physical silk strands',v,f,red)
vg=tassel.vertex_groups.new(name='Pinned knot attachment'); vg.add(pins,1,'REPLACE')
cl=tassel.modifiers.new('Silk dynamics','CLOTH'); st=cl.settings
st.quality=8; st.mass=.025; st.vertex_group_mass=vg.name; st.tension_stiffness=22; st.compression_stiffness=22; st.shear_stiffness=10; st.bending_stiffness=.06; st.air_damping=3
cl.collision_settings.use_self_collision=False; cl.point_cache.frame_end=160
so=tassel.modifiers.new('Silk strand thickness','SOLIDIFY'); so.thickness=.00025
for frame,ang in [(1,0),(22,0),(48,-16),(77,19),(105,-12),(132,6),(160,0)]:
    root.rotation_euler[1]=math.radians(ang); root.keyframe_insert(data_path='rotation_euler',frame=frame)
# Preserve a separate full-height scale reference from the previous asset.
with bpy.data.libraries.load(os.path.join(OUT,'PeachwoodSword.blend'),link=False) as (a,b):b.collections=[name for name in a.collections if name.startswith('REFERENCE')]
for collection in b.collections:
    if collection:
        scene.collection.children.link(collection)
        for o in collection.objects:o.hide_render=True
cube('Studio floor',(0,0,-.025),(200,200,.04),floor,None)
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(.8,-3.3,1.4)); cam=bpy.context.object; cam.name='Camera | reference sword'; aim(cam,(.025,0,.56)); cam.data.type='ORTHO'; cam.data.ortho_scale=1.18; scene.camera=cam
for name,loc,power,size in [('Key',(-2,-3,3),210,2),('Rim',(1,1,2.4),320,1.7),('Fill',(2,-1,1),65,1.5)]:
    bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; aim(o,(0,0,.6))
scene.world.color=(.14,.14,.14)
scene.render.resolution_x=1100; scene.render.resolution_y=1500; scene.cycles.samples=40
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT'); root.select_set(True); bpy.context.view_layer.objects.active=root
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active; sp.overlay.show_relationship_lines=False; sp.overlay.show_extras=False
            sp.region_3d.view_location=(.02,0,.57); sp.region_3d.view_distance=1.45
            sp.region_3d.view_rotation=Quaternion((1,0,0),math.pi/2)
            sp.shading.color_type='MATERIAL'
scene['README']='Reference-style peachwood sword. 1.015 m overall; 1.8 m adult scale reference. Play frames 1-160; physical silk roots pinned to knot. Knot and suspension cord are fixed decorations. Unreal runtime physics requires separate setup.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'PeachwoodSword_Reference.blend'))
positions={}
for frame in range(1,161):
    scene.frame_set(frame)
    if frame in [1,77,132]:
        ev=tassel.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh(); positions[frame]=list(me.vertices[49].co); ev.to_mesh_clear()
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.bake_from_cache()
assert abs(positions[77][0]-positions[1][0])>.025
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'PeachwoodSword_Reference.blend'))
with open(os.path.join(OUT,'reference_verification.json'),'w') as file:json.dump({'positions':positions,'baked':cl.point_cache.is_baked,'overall_m':1.015,'silk_strands':96},file,indent=2)
scene.render.filepath=os.path.join(OUT,'Reference_Preview.png'); bpy.ops.render.render(write_still=True)
cam.location=(.25,-.8,1.12); aim(cam,(.025,0,.915)); cam.data.ortho_scale=.38
scene.render.resolution_x=1400; scene.render.resolution_y=1200
scene.render.filepath=os.path.join(OUT,'Reference_Detail.png'); bpy.ops.render.render(write_still=True)
cam.location=(.8,-3.3,1.4); aim(cam,(.025,0,.56)); cam.data.ortho_scale=1.18
scene.frame_set(1)
result={'file':bpy.data.filepath,'physics_baked':cl.point_cache.is_baked,'strand_positions':positions}

