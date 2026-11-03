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

    # pena (o mesmo desenho do ícone "Limpeza" do menu), em grade 24x24, centralizada
    k = s / 24.0
    ox, oy = 1.1, 0.0
    P = lambda *pts: [((x + ox) * k, (y + oy) * k) for x, y in zip(pts[::2], pts[1::2])]  # noqa: E731
    white = (255, 255, 255, 255)
    w = int(s * 0.06)
    dr.line(P(18.0, 4.6, 12.4, 11.4), fill=white, width=w)
    for x, y in P(18.0, 4.6):
        dr.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=white)
    dr.polygon(P(11.0, 10.6, 15.0, 14.4, 10.2, 19.8, 4.6, 19.8, 4.6, 16.6), fill=white)
    mid = tuple(int(c1[i] + (c2[i] - c1[i]) * 0.7) for i in range(3)) + (255,)
    lw = max(2, int(s * 0.022))
    dr.line(P(7.4, 19.8, 11.4, 15.2), fill=mid, width=lw)
    dr.line(P(9.9, 19.8, 12.9, 16.4), fill=mid, width=lw)
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
