import numpy as np, pickle, sys
from PIL import Image
from scipy import ndimage
CODES = {'01':'warrior','02':'archer','03':'thief','04':'healer','05':'mage','06':'greatsword','07':'shield','08':'rider','09':'trapper','10':'bowman',
         '11':'dagger','12':'shuriken','13':'dancer','14':'priest','15':'monk','16':'wizard','18':'elementalist'}  # 17 = 레인저(3차) 제외
def runs(v):
    g=[];s=None
    for i,x in enumerate(v):
        if x and s is None: s=i
        if not x and s is not None: g.append((s,i-1)); s=None
    if s is not None: g.append((s,len(v)-1))
    return g
def rows_of(sat, x0, x1):
    col=(sat[:, x0:x1]>60).mean(1)>.6
    st=[]
    for a,b in runs(col):
        if b-a>20 and a>200 and (not st or a-st[-1]>70): st.append(a)
    assert len(st)==8, st
    return st
def bgmask(a):
    mx=a.max(2); mn=a.min(2)
    return ((mx-mn)<16)&(mn>178) | ((a[:,:,0]>235)&(a[:,:,1]>225)&(a[:,:,2]>228)&(mx-mn<30))  # 회색·흰 체크무늬 + 연분홍 판
OUT={}
for n,code in CODES.items():
    a=np.array(Image.open(n+'.png').convert('RGB')).astype(int); sat=a.max(2)-a.min(2)
    bg=bgmask(a)
    for side,(lx0,lx1),(cx0,cx1) in [('f',(30,110),(126,762)),('b',(790,870),(884,1518))]:
        st=rows_of(sat,lx0,lx1)
        fgp=ndimage.uniform_filter1d((~bg[:,cx0:cx1]).sum(1).astype(float),5)
        yb=[217]
        for s_ in st[1:]:
            lo,hi=s_-40,s_+12; yb.append(lo+int(np.argmin(fgp[lo:hi])))
        yb.append(1010)
        cw=(cx1-cx0)/4
        for r in range(8):
            for c in range(4):
                X0=int(cx0+c*cw); X1=int(cx0+(c+1)*cw); Y0=yb[r]; Y1=yb[r+1]
                wx0,wx1,wy0,wy1=max(cx0-4,X0-14),min(cx1+4,X1+14),max(217,Y0-10),min(1015,Y1+10)
                win=~bg[wy0:wy1,wx0:wx1]
                # 창 테두리에 닿은 배경만 배경으로: 테두리와 이어진 bg 영역
                bgw=bg[wy0:wy1,wx0:wx1]
                lab,k=ndimage.label(bgw)
                edge=set(np.unique(np.r_[lab[0],lab[-1],lab[:,0],lab[:,-1]]))-{0}
                fg=~np.isin(lab,list(edge))
                # 효과 속에 갇힌 체크무늬(회색·흰 칸이 번갈아 있는 곳)도 지움
                A=a[wy0:wy1,wx0:wx1]; mn=A.min(2); ls=(A.max(2)-mn)<16
                gr=ls&(mn>185)&(mn<218); wh=ls&(mn>238)
                zone=(ndimage.uniform_filter(gr.astype(float),15)>.1)&(ndimage.uniform_filter(wh.astype(float),15)>.1)
                fg&=~((gr|wh)&zone)
                # 효과(반투명 빛)가 체크무늬 위에 칠해져 남은 연한 칸은 흐리게
                faint=ndimage.binary_dilation(zone,iterations=6)&(mn>165)&((A.max(2)-mn)<70)
                fg=ndimage.binary_opening(fg,np.ones((2,2)))
                lab2,k2=ndimage.label(fg,np.ones((3,3)))
                if not k2: OUT[(code,side,r,c)]=None; continue
                sz=ndimage.sum(fg,lab2,range(1,k2+1)); objs=ndimage.find_objects(lab2)
                keep=np.zeros_like(fg)
                big=int(np.argmax(sz)); B=objs[big]
                for i,s in enumerate(objs):
                    d=max(B[0].start-s[0].stop, s[0].start-B[0].stop, B[1].start-s[1].stop, s[1].start-B[1].stop, 0)
                    if i!=big and d>10 and sz[i]<.15*sz[big]: continue  # 몸에서 떨어진 작은 조각(판 장식·옆 칸 부스러기)
                    cy=(s[0].start+s[0].stop)/2+wy0; cxx=(s[1].start+s[1].stop)/2+wx0
                    h_=s[0].stop-s[0].start; w_=s[1].stop-s[1].start
                    if min(h_,w_)<=4 and max(h_,w_)>25: continue  # 판 테두리 선
                    if sz[i]>=25 and X0<=cxx<X1 and Y0<=cy<Y1: keep|=lab2==i+1
                al=np.where(keep, 255, 0)
                rgba=np.dstack([a[wy0:wy1,wx0:wx1],al]).astype(np.uint8)
                im=Image.fromarray(rgba,'RGBA'); bb=im.getchannel('A').getbbox()
                OUT[(code,side,r,c)]=(im.crop(bb), wx0+bb[0]-X0, wy0+bb[3]-Y0, X1-X0) if bb else None  # 그림, 칸 안 왼쪽 위치, 칸 안 발 위치, 칸 폭
    print(n,code,'ok')
pickle.dump(OUT,open('cells.pkl','wb'))
