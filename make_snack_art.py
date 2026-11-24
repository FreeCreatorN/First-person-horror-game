"""Original illustrated Chinese shop packaging. Pillow/numpy; no external art.

Atlas convention: flavor order starts at V=0 (image bottom), front U=0..0.5,
back U=0.5..1. Exact pixel rectangles and UVs are in the emitted manifest.
"""
from pathlib import Path
import math, json, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'SourceArt' / 'SnackIceCreamSet' / 'Textures'
OUT.mkdir(parents=True, exist_ok=True)
SIZE, INSET = 2048, 8
FREG = 'C:/Windows/Fonts/msyh.ttc'
FBOLD = 'C:/Windows/Fonts/msyhbd.ttc'
FSONG = 'C:/Windows/Fonts/simsun.ttc'
FLAT = 'C:/Windows/Fonts/arial.ttf'
RNG = np.random.default_rng(33241)

FAMILIES = [
 ('Chips', .72, [('Original','薯片','原味','#e9bb38'),('Cucumber','薯片','黄瓜味','#598849')]),
 ('Biscuits',1.65,[('Butter','香酥饼干','黄油味','#a6372e'),('Milk','牛奶饼干','醇香奶味','#417295')]),
 ('CandyBag',.72,[('Fruit','水果糖','缤纷果味','#b73532'),('Mint','薄荷糖','清凉薄荷','#497b9c')]),
 ('Bakery',.72,[('Bread','夹心面包','香浓奶油','#c88b39'),('Cake','蛋糕小点','绵软奶香','#ece3cd')]),
 ('Spicy',.72,[('Hot','辣条','香辣味','#a62c28'),('Original','辣条','原味','#634333')]),
 ('Nuts',.72,[('Seeds','瓜子','五香味','#4c7857'),('Peanut','花生','咸香味','#be973f')]),
 ('Jelly',1.7,[('Orange','果冻杯','香橙味','#df8a35'),('Strawberry','果冻杯','草莓味','#c9687b'),('Grape','果冻杯','葡萄味','#826498')]),
 ('CandyJar',1.3,[('Fruit','什锦糖果','缤纷果味','#ad3936'),('Mint','棒棒糖','清凉薄荷','#d4b348')]),
]

def rgb(s):
    return tuple(int(s[i:i+2],16) for i in (1,3,5))
def font(n,bold=False,latin=False):
    return ImageFont.truetype(FLAT if latin else FBOLD if bold else FREG,max(8,int(n)))
def center(d,xy,t,size,fill,bold=False,latin=False,stroke=0):
    f=font(size,bold,latin); box=d.textbbox((0,0),t,font=f,stroke_width=stroke)
    d.text((xy[0]-(box[2]-box[0])/2,xy[1]-box[1]),t,font=f,fill=fill,stroke_width=stroke,stroke_fill=fill)
def fitcenter(d,xy,t,maxw,size,fill,bold=False):
    while d.textlength(t,font=font(size,bold))>maxw: size-=1
    center(d,xy,t,size,fill,bold)
def rounded(d,box,r,fill,outline=None,width=1):
    d.rounded_rectangle(tuple(map(int,box)),int(r),fill=fill,outline=outline,width=width)

def object_image(w,h,maskfn,base,seed=0,ridges=False):
    """A softly lit, textured food silhouette, then an offset contact shadow."""
    yy,xx=np.mgrid[0:h,0:w]; u=xx/w; v=yy/h
    mask=Image.new('L',(w,h)); md=ImageDraw.Draw(mask); maskfn(md,w,h)
    noise=np.random.default_rng(seed).normal(0,2.8,(h,w))
    shade=1.10-.22*v-.10*u+.12*np.exp(-((u-.33)**2+(v-.28)**2)/.04)
    if ridges: shade+=.026*np.sin((u+v*.15)*80)
    data=np.clip(np.array(base)[None,None,:]*shade[:,:,None]+noise[:,:,None],0,255).astype('uint8')
    im=Image.fromarray(data).convert('RGBA'); im.putalpha(mask)
    return im

def paste_shadow(canvas,obj,xy,angle=0,scale=1):
    if scale!=1: obj=obj.resize((int(obj.width*scale),int(obj.height*scale)),Image.Resampling.LANCZOS)
    if angle: obj=obj.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    x,y=map(int,xy); sh=Image.new('RGBA',obj.size,(38,20,9,0)); sh.putalpha(obj.getchannel('A').point(lambda a:int(a*.25)))
    sh=sh.filter(ImageFilter.GaussianBlur(max(2,obj.width/45)))
    canvas.alpha_composite(sh,(x+6,y+12)); canvas.alpha_composite(obj,(x,y))

def chip(seed=1):
    rr=random.Random(seed)
    def mask(d,w,h):
        pts=[]
        for k in range(120):
            a=k*math.tau/120; r=1+.025*math.sin(a*11)+.013*math.cos(a*19)
            pts.append((w*.5+math.cos(a)*w*.465*r,h*.5+math.sin(a)*h*.43*r))
        d.polygon(pts,fill=255)
    im=object_image(300,190,mask,(226,175,71),seed,True); d=ImageDraw.Draw(im)
    for x in range(35,280,12): d.arc((x-40,13,x+110,176),110,240,fill=(174,120,46,45),width=2)
    for _ in range(80):
        x=rr.randint(23,276);y=rr.randint(26,162)
        if im.getpixel((x,y))[3]:d.ellipse((x,y,x+rr.randint(1,3),y+2),fill=(144,94,25,rr.randint(30,95)))
    return im

def biscuit(seed=2):
    def mask(d,w,h):
        p=[]
        for k in range(160):
            a=k*math.tau/160;r=.45+.015*math.cos(a*20)
            p.append((w*.5+math.cos(a)*w*r,h*.5+math.sin(a)*h*r))
        d.polygon(p,fill=255)
    im=object_image(260,260,mask,(216,165,83),seed);d=ImageDraw.Draw(im)
    d.ellipse((23,23,237,237),outline=(150,99,41,180),width=3)
    d.ellipse((32,32,228,228),outline=(245,207,139,220),width=4)
    for row in range(5):
        for col in range(5):
            x=65+col*32;y=65+row*32
            if (x-130)**2+(y-130)**2<6300:
                d.ellipse((x-3,y-3,x+4,y+4),fill=(124,79,31,230));d.arc((x-5,y-5,x+7,y+7),160,320,fill=(248,209,143,250),width=2)
    center(d,(130,112),'酥',36,(167,113,51,180),True)
    return im

def candy(color=(207,60,54),seed=3):
    im=Image.new('RGBA',(220,120));d=ImageDraw.Draw(im)
    d.polygon([(62,34),(11,13),(18,58),(7,101),(64,83)],fill=(*color,180),outline=(255,225,176,180))
    d.polygon([(158,34),(209,13),(202,58),(214,101),(156,83)],fill=(*color,180),outline=(255,225,176,180))
    for x in (18,30,40,181,191,201):d.line((x,25,x+6,91),fill=(255,255,227,120),width=2)
    obj=object_image(122,86,lambda dr,w,h:dr.rounded_rectangle((1,1,w-2,h-2),25,fill=255),color,seed)
    od=ImageDraw.Draw(obj);od.arc((7,4,113,79),190,320,fill=(255,244,210,205),width=5)
    im.alpha_composite(obj,(49,17));return im

def lollipop(color=(88,157,160),seed=3):
    im=Image.new('RGBA',(180,290));d=ImageDraw.Draw(im)
    d.line((89,125,89,284),fill='#d0c3a6',width=10)
    d.line((86,125,86,284),fill='#fff7e3',width=5)
    ob=object_image(164,164,lambda dr,w,h:dr.ellipse((5,5,w-6,h-6),fill=255),color,seed)
    od=ImageDraw.Draw(ob)
    pts=[]
    for k in range(230):
        a=k*.069;r=3+k*.285;pts.append((82+math.cos(a)*r,82+math.sin(a)*r))
    od.line(pts,fill='#fff1d0',width=10,joint='curve')
    od.arc((16,12,148,146),195,280,fill=(255,255,230,190),width=4)
    im.alpha_composite(ob,(7,0));return im

def bread(seed=2):
    im=object_image(370,240,lambda d,w,h:d.rounded_rectangle((10,15,w-10,h-18),90,fill=255),(210,141,58),seed)
    d=ImageDraw.Draw(im)
    for x in (90,155,220):
        d.line([(x,68),(x+35,49),(x+74,63)],fill=(139,76,27,170),width=14)
        d.line([(x,65),(x+35,49),(x+74,61)],fill=(244,205,139,255),width=8)
    d.arc((19,95,350,225),4,174,fill=(250,219,158,230),width=15)
    d.arc((19,100,350,231),4,174,fill=(159,89,31,160),width=3)
    return im

def cake(seed=2):
    im=Image.new('RGBA',(360,300));d=ImageDraw.Draw(im)
    d.polygon([(45,70),(220,25),(330,83),(150,132)],fill='#fff4db')
    d.polygon([(45,70),(150,132),(150,278),(45,207)],fill='#dba658')
    d.polygon([(150,132),(330,83),(330,226),(150,278)],fill='#e5b56c')
    for a,b in ((115,137),(170,191)):
        d.polygon([(45,a),(150,a+62),(330,a+13),(330,b+13),(150,b+62),(45,b)],fill='#fff0cf')
    rr=random.Random(seed)
    for _ in range(170):
        x=rr.randint(155,325);y=rr.randint(145,235)
        d.ellipse((x,y,x+2,y+2),fill=(170,115,47,100))
    d.ellipse((136,53,221,110),fill='#fffdf0'); d.ellipse((156,30,202,82),fill='#b83e35')
    for i in range(14):
        x=162+rr.randrange(32);y=38+rr.randrange(36);d.ellipse((x,y,x+2,y+3),fill='#f7ca7c')
    d.polygon([(175,31),(154,29),(168,38),(180,19),(186,34),(203,26),(192,42)],fill='#4f783e')
    return im

def spicy(seed=2):
    im=object_image(90,380,lambda d,w,h:d.rounded_rectangle((7,2,w-6,h-2),16,fill=255),(159,58,24),seed,True)
    d=ImageDraw.Draw(im);rr=random.Random(seed)
    for x in range(15,85,9):d.line((x,10,x-2,370),fill=(224,114,45,140),width=3)
    for _ in range(55):
        x=rr.randint(10,80);y=rr.randint(12,367)
        d.ellipse((x,y,x+3,y+6),fill=rr.choice(['#e1b76c','#86331b','#c95929']))
    return im

def seednut(seed=1):
    im=object_image(68,150,lambda d,w,h:d.polygon([(34,2),(55,34),(63,80),(51,128),(34,148),(15,126),(5,78),(13,34)],fill=255),(58,53,42),seed)
    d=ImageDraw.Draw(im);d.line([(34,7),(25,42),(22,90),(34,144)],fill=(209,190,145,210),width=6)
    d.line([(38,8),(46,53),(45,103),(35,145)],fill=(144,130,98,200),width=3)
    return im

def peanut(seed=1):
    im=object_image(110,210,lambda d,w,h:(d.ellipse((12,4,99,115),fill=255),d.ellipse((6,89,104,205),fill=255)),(192,141,78),seed)
    d=ImageDraw.Draw(im)
    for y in range(17,204,15):d.arc((15,y-12,99,y+23),0,180,fill=(134,92,47,180),width=2)
    for x in (25,44,64,83):d.line([(x,17),(x-5,61),(x+3,111),(x-7,170),(x,192)],fill=(143,100,50,190),width=2)
    return im

def leaf(im,xy,scale=1):
    x,y=xy;d=ImageDraw.Draw(im);w,h=130*scale,64*scale
    d.polygon([(x,y),(x+w*.42,y-h*.8),(x+w,y-h*.4),(x+w*.64,y+h*.25)],fill='#4f793a')
    d.line((x,y,x+w,y-h*.4),fill='#a8bc70',width=max(1,int(3*scale)))
    for t in (.25,.45,.65):d.line((x+w*t,y-h*.4*t,x+w*t,y-h*.7),fill='#8fa660',width=1)

def fruit(im,xy,kind='Orange',scale=1):
    x,y=map(int,xy);r=int(70*scale);d=ImageDraw.Draw(im)
    if kind=='Strawberry':
        d.polygon([(x-r,y-r*.65),(x+r,y-r*.65),(x+r*.7,y+r*.3),(x,y+r),(x-r*.7,y+r*.3)],fill='#bb4141')
        for a in range(22):
            xx=x+random.Random(a).randint(-r//2,r//2);yy=y+random.Random(a+40).randint(-r//2,r//2)
            d.ellipse((xx,yy,xx+3,yy+5),fill='#eac66f')
        leaf(im,(x-r//3,y-r*.6),.6*scale)
    elif kind=='Grape':
        for dx,dy in [(-.7,-.5),(.25,-.6),(.8,-.15),(-.65,.35),(.2,.3),(-.15,1)]:
            rr=r*.56;cx=x+dx*r;cy=y+dy*r;d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill='#604776',outline='#b29cbd',width=2)
            d.arc((cx-rr*.7,cy-rr*.7,cx+rr*.7,cy+rr*.7),190,270,fill='#b2a1ba',width=4)
        leaf(im,(x,y-r),.7*scale)
    else:
        d.ellipse((x-r,y-r,x+r,y+r),fill='#de8f29',outline='#f4cb66',width=6)
        d.ellipse((x-r+10,y-r+10,x+r-10,y+r-10),fill='#edb146',outline='#fff0ad',width=5)
        for a in range(9):
            ang=a*math.tau/9;d.line((x,y,x+math.cos(ang)*(r-15),y+math.sin(ang)*(r-15)),fill='#fff0ba',width=3)
        d.ellipse((x-7,y-7,x+7,y+7),fill='#fff0ba')

def jellycup(kind='Orange'):
    im=Image.new('RGBA',(400,330));d=ImageDraw.Draw(im)
    col={'Orange':'#e8a139','Strawberry':'#cd697f','Grape':'#90709b'}[kind]
    d.polygon([(42,96),(359,96),(312,284),(94,284)],fill='#f4e6c6',outline='#d4cbb4')
    d.polygon([(58,107),(343,107),(301,263),(104,263)],fill=col)
    d.ellipse((94,229,312,306),fill=col,outline='#f3e4ce',width=7)
    d.ellipse((40,49,360,152),fill='#f8edd9',outline='#d7cdbb',width=5)
    d.ellipse((58,61,342,140),fill=col,outline='#e5be76',width=4)
    d.arc((79,65,322,129),190,320,fill='#fff6d5',width=5)
    d.line((75,145,111,255),fill=(255,255,255,180),width=10)
    d.line((330,146,302,251),fill=(255,255,255,110),width=5)
    return im

def illustration(im,box,fam,flavor):
    x,y,w,h=box; layer=Image.new('RGBA',(int(w),int(h)))
    ww,hh=layer.size
    if fam=='Chips':
        for i,(px,py,ang,sc) in enumerate([(0.12,.40,-15,.85),(.42,.40,12,.8),(.27,.12,25,.92),(.04,.20,-30,.95),(.44,.02,5,.83),(.23,.63,10,.85)]):
            obj=chip(50+i);paste_shadow(layer,obj,(ww*px,hh*py),ang,ww/690*sc)
        if flavor=='Cucumber':
            for px,py in [(.08,.77),(.73,.72)]:
                d=ImageDraw.Draw(layer);cx,cy=ww*px,hh*py;rw=ww*.115
                d.ellipse((cx-rw,cy-rw*.75,cx+rw,cy+rw*.75),fill='#5e8c42',outline='#d9db9b',width=4)
                d.ellipse((cx-rw*.8,cy-rw*.6,cx+rw*.8,cy+rw*.6),fill='#b9c67d')
                for a in range(8):
                    an=a*math.tau/8;d.ellipse((cx+math.cos(an)*rw*.35-3,cy+math.sin(an)*rw*.28-3,cx+math.cos(an)*rw*.35+3,cy+math.sin(an)*rw*.28+3),fill='#e9ddb0')
    elif fam=='Biscuits':
        for i,(px,py,a,s) in enumerate([(.05,.16,5,.78),(.23,.04,-15,.86),(.47,.13,12,.92),(.65,.34,-8,.87),(.33,.45,18,.8)]):paste_shadow(layer,biscuit(i),(ww*px,hh*py),a,min(ww/970,hh/330)*s)
    elif fam=='CandyJar' and flavor=='Mint':
        colors=[(76,145,147),(216,139,141),(216,172,67),(119,155,94),(92,145,179)]
        sc=min(ww/720,hh/300)
        for i,(px,py,ang) in enumerate([(.06,.06,-20),(.25,.00,14),(.44,.02,-9),(.63,.03,18),(.78,.05,-10)]):
            paste_shadow(layer,lollipop(colors[i],i),(ww*px,hh*py),ang,sc)
        leaf(layer,(ww*.72,hh*.86),.50)
    elif fam in ('CandyBag','CandyJar'):
        colors=[(205,63,51),(223,170,48),(74,140,86),(136,91,143),(222,125,64)] if flavor=='Fruit' else [(99,162,158),(224,214,163),(104,161,188),(241,225,189)]
        for i in range(9):
            px=(i%3)*.28+(.02 if i//3%2 else .08);py=(i//3)*.25
            paste_shadow(layer,candy(colors[i%len(colors)],i),(ww*px,hh*py),[-24,18,-5][i%3],ww/720)
        if flavor=='Mint':leaf(layer,(ww*.58,hh*.83),ww/500)
    elif fam=='Bakery':
        if flavor=='Bread':
            paste_shadow(layer,bread(2),(ww*.10,hh*.16),-12,ww/440)
            paste_shadow(layer,bread(3),(ww*.26,hh*.49),12,ww/590)
        else:
            paste_shadow(layer,cake(),(ww*.05,hh*.03),-7,ww/430)
            paste_shadow(layer,cake(7),(ww*.38,hh*.42),8,ww/690)
    elif fam=='Spicy':
        for i in range(8):paste_shadow(layer,spicy(i),(ww*(.01+i*.092),hh*(.05+(i%3)*.065)),[-20,-12,15,25][i%4],ww/670)
        d=ImageDraw.Draw(layer)
        for px,py in [(.15,.82),(.72,.76)]:
            d.arc((ww*px,hh*py-40,ww*px+ww*.3,hh*py+30),10,170,fill='#8b2f22',width=int(ww*.045));leaf(layer,(ww*px+ww*.27,hh*py-5),.28)
    elif fam=='Nuts':
        rr=random.Random(74)
        for i in range(23 if flavor=='Seeds' else 14):
            ob=seednut(i) if flavor=='Seeds' else peanut(i)
            paste_shadow(layer,ob,(rr.uniform(.06,.78)*ww,rr.uniform(.02,.65)*hh),rr.uniform(-65,65),ww/(490 if flavor=='Seeds' else 650))
    elif fam=='Jelly':
        cupscale=min(ww/590,hh/345)
        paste_shadow(layer,jellycup(flavor),(ww*.5-200*cupscale,hh*.00),-3,cupscale)
        fruit(layer,(ww*.26,hh*.61),flavor,min(ww/720,hh/170))
        fruit(layer,(ww*.74,hh*.63),flavor,min(ww/960,hh/210))
    im.alpha_composite(layer,(int(x),int(y)))

def decoration(im,col):
    d=ImageDraw.Draw(im);w,h=im.size
    # Small offset linework and restrained half-tone rays add depth without a brand imitation.
    for k in range(16):
        a=k*math.tau/16;x=w*.5+math.cos(a)*w*.65;y=h*.68+math.sin(a)*h*.46
        d.line((w*.5,h*.65,x,y),fill=(*col,28),width=max(2,int(w*.014)))
    d.rectangle((w*.025,h*.015,w*.975,h*.985),outline=(*col,90),width=2)

def barcode(d,box,code):
    x,y,w,h=map(int,box);d.rectangle((x-8,y-7,x+w+8,y+h+24),fill='#f8efdc')
    # Deterministic retail-style bars, with long guard bars and readable digits.
    rr=random.Random(int(code));pos=x
    bars=[1,1,1]+[rr.choice([1,1,2,2,3]) for _ in range(82)]+[1,1,1]
    unit=w/sum(bars)
    for j,b in enumerate(bars):
        if j%2==0:d.rectangle((pos,y,pos+unit*b,max(y,y+h-(0 if j<3 or j>82 else 6))),fill='#3f382e')
        pos+=unit*b
    center(d,(x+w/2,y+h+4),code,18,'#3f382e',latin=True)

def make_art(fam,aspect,flavor,title,tag,color,back=False):
    w=900;h=int(w/aspect);base=rgb(color)
    cream=(245,235,208);ink=(68,48,32);white=(255,247,222)
    pale = fam=='Bakery' and flavor=='Cake'
    im=Image.new('RGBA',(w,h),(*cream,255));d=ImageDraw.Draw(im)
    if back:
        d.rectangle((0,0,w,int(h*.16)),fill=base)
        fitcenter(d,(w*.5,h*.025),title+' · '+tag,w*.9,min(h*.055,68),white if not pale else ink,True)
        center(d,(w*.5,h*.105),'老街小食  ·  一口好滋味',max(14,h*.022),white if not pale else ink)
        margin=w*.065;yy=h*.19;body=max(18,min(27,h*.026));row=body*1.7
        lines=[('产品名称',title+'（'+tag+'）'),('配料', {'Chips':'马铃薯、植物油、食用盐、香辛料','Biscuits':'小麦粉、白砂糖、植物油、乳粉','CandyBag':'白砂糖、葡萄糖浆、果汁、薄荷','Bakery':'小麦粉、鸡蛋、白砂糖、乳粉','Spicy':'小麦粉、植物油、辣椒、香辛料','Nuts':'精选原料、食用盐、香辛料','Jelly':'饮用水、白砂糖、果汁、魔芋粉','CandyJar':'白砂糖、葡萄糖浆、果汁'}[fam]),('贮存条件','置于阴凉干燥处，避免阳光直射'),('保质期','见包装标示'),('生产日期','见封口处喷码'),('温馨提示','开封后请及时食用')]
        for key,val in lines:
            d.text((margin,yy),key+'：',font=font(body,True),fill=ink)
            # Wrap Chinese back-print at the available width.
            tx=margin+body*5;line='';cur=yy
            for ch in val:
                if d.textlength(line+ch,font=font(body))>w-tx-margin:
                    d.text((tx,cur),line,font=font(body),fill=ink);line='';cur+=row
                line+=ch
            d.text((tx,cur),line,font=font(body),fill=ink);yy=cur+row
        # On wide tubs/boxes the information forms two short columns.
        table_y=max(yy+h*.022,h*.48);table_h=min(h*.28,h-table_y-h*.18)
        if table_h<90:table_y=h*.47;table_h=h*.28
        tw=w*.86;tx=w*.07;rrh=table_h/7;ts=max(13,min(body,int(rrh*.54)))
        d.rectangle((tx,table_y,tx+tw,table_y+table_h),outline=ink,width=2)
        center(d,(w/2,table_y+rrh*.10),'营养成分表',ts+3,ink,True)
        rows=[('项目','每 100 克','NRV%'),('能量','2080 千焦','25%'),('蛋白质','6.0 克','10%'),('脂肪','24.0 克','40%'),('碳水化合物','62.0 克','21%'),('钠','380 毫克','19%')]
        for k,items in enumerate(rows):
            ly=table_y+rrh*(k+1);d.line((tx,ly,tx+tw,ly),fill=ink,width=1)
            for cx,t in zip((.21,.54,.81),items):center(d,(tx+tw*cx,ly+rrh*.12),t,ts,ink,k==0)
        barcode(d,(w*.31,h*.835,w*.38,h*.075),'690'+str(sum(ord(c) for c in fam+flavor)).zfill(9)+'8')
        d.text((w*.07,h*.955),'净含量见正面  /  包装请分类投放',font=font(max(12,h*.018)),fill=ink)
    else:
        # Colored top and bottom, cream middle: characteristic corner-shop packages.
        d.rectangle((0,0,w,h*.43),fill=base)
        d.polygon([(0,h*.37),(w,h*.32),(w,h*.52),(0,h*.61)],fill=base)
        d.rectangle((0,h*.90,w,h),fill=base)
        decoration(im,base);d=ImageDraw.Draw(im)
        seal_h=max(10,h*.018)
        for edge in (0,h-seal_h):
            d.rectangle((0,edge,w,edge+seal_h),fill=tuple(int(x*.81) for x in base))
            for sx in range(6,w,12):d.line((sx,edge,sx,edge+seal_h),fill=(*cream,80),width=2)
        brand_y=h*.038
        rounded(d,(w*.335,brand_y,w*.665,brand_y+h*.058),h*.018,cream)
        center(d,(w*.5,brand_y+h*.007),'老街小食',min(44,h*.038),ink,True)
        tc=white if not pale else (110,75,39)
        title_size=min(150,h*.12)
        fitcenter(d,(w*.5,h*.135),title,w*.89,title_size,tc,True)
        center(d,(w*.5,h*.28),{'Chips':'CRISPY POTATO CHIPS','Biscuits':'GOLDEN BAKED BISCUITS','CandyBag':'HAPPY SWEET MOMENTS','Bakery':'SOFT & FRESHLY BAKED','Spicy':'SAVOURY WHEAT SNACK','Nuts':'ROASTED TRADITIONAL SNACK','Jelly':'FRUIT JELLY CUP','CandyJar':'A JAR FULL OF SWEETNESS'}[fam],min(22,h*.026),tc,latin=True)
        ty=h*.35;th=h*.066
        rounded(d,(w*.27,ty,w*.73,ty+th),th*.35,cream)
        center(d,(w*.5,ty+th*.06),tag,min(49,h*.047),ink,True)
        illustration(im,(w*.02,h*.435,w*.96,h*.41),fam,flavor)
        d=ImageDraw.Draw(im)
        slogan={'Chips':'片片金黄  咔嚓好滋味','Biscuits':'慢火烘焙  香酥可口','CandyBag':'甜在口中  乐在心间','Bakery':'柔软细腻  香甜一刻','Spicy':'嚼劲十足  香辣过瘾','Nuts':'粒粒精选  越嚼越香','Jelly':'晶莹果香  清甜爽滑','CandyJar':'分享甜蜜  分享好心情'}[fam]
        center(d,(w*.5,h*.847),slogan,min(35,h*.031),ink,True)
        weight={'Chips':'60 克','Biscuits':'120 克','CandyBag':'90 克','Bakery':'80 克','Spicy':'45 克','Nuts':'100 克','Jelly':'100 克','CandyJar':'220 克'}[fam]
        center(d,(w*.5,h*.926),'净含量：'+weight,min(28,h*.026),tc)
        d.text((w*.045,h*.886),'食物图案仅供参考',font=font(max(11,h*.014)),fill=(*ink,190))
        # A little round emblem evokes independent neighbourhood snack makers.
        er=min(w*.075,h*.08);cx=w*.865;cy=h*.82
        d.ellipse((cx-er,cy-er,cx+er,cy+er),fill=cream,outline=base,width=4)
        center(d,(cx,cy-er*.52),'甄选',er*.49,base,True)
        center(d,(cx,cy+er*.08),'好味',er*.42,base,True)
    # Faded paper/plastic ink; enough variation to read as printed packaging.
    arr=np.array(im.convert('RGB')).astype(np.float32)
    noise=np.random.default_rng(sum(ord(c) for c in fam+flavor)+int(back)).normal(0,.95,(h,w,1))
    yy,xx=np.mgrid[0:h,0:w];shade=1+.006*np.sin(xx*.07)+.005*np.sin(yy*.19)
    arr=np.clip(arr*shade[:,:,None]+noise+np.array([1.0,.5,-.5]),0,255).astype(np.uint8)
    im=Image.fromarray(arr)
    return im

def create(only=None):
    manifest={'version':1,'resolution':[SIZE,SIZE],'color_space':{'BaseColor':'sRGB','ORM':'linear','Normal':'linear, OpenGL +Y'},'atlas_origin':'bottom-left UV; top-left image pixel coordinates','layout':'horizontal flavor bands; front U 0..0.5, back U 0.5..1; 8 px duplicated inset borders','shared_normal':'T_Goods_Pack_Normal.png','normal_note':'subtle print fibre and broad film wrinkles, tangent-space OpenGL +Y','families':{}}
    fronts=[];backs=[]
    for fam,aspect,flavors in FAMILIES:
        atlas=Image.new('RGB',(SIZE,SIZE));orm=Image.new('RGB',(SIZE,SIZE),(255,160,0));entries=[]
        n=len(flavors)
        for index,(flavor,title,tag,color) in enumerate(flavors):
            y0=SIZE-round((index+1)*SIZE/n);y1=SIZE-round(index*SIZE/n)
            rects={}
            for side in ('front','back'):
                x0=0 if side=='front' else SIZE//2;x1=x0+SIZE//2
                art=make_art(fam,aspect,flavor,title,tag,color,side=='back')
                tile=art.resize((x1-x0-2*INSET,y1-y0-2*INSET),Image.Resampling.LANCZOS)
                padded=Image.fromarray(np.pad(np.array(tile),((INSET,INSET),(INSET,INSET),(0,0)),mode='edge'))
                atlas.paste(padded,(x0,y0))
                rects[side]={'pixel_outer_xyxy':[x0,y0,x1,y1],'pixel_content_xyxy':[x0+INSET,y0+INSET,x1-INSET,y1-INSET],'uv_outer':[x0/SIZE,1-y1/SIZE,x1/SIZE,1-y0/SIZE],'uv_content':[(x0+INSET)/SIZE,1-(y1-INSET)/SIZE,(x1-INSET)/SIZE,1-(y0+INSET)/SIZE]}
                # Ink changes roughness slightly; sealed bag remains plastic, box paper rougher.
                arr=np.asarray(padded).astype(np.float32);lum=arr.mean(axis=2)
                rough={'Biscuits':178,'Bakery':167,'Nuts':163,'Jelly':131,'CandyJar':151}.get(fam,150)
                rr=np.clip(rough+(lum-150)*.022+np.random.default_rng(index+len(fam)).normal(0,1.2,lum.shape),0,255).astype(np.uint8)
                oa=np.zeros_like(arr,dtype=np.uint8);oa[:,:,0]=255;oa[:,:,1]=rr
                orm.paste(Image.fromarray(oa),(x0,y0))
                if side=='front':fronts.append((fam,flavor,art))
                elif index==0:backs.append((fam,flavor,art))
            entries.append({'id':flavor,'title':title,'flavor_label':tag,'order_from_bottom':index,'v_band':[1-y1/SIZE,1-y0/SIZE],'rects':rects})
        bc=f'T_Goods_{fam}_BaseColor.png';om=f'T_Goods_{fam}_ORM.png'
        if only is None or fam in only:
            atlas.save(OUT/bc,compress_level=6);orm.save(OUT/om,compress_level=6)
        manifest['families'][fam]={'front_art_width_over_height':aspect,'base_color':bc,'orm':om,'flavors':entries}
        print(f'{fam}: {bc}, {om}',flush=True)
    # A continuous field can be tiled across all packaging without a hard center seam.
    yy,xx=np.mgrid[0:SIZE,0:SIZE];x=xx/SIZE*math.tau;y=yy/SIZE*math.tau
    height=.48*np.sin(x*3+y*2)+.22*np.sin(x*9-y*5)+.13*np.sin(x*19+y*11)+.035*np.sin(x*190)+.022*np.sin(y*330)
    height+=np.random.default_rng(52).normal(0,.012,(SIZE,SIZE))
    dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*1.3
    dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*1.3
    normal=np.stack((-dx,dy,np.ones_like(dx)),axis=2);normal/=np.linalg.norm(normal,axis=2)[:,:,None]
    if only is None:
        Image.fromarray(np.clip((normal*.5+.5)*255,0,255).astype('uint8')).save(OUT/'T_Goods_Pack_Normal.png',compress_level=6)
    (OUT/'SnackPackaging_AtlasManifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Front previews retain their intended physical aspect, independent of atlas storage.
    cw,ch=400,650;sheet=Image.new('RGB',(cw*6,ch*3),(43,46,48));d=ImageDraw.Draw(sheet)
    for j,(fam,flavor,art) in enumerate(fronts):
        cx=(j%6)*cw;cy=(j//6)*ch
        art.thumbnail((cw-28,ch-65),Image.Resampling.LANCZOS)
        sheet.paste(art,(cx+(cw-art.width)//2,cy+42+(ch-65-art.height)//2))
        center(d,(cx+cw/2,cy+8),fam+' / '+flavor,20,(238,233,216),latin=True)
    sheet.save(OUT/'SnackPackaging_ContactSheet.jpg',quality=93)
    sheet=Image.new('RGB',(cw*4,ch*2),(43,46,48));d=ImageDraw.Draw(sheet)
    for j,(fam,flavor,art) in enumerate(backs):
        cx=(j%4)*cw;cy=(j//4)*ch
        art.thumbnail((cw-28,ch-65),Image.Resampling.LANCZOS)
        sheet.paste(art,(cx+(cw-art.width)//2,cy+42+(ch-65-art.height)//2))
        center(d,(cx+cw/2,cy+8),fam+' / BACK',20,(238,233,216),latin=True)
    sheet.save(OUT/'SnackPackaging_BackProof.jpg',quality=93)
    print('Created 16 family maps, shared normal, manifest, and contact sheet.',flush=True)

if __name__=='__main__':create()
