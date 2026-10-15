import numpy as np
from PIL import Image
C=128; FOOT=110; MAXH=C-6
def legs_x(im):
    a=np.array(im)[:,:,3]>40; h=a.shape[0]; xs=np.nonzero(a[int(h*.62):])[1]
    return float(np.median(xs)) if len(xs) else im.width/2
def place_row(sh, frames, r, k, lying=False):
    """frames: [(그림, 칸 안 x, 칸 안 발 y)] — 줄 전체를 한 번만 옮겨 원래 움직임(숨쉬기·흔들림)을 그대로 살림"""
    F=[(im.resize((max(1,round(im.width*k)),max(1,round(im.height*k))),Image.LANCZOS), ox*k, by*k) for im,ox,by in frames]
    ax=np.median([ox+(im.width/2 if lying else legs_x(im)) for im,ox,by in F])   # 줄의 몸 가운데
    ay=np.median([by for im,ox,by in F])                                          # 줄의 발바닥
    for c,(im,ox,by) in enumerate(F):
        x=round(c*C+C/2+(ox-ax)); y=round(r*C+FOOT+(by-ay)-im.height)
        L=max(0,c*C+2-x); R=max(0,(x+im.width)-((c+1)*C-2)); T=max(0,r*C+3-y); B=max(0,(y+im.height)-((r+1)*C-2))
        im=im.crop((L,T,im.width-R,im.height-B)); sh.alpha_composite(im,(x+L,y+T))
