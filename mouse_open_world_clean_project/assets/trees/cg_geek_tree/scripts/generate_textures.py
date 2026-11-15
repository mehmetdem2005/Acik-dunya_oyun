"""Generate small ORIGINAL placeholder bark and leaf branch images. Pillow only."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math,random
BASE=Path(__file__).resolve().parent.parent
ASSETS=BASE/'assets';ASSETS.mkdir(exist_ok=True)

def bark():
    rng=random.Random(21); w,h=256,512
    im=Image.new('RGBA',(w,h))
    px=im.load()
    streaks=[(rng.uniform(-1,1),rng.uniform(.05,2.0),rng.uniform(0,7)) for _ in range(14)]
    for y in range(h):
        for x in range(w):
            v=.5+.15*math.sin(x*.097+2*math.sin(y*.014))+.09*math.sin(x*.28+math.sin(y*.09))
            for amp,freq,shift in streaks:
                v+=amp*.018*math.sin(x*freq*.24+shift+math.sin(y*.018))
            v+=(rng.random()-.5)*.07
            v=max(0,min(1,v))
            px[x,y]=(int(54+58*v),int(37+40*v),int(23+22*v),255)
    im.save(ASSETS/'bark_original_256.png', optimize=True)

def leaf():
    rng=random.Random(7)
    sz=512
    im=Image.new('RGBA',(sz,sz),(0,0,0,0))
    d=ImageDraw.Draw(im,'RGBA')
    # Original painted leaf group; entirely provisional until final texture is supplied.
    branches=[((254,460),(256,264)),((258,355),(147,200)),((257,330),(357,189)),
              ((248,412),(190,306)),((253,385),(319,293)),((258,290),(262,120))]
    for (x0,y0),(x1,y1) in branches:
        d.line([(x0,y0),(x1,y1)],fill=(71,92,42,255),width=9)
    ellipse_specs=[(262,133,78,41,-8),(171,187,83,39,-45),(352,178,80,43,44),
                   (194,288,65,36,-30),(319,275,70,42,35),(131,234,58,37,-50),
                   (380,225,58,35,47),(252,243,69,35,4),(286,321,62,31,18),
                   (218,351,67,34,-23),(306,141,67,34,27),(203,146,57,32,-20)]
    # rotate a locally generated leaf polygon about each center
    for cx,cy,rx,ry,ang in ellipse_specs:
        ang=math.radians(ang)
        pts=[]
        for i in range(13):
            t=i/12*math.pi
            # elliptical full leaf (tip -> widest -> tip)
            x= -rx + 2*rx*i/12
            y=math.sin(t)*ry * (1 if i<=6 else .97)
            for vy in [y] if i==0 or i==12 else [y]:
                pts.append((cx+x*math.cos(ang)-vy*math.sin(ang),cy+x*math.sin(ang)+vy*math.cos(ang)))
        for i in range(11,-1,-1):
            t=i/12*math.pi;x=-rx+2*rx*i/12;y=-math.sin(t)*ry
            pts.append((cx+x*math.cos(ang)-y*math.sin(ang),cy+x*math.sin(ang)+y*math.cos(ang)))
        green=(60+rng.randint(-12,18),125+rng.randint(-24,22),45+rng.randint(-12,10),255)
        d.polygon(pts,fill=green)
        # an irregular light vein
        d.line([(cx-rx*.8*math.cos(ang),cy-rx*.8*math.sin(ang)),
                (cx+rx*.8*math.cos(ang),cy+rx*.8*math.sin(ang))],
               fill=(120,164,76,110),width=3)
    im.save(ASSETS/'leaf_PLACEHOLDER.png', optimize=True)

if __name__=='__main__':
    bark();leaf();print('Original temporary bark and alpha leaf PNGs generated')