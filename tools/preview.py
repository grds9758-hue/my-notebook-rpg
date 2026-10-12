import sys
from PIL import Image
# preview.py out.png img1 img2 ...  -> side by side 4x on beige
ims=[Image.open(p).convert('RGBA') for p in sys.argv[2:]]
W=sum(i.width for i in ims)+4*(len(ims)-1)
bg=Image.new('RGBA',(W,64),(235,225,205,255));x=0
for i in ims: bg.alpha_composite(i,(x,0)); x+=i.width+4
bg.resize((W*5,320),Image.NEAREST).save(sys.argv[1])
