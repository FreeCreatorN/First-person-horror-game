"""DL envelope set: closed, truly open pocket, and independently movable paper."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\Envelope\Replacement');rng=random.Random(2108)
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
export_col=bpy.data.collections.new('UE meshes - canonical origins');s.collection.children.link(export_col)
source_col=bpy.data.collections.new('SOURCE - individual paper folds');s.collection.children.link(source_col)
display_col=bpy.data.collections.new('Envelope set - display assembly');s.collection.children.link(display_col)
PAPER=.00028;FRONT=.00028;OPEN_HEIGHT=.004;CLOSED_HEIGHT=.0015

def shader(name,color,rough=.88,variation=.14):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    ns=m.node_tree.nodes;ls=m.node_tree.links;ns.clear()
    p=ns.new('ShaderNodeBsdfPrincipled');p.inputs['Metallic'].default_value=0;p.inputs['Specular IOR Level'].default_value=.22
    out=ns.new('ShaderNodeOutputMaterial');ls.new(p.outputs['BSDF'],out.inputs['Surface'])
    co=ns.new('ShaderNodeAttribute');co.attribute_name='PaperCoord'
    tone=ns.new('ShaderNodeAttribute');tone.attribute_name='PaperTone'
    broad=ns.new('ShaderNodeTexNoise');ls.new(co.outputs['Vector'],broad.inputs['Vector']);broad.inputs['Scale'].default_value=190;broad.inputs['Detail'].default_value=3
    ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.12;ramp.color_ramp.elements[0].color=(*(v*(1-variation) for v in color),1)
    ramp.color_ramp.elements[1].position=.86;ramp.color_ramp.elements[1].color=(*(v*(1+variation) for v in color),1);ls.new(broad.outputs['Fac'],ramp.inputs[0])
    scale=ns.new('ShaderNodeVectorMath');scale.operation='SCALE';ls.new(ramp.outputs[0],scale.inputs[0]);ls.new(tone.outputs['Fac'],scale.inputs['Scale']);ls.new(scale.outputs[0],p.inputs['Base Color'])
    fine=ns.new('ShaderNodeTexNoise');ls.new(co.outputs['Vector'],fine.inputs['Vector']);fine.inputs['Scale'].default_value=8500;fine.inputs['Detail'].default_value=2
    bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.20 if variation>.02 else .10;bump.inputs['Distance'].default_value=.000028 if variation>.02 else .000008
    ls.new(fine.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs['Normal'],p.inputs['Normal'])
    roughnode=ns.new('ShaderNodeMapRange');ls.new(broad.outputs['Fac'],roughnode.inputs['Value']);roughnode.inputs['To Min'].default_value=rough-.035;roughnode.inputs['To Max'].default_value=rough+.035;ls.new(roughnode.outputs[0],p.inputs['Roughness'])
    return m

outer=shader('M_Kraft_Outer',(.29,.150,.055))
inner=shader('M_Kraft_Inner',(.23,.112,.037),.91)
edge=shader('M_Kraft_Edge',(.115,.050,.014),.94,.10)
gum=shader('M_Kraft_Gum',(.20,.128,.044),.84,.07)
white=shader('M_Letter_Paper',(.82,.82,.80),.86,.012)

def smooth(v):v=max(0,min(1,v));return v*v*(3-2*v)
def signed_distance(poly,x,y):
    return min(((b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]))/math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(poly,poly[1:]+poly[:1]))
def outline_samples(points,steps=12):
    return [(a[0]+(b[0]-a[0])*j/steps,a[1]+(b[1]-a[1])*j/steps) for a,b in zip(points,points[1:]+points[:1]) for j in range(steps)]
def rounded_rect(w,h,r=.0008):
    ps=[]
    for cx,cy,degrees in ((w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)):
        for j in range(9):
            a=math.radians(degrees+90*j/8);ps.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return ps

def sheet(name,outline,top_function,thickness=PAPER,top_mat=outer,bottom_mat=inner,tone=1,bevel=.000065):
    count=len(outline);cx=sum(x for x,y in outline)/count;cy=sum(y for x,y in outline)/count
    radii=(.20,.40,.60,.76,.87,.93,.97,.985,1.)
    xy=[(cx,cy)]+[(cx+(x-cx)*r,cy+(y-cy)*r) for r in radii for x,y in outline]
    verts=[(x,y,top_function(x,y)) for x,y in xy]+[(x,y,top_function(x,y)-thickness) for x,y in xy]
    n=len(xy);top=[(0,1+j,1+(j+1)%count) for j in range(count)]
    for k in range(len(radii)-1):
        lo=1+k*count;hi=lo+count
        top += [(lo+j,hi+j,hi+(j+1)%count,lo+(j+1)%count) for j in range(count)]
    boundary=1+(len(radii)-1)*count
    faces=top+[tuple(i+n for i in reversed(f)) for f in top]+[(boundary+j,boundary+(j+1)%count,boundary+(j+1)%count+n,boundary+j+n) for j in range(count)]
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o)
    for m in (top_mat,bottom_mat,edge):me.materials.append(m)
    for i,p in enumerate(me.polygons):p.material_index=0 if i<len(top) else (1 if i<2*len(top) else 2);p.use_smooth=i<2*len(top)
    ca=me.attributes.new('PaperCoord','FLOAT_VECTOR','POINT');ta=me.attributes.new('PaperTone','FLOAT','POINT');wa=me.attributes.new('Wear','FLOAT','POINT')
    shift=Vector((rng.random(),rng.random(),rng.random()))
    for v in me.vertices:ca.data[v.index].vector=v.co+shift;ta.data[v.index].value=tone;wa.data[v.index].value=0
    if bevel:
        b=o.modifiers.new('Soft fiber edge','BEVEL');b.width=bevel;b.segments=2;b.harden_normals=True
        o.modifiers.new('Paper face normals','WEIGHTED_NORMAL')
    return o

def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges)
    me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
def cube_hull(name,loc,size):return hull(name,[(loc[0]+x*size[0]/2,loc[1]+y*size[1]/2,loc[2]+z*size[2]/2) for x in (-1,1) for y in (-1,1) for z in (-1,1)])

def clip_polygon(poly,axis,bound,keep_above):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        inside_a=(a[axis]>=bound) if keep_above else (a[axis]<=bound)
        inside_b=(b[axis]>=bound) if keep_above else (b[axis]<=bound)
        if inside_a:result.append(a)
        if inside_a!=inside_b:
            t=(bound-a[axis])/(b[axis]-a[axis]);result.append(tuple(a[i]+(b[i]-a[i])*t for i in range(2)))
    return result

def pocket_panel_colliders(name,panel_specs):
    result=[]
    # Keep the raised panels separate from their folded roots. A single hull
    # across an entire bent panel would fill the usable letter cavity.
    for poly,upper in panel_specs:
        regions=[[(0,-.106,True),(0,.106,False),(1,-.051,True)]]
        for axis,start,step,above in [(0,-.11,.001,True),(0,.11,-.001,False),(1,-.055,.001,True)]:
            for j in range(4):
                lo,hi=sorted((start+j*step,start+(j+1)*step))
                regions.append([(axis,lo,True),(axis,hi,False)])
        for bounds in regions:
            clipped=list(poly)
            for axis,bound,above in bounds:
                if clipped:clipped=clip_polygon(clipped,axis,bound,above)
            if len(clipped)<3:continue
            area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(clipped,clipped[1:]+clipped[:1])))
            if area<1e-10:continue
            # Sampling each boundary follows the root bend. Each strip is only
            # 1 mm wide and remains outside the 205 x 95 mm letter footprint.
            points=[]
            for x,y in outline_samples(clipped,3):
                z=upper(x,y);points.extend([(x,y,z+.00008),(x,y,z-PAPER-.00008)])
            result.append(hull('UCX_'+name+'_%02d'%(len(result)+1),points))
    return result

def pocket(is_open):
    height=OPEN_HEIGHT if is_open else CLOSED_HEIGHT
    def zbase(x,y):return FRONT+(height-FRONT)*smooth(min(.11-abs(x),y+.055)/.004)
    body=sheet('Front sheet and continuous fold roots',rounded_rect(.22,.11),lambda x,y:FRONT,bottom_mat=outer,top_mat=inner)
    pieces=[body];panels=[];previous=[]
    outlines=[('Left fold',[(-.1096,-.0546),(.012,-.009),(-.1096,.0546)],.91),
        ('Right fold',[(.1096,-.0546),(.1096,.0546),(-.012,-.009)],.96),
        ('Bottom fold',[(-.1096,-.0546),(.1096,-.0546),(.027,.014),(-.027,.014)],.93)]
    for layer,(name,poly,tone) in enumerate(outlines):
        def upper(x,y,layer=layer):
            fold=smooth(min(.11-abs(x),y+.055)/.004)
            return zbase(x,y)+layer*(PAPER+.00012)*fold
        obj=sheet(name,outline_samples(poly),upper,tone=tone);pieces.append(obj);panels.append(obj);previous.append((poly,upper))
    old=tuple(previous) if not is_open else ()
    def sealing_z(x,y):
        top=CLOSED_HEIGHT+(3*(PAPER+.00012) if not is_open else 0)
        return FRONT+(top-FRONT)*smooth((.055-y)/.006)
    flap_outline=[(-.1094,.0548),(-.002,-.023),(0,-.0243),(.002,-.023),(.1094,.0548)]
    flap=sheet('Large V sealing flap',outline_samples(flap_outline),sealing_z,tone=1.08)
    flap['hinge_location_m']=(0,.055,FRONT)
    flap_parts=[flap]
    # A genuine gummed border is on the inside of the flap.
    for a,b in [((-.101,.049),(0,-.017)),((0,-.017),(.101,.049))]:
        direction=Vector((b[0]-a[0],b[1]-a[1]));perp=Vector((-direction.y,direction.x)).normalized()*.0015
        poly=[(a[0]-perp.x,a[1]-perp.y),(b[0]-perp.x,b[1]-perp.y),(b[0]+perp.x,b[1]+perp.y),(a[0]+perp.x,a[1]+perp.y)]
        area=sum(poly[i][0]*poly[(i+1)%4][1]-poly[(i+1)%4][0]*poly[i][1] for i in range(4))
        if area<0:poly.reverse()
        ribbon=sheet('Gummed inner V border',outline_samples(poly,5),lambda x,y:sealing_z(x,y)-PAPER+.000004,thickness=.000035,top_mat=gum,bottom_mat=gum,tone=1,bevel=.000007)
        flap_parts.append(ribbon)
    if is_open:
        transform=Matrix.Translation((0,.055,FRONT))@Matrix.Rotation(math.radians(-140),4,'X')@Matrix.Translation((0,-.055,-FRONT))
        for obj in flap_parts:
            obj.data.transform(transform);obj.data.update()
    # Actual rolled paper at the hinge overlaps both connected paper volumes.
    # It bridges the small setback needed to rotate a finite-thickness flap.
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.00030,depth=.2188,
        location=(0,.055,.00030),rotation=(0,math.pi/2,0))
    hinge=bpy.context.object;hinge.name='Continuous rolled fold hinge'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    hinge.data.materials.append(outer)
    for p in hinge.data.polygons:p.use_smooth=len(p.vertices)==4
    coord=hinge.data.attributes.new('PaperCoord','FLOAT_VECTOR','POINT')
    tint=hinge.data.attributes.new('PaperTone','FLOAT','POINT')
    for v in hinge.data.vertices:coord.data[v.index].vector=v.co;tint.data[v.index].value=1
    pieces.append(hinge)
    pieces+=flap_parts
    return pieces,body,panels,flap,previous

assets={};colliders={};model={}
for kind,is_open in (('Closed',False),('Open',True)):
    name='SM_Envelope_'+kind
    pieces,body,panels,flap,panel_specs=pocket(is_open)
    for obj in pieces:
        duplicate=obj.copy();duplicate.data=obj.data.copy();source_col.objects.link(duplicate)
    if is_open:
        cs=[cube_hull('UCX_'+name+'_00',(0,0,.00050),(.22,.11,.0010))]
        cs+=pocket_panel_colliders(name,panel_specs)
        for i,obj in enumerate([flap],len(cs)):
            ps=[v.co.copy() for v in obj.data.vertices]
            if obj==flap:
                normal=Vector((0,-math.sin(math.radians(-140)),math.cos(math.radians(-140))))*.0004
                ps=[p+normal for p in ps]+[p-normal for p in ps]
            cs.append(hull('UCX_'+name+'_%02d'%i,ps))
    else:cs=[cube_hull('UCX_'+name+'_00',(0,0,.0015),(.22,.11,.003))]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in pieces:obj.select_set(True)
    bpy.context.view_layer.objects.active=body;bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name=name
    assets[name]=asset;colliders[name]=cs

paper=sheet('SM_LetterPaper',rounded_rect(.205,.095,.0005),lambda x,y:.00013+.00023*(.5+.5*math.sin(math.pi*x/.205))*math.sin(math.pi*(y+.0475)/.095)**2,
    thickness=.00013,top_mat=white,bottom_mat=white,tone=1,bevel=.000018)
paper.data.materials[2]=white
for p in paper.data.polygons:p.material_index=0
paper.data.materials.clear();paper.data.materials.append(white)
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active=paper;paper.select_set(True);bpy.ops.object.convert(target='MESH')
assets['SM_LetterPaper']=paper;colliders['SM_LetterPaper']=[cube_hull('UCX_SM_LetterPaper_00',(0,0,.0005),(.205,.095,.001))]

for name,obj in assets.items():
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for uv in list(obj.data.uv_layers):obj.data.uv_layers.remove(uv)
    obj.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(70),island_margin=.006);bpy.ops.object.mode_set(mode='OBJECT')
    mod=obj.modifiers.new('Final game triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in colliders[name]:c.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
    bm=bmesh.new();bm.from_mesh(obj.data);assert all(e.is_manifold for e in bm.edges),name;bm.free()
    target_mat={'SM_Envelope_Closed':'M_EnvelopeClosed','SM_Envelope_Open':'M_EnvelopeOpen','SM_LetterPaper':'M_LetterPaper'}[name]
    model[name]={'filename':name+'.fbx','dimensions_cm':[v*100 for v in obj.dimensions],'triangles':len(obj.data.polygons),
        'collision_hulls':len(colliders[name]),'uv_channels':1,'non_manifold_edges':0,
        'material_slots':{m.name:target_mat for m in obj.data.materials}}
    for c in colliders[name]:bpy.data.objects.remove(c,do_unlink=True)
    for c in list(obj.users_collection):c.objects.unlink(obj)
    export_col.objects.link(obj)

# Check the real mesh surfaces in the suggested inserted-paper pose.
def bvh(obj,offset=Vector((0,0,0))):
    obj.data.calc_loop_triangles()
    return BVHTree.FromPolygons([obj.matrix_world@v.co+offset for v in obj.data.vertices],[tuple(t.vertices) for t in obj.data.loop_triangles],all_triangles=True)
overlaps=bvh(assets['SM_Envelope_Open']).overlap(bvh(assets['SM_LetterPaper'],Vector((0,0,.0013))))
assert not overlaps,('Letter intersects the open envelope',len(overlaps))

display={}
for name,obj in assets.items():
    view=obj.copy();view.data=obj.data;view.name='VIEW_'+name.removeprefix('SM_');display_col.objects.link(view);display[name]=view
display['SM_Envelope_Closed'].location=(-.135,-.035,0)
display['SM_Envelope_Closed'].rotation_euler.z=math.radians(-5)
display['SM_Envelope_Open'].location=(.13,.025,0)
display['SM_LetterPaper'].location=(.13,.025,.0013)
export_col.hide_viewport=True;export_col.hide_render=True;source_col.hide_viewport=True;source_col.hide_render=True

studio=bpy.data.collections.new('Preview studio - excluded from exports');s.collection.children.link(studio)
def studio_object(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor=bpy.data.materials.new('Preview grey');floor.use_nodes=True;p=next(n for n in floor.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.065,.07,.078,1);p.inputs['Roughness'].default_value=.9
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0001));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_object(o)
target=Vector((0,.02,.015));bpy.ops.object.camera_add(location=(.23,-.47,.58));cam=bpy.context.object;cam.name='Camera_EnvelopeSet'
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.59;cam.data.clip_start=.0001;s.camera=cam;studio_object(cam)
for name,pos,power,size,col in [('Key',(-.2,-.15,.50),10,.36,(1,.94,.86)),('Fill',(.30,-.02,.4),3.5,.32,(.86,.92,1)),('Rim',(.0,.3,.45),7,.30,(1,.96,.9))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_object(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_x=1800;s.render.resolution_y=1100;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'EnvelopeSet_Preview.png');s.view_settings.view_transform='AgX';s.view_settings.exposure=-.35;studio.hide_viewport=True
report={'parts':model,'texture_sets':{key:{'prefix':prefix,**{ch:'Textures/'+prefix+'_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal')}}
    for key,prefix in [('Closed','T_EnvelopeClosed'),('Open','T_EnvelopeOpen'),('LetterPaper','T_LetterPaper')]},
    'materials':{'M_EnvelopeClosed':{'texture_set':'Closed'},'M_EnvelopeOpen':{'texture_set':'Open'},'M_LetterPaper':{'texture_set':'LetterPaper'}},
    'assembly':{'paper_in_open_envelope_offset_blender_m':[0,0,.0013],'paper_in_open_envelope_offset_ue_cm':[0,0,.13],
        'paper_surface_intersections':len(overlaps),'open_flap_rotation_degrees':140},
    'reference_urls':['https://www.colourcraftdirect.com/fleck-craft-recycled-gummed-dl-110-mm-x-220-mm-envelope',
        'https://www.vaessen-creative.com/en/p/florence-envelopes-120g-8-27x4-33inch-kraft-100x-200112-1502'],
    'paper_layer_thickness_mm':.28,'letter_thickness_mm':.13,'real_open_pocket':True,'exported_lights':0,'exported_cameras':0}
bpy.ops.object.select_all(action='DESELECT')
for obj in display.values():obj.select_set(True)
bpy.context.view_layer.objects.active=display['SM_Envelope_Open']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'EnvelopeSet.blend'));(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
