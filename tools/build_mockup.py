import base64, io, json
from PIL import Image
A = 'assets/'
def uri(im):
    b = io.BytesIO(); im.save(b, 'PNG'); return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
bald = Image.open(A+'novice_bald.png').convert('RGBA')
def char(color, weapon=True):
    c = bald.copy(); c.alpha_composite(Image.open(A+f'hair/hair1_{color}.png').convert('RGBA'))
    if weapon:
        c.alpha_composite(Image.open(A+'weapon_lv1.png').convert('RGBA')); c.alpha_composite(Image.open(A+'hand_fist.png').convert('RGBA'))
    return c
colors = ['brown','black','blonde','red','silver','blue','pink']
subs = {'BALD': uri(bald), 'HAIR_brown': uri(Image.open(A+'hair/hair1_brown.png')),
        'CHAR': uri(char('brown')), 'CHAR_B': uri(char('blonde', False)), 'CHAR_C': uri(char('pink', False)),
        'BATICON': uri(Image.open(A+'raw/weapon_1_obj2.png').convert('RGBA')),
        'HAIRS': json.dumps([uri(Image.open(A+f'hair/hair1_{c}.png')) for c in colors])}
s = open('mockup/ui-preview.src.html', encoding='utf-8').read()
for k, v in subs.items(): s = s.replace('{{'+k+'}}', v)
open('mockup/ui-preview.html', 'w', encoding='utf-8').write(s)
print(len(s))
