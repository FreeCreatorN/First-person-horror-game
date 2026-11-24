"""Original generic shop labels. Flat albedo artwork; no baked lighting."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random, math, json, hashlib

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'Textures';OUT.mkdir(exist_ok=True)
FONT=Path('C:/Windows/Fonts/simhei.ttf')
SMALL=Path('C:/Windows/Fonts/simsun.ttc')
LATIN=Path('C:/Windows/Fonts/georgia.ttf')
randomizer=random.Random(1118)

def font(size,small=False,latin=False):
    return ImageFont.truetype(str(LATIN if latin else SMALL if small else FONT),size)

def centered(draw,text,x,y,size,fill,small=False,latin=False):
    f=font(size,small,latin)
    bounds=draw.textbbox((0,0),text,font=f)
    draw.text((x-(bounds[2]-bounds[0])/2,y-bounds[1]),text,font=f,fill=fill)

def paper(w,h,seed):
    rng=random.Random(seed)
    pix=Image.new('RGB',(w,h));px=pix.load()
    for y in range(h):
        for x in range(w):
            noise=rng.gauss(0,1.8)
            stain=2.3*math.sin(x*.011+y*.004)+1.7*math.sin(y*.029)
            edge=min(x,y,w-1-x,h-1-y)
            dark=max(0,1-edge/20)*5
            px[x,y]=(int(217+noise+stain-dark),int(207+noise+stain-dark),int(181+noise+stain-dark))
    d=ImageDraw.Draw(pix)
    for _ in range(w*h//1300):
        x=rng.randrange(w);y=rng.randrange(h)
        d.line((x,y,x+rng.randint(-3,6),y+rng.randint(1,2)),fill=(194,185,161),width=1)
    return pix

def leaf(draw,xy,scale,ink,angle=0):
    # A slender hand-drawn leaf silhouette with a central vein.
    x,y=xy
    def p(u,v):
        return (x+scale*(u*math.cos(angle)-v*math.sin(angle)),y+scale*(u*math.sin(angle)+v*math.cos(angle)))
    shape=[p(0,0),p(-.33,-.25),p(-.38,-.63),p(-.12,-1),p(0,-1.22),p(.18,-.97),p(.36,-.60),p(.26,-.23),p(0,0)]
    draw.line(shape,fill=ink,width=max(1,int(scale*.035)),joint='curve')
    draw.line([p(0,0),p(0,-1.13)],fill=ink,width=max(1,int(scale*.025)))
    for k in (.3,.5,.7,.9):
        draw.line([p(0,-k),p(-.22,-k-.12)],fill=ink,width=1)
        draw.line([p(0,-k),p(.22,-k-.12)],fill=ink,width=1)

def botanical(draw,cx,cy,size,kind,ink):
    if kind=='mint':
        draw.line((cx,cy+size*.35,cx,cy-size*.35),fill=ink,width=3)
        leaf(draw,(cx,cy),size*.65,ink,-.75)
        leaf(draw,(cx,cy-size*.13),size*.65,ink,.75)
        leaf(draw,(cx,cy-size*.28),size*.5,ink,0)
    elif kind=='wheat':
        for tilt in (-.22,.22):
            draw.line((cx,cy+size*.4,cx+size*tilt,cy-size*.65),fill=ink,width=3)
            for i in range(5):
                yy=cy-size*.54+i*size*.15;xx=cx+size*tilt*(.9-i*.12)
                draw.ellipse((xx-size*.20,yy-size*.05,xx,yy+size*.08),outline=ink,width=2)
                draw.ellipse((xx,yy-size*.05,xx+size*.20,yy+size*.08),outline=ink,width=2)
    elif kind=='tea':
        draw.arc((cx-size*.45,cy-size*.2,cx+size*.45,cy+size*.4),0,180,fill=ink,width=4)
        draw.line((cx-size*.45,cy+size*.1,cx-size*.34,cy+size*.42,cx+size*.32,cy+size*.42,cx+size*.45,cy+size*.1),fill=ink,width=3)
        draw.arc((cx+size*.3,cy-size*.02,cx+size*.65,cy+size*.25),260,110,fill=ink,width=3)
        leaf(draw,(cx,cy-size*.15),size*.5,ink,.35)
    else:
        rr=size*.46
        draw.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline=ink,width=3)
        draw.ellipse((cx-rr*.85,cy-rr*.85,cx+rr*.85,cy+rr*.85),outline=ink,width=2)
        for angle in range(0,360,60):
            a=math.radians(angle)
            draw.line((cx,cy,cx+math.cos(a)*rr*.85,cy+math.sin(a)*rr*.85),fill=ink,width=2)
        leaf(draw,(cx+size*.17,cy-size*.44),size*.34,ink,.85)

def worn_print(base,ink_layer,seed):
    # Print loss is sparse and irregular, so the design survives small UV sizes.
    rng=random.Random(seed)
    mask=ink_layer.getchannel('A')
    d=ImageDraw.Draw(mask)
    for _ in range(680):
        x=rng.randrange(base.width);y=rng.randrange(base.height)
        rr=rng.choice((1,1,2))
        d.ellipse((x,y,x+rr,y+rr),fill=0)
    ink_layer.putalpha(mask)
    base.paste(ink_layer,(0,0),ink_layer)
    return base

def carton(name,title,english,sub,kind,ink,seed):
    w,h=1024,384;base=paper(w,h,seed)
    layer=Image.new('RGBA',(w,h));d=ImageDraw.Draw(layer)
    c=(*ink,238)
    d.rectangle((18,18,w-19,h-19),outline=c,width=5)
    d.rectangle((28,28,w-29,h-29),outline=c,width=2)
    # Fine square corner ornaments and horizontal separators.
    for x in (39,w-40):
        for y in (39,h-40):
            d.rectangle((x-5,y-5,x+5,y+5),outline=c,width=2)
    d.line((243,60,243,h-60),fill=c,width=2)
    botanical(d,140,209,106,kind,c)
    centered(d,'小 铺 精 选',636,48,30,c,small=True)
    centered(d,title,638,105,107,c)
    d.line((326,231,946,231),fill=c,width=2)
    centered(d,english,638,249,25,c,latin=True)
    centered(d,sub,638,300,32,c,small=True)
    im=worn_print(base,layer,seed+400)
    path=OUT/name;im.save(path)
    return path

def jar(name,title,sub,kind,ink,seed):
    w=h=768;base=paper(w,h,seed)
    layer=Image.new('RGBA',(w,h));d=ImageDraw.Draw(layer);c=(*ink,235)
    d.rounded_rectangle((23,23,w-24,h-24),radius=14,outline=c,width=7)
    d.rounded_rectangle((35,35,w-36,h-36),radius=11,outline=c,width=2)
    centered(d,'传 统 风 味',w/2,61,35,c,small=True)
    d.line((120,124,w-120,124),fill=c,width=2)
    botanical(d,w/2,268,174,kind,c)
    centered(d,title,w/2,405,124,c)
    centered(d,sub,w/2,563,32,c,small=True)
    d.line((122,625,w-122,625),fill=c,width=2)
    centered(d,'散 装 称 重',w/2,659,34,c,small=True)
    im=worn_print(base,layer,seed+400);path=OUT/name;im.save(path);return path

files=[
    carton('T_StockLabel_Mint.png','薄荷糖','COOL MINT DROPS','清凉薄荷 · 传统糖果','mint',(39,77,57),71),
    carton('T_StockLabel_Biscuit.png','麦香饼','CLASSIC WHEAT BISCUITS','香脆可口 · 麦香风味','wheat',(116,72,35),72),
    carton('T_StockLabel_Tea.png','红 茶','SELECT BLACK TEA','精选茶叶 · 经典红茶','tea',(118,44,32),73),
    carton('T_StockLabel_Citrus.png','陈皮糖','TANGERINE PEEL SWEETS','酸甜回甘 · 传统糖果','citrus',(40,76,86),74),
    jar('T_StockLabel_JarSweets.png','什锦糖','多种口味 · 传统糖果','mint',(124,44,33),75),
    jar('T_StockLabel_JarPlum.png','陈皮梅','酸甜果香 · 蜜饯果脯','citrus',(70,90,51),76),
]
atlas=paper(2048,2048,130)
entries=[]
positions=[(0,0),(1024,0),(0,384),(1024,384),(96,960),(1184,960)]
for path,xy in zip(files,positions):
    im=Image.open(path);atlas.paste(im,xy)
    x,y=xy;w,h=im.size
    entries.append({'file':path.name,'pixels':[x,y,w,h],
                    'uv_blender':[x/2048,1-(y+h)/2048,(x+w)/2048,1-y/2048]})
atlas_path=OUT/'T_StockLabels_Atlas.png';atlas.save(atlas_path)
manifest={'source':'original generic fictional shop-label artwork','color_space':'sRGB','suggested_roughness':.78,
    'atlas':atlas_path.name,'atlas_size':[2048,2048],'labels':entries,
    'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files+[atlas_path]}}
(OUT/'stock_labels_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'success':True,'output':str(OUT),'files':[p.name for p in files+[atlas_path]]}))
