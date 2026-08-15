import math, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 640
ROOT = "/Users/hefeiyu/WorkBuddy/2026-08-12-19-22-28"
FONT_DIR = "/Users/hefeiyu/.workbuddy/skills/canvas-design/canvas-fonts"
ZH = "/System/Library/Fonts/Supplemental/STHeiti Medium.ttc"
EN_TITLE = os.path.join(FONT_DIR, "BricolageGrotesque-Bold.ttf")
MONO = os.path.join(FONT_DIR, "GeistMono-Bold.ttf")

# ---- 背景竖直渐变 ----
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
px = img.load()
top, bottom = (12, 18, 38), (6, 10, 22)
for y in range(H):
    t = y / (H - 1)
    r = int(top[0] + (bottom[0] - top[0]) * t)
    g = int(top[1] + (bottom[1] - top[1]) * t)
    b = int(top[2] + (bottom[2] - top[2]) * t)
    for x in range(W):
        px[x, y] = (r, g, b, 255)

draw = ImageDraw.Draw(img, "RGBA")

# ---- 辉光 ----
def glow(size, color, max_alpha=160):
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    c = size // 2
    for r in range(size // 2, 0, -3):
        a = int(max_alpha * (1 - r / (size // 2)) ** 1.8)
        gd.ellipse([c - r, c - r, c + r, c + r], fill=color + (a,))
    return g.filter(ImageFilter.GaussianBlur(size // 14))

def add_glow(cx, cy, size, color, alpha=160):
    g = glow(size, color, alpha)
    img.alpha_composite(g, (cx - size // 2, cy - size // 2))

add_glow(985, 305, 580, (40, 170, 200))
add_glow(985, 305, 430, (70, 120, 255))
add_glow(300, 250, 540, (28, 86, 145))

# ---- 左脑：网格点阵 ----
grid_col = (90, 200, 220, 38)
for gx in range(108, 470, 32):
    for gy in range(150, 520, 32):
        draw.ellipse([gx - 1.6, gy - 1.6, gx + 1.6, gy + 1.6], fill=grid_col)

# ---- 右脑：声波 ----
cyan = (90, 220, 235, 150)
blue = (110, 150, 255, 150)
for i, phase in enumerate([0.0, 0.7, 1.4]):
    pts, amp, freq = [], 46, 0.055
    for x in range(770, 1205):
        dx = x - 985
        env = max(0.0, 1 - abs(dx) / 235)
        yy = 305 - amp * math.sin(x * freq + phase) * env
        pts.append((x, int(yy)))
    draw.line(pts, fill=(cyan if i % 2 == 0 else blue), width=3)

# ---- ∞ 双环（双脑协同 + 闭环） ----
cx, cy = 985, 305
left, right = [cx - 150, cy - 115, cx + 55, cy + 115], [cx - 55, cy - 115, cx + 150, cy + 115]
draw.ellipse(left, outline=(95, 222, 236, 205), width=9)
draw.ellipse(right, outline=(112, 152, 255, 205), width=9)
# 内侧细高光，增强环的精致度
inner_l = [v + (4 if i % 2 == 0 else -4) for i, v in enumerate(left)]
inner_r = [v + (4 if i % 2 == 0 else -4) for i, v in enumerate(right)]
draw.ellipse(inner_l, outline=(210, 245, 255, 55), width=2)
draw.ellipse(inner_r, outline=(210, 245, 255, 55), width=2)
add_glow(cx, cy, 175, (185, 232, 255), 120)

# ---- 文字 ----
def fnt(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)

zh, en = fnt(ZH, 96, 1), fnt(EN_TITLE, 88)
zh_sub, mono = fnt(ZH, 36, 1), fnt(MONO, 22)

draw.text((94, 104), "SYNERGYOS", font=mono, fill=(132, 182, 212, 185), anchor="ls")
draw.text((94, 162), "灵犀  自进化协作智能体", font=zh_sub, fill=(150, 190, 216, 185), anchor="ls")

draw.text((92, 286), "灵犀", font=zh, fill=(242, 249, 255, 255), anchor="ls")
lw = draw.textlength("灵犀", font=zh)
add_glow(92 + int(lw / 2), 286, 120, (255, 255, 255), 28)
draw.text((92, 286), "灵犀", font=zh, fill=(242, 249, 255, 255), anchor="ls")
draw.text((92 + lw + 18, 294), "SynergyOS", font=en, fill=(122, 226, 240, 255), anchor="ls")

draw.text((94, 408), "以用户为中心的多角色 AI 智能体网络", font=zh_sub, fill=(202, 221, 236, 235), anchor="ls")
draw.text((94, 466), "DUAL-BRAIN  ·  REFLEXION SELF-HEAL  ·  HONEST OMISSION", font=mono, fill=(120, 200, 220, 210), anchor="ls")

x = 94
for lb in ["# multi-agent", "# reflexion", "# verification", "# zero-dependency"]:
    draw.text((x, 590), lb, font=mono, fill=(110, 210, 230, 230), anchor="ls")
    x += draw.textlength(lb, font=mono) + 34

draw.rectangle([18, 18, W - 18, H - 18], outline=(120, 200, 230, 42), width=2)

img.convert("RGB").save(os.path.join(ROOT, "social-preview.png"), "PNG")
print("saved social-preview.png", os.path.getsize(os.path.join(ROOT, "social-preview.png")), "bytes")
