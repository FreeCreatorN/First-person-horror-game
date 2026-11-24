"""Original, unlit printed enamel artwork for the shop freezer front."""
from pathlib import Path
import json, math, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'Textures';OUT.mkdir(parents=True,exist_ok=True)
W,H=2048,1024
rng=np.random.default_rng(71398)
FONT=Path('C:/Windows/Fonts/msyhbd.ttc')
REGULAR=Path('C:/Windows/Fonts/msyh.ttc')
IVORY=(193,190,178)
BLUE=(71,106,128)
INK_LIGHT=(107,137,150)
RED=(165,102,91)
YELLOW=(179,151,91)

def coarse_noise(w,h,grid_x,grid_y):
    raw=Image.fromarray(rng.integers(0,256,(grid_y,grid_x),dtype=np.uint8),'L')
    return np.asarray(raw.resize((w,h),Image.Resampling.BICUBIC),dtype=np.float32)/255

# Diffuse variations are material damage, with no directional illumination.
grain=rng.normal(0,1.55,(H,W))
soft=(coarse_noise(W,H,56,28)-.5)*5.0
finer=(coarse_noise(W,H,260,130)-.5)*2.8
base=np.clip(np.asarray(IVORY)[None,None,:]+(grain+soft+finer)[:,:,None],0,255).astype(np.uint8)
base_img=Image.fromarray(base,'RGB').convert('RGBA')
art=Image.new('RGBA',(W,H));d=ImageDraw.Draw(art)

def snow(cx,cy,r,stroke=6):
    for a in range(0,180,60):
        th=math.radians(a);dx,dy=math.cos(th),math.sin(th)
        d.line((cx-dx*r,cy-dy*r,cx+dx*r,cy+dy*r),fill=BLUE+(228,),width=stroke)
        for sg in (-1,1):
            for branch in (-1,1):
                bx,by=cx+sg*dx*r*.59,cy+sg*dy*r*.59
                aa=th+math.radians(branch*48)
                ex,ey=bx-sg*math.cos(aa)*r*.29,by-sg*math.sin(aa)*r*.29
                d.line((bx,by,ex,ey),fill=BLUE+(228,),width=max(3,stroke-1))

# Broad, simple lettering reads at game-camera distance.
title=ImageFont.truetype(str(FONT),224)
d.text((208,192),'冰淇淋',font=title,fill=BLUE+(242,),stroke_width=1)
small=ImageFont.truetype(str(REGULAR),40)
d.text((236,464),'清 凉 好 滋 味',font=small,fill=BLUE+(192,))
for values in [(113,208,45,7),(169,449,31,6),(1010,266,36,6),(1085,496,49,7),(245,639,35,6),(1210,124,24,5)]:
    snow(*values)

# Original two-wave shop illustration, deliberately flat printed colors.
points=[]
for x in range(-10,W+11,8):
    y=780+36*math.sin(x/W*math.pi*2.2-.6)+14*math.sin(x/W*math.pi*4)
    points.append((x,y))
d.polygon(points+[(W+10,944),(-10,944)],fill=BLUE+(187,))
points2=[]
for x in range(-10,W+11,8):
    y=835+28*math.sin(x/W*math.pi*2.2+.55)
    points2.append((x,y))
d.polygon(points2+[(W+10,944),(-10,944)],fill=INK_LIGHT+(130,))

# Popsicle artwork: transparent paper-print layer, no glossy or shaded highlights.
pop=Image.new('RGBA',(340,650));p=ImageDraw.Draw(pop)
p.rounded_rectangle((143,390,196,625),radius=24,fill=YELLOW+(242,),outline=(133,116,81,205),width=5)
p.rounded_rectangle((44,37,294,469),radius=109,fill=RED+(240,),outline=(140,91,83,232),width=7)
p.arc((76,91,260,429),240,310,fill=(192,139,118,192),width=6)
p.line([(105,154),(127,130),(161,121)],fill=(198,153,132,180),width=7)
for x,y in [(89,246),(215,192),(164,327),(231,358),(127,412),(225,267)]:
    p.ellipse((x-7,y-5,x+7,y+5),fill=(132,87,80,155))
pop=pop.rotate(-23,resample=Image.Resampling.BICUBIC,expand=True)
art.alpha_composite(pop,(1167,115))

# Small frozen-dessert cup to accompany the ice pop.
cup=Image.new('RGBA',(382,390));c=ImageDraw.Draw(cup)
c.polygon([(44,127),(333,127),(279,350),(104,350)],fill=INK_LIGHT+(242,),outline=BLUE+(240,),width=6)
for y in (198,244,290):
    t=(y-127)/(350-127);left=44+60*t;right=333-54*t
    c.line((left,y,right,y),fill=(183,174,132,230),width=17)
c.ellipse((38,90,339,167),fill=YELLOW+(245,),outline=(132,120,88,230),width=6)
c.polygon([(115,118),(147,78),(181,58),(218,82),(244,116)],fill=(196,176,126,240),outline=(153,133,94,220),width=4)
c.arc((115,32,245,116),175,340,fill=(201,183,139,240),width=29)
c.polygon([(199,68),(218,10),(238,9),(227,84)],fill=YELLOW+(245,))
c.ellipse((198,0,237,24),fill=(198,177,119,240),outline=(151,134,89,220),width=3)
cup=cup.rotate(8,resample=Image.Resampling.BICUBIC,expand=True)
art.alpha_composite(cup,(1540,383))

# Abrasion knocks small fragments out of all colors uniformly.
alpha=np.asarray(art.getchannel('A'),dtype=np.float32)
wear=coarse_noise(W,H,240,120)
holes=(wear>.78) | (rng.random((H,W))<.009)
alpha[holes]*=.18
alpha*=.84+.12*coarse_noise(W,H,110,55)
art.putalpha(Image.fromarray(np.clip(alpha,0,255).astype(np.uint8),'L'))
printed=Image.alpha_composite(base_img,art)

# Sparse enamel damage and oxidation. Brown is pigmentation, never a cast shadow.
damage=Image.new('RGBA',(W,H));z=ImageDraw.Draw(damage)
for i in range(920):
    x=float(rng.uniform(8,W-8));y=float(rng.uniform(6,H-6))
    dist=min(x,W-x,y,H-y)
    if rng.random()>.15+.8*math.exp(-dist/42):continue
    radius=float(rng.uniform(.9,4.0))
    z.ellipse((x-radius,y-radius*.65,x+radius,y+radius*.65),fill=(126,111,87,int(rng.uniform(35,105))))
for i in range(170):
    x=float(rng.uniform(12,W-12));y=float(rng.uniform(H-37,H-2))
    r=float(rng.uniform(1,8))
    z.ellipse((x-r,y-r*.5,x+r,y+r*.5),fill=(112,82,55,int(rng.uniform(45,135))))
for i in range(76):
    x=float(rng.uniform(18,W-18));y=float(rng.uniform(20,H-20))
    length=float(rng.uniform(9,66));dx=float(rng.uniform(-8,8))
    z.line([(x,y),(x+dx,y+length*.4),(x+dx*.6,y+length)],fill=(137,125,103,int(rng.uniform(22,64))),width=1)
printed=Image.alpha_composite(printed,damage).convert('RGB')
base_path=OUT/'T_FreezerFront_BaseColor.png';printed.save(base_path)
mask_path=OUT/'T_FreezerFront_PrintMask.png';art.getchannel('A').save(mask_path)
rough=np.clip(180+grain*1.5+(coarse_noise(W,H,70,35)-.5)*20+np.asarray(damage.getchannel('A'))*.20,140,235).astype(np.uint8)
rough_path=OUT/'T_FreezerFront_Roughness.png';Image.fromarray(rough,'L').save(rough_path)
preview=printed.resize((1024,512),Image.Resampling.LANCZOS);preview.save(OUT/'FreezerFront_Preview.png')
manifest={'description':'Original fictional ice-cream freezer enamel print; unlit base-color artwork',
          'resolution':[W,H],'base_color':base_path.name,'roughness':rough_path.name,'print_mask':mask_path.name,
          'color_spaces':{'base_color':'sRGB','roughness':'Non-Color','print_mask':'Non-Color'},
          'palette_srgb_255':{'ivory':IVORY,'blue':BLUE,'light_blue':INK_LIGHT,'red':RED,'yellow':YELLOW},
          'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (base_path,rough_path,mask_path)}}
(OUT/'front_graphic_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'success':True,'files':list(manifest['sha256']),'output':str(OUT)}))
