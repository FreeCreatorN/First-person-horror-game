"""Original unlit paint/sign art for a small-shop upright beverage refrigerator."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'Textures';OUT.mkdir(parents=True,exist_ok=True)
FONT='C:/Windows/Fonts/msyhbd.ttc'
REG='C:/Windows/Fonts/msyh.ttc'
RED=(133,46,39)
LIGHT_RED=(151,54,44)
CREAM=(218,210,189)
GRAY=(115,111,102)
RUST=(93,64,43)

def noise(rng,w,h,gx,gy):
    image=Image.fromarray(rng.integers(0,256,(gy,gx),dtype=np.uint8),'L')
    return np.asarray(image.resize((w,h),Image.Resampling.BICUBIC),dtype=np.float32)/255.

def paint(w,h,seed,red=RED):
    rng=np.random.default_rng(seed)
    variation=(noise(rng,w,h,22,32)-.5)*10+(noise(rng,w,h,180,220)-.5)*4+rng.normal(0,.75,(h,w))
    base=np.clip(np.asarray(red)[None,None,:]+variation[:,:,None],0,255).astype(np.uint8)
    return rng,Image.fromarray(base,'RGB').convert('RGBA'),variation

def bottle(draw,box,fill,red):
    # Generic capped bottle icon with no trademarked silhouette or label.
    x0,y0,x1,y1=box;w=x1-x0;h=y1-y0
    p=lambda x,y:(x0+w*x,y0+h*y)
    draw.rounded_rectangle((*p(.31,.015),*p(.69,.090)),radius=max(2,int(w*.035)),fill=fill)
    poly=[p(.34,.085),p(.66,.085),p(.67,.22),p(.83,.34),p(.84,.90),p(.77,.98),p(.23,.98),p(.16,.90),p(.17,.34),p(.33,.22)]
    draw.polygon(poly,fill=fill)
    draw.rounded_rectangle((*p(.23,.44),*p(.77,.74)),radius=max(2,int(w*.04)),outline=red,width=max(2,int(w*.025)))
    draw.line([p(.33,.54),p(.67,.54)],fill=red,width=max(2,int(w*.025)))
    draw.line([p(.34,.64),p(.66,.64)],fill=red,width=max(2,int(w*.018)))

def apply_print(base,art,rng,grain_scale=1):
    w,h=base.size
    alpha=np.asarray(art.getchannel('A'),dtype=np.float32)
    mottled=noise(rng,w,h,max(28,w//6),max(24,h//6))
    holes=(mottled>.94)|(rng.random((h,w))<.0007)
    alpha[holes]*=.16
    alpha*=.94+.05*noise(rng,w,h,max(10,w//80),max(8,h//80))
    art.putalpha(Image.fromarray(np.clip(alpha,0,255).astype(np.uint8),'L'))
    return Image.alpha_composite(base,art),art.getchannel('A')

def age(image,rng,variation,sign=False):
    w,h=image.size
    layer=Image.new('RGBA',image.size);d=ImageDraw.Draw(layer)
    # Edge-only paint loss and rust. The broad faces retain readable red paint.
    count=430 if sign else 2900
    for i in range(count):
        edge=i%4
        if edge==0:x,y=rng.uniform(0,w),abs(rng.normal(0,h*.018))
        elif edge==1:x,y=rng.uniform(0,w),h-abs(rng.normal(0,h*.024))
        elif edge==2:x,y=abs(rng.normal(0,w*.018)),rng.uniform(0,h)
        else:x,y=w-abs(rng.normal(0,w*.018)),rng.uniform(0,h)
        r=float(rng.uniform(.7,3.5 if sign else 6.5))
        color=GRAY if rng.random()<.68 else RUST
        d.ellipse((x-r,y-r*.55,x+r,y+r*.55),fill=(*color,int(rng.uniform(80,185))))
    # Sparse scored paint, no directional lighting or cast shadows.
    for i in range(65 if sign else 360):
        x=float(rng.uniform(w*.025,w*.975));y=float(rng.uniform(h*.035,h*.96))
        length=float(rng.uniform(5,28 if sign else 76))
        dx=float(rng.uniform(-6,6))
        d.line([(x,y),(x+dx,y+length)],fill=(182,156,131,int(rng.uniform(26,79))),width=1 if sign else int(rng.choice([1,1,1,2])))
    result=Image.alpha_composite(image,layer).convert('RGB')
    mask=np.asarray(layer.getchannel('A'),dtype=np.float32)
    rough=np.clip(174+variation*.7+(noise(rng,w,h,40,60)-.5)*15+mask*.15,145,226).astype(np.uint8)
    return result,Image.fromarray(rough,'L')

def header():
    w,h=1024,384;rng,base,var=paint(w,h,6241,LIGHT_RED)
    art=Image.new('RGBA',(w,h));d=ImageDraw.Draw(art)
    cream=(*CREAM,250)
    d.rectangle((18,18,w-19,h-19),outline=(*CREAM,155),width=4)
    d.rectangle((28,28,w-29,h-29),outline=(*CREAM,83),width=2)
    bottle(d,(57,49,184,307),cream,(*LIGHT_RED,240))
    font=ImageFont.truetype(FONT,137)
    title='冰镇饮料';bbox=d.textbbox((0,0),title,font=font)
    tx=238+(w-238-47-(bbox[2]-bbox[0]))/2
    d.text((tx,69),title,font=font,fill=cream,stroke_width=1)
    small=ImageFont.truetype(REG,26)
    text='清 凉 畅 饮';bbox=d.textbbox((0,0),text,font=small)
    d.text((tx+((bbox[2]-bbox[0])*.05),243),text,font=small,fill=(*CREAM,174))
    path=[]
    for x in range(215,w-33,5):
        y=302+13*math.sin((x-215)/(w-248)*math.pi*1.25+.5)
        path.append((x,y))
    d.line(path,fill=(*CREAM,224),width=12,joint='curve')
    printed,mask=apply_print(base,art,rng)
    color,rough=age(printed,rng,var,True)
    p=OUT/'T_BeverageHeader_BaseColor.png';color.save(p)
    r=OUT/'T_BeverageHeader_Roughness.png';rough.save(r)
    mask.save(OUT/'T_BeverageHeader_PrintMask.png')
    color.resize((1024,384),Image.Resampling.LANCZOS).save(OUT/'BeverageHeader_Preview.png')
    return [p,r,OUT/'T_BeverageHeader_PrintMask.png']

def side():
    w,h=700,2048;rng,base,var=paint(w,h,6242,RED)
    art=Image.new('RGBA',(w,h));d=ImageDraw.Draw(art);cream=(*CREAM,236)
    # Portrait UV matches the 0.625m x1.83m side without distorting the icon.
    bottle(d,(w*.34,h*.195,w*.66,h*.485),cream,(*RED,242))
    upper=[];lower=[]
    for x in range(-8,w+9,8):
        t=x/w
        y=h*.551+h*.0415*math.sin(t*math.pi*1.55+.15)-h*.0586*t
        upper.append((x,y));lower.append((x,y+h*.038+12*math.sin(t*math.pi)))
    d.polygon(upper+list(reversed(lower)),fill=(*CREAM,229))
    # A second quiet hairline gives the old sign-paint sweep some shape.
    d.line([(x,y+107) for x,y in upper],fill=(*CREAM,120),width=9)
    printed,mask=apply_print(base,art,rng)
    color,rough=age(printed,rng,var,False)
    p=OUT/'T_BeverageSide_BaseColor.png';color.save(p)
    r=OUT/'T_BeverageSide_Roughness.png';rough.save(r)
    mask.save(OUT/'T_BeverageSide_PrintMask.png')
    # Preview at expected physical aspect, not square texture aspect.
    color.resize((350,1024),Image.Resampling.LANCZOS).save(OUT/'BeverageSide_PhysicalPreview.png')
    return [p,r,OUT/'T_BeverageSide_PrintMask.png']

files=header()+side()
manifest={'description':'Original generic red painted beverage cooler artwork; no lighting or emission baked',
    'header':{'resolution':[1024,384],'base_color':files[0].name,'roughness':files[1].name,'print_mask':files[2].name,
              'uv':'front-facing rectangular sign, U left-to-right, V bottom-to-top'},
    'body_side':{'resolution':[700,2048],'base_color':files[3].name,'roughness':files[4].name,'print_mask':files[5].name,
                 'uv':'full tall case side, U front-to-back or mirrored as needed, V bottom-to-top',
                 'intended_physical_aspect_width_over_height':.625/1.83},
    'palette_srgb_255':{'aged_red':RED,'header_red':LIGHT_RED,'cream_ink':CREAM,'paint_chip':GRAY,'rust':RUST},
    'color_spaces':{'base_color':'sRGB','roughness':'Non-Color','print_mask':'Non-Color'},
    'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(OUT/'graphics_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'success':True,'directory':str(OUT),'files':[p.name for p in files]}))
