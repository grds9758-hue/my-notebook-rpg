import numpy as np, pickle
from PIL import Image
FR=pickle.load(open('FR.pkl','rb'))
cols={'mf':[139,224,303,381],'mb':[486,565,644,723],'ff':[916,993,1078,1150],'fb':[1257,1333,1410,1489]}
def get(b,r,c):
  im,bb=FR[(b,r,c)]
  if b in ('ff','fb'):
    cs=cols[b]; xb=[cs[0]-50]+[(cs[i]+cs[i+1])//2 for i in range(3)]+[cs[3]+50]
    lo,hi=xb[c]-1,xb[c+1]+1
    a=np.array(im); x=np.arange(bb[0],bb[2]); a[:,(x<lo)|(x>hi),3]=0
    im=Image.fromarray(a); im=im.crop(im.getchannel('A').getbbox())
  return im
BACK=[[(0,0),(0,1),(0,2),(0,3)],[(3,0),(3,1),(3,2),(3,3)],[(6,0),(6,1),(6,2),(6,3)],[(4,0),(4,1)],[(0,0),(0,2)],[(7,0),(7,1)],[(5,1),(5,2),(5,3)],[(7,1),(7,2),(7,3)]]
FRONT=[[(0,0),(0,1),(0,2),(0,3)],[(1,0),(1,1),(1,2),(1,3)],[(7,0),(7,1),(7,2)],[(6,3)],[(0,0),(0,1)]]
C=128; FOOT=112; TARGET=90
for sex in 'mf':
  for side,L,blk in [('back',BACK,sex+'b'),('front',FRONT,sex+'f')]:
    k=TARGET/np.median([get(blk,0,c).height for c in range(4)])   # 대기 키 → 90px
    sh=Image.new('RGBA',(4*C,len(L)*C),(0,0,0,0))
    for r,row in enumerate(L):
      for c,(sr,sc) in enumerate(row):
        im=get(blk,sr,sc); im=im.resize((max(1,round(im.width*k)),max(1,round(im.height*k))),Image.LANCZOS)
        sh.alpha_composite(im,(c*C+(C-im.width)//2, r*C+FOOT-im.height))
    sh.save(f'out/char_novice_{sex}_{side}.png'); print(sex,side,round(k,3))
