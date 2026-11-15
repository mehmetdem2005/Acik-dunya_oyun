"""Deterministic low-poly broadleaf tree geometry,  Z-up metres. No dependencies.

This is an ORIGINAL procedural implementation inspired by the techniques
shown in CG Geek's 2019 low-poly tree video; not a ripped or extracted model.
Texture leaves are placeholder cards designed for a future user-supplied PNG.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass

TAU = 2.0 * math.pi

@dataclass
class MeshData:
    vertices: list
    faces: list
    uv: list

class Builder:
    def __init__(self):
        self.vertices=[]
        self.faces=[]
        self.uv=[]
    def quad(self, corners, uv=None):
        ix=len(self.vertices)
        self.vertices.extend(corners)
        self.uv.extend(uv if uv is not None else [(0,0),(1,0),(1,1),(0,1)])
        self.faces.extend([(ix,ix+1,ix+2),(ix,ix+2,ix+3)])
    def tri(self, corners, uv=None):
        ix=len(self.vertices)
        self.vertices.extend(corners)
        self.uv.extend(uv if uv is not None else [(0,0),(1,0),(0.5,1)])
        self.faces.append((ix,ix+1,ix+2))
    def build(self):
        return MeshData(self.vertices,self.faces,self.uv)

def sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def add(a,b): return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def mul(a,s): return (a[0]*s,a[1]*s,a[2]*s)
def dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a):
    l=math.sqrt(max(dot(a,a),1e-20))
    return (a[0]/l,a[1]/l,a[2]/l)
def interp(a,b,s): return add(mul(a,1-s),mul(b,s))

# Each tube is coarse 8-sided, with ring-side variation for organic rough bark.
def tube(b, points, radii, sides=8, offset=0., seed=17):
    rng=random.Random(seed)
    base_v=0.
    for j in range(len(points)-1):
        p0,p1=points[j],points[j+1]
        tangent=norm(sub(p1,p0))
        ref=(1,0,0) if abs(tangent[0])<0.85 else (0,1,0)
        axis1=norm(cross(tangent,ref))
        axis2=norm(cross(tangent,axis1))
        step=math.sqrt(dot(sub(p1,p0),sub(p1,p0)))
        for i in range(sides):
            a=TAU*(i/sides)+offset
            an=TAU*((i+1)/sides)+offset
            def p_on(p,r,angle, ring):
                # modest faceting without random crumpling
                wave=1.0+0.055*math.sin(angle*3.0+0.31*ring+seed)
                o=add(mul(axis1,r*wave*math.cos(angle)),mul(axis2,r*wave*math.sin(angle)))
                return add(p,o)
            corners=[p_on(p0,radii[j],a,j),p_on(p0,radii[j],an,j),
                     p_on(p1,radii[j+1],an,j+1),p_on(p1,radii[j+1],a,j+1)]
            b.quad(corners,[(i/sides,base_v/1.2),((i+1)/sides,base_v/1.2),
                            ((i+1)/sides,(base_v+step)/1.2),(i/sides,(base_v+step)/1.2)])
        base_v+=step
    # cap tip; base is open so the roots meet the ground without flat tabletop
    top=points[-1]
    tangent=norm(sub(points[-1],points[-2]));ref=(1,0,0) if abs(tangent[0])<0.85 else (0,1,0)
    u=norm(cross(tangent,ref));v=norm(cross(tangent,u));
    for i in range(sides):
        a=TAU*i/sides+offset; an=TAU*(i+1)/sides+offset
        b.tri([top,add(top,add(mul(u,radii[-1]*math.cos(a)),mul(v,radii[-1]*math.sin(a)))),
               add(top,add(mul(u,radii[-1]*math.cos(an)),mul(v,radii[-1]*math.sin(an))))])

TRUNK_POINTS=[(0.0,0.0,-0.09),(.02,-.01,.16),(-.045,.025,.69),(-.05,-.03,1.33),
              (.07,-.06,2.03),(.11,.04,2.72),(.04,.10,3.44),(-.08,.08,4.03),(-.12,.16,4.65)]
TRUNK_RADII=[.41,.33,.275,.245,.215,.19,.155,.11,.032]
# Primary branches originate along trunk and form an irregular umbrella crown.
PRIMARY=[
 (3,  .35, 2.5, .13, 4.48, .58),
 (4, 1.45, 2.3, .42, 4.78, .66),
 (4, 2.63, 2.5, .33, 5.02, .62),
 (5, 3.50, 2.2, .45, 5.05, .59),
 (5, 4.51, 2.48, .42, 5.26, .64),
 (6, 5.48, 2.1, .45, 5.40, .56),
 (6, .97, 1.7, .45, 5.45, .47),
 (7, 2.16, 1.65,.44, 5.66, .46),
 (7, 4.08, 1.72,.43, 5.62, .48),
 (7, 5.78, 1.44,.45, 5.88, .40),
]

def generate(seed=2026, lod=0):
    rng=random.Random(seed)
    wood=Builder(); cards=Builder(); tips=[]
    tube(wood,TRUNK_POINTS,TRUNK_RADII,sides=8,seed=100)
    # low-poly buttress roots at soil surface
    for i in range(5):
        a=TAU*i/5+.14
        start=(.23*math.cos(a),.23*math.sin(a),.22)
        out=(.50*math.cos(a+.13),.50*math.sin(a+.13),.05)
        end=(.78*math.cos(a+.13),.77*math.sin(a+.13),-.015)
        tube(wood,[start,out,end],[.14,.094,.011],sides=6,seed=202+i)
    for i,(anchor,angle,distance,curv,tip_z,spread) in enumerate(PRIMARY):
        p=TRUNK_POINTS[anchor]
        dx,dy=math.cos(angle),math.sin(angle)
        center=(p[0]+.55*distance*dx,p[1]+.55*distance*dy,p[2]+(tip_z-p[2])*.48)
        tip=(p[0]+distance*dx,p[1]+distance*dy,tip_z)
        turn=(-dy*curv,dx*curv,0)
        mid=add(center,turn)
        pbase=add(p,(dx*.07,dy*.07,0))
        tube(wood,[pbase,interp(pbase,mid,.36),mid,tip],
             [max(.11,.18-0.007*anchor),.14,.085,.016],sides=7,seed=311+i)
        tips.append((tip,spread,angle))
        # finer, upward split twigs with leaf cards clustered at terminals
        if lod==0:
            for k in range(2):
                phi=angle+((k-.5)*.7)
                sub_start=interp(mid,tip,.50+.15*k)
                sub_tip=(sub_start[0]+.45*math.cos(phi),sub_start[1]+.45*math.sin(phi),
                         sub_start[2]+(.33 if k==0 else .48))
                tube(wood,[sub_start,sub_tip],[.056,.010],sides=5,seed=600+i*2+k)
                tips.append((sub_tip,spread*.75,phi))
    tips.append((TRUNK_POINTS[-1],.52,0.0))
    # Leaf clusters: small translucent tex-card billboards, UV 0..1 per quad.
    # Each plane has a slight vertical tilt and an explicit physically plausible width.
    for ti,(tip,sp,phi) in enumerate(tips):
        count = (16 if lod==0 else 7) if ti<10 else (8 if lod==0 else 0)
        for j in range(count):
            # random sphere offsets around a branch end, canopy stronger at upper levels
            theta=rng.uniform(0,TAU)
            elevation=rng.uniform(-.48,.7)
            rad=sp*math.sqrt(rng.random())*.8
            center=(tip[0]+rad*math.cos(theta),tip[1]+rad*math.sin(theta),
                    tip[2]+rad*elevation)
            w=rng.uniform(.35,.58)*(1 if lod==0 else 1.22)
            h=rng.uniform(.60,.91)*(1 if lod==0 else 1.22)
            yaw=rng.uniform(0,TAU)
            # planes are mainly upright and varied to work from ground-level cameras
            vec_u=(math.cos(yaw)*w*.5, math.sin(yaw)*w*.5,rng.uniform(-.09,.09))
            vec_v=(-.19*math.sin(yaw)*h,.19*math.cos(yaw)*h, h*.5)
            a=add(center,add(mul(vec_u,-1),mul(vec_v,-1)))
            b=add(center,add(vec_u,mul(vec_v,-1)))
            c=add(center,add(vec_u,vec_v))
            d=add(center,add(mul(vec_u,-1),vec_v))
            cards.quad([a,b,c,d],[(0,0),(1,0),(1,1),(0,1)])
    return {'wood':wood.build(),'leaves':cards.build(),'name':'CGGeekInspired_Broadleaf_LOD'+str(lod)}

if __name__=='__main__':
    for lod in (0,1):
        g=generate(lod=lod)
        print(lod,[(k,len(v.vertices),len(v.faces)) for k,v in g.items() if isinstance(v,MeshData)])