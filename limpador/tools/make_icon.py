"""Gera assets/icon.png, assets/icon.ico e limpapc/icon_data.py (ícone da janela). Requer Pillow."""
import base64
import io
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def make(size=1024):
    s = size
    grad = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(grad)
    c1, c2 = (109, 93, 252), (34, 211, 238)
    for y in range(s):
        for_t = y / (s - 1)
        d.line([(0, y), (s, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * for_t) for i in range(3)))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.24), fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    dr = ImageDraw.Draw(img)

    def star(cx, cy, r, k=0.22):
        pts = []
        for i in range(8):
            rad = r if i % 2 == 0 else r * k
            import math
            a = -math.pi / 2 + i * math.pi / 4
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        dr.polygon(pts, fill=(255, 255, 255, 255))

    star(s * 0.44, s * 0.55, s * 0.30)
    star(s * 0.74, s * 0.27, s * 0.13)
    star(s * 0.76, s * 0.76, s * 0.07)
    return img


if __name__ == "__main__":
    big = make()
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(ROOT, "assets", "icon.png"))
    big.save(os.path.join(ROOT, "assets", "icon.ico"),
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    buf = io.BytesIO()
    big.resize((64, 64), Image.LANCZOS).save(buf, "PNG")
    with open(os.path.join(ROOT, "limpapc", "icon_data.py"), "w") as f:
        f.write('"""Ícone da janela (PNG 64x64 em base64) — gerado por tools/make_icon.py."""\n')
        f.write(f'ICON_PNG = "{base64.b64encode(buf.getvalue()).decode()}"\n')
    print("ok")
