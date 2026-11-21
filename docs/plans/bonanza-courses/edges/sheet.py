import sys
from PIL import Image, ImageDraw
d, course, box, z, out = sys.argv[1], sys.argv[2], tuple(map(int, sys.argv[3].split(","))), int(sys.argv[4]), sys.argv[5]
styles = sys.argv[6].split(",")
cols = 2
w, h = (box[2]-box[0])*z, (box[3]-box[1])*z
pad = 22
sheet = Image.new("RGB", (cols*w + (cols+1)*8, ((len(styles)+cols-1)//cols)*(h+pad+8) + 8), (40, 40, 48))
dr = ImageDraw.Draw(sheet)
for i, (st) in enumerate(styles):
    name, _, label = st.partition("=")
    im = Image.open("%s/%s-%s.png" % (d, course, name)).crop(box).resize((w, h), Image.NEAREST)
    x, y = 8 + (i % cols)*(w+8), 8 + (i//cols)*(h+pad+8)
    dr.text((x+2, y+4), label or name, fill=(255, 255, 160))
    sheet.paste(im, (x, y+pad))
sheet.save(out)
print(out, sheet.size)
