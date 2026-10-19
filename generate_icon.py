#!/usr/bin/env python3
from PIL import Image, ImageDraw
import os

# Config
SIZE = 512
OUT = r"D:\tech\tech-main\icon-512.png"
BG = (15, 76, 140)  # #0f4c8c deep blue
WHITE = (255, 255, 255)
YELLOW = (255, 204, 51)  # #ffcc33 yellow accent
YELLOW_DARK = (242, 185, 20)
LIGHT_BLUE = (207, 223, 242)  # for journal lines
LINE_COLOR = (185, 205, 230)

# Create supersampled image for anti-aliasing (2x)
SCALE = 2
S = SIZE * SCALE

# Create base image with rounded corners background
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded background - RuStore icon should be square with rounded corners ~22% radius (112px at 512 -> 224 at 1024)
radius = int(112 * SCALE)  # 224
draw.rounded_rectangle([(0, 0), (S-1, S-1)], radius=radius, fill=BG + (255,))

# Add subtle top highlight - clipped to rounded background to avoid corner bleed
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([(0,0),(S-1,S-1)], radius=radius, fill=255)
highlight = Image.new("RGBA", (S, S), (0,0,0,0))
hd = ImageDraw.Draw(highlight)
hd.ellipse([(-200, -400), (S+200, int(S*0.55))], fill=(255,255,255,18))
# clip highlight to mask
highlight.putalpha(Image.new("L", (S,S), 0))
# apply mask via composition: only keep highlight where mask is white
clipped = Image.new("RGBA", (S,S), (0,0,0,0))
clipped.paste(highlight, mask=mask)
# need to recreate highlight with alpha then clip: simpler - draw highlight on transparent then composite with mask
highlight2 = Image.new("RGBA", (S, S), (0,0,0,0))
hd2 = ImageDraw.Draw(highlight2)
hd2.ellipse([(-200, -400), (S+200, int(S*0.55))], fill=(255,255,255,14))
# composite only inside mask by using mask as alpha
highlight2.putalpha(mask)
# Actually to properly clip, create highlight then set alpha = min(original alpha, mask)
# PIL putalpha replaces, so use this approach: create highlight, then multiply alpha
highlight_alpha = highlight2.split()[3]
# highlight2 already has mask as alpha, but original ellipse had 14 alpha - need combine
# recreate correctly: mask * 14/255
combined_alpha = Image.new("L", (S,S), 0)
# draw ellipse alpha 14 where mask is 255 -> result 14 inside mask, 0 outside
tmp = Image.new("L", (S,S), 0)
td = ImageDraw.Draw(tmp)
td.ellipse([(-200, -400), (S+200, int(S*0.55))], fill=14)
combined_alpha = Image.new("L", (S,S), 0)
combined_alpha = Image.composite(tmp, Image.new("L", (S,S), 0), mask)
highlight_final = Image.new("RGBA", (S,S), (255,255,255,0))
highlight_final.putalpha(combined_alpha)
img = Image.alpha_composite(img, highlight_final)
draw = ImageDraw.Draw(img)

# Book dimensions (centered)
# Book: centered, 2x scale
book_w = int(264 * SCALE)
book_h = int(312 * SCALE)
book_x0 = (S - book_w)//2
book_y0 = (S - book_h)//2 - int(12*SCALE)  # slightly up to balance badge
book_x1 = book_x0 + book_w
book_y1 = book_y0 + book_h
book_r = int(22 * SCALE)

# Drop shadow for book
shadow_offset = int(14*SCALE)
shadow = Image.new("RGBA", (S, S), (0,0,0,0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle([(book_x0+shadow_offset, book_y0+shadow_offset), (book_x1+shadow_offset, book_y1+shadow_offset)], radius=book_r, fill=(0, 20, 50, 55))
# blur shadow a bit by resizing? simple composite is fine. Add extra soft shadow
img = Image.alpha_composite(img, shadow)
draw = ImageDraw.Draw(img)

# Book body - white
draw.rounded_rectangle([(book_x0, book_y0), (book_x1, book_y1)], radius=book_r, fill=WHITE)

# Book spine accent - left edge thicker line + subtle spine
spine_w = int(28*SCALE)
# spine highlight - slightly darker blue strip on left inside book
draw.rounded_rectangle([(book_x0, book_y0), (book_x0+spine_w, book_y1)], radius=book_r, fill=(232, 240, 251))
# inner spine line
spine_line_x = book_x0 + spine_w
draw.line([(spine_line_x, book_y0+book_r//2), (spine_line_x, book_y1-book_r//2)], fill=(185,205,230), width=int(3*SCALE))
# small notches at top/bottom of spine to suggest binding
for y in [book_y0+int(52*SCALE), book_y0+int(92*SCALE), book_y1-int(52*SCALE), book_y1-int(92*SCALE)]:
    draw.rounded_rectangle([(book_x0+int(8*SCALE), y-int(6*SCALE)), (book_x0+spine_w-int(8*SCALE), y+int(6*SCALE))], radius=int(3*SCALE), fill=(185,205,230))

# Journal lines inside book (to the right of spine) - 3 lines + one shorter
line_x0 = book_x0 + int(48*SCALE)
line_x1 = book_x1 - int(36*SCALE)
line_w = line_x1 - line_x0
line_h = int(14*SCALE)
line_r = int(7*SCALE)
lines_y = [book_y0+int(78*SCALE), book_y0+int(112*SCALE), book_y0+int(146*SCALE)]
for y in lines_y:
    draw.rounded_rectangle([(line_x0, y), (line_x1, y+line_h)], radius=line_r, fill=LIGHT_BLUE)
# 4th line shorter (like grade entry) with yellow accent dot
y4 = book_y0+int(190*SCALE)
draw.rounded_rectangle([(line_x0, y4), (line_x0+int(line_w*0.62), y4+line_h)], radius=line_r, fill=LIGHT_BLUE)
# tiny yellow square to suggest highlight/grade
draw.rounded_rectangle([(line_x0+int(line_w*0.68), y4-2), (line_x0+int(line_w*0.92), y4+line_h+2)], radius=int(5*SCALE), fill=(255, 233, 150))

# Yellow accent bar at top of book (like journal header)
bar_h = int(42*SCALE)
bar_m = int(14*SCALE)
draw.rounded_rectangle([(book_x0+int(18*SCALE), book_y0+int(18*SCALE)), (book_x1-int(18*SCALE), book_y0+int(18*SCALE)+bar_h)], radius=int(10*SCALE), fill=YELLOW)
# small white "check" icon placeholder in bar? Actually add icon: small open-book + subtle text lines indicator
# Add 3 small white dots in yellow bar to suggest minimal header (optional)
# Center white small rounded rect inside yellow bar as highlight
# Draw white check-like? Keep clean.

# Badge: yellow circle with white checkmark, overlapping bottom-right of book
badge_d = int(132*SCALE)
badge_r = badge_d//2
badge_cx = book_x1 - int(18*SCALE)
badge_cy = book_y1 - int(18*SCALE)
bx0 = badge_cx - badge_r
by0 = badge_cy - badge_r
bx1 = badge_cx + badge_r
by1 = badge_cy + badge_r

# Badge shadow
bshadow = Image.new("RGBA", (S,S), (0,0,0,0))
bsd = ImageDraw.Draw(bshadow)
bsd.ellipse([(bx0+int(10*SCALE), by0+int(10*SCALE)), (bx1+int(10*SCALE), by1+int(10*SCALE))], fill=(0,25,60,60))
img = Image.alpha_composite(img, bshadow)
draw = ImageDraw.Draw(img)

# Badge outer white ring (for contrast on white book)
draw.ellipse([(bx0-int(8*SCALE), by0-int(8*SCALE)), (bx1+int(8*SCALE), by1+int(8*SCALE))], fill=WHITE)
# Yellow circle
draw.ellipse([(bx0, by0), (bx1, by1)], fill=YELLOW)
# Inner subtle inner shadow for depth (ellipse with darker yellow at bottom)
inner = Image.new("RGBA", (S,S), (0,0,0,0))
idraw = ImageDraw.Draw(inner)
idraw.ellipse([(bx0+int(14*SCALE), by0+int(22*SCALE)), (bx1-int(10*SCALE), by1-int(6*SCALE))], fill=(242,185,20, 55))
img = Image.alpha_composite(img, inner)
draw = ImageDraw.Draw(img)

# White checkmark - thick, rounded caps
# Coordinates for check at 2x scale: centered in badge
# Check shape: polyline with thickness
check_w = int(12*SCALE)  # stroke width
# Define points: start, middle, end
# Adjusted to look balanced
p1 = (badge_cx - int(32*SCALE), badge_cy + int(2*SCALE))
p2 = (badge_cx - int(8*SCALE), badge_cy + int(26*SCALE))
p3 = (badge_cx + int(36*SCALE), badge_cy - int(22*SCALE))

# Draw check with rounded line
draw.line([p1, p2], fill=WHITE, width=check_w, joint="round")
draw.line([p2, p3], fill=WHITE, width=check_w, joint="round")
# Add round caps
draw.ellipse([(p1[0]-check_w//2, p1[1]-check_w//2), (p1[0]+check_w//2, p1[1]+check_w//2)], fill=WHITE)
draw.ellipse([(p3[0]-check_w//2, p3[1]-check_w//2), (p3[0]+check_w//2, p3[1]+check_w//2)], fill=WHITE)
# joint smoothing
draw.ellipse([(p2[0]-check_w//2, p2[1]-check_w//2), (p2[0]+check_w//2, p2[1]+check_w//2)], fill=WHITE)

# Optional: tiny graduation cap hint? We chose book+checkmark which is clearer at small sizes for Education/Journal.
# Add subtle bottom edge shadow of book for depth (thin line at bottom of book)
draw.rounded_rectangle([(book_x0+int(30*SCALE), book_y1-int(6*SCALE)), (book_x1-int(30*SCALE), book_y1-int(2*SCALE))], radius=int(2*SCALE), fill=(210,220,235, 120))

# Downscale to 512x512 with LANCZOS for crisp anti-aliasing
img_small = img.resize((SIZE, SIZE), Image.LANCZOS)

# Ensure background is opaque (no transparency outside rounded corners should be transparent? For store, both are accepted but better opaque with rounded corners on blue? We'll keep transparent corners but ensure file has alpha. RuStore often expects no transparency issues - we have rounded corners with transparent outer pixels. If they want square, they can composite. We'll keep rounded transparent - looks professional. If they require opaque square, we can provide alternative. We'll ensure outer area is BG? Currently transparent outside rounded rect. Let's make final background opaque square option? Keep transparent for nice icon; but to avoid validation issues, we keep transparent else but also provide square fallback via opaque background. We'll keep as is with transparent corners - still valid PNG 512x512. If need opaque, it's one line change.)

# Alternative: composite onto solid BG to make square opaque (uncomment if needed)
# But keep rounded transparent as premium look; RuStore accepts both. We'll keep transparent.

# Save optimized PNG
img_small.save(OUT, "PNG", optimize=True)

# Verification
size_bytes = os.path.getsize(OUT)
im_check = Image.open(OUT)
w, h = im_check.size
mode = im_check.mode
print(f"SAVED: {OUT}")
print(f"Dimensions: {w}x{h}")
print(f"Mode: {mode}")
print(f"Size: {size_bytes} bytes ({size_bytes/1024:.1f} KB)")
print(f"Size MB: {size_bytes/(1024*1024):.3f} MB")
print(f"Within 1MB: {size_bytes <= 1024*1024}")
print(f"Is PNG: {im_check.format}")
# also check that image is valid
try:
    im_check.verify()
    print("PNG valid: True")
except Exception as e:
    print(f"PNG valid: False - {e}")
