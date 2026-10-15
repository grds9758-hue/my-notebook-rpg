import numpy as np
from PIL import Image
C=128; FOOT=110; MAXW=C-4; MAXH=C-6
def legs_x(im):
    a=np.array(im)[:,:,3]>40; h=a.shape[0]
    sub=a[int(h*.62):]  # 다리·발 부분
    xs=np.nonzero(sub)[1]
    return float(np.median(xs)) if len(xs) else im.width/2
def place(sh, im, r, c, k, lying=False):
    im=im.resize((max(1,round(im.width*k)),max(1,round(im.height*k))),Image.LANCZOS)
    lx=im.width/2 if lying else legs_x(im)
    x=round(c*C+C/2-lx)
    # 칸 밖으로 나가는 부분(넓은 효과)은 잘라 냄 → 몸 위치·크기는 그대로
    L=max(0,c*C+2-x); R=max(0,(x+im.width)-((c+1)*C-2))
    im=im.crop((L,0,im.width-R,im.height)); x+=L
    if im.height>MAXH: im=im.crop((0,im.height-MAXH,im.width,im.height))
    y=r*C+FOOT-im.height
    sh.alpha_composite(im,(x,max(r*C+3,y)))
