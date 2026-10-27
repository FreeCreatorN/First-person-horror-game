"""V3 architectural review drawings only. No UE imports or Content writes."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from pypdf import PdfReader
import DrawOldTownRedesignReviewV2 as b

ROOT = b.ROOT
OUT = ROOT / 'Saved/CodexOutputs/ArchitectureRedesignReview_20261008_V3'
C, W, H = b.C, b.W, b.H
Plan, text, wrapped, notes = b.Plan, b.text, b.wrapped, b.notes
furniture, toilet, basin = b.furniture, b.toilet, b.basin
translated = b.translated


def sheet(n, title, subtitle):
    im = Image.new('RGB', (W, H), C['paper'])
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 24), fill=C['guest'])
    text(d, (170, 92), '老城街区  /  建筑重设计', 36, C['muted'], True)
    text(d, (170, 166), title, 74, bold=True)
    text(d, (170, 274), subtitle, 37, C['muted'])
    d.rounded_rectangle((3410, 88, 4030, 180), radius=20, fill=C['circulation'])
    text(d, (3720, 130), 'V3  审查稿 · 未实施', 35, C['guest'], True, 'mm')
    d.line((170, 355, 4030, 355), fill=C['grid'], width=3)
    d.line((170, 2820, 4030, 2820), fill=C['grid'], width=3)
    text(d, (170, 2855), '2026-10-08  |  先审查平面，再建模  |  单位：m  |  面积为方案估算', 31, C['muted'])
    text(d, (4020, 2866), f'{n:02d} / 07', 35, C['muted'], anchor='ra')
    return im, d


def enclosed(p, clear, fill):
    x0, y0, x1, y1 = clear
    p.rect((x0-.2, y0-.2, x1+.2, y1+.2), C['wall'])
    p.rect(clear, fill)


def safety_stair(p, ground=False, detail=True):
    # Rotated U stair: right = SAME FLOOR; left = half-storey turn platform.
    # Clear 5.88 x 3.20. Two 1.40 m flights, 3.08 run, 1.40 end landings.
    enclosed(p, (10.72, .2, 16.60, 3.40), C['circulation'])
    for ya, yb in ((.2, 1.6), (2.0, 3.4)):
        p.rect((12.12, ya, 15.20, yb), '#EEF3F5', C['muted'], 3)
        for i in range(12):
            xx = 12.12 + 3.08*i/11
            p.line((xx, ya), (xx, yb), C['muted'], 2)
    p.rect((12.12, 1.6, 15.2, 2.0), C['paper'], C['muted'], 2)
    p.line((12.18,1.66),(15.14,1.94),C['muted'],2)
    p.line((12.18,1.94),(15.14,1.66),C['muted'],2)
    p.route([(15.0,.9),(12.35,.9)],dash=False)
    p.route([(12.35,2.7),(15.0,2.7)],dash=False)
    # Corridor door opens inside onto the SAME FLOOR platform, never onto steps.
    p.door(16.50, 3.50, 1.2, 'W', 'S')
    if ground:
        p.door(15.30, .10, 1.2, 'E', 'S')
        p.route([(15.90,1.40),(15.90,-1.0)],dash=False)
    if detail:
        p.label(11.42,1.8,'半层\n转台',28)
        p.label(15.90,1.85,'同层\n平台',28)
        p.label(13.65,2.7,'上',25,C['guest'])
    else:
        p.label(13.25,1.8,'安全梯',25)


def lift(p, detail=True):
    enclosed(p, (16.8,7.2,19.8,10.2), C['service'])
    p.door(17.6,7.1,1.4,'E','S',False)
    p.label(18.3,8.9,'电梯井\n3 × 3',36 if detail else 26)


def lobby(p, detail=True):
    p.rect((.2,.2,19.8,10.2),C['public'])
    # All three offices form one rear row; doors face the same staff corridor.
    offices=[((.2,7.0,4.2,10.2),'前台办公室\n12.8㎡'),
             ((4.4,7.0,7.4,10.2),'值班 / 员工\n9.6㎡'),
             ((7.6,7.0,10.52,10.2),'管理 / 弱电\n9.3㎡')]
    for box, label in offices:
        enclosed(p,box,C['service'])
        cx=(box[0]+box[2])/2
        p.door(cx-.45,6.9,.9,'E','N')
        if detail:
            furniture(p,(box[0]+.3,9.05,min(box[0]+1.7,box[2]-.25),9.75),'desk')
        p.label(cx,8.2,label,32 if detail else 24)
    # Vestibule shifted left to leave the new independent stair exit clear.
    enclosed(p,(5.6,.2,9.6,3.0),C['circulation'])
    p.double(6.6,.1,2,'N');p.double(6.6,3.1,2,'N')
    p.label(7.6,1.55,'门斗\n4 × 2.8',34 if detail else 25)
    furniture(p,(.8,4.6,5.0,5.4))
    p.label(2.9,5.0,'前台 4.2m',33 if detail else 25)
    # Two seats left and eight rear. Front and the east staff doorway stay clear.
    furniture(p,(.8,2.9,3.0,3.7),'sofa')
    furniture(p,(1.25,3.95,2.55,4.4),'desk')
    furniture(p,(10.92,7.45,11.72,9.55),'sofa')
    furniture(p,(15.2,7.45,16.0,9.55),'sofa')
    furniture(p,(12.1,8.2,14.65,8.9),'desk')
    for x in (12.2,14.0):furniture(p,(x,7.2,x+.65,7.85),'sofa')
    furniture(p,(12.2,9.3,14.4,10.1),'sofa')
    safety_stair(p,True,detail)
    lift(p,detail)
    p.route([(7.6,-1.0),(7.6,.4)])
    p.route([(7.6,3.4),(6.5,4.1),(4.3,4.1)])
    p.route([(7.6,3.6),(7.6,4.8),(13.4,4.8),(17.4,4.8),(17.4,6.2),(18.3,6.2),(18.3,6.8)])
    # Left/right corridor branches bypass the stair on its rear side.
    p.route([(5.2,4.2),(4.2,4.2),(4.2,1.3),(0,1.3)])
    p.route([(17.4,4.8),(18.0,4.8),(18.0,1.3),(20,1.3)])
    p.route([(13.4,4.8),(15.9,4.8),(15.9,3.8)])
    p.route([(5.7,6.2),(2.9,6.2),(2.9,5.8)],True)
    p.route([(5.7,6.2),(10.1,6.2),(16.0,6.2),(20.0,6.2)],True)
    if detail:
        p.label(1.9,2.55,'2座短候',29)
        p.label(13.4,6.95,'8座会客区',30)
        p.label(12.3,5.45,'公共过厅 / 绕梯通行',33,C['guest'])
        p.label(5.9,6.2,'员工通道 1.4',29,C['staff'])
        p.label(18.0,5.5,'候梯',29,C['guest'])
        p.win((.5,.1),(4.9,.1))
        p.win((17.2,.1),(19.6,.1))
    # External walls are reopened only at the shared passage connections.
    p.door(.1,.4,1.8,'N','E',False)
    p.door(19.9,.4,1.8,'N','W',False)
    p.door(19.9,5.5,1.4,'N','W',False)


def draw_first_floor():
    im,d=sheet(2,'酒店首层  /  后场成排，新增临街安全梯','大厅右后角电梯；办公室集中后墙；取消行李室。首层无客房，住宅方案沿用V2。')
    p=Plan(d,330,680,50,10.4)
    b.hotel_shell(p,True)
    # Dining and two public WCs retain the reviewed V2 arrangement.
    p.wall((6,2.5),(26,2.5));p.wall((20,2.6),(20,10.2));p.wall((26,.2),(26,10.2))
    p.rect((6.2,2.6,19.8,10.2),C['public'])
    p.rect((20.2,2.6,25.8,5.6),C['service'])
    p.rect((20.2,5.8,25.8,10.2),C['service'])
    p.wall((20,5.7),(26,5.7));p.wall((22.9,2.6),(22.9,5.6),.12)
    p.double(10.1,2.5,1.8,'N')
    p.door(21.4,2.5,.9,'E','N');p.door(23.5,2.5,1,'E','N');p.door(20,7,1,'N','W')
    for xx in (8,12,16):
        for yy in (4.1,7.4):
            furniture(p,(xx,yy,xx+1.3,yy+.8),'desk')
            for cx in (xx+.1,xx+.75):
                for cy in (yy-.65,yy+.9):furniture(p,(cx,cy,cx+.45,cy+.45))
    furniture(p,(24.6,6.3,25.6,9.8))
    toilet(p,21,5);toilet(p,24.7,5)
    basin(p,(20.4,2.8,21.1,3.4));basin(p,(25,2.8,25.6,3.4))
    p.label(13,9.35,'早餐 / 茶厅 24座',34)
    p.label(23,8.1,'备餐',32);p.label(21.5,4,'WC 1',26);p.label(24.5,4.1,'WC 2',26)
    p.wall((46,.2),(46,10.2))
    lobby(translated(p,26),False)
    # Rear service rooms align with the offices at y7.0..10.2.
    p.rect((46.2,2.6,63.8,6.8),C['service'])
    p.wall((46,2.5),(64,2.5))
    parts=[((46.2,7,50.4,10.2),'清布草'),((50.6,7,54.8,10.2),'污布草'),
           ((55,7,58.8,10.2),'更衣'),((59,7,61.2,10.2),'员工WC'),
           ((61.4,7,63.8,10.2),'设备')]
    for box,label in parts:
        enclosed(p,box,C['service'])
        cx=(box[0]+box[2])/2
        p.door(cx-.45,6.9,.9,'E','N')
        p.label(cx,8.6,label,27)
    toilet(p,60.7,9.5);basin(p,(59.2,9.4,59.9,10))
    for xx in (47,51):furniture(p,(xx,3.2,xx+2.7,4.0),'cabinet')
    p.label(55,4.4,'后勤操作 / 备品整理',31,C['staff'])
    p.label(55,6.2,'成排房间，各自开门',28,C['staff'])
    p.double(60.3,.2,1.4,'N');p.double(60.3,2.5,1.4,'N')
    p.route([(61,-1),(61,5.2),(56,5.2),(56,6.5)],True)
    p.route([(56,5.2),(47.5,5.2),(47.5,6.2),(46.1,6.2)],True)
    for xx in (8,12,16,20.5,24,27,31,35,47,51,55,59,62):p.win((xx,10.3),(xx+1.5,10.3))
    p.hdim(0,70,12.4,'70.0 m 总长',38)
    for a,z,v in [(0,6,'6 南梯'),(6,20,'14 餐茶'),(20,26,'6 WC / 备餐'),
                  (26,46,'20 大厅'),(46,64,'18 后勤'),(64,70,'6 北梯')]:p.hdim(a,z,11.35,v,31)
    p.vdim(-1.1,0,10.4,'10.4',35)
    for xx,label,col in [(33.6,'主入口','guest'),(41.9,'安全梯出口','guest'),(61,'后勤入口','staff'),(3,'出口','guest'),(67,'出口','guest')]:
        p.label(xx,-1.6,label,31,C[col],True)
    text(d,(330,1410),'中央20m段  /  公共净区约127㎡  /  后墙房间成排',55,bold=True)
    text(d,(330,1508),'井道位于大厅右后角；新增封闭安全梯直接临街；取消行李室后不另设寄存房。',37,C['muted'])
    b.legend(d,330,1610)
    notes(d,330,1790,1050,'前场：接待与候客',[
        ('门斗移向左侧','门斗正对公共过厅，前台在左前方；10个候客座席与入口、候梯流线分开。'),
        ('新增安全梯独立出口','临街封闭梯在同层平台开入口，首层直接出街；大厅路线绕梯后侧通行。')],36)
    notes(d,1660,1790,1050,'后场：一排房间',[
        ('办公室统一排布','前台办公室、员工值班、管理/弱电沿后墙一排，门均面向同一条1.4m员工通道。'),
        ('北段后勤也沿后墙排布','清布草、污布草、更衣、员工WC、设备各有独立门；前侧留整理与收货区域。')],36)
    notes(d,2980,1790,970,'同步处理上层',[
        ('位置逐层一致','角部电梯井与新增楼梯上下对齐；原两端楼梯保留，客房门仍面向共有走廊。'),
        ('不硬塞客房','上层核心扩大到15m，左右共9间/层；三层合计27间。下一步复核结构与级数。')],36)
    return b.save(im,'02_Hotel_GroundFloor')


def draw_lobby():
    im,d=sheet(3,'接待大厅放大  /  角部电梯与临街安全梯','对应首层26–46m段；前场候客、后场成排办公室，各层电梯与楼梯对齐。')
    p=Plan(d,340,690,132,10.4)
    p.rect((0,-1.7,20,0),'#ECE8DD')
    p.rect((0,0,20,10.4),C['wall'])
    lobby(p,True)
    p.hdim(0,20,11.8,'20.0 m 大厅段',38)
    p.vdim(-.75,.2,10.2,'10.0 m',36)
    p.label(7.6,-1.2,'主入口',35,C['guest'],True)
    p.label(15.9,-1.25,'安全梯直接出街',32,C['guest'],True)
    p.label(2.3,-1.15,'临街前场（局部）',30,C['muted'])
    notes(d,3130,595,860,'这次四处调整',[
        ('电梯在大厅右后角','井道净3×3m。门面向公共候梯区，去电梯不用经过办公室。'),
        ('后墙统一成排','三间办公室的门对同一条员工通道，前台背后直接接入。'),
        ('行李室完全取消','不保留旧隔墙或换名；左侧回到候客与接待空间。'),
        ('新增封闭安全梯','两跑各净1.4m，同层平台在右端；从平台直接出街，不经过办公室。')],35)
    text(d,(340,2470),'空间核算与下一步',45,bold=True)
    wrapped(d,(340,2550),'中央段内净区196㎡；扣成排房间围护、楼梯围护、井道与门斗隔墙后，公共净区约127㎡（含门斗、柜台与座席）。楼梯净5.88×3.2m，围护6.28×3.6m；级数随各层高度细化。',2660,36,C['muted'])
    return b.save(im,'03_Hotel_Lobby_Enlarged')


def hotel_room(p,x=0,bay=5,twin=True,detail=True):
    # Right-wing rooms are 4.5m bays, with adapted furniture, not a stretched 5m plan.
    p.rect((x+.1,2.6,x+bay-.1,10.2),C['private'])
    p.wall((x,2.5),(x+bay,2.5));p.wall((x,2.6),(x,10.2));p.wall((x+bay,2.6),(x+bay,10.2))
    entry=x+bay-1.6
    p.door(entry,2.5,1,'E','N')
    p.rect((x+.2,2.6,x+2.6,5.0),'#E5EEEA',C['wall'],max(5,round(.12*p.s)))
    p.door(x+2.6,3.5,.85,'N','W',False)
    p.rect((x+.3,2.8,x+1.25,3.75),None,C['muted'],3)
    toilet(p,x+.85,4.45);basin(p,(x+1.7,2.8,x+2.5,3.4))
    p.rect((x+2.05,4.5,x+2.5,4.95),C['wall'])
    furniture(p,(x+bay-.7,3.85,x+bay-.1,5.65),'cabinet')
    if twin:
        furniture(p,(x+.5,7.7,x+1.5,9.7),'bed')
        furniture(p,(x+bay-1.55,7.7,x+bay-.55,9.7),'bed')
    else:furniture(p,(x+1.2,7.7,x+2.8,9.7),'bed')
    desk_x=1.7 if twin else 3.1
    furniture(p,(x+desk_x,9.5,x+desk_x+1.1,10.1),'desk')
    furniture(p,(x+.4,5.45,x+1.2,6.8),'sofa')
    furniture(p,(x+1.65,5.65,x+2.8,6.3),'desk')
    p.win((x+1.25,10.3),(x+bay-1.25,10.3))
    if detail:
        p.label(x+1.4,4.05,'卫浴',32)
        p.label(x+bay-1,3.1,'入口',28)
        p.label(x+bay/2,7.0,'床前通行',30,C['guest'])
        p.route([(entry+.5,2.1),(entry+.5,4.5),(x+3.1,6.9),(x+bay/2,8.8)])


def upper_core(p,detail=True):
    # Coordinates relative to s26, as on the ground floor. Core starts at local x5.
    p.rect((5.1,.2,19.9,10.2),C['circulation'])
    p.wall((5,2.5),(5,10.2));p.wall((20,2.5),(20,10.2))
    safety_stair(p,False,detail);lift(p,detail)
    for box,label in [((5.2,7.0,8.6,10.2),'楼层布草'),((8.8,7.0,10.5,10.2),'清洁')]:
        enclosed(p,box,C['service'])
        p.door(box[0]+.3,6.9,.9,'E','N')
        p.label((box[0]+box[2])/2,8.5,label,29 if detail else 24)
    p.route([(5,1.3),(7.2,1.3),(7.2,4.8),(18.3,4.8),(18.3,1.3),(20,1.3)])
    p.route([(18.3,4.8),(18.3,6.8)])
    p.route([(14.0,4.8),(15.9,4.8),(15.9,3.8)])
    if detail:
        p.label(12.2,5.5,'绕梯的公共过厅',32,C['guest'])
        p.label(6.4,3.0,'左侧\n5.42',28,C['guest'])
        p.label(18.6,2.7,'右侧\n3.10',28,C['guest'])
        p.label(18.25,6.1,'候梯',28,C['guest'])
        p.label(12.5,6.45,'上层无临街出口，走廊绕梯间',27,C['muted'])


def draw_standard():
    im,d=sheet(4,'酒店标准层  /  核心贯通，9间一层共27间','原两端楼梯 + 新增中部封闭梯；电梯井与首层同位，公共走廊绕新梯后侧。')
    p=Plan(d,330,550,50,10.4)
    b.hotel_shell(p)
    for i in range(5):
        x=6+i*5;hotel_room(p,x,5,i%3!=2,False)
        p.label(x+2.5,6.7,f'2{i+1:02d}\n36.5㎡',28)
    for i in range(4):
        x=46+i*4.5;hotel_room(p,x,4.5,i%3!=1,False)
        p.label(x+2.25,6.7,f'2{i+6:02d}\n32.7㎡',28)
    upper_core(translated(p,26),False)
    p.hdim(0,70,12.6,'70.0 m',36)
    for a,z,v in [(0,6,'6'),(6,31,'5 × 5.0 = 25'),(31,46,'15 交通核心'),(46,64,'4 × 4.5 = 18'),(64,70,'6')]:p.hdim(a,z,11.5,v,31)
    p.vdim(-1,.2,2.4,'2.2',30);p.vdim(-1,2.6,10.2,'7.6',30)
    text(d,(330,1170),'右段4.5m客房放大',45,bold=True)
    q=Plan(d,425,1430,140,10.4)
    hotel_room(q,0,4.5,True,True)
    q.hdim(.1,4.4,11.2,'净宽4.3m',32)
    q.vdim(-.6,2.6,10.2,'净深7.6',30)
    q.label(2.25,1.9,'共有走廊',30,C['guest'])
    text(d,(1420,1170),'中部15m交通核心放大',45,bold=True)
    a=Plan(d,1430,1430,96,10.4)
    a.rect((0,0,15,10.4),C['wall'])
    upper_core(translated(a,-5),True)
    a.hdim(0,15,11.2,'与首层同轴：电梯 + 安全梯',31)
    notes(d,3120,1330,885,'为首层修改同步让位',[
        ('房数重新核算','左五房各36.5㎡，右四房各32.7㎡，含卫浴；201–209 / 301–309 / 401–409。'),
        ('电梯没有错层','净井道s42.8–45.8，y7.2–10.2；各层位置完全一致。'),
        ('楼梯不作穿行通道','两端走廊经公共过厅绕中部梯间；门只接同层平台，不把梯间当捷径。'),
        ('下一步再定级数','此图示两跑与1.4m平台。原柱梁、层高、门型及完整疏散距离仍需深化。')],35)
    text(d,(330,2690),'面积为房内清晰围合估算；上层新增梯不占用客房。图纸未实施，原地图保持。',34,C['muted'])
    return b.save(im,'04_Hotel_TypicalFloor')


def draw_site():
    # Reuse verified V2 site geometry, changing only the hotel callout and entry.
    # Explicitly generate the site rather than retouching a raster drawing.
    im,d=sheet(1,'街区入口系统  /  单元共住与酒店新核心','住宅各层共用单元楼道；道路、步道、巷口沿用。V3调整酒店大厅与交通核心。')
    p=Plan(d,260,500,29,70)
    def r(x0,y0,x1,y1,fill):p.rect((x0-6,y0+35,x1-6,y1+35),fill,C['muted'],3)
    r(6,-3.5,82.5,3.5,'#D9DADA');r(6,3.5,82.5,5.3,'#ECE8DD');r(6,-5.3,82.5,-3.5,'#ECE8DD')
    r(75.5,-20.75,82.5,20.75,'#D9DADA');r(82.5,-20.75,84.3,20.75,'#ECE8DD');r(84.3,-35,90,35,'#F0EBDD')
    p.label(44,35,'主街  /  7.0m机动车道',42,C['muted'])
    for north in (False,True):
        y0,y1=(21,31) if north else (-31,-21)
        for k in range(4):
            x0=6+15*k;r(x0,y0,x0+15,y1,C['private'])
            p.label(x0+7.5-6,(y0+y1)/2+35,f'{"北" if north else "南"}{k+1}单元\n上层多户共住',30)
            doorY=y0 if north else y1;px,py=p.p(x0+7.5-6,doorY+35)
            d.ellipse((px-12,py-12,px+12,py+12),fill=C['guest'])
            p.route([(x0+7.5-6,doorY+35+(-1.5 if north else 1.5)),(x0+7.5-6,doorY+35+(.65 if north else -.65))],dash=False)
    p.label(30,69,'北侧连排：60m = 4个15m单元',38,C['ink'],True)
    p.label(30,1,'南侧连排：共有楼道 → 分户门',36,C['ink'],True)
    fronts=[(8,-13.3,13,-5.3,'店'),(14.5,-15.3,23.5,-5.3,'C'),(27.9,-13.8,34.4,-5.3,'店'),(35.9,-16.3,45.9,-5.3,'A'),(47.4,-15.3,56.4,-5.3,'多户'),(14,5.3,23.5,15.3,'D'),(27.9,5.3,36.9,17.3,'多户'),(38.4,5.3,48.4,16.3,'B'),(49.9,5.3,57.9,15.3,'多户')]
    for x0,y0,x1,y1,name in fronts:
        r(x0,y0,x1,y1,C['public'] if name=='店' else C['private'])
        p.label((x0+x1)/2-6,(y0+y1)/2+35,f'{name}\n店 / 住宅' if name!='店' else '单层\n商铺',29)
        if name!='店':
            yy=y1 if y1<0 else y0;xx=x0+.9
            p.route([(xx-6,yy+35+(.8 if yy<0 else -.8)),(xx-6,yy+35+(-.6 if yy<0 else .6))],dash=False)
    r(90,-35,100.4,35,C['public'])
    p.label(89.2,61,'北梯',34);p.label(89.2,9,'南梯',34)
    p.label(89.2,36,'酒店\n中央\n大厅',40,C['guest'],True)
    p.route([(77.8,33.6),(82.5,33.6),(85.5,33.6)],dash=False)
    p.route([(85.5,41.9),(82.5,41.9)],dash=False)
    p.hdim(0,60,72.5,'60.0m 连排住宅',36)
    p.label(43,54.5,'后街 / 生活通行',32,C['muted']);p.label(43,14.5,'后街 / 生活通行',32,C['muted'])
    notes(d,3380,520,655,'入口与共用交通',[
        ('同楼多户','住宅先进入共用单元门，楼上再分到各家住户。详图沿用V2。'),
        ('连排按单元划分','后排连续60m分四个15m单元，每个单元楼梯服务多户。'),
        ('酒店重新排核心','首层20m中央大厅，后墙房间成排；角部电梯、新增临街安全梯。'),
        ('上层同步','三层各9间，共27间。电梯与楼梯位置逐层对齐。')],34)
    b.legend(d,260,2655)
    text(d,(260,2730),'蓝色为共有入口 / 客人通行；酒店前场新增梯出口。外围为位置示意，室内详图见02–07。',31,C['muted'])
    return b.save(im,'01_District_Entry_System')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b.OUT=OUT;b.sheet=sheet
    protected=[ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap',
               ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json',
               ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261007_V2/OldTown_Architecture_Redesign_V2_Review.pdf']
    before={str(p):sha(p) for p in protected}
    paths=[draw_site(),draw_first_floor(),draw_lobby(),draw_standard(),b.draw_house(5,True),b.draw_house(6,False),b.draw_narrow()]
    pdf=OUT/'OldTown_Architecture_Redesign_V3_Review.pdf'
    c=canvas.Canvas(str(pdf),pagesize=(420*mm,297*mm))
    c.setTitle('Old Town Architecture Redesign V3 - Hotel Ground Floor Review')
    c.setAuthor('Codex | HorrorGame architecture review')
    for path in paths:c.drawImage(ImageReader(str(path)),0,0,width=420*mm,height=297*mm);c.showPage()
    c.save()
    assert len(PdfReader(str(pdf)).pages)==7
    assert before=={str(p):sha(p) for p in protected},'Protected map/evidence/V2 changed during drawing.'
    assert sum((6,25,15,18,6))==70
    net=196 - (10.52*3.4) - (6.28*3.4) - (3.2*3.2) - 1.2
    v2=json.loads((ROOT/'Saved/CodexOutputs/ArchitectureRedesignReview_20261007_V2/Proposal.json').read_text(encoding='utf-8'))
    proposal=dict(status='AWAITING_USER_REVIEW',implemented=False,review_date='2026-10-08',
        created_at_utc=datetime.now(timezone.utc).isoformat(),changes_to_ue_assets=0,
        protected_file_sha256=before,
        hotel=dict(shell_m=[70,10.4],floors=4,ground_guest_rooms=0,upper_rooms_per_floor=9,total_rooms=27,
            lobby_segment_m=[26,46],lobby_region_nominal_m2=200,lobby_clear_envelope_m2=196,
            public_lobby_estimated_m2=round(net,2),public_area_definition='Includes vestibule, reception counter and seats; excludes rear office enclosure, enclosed stair, shaft and vestibule walls. Concept geometry, not measured existing building.',
            area_deductions_m2=dict(rear_office_enclosure=35.768,stair_enclosure_inside_lobby=21.352,lift_enclosure_inside_lobby=10.24,vestibule_walls_after_door_openings=1.2),
            luggage_room=False,waiting_seats=10,dining_seats=24,reception_counter_m=4.2,
            office_clear_boxes_lobby_local_m=[[.2,7,4.2,10.2],[4.4,7,7.4,10.2],[7.6,7,10.52,10.2]],office_staff_passage_clear_m=1.4,
            reception_counter_clear_box_lobby_local_m=[.8,4.6,5,5.4],staff_passage_clear_y_m=[5.4,6.8],
            lift_clear_global_sd_m=[42.8,7.2,45.8,10.2],lift_clear_m=[3,3],lift_corner='Lobby rear-right',
            central_stair_clear_global_sd_m=[36.72,.2,42.6,3.4],central_stair_enclosure_global_sd_m=[36.52,0,42.8,3.6],
            central_stair_flight_clear_m=1.4,central_stair_run_m=3.08,central_stair_landings_m=1.4,
            central_stair_same_floor_landing_side='right',central_stair_ground_exit_global_s_m=[41.3,42.5],central_stair_lobby_door_global_s_m=[41.3,42.5],
            central_stair_floor_opening='Two flight runs and half-level turn landing; preserve right same-floor landing. To detail with actual slab heights before modelling.',
            upper_core_segment_m=[31,46],left_room_bay_m=5,right_room_bay_m=4.5,
            left_rooms_per_floor=5,right_rooms_per_floor=4,left_room_envelope_m2=36.48,right_room_envelope_m2=32.68,
            wing_corridor_clear_m=2.2,core_bypass_clear_y_m=[3.6,6.8],left_stair_bypass_clear_x_m=[31.1,36.52],right_stair_bypass_clear_x_m=[42.8,45.9],
            upper_public_route_global_sd_m=[[31,1.3],[33.2,1.3],[33.2,4.8],[44.3,4.8],[44.3,1.3],[46,1.3]],
            ground_program_segments=[['south_stair',0,6],['tea_dining',6,20],['wc_pantry',20,26],['lobby_offices_lift_new_stair',26,46],['staff_rooms',46,64],['north_stair',64,70]]),
        residential=v2['residential'],drawing=dict(pages=7,pixel_size=[W,H],paper_mm=[420,297],units='metres',page_files=[p.name for p in paths],png_sha256={p.name:sha(p) for p in paths},pdf=pdf.name,pdf_sha256=sha(pdf)),
        open_items=['User review of ground lobby, corner lift and new stair arrangement.',
                    'Actual floor heights, riser count, slab openings, door fire construction, existing columns and complete egress distances require detailed design before UE implementation.',
                    'Residential proposals unchanged from V2; narrow-house interiors still need further detailing.'],
        sources=[dict(title='UK Government - Fire safety risk assessment: sleeping accommodation',url='https://www.gov.uk/government/publications/fire-safety-risk-assessment-sleeping-accommodation/fire-safety-risk-assessment-sleeping-accommodation-accessible',use='General circulation reference: enclosed stair to an outside exit and public route around its enclosure. Not Chinese approval or project dimension criteria.')])
    (OUT/'Proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,status=proposal['status'],pages=7,hotel_rooms=27,public_lobby_m2=round(net,2),protected_files_unchanged=True,output=str(OUT)),ensure_ascii=False))


if __name__=='__main__':main()
