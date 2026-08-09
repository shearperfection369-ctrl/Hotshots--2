"""Compose branded ad images for Craigslist / Facebook from real assets."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

INK = (13, 17, 23)
AMBER = (245, 158, 11)
CYAN = (34, 211, 238)
EMERALD = (16, 185, 129)
WHITE = (255, 255, 255)
GREY = (148, 163, 184)
FB = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
FR = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
FM = "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf"
MERCH = "/app/frontend/public/merch"
OUT = "/app/frontend/public/ads"
LOGO = Image.open("/app/frontend/public/tc-logo.png").convert("RGBA")


def f(path, size):
    return ImageFont.truetype(path, size)


def cover(img, w, h):
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1))
    x = (img.width - w) // 2
    return img.crop((x, 0, x + w, h))


def pill(d, xy, text, font, fg, bg, pad=(28, 14)):
    x, y = xy
    tw = d.textlength(text, font=font)
    th = font.size
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + th + pad[1] * 2], radius=(th + pad[1] * 2) // 2, fill=bg)
    d.text((x + pad[0], y + pad[1] - 2), text, font=font, fill=fg)
    return x + tw + pad[0] * 2


def header(im, d, W, brand_size=54, sub="MOBILE FLEET & CAB CLEANING — TWIN CITIES"):
    logo = LOGO.resize((150, int(150 * LOGO.height / LOGO.width)))
    im.paste(logo, (48, 40), logo)
    x = 220
    d.text((x, 62), "ORISEI", font=f(FB, brand_size), fill=WHITE)
    w1 = d.textlength("ORISEI ", font=f(FB, brand_size))
    d.text((x + w1, 62), "TRUCK CLEANING", font=f(FB, brand_size), fill=AMBER)
    d.text((x, 62 + brand_size + 12), sub, font=f(FM, 26), fill=CYAN)


def footer(d, W, H):
    d.rectangle([0, H - 130, W, H], fill=AMBER)
    d.text((48, H - 112), "CALL / TEXT (763) 443-4459", font=f(FB, 44), fill=INK)
    d.text((48, H - 52), "BOOK ONLINE: oriseifreightsolutions.com/wash", font=f(FB, 32), fill=INK)


def fleet_square():
    W = H = 1080
    im = Image.new("RGB", (W, H), INK)
    photo = cover(Image.open(f"{MERCH}/ts_crew.jpg"), W, 560)
    im.paste(photo, (0, 200))
    grad = Image.new("L", (1, 560), 0)
    for i in range(560):
        grad.putpixel((0, i), max(0, 190 - int(i / 560 * 190)) if i < 280 else min(200, int((i - 280) / 280 * 200)))
    dark = Image.new("RGB", (W, 560), INK)
    im.paste(dark, (0, 200), grad.resize((W, 560)))
    d = ImageDraw.Draw(im)
    header(im, d, W)
    d.text((48, 700), "YOUR DRIVERS SIT IN IT ALL DAY.", font=f(FB, 52), fill=WHITE)
    d.text((48, 762), "MAKE IT SHOWROOM CLEAN.", font=f(FB, 52), fill=AMBER)
    d.text((48, 838), "45-minute deep clean at YOUR yard · before/after photo proof · insured crews", font=f(FR, 28), fill=GREY)
    x = 48
    x = pill(d, (x, 892), "$175 one-time", f(FB, 32), INK, AMBER) + 20
    x = pill(d, (x, 892), "$130 bi-weekly", f(FB, 32), WHITE, (8, 145, 178)) + 20
    pill(d, (x, 892), "Fleet 10+: $150", f(FB, 32), WHITE, EMERALD)
    footer(d, W, H)
    im.save(f"{OUT}/fb_fleet_1080.png")


def car_square():
    W = H = 1080
    im = Image.new("RGB", (W, H), INK)
    photo = cover(Image.open(f"{MERCH}/ts_car_detail.jpg"), W, 560)
    im.paste(photo, (0, 200))
    grad = Image.new("L", (1, 560), 0)
    for i in range(560):
        grad.putpixel((0, i), max(0, 190 - int(i / 560 * 190)) if i < 280 else min(200, int((i - 280) / 280 * 200)))
    dark = Image.new("RGB", (W, 560), INK)
    im.paste(dark, (0, 200), grad.resize((W, 560)))
    d = ImageDraw.Draw(im)
    header(im, d, W, sub="WE COME TO YOUR DRIVEWAY — TWIN CITIES")
    d.text((48, 700), "FULL CAR DETAIL — $150", font=f(FB, 60), fill=AMBER)
    d.text((48, 780), "INSIDE & OUT, AT YOUR HOME OR OFFICE.", font=f(FB, 40), fill=WHITE)
    d.text((48, 842), "Interior vacuum & wipe-down · hand wash · windows · tire shine · air freshener", font=f(FR, 27), fill=GREY)
    x = 48
    x = pill(d, (x, 896), "+ Ceramic $75", f(FB, 28), WHITE, (139, 92, 246)) + 16
    x = pill(d, (x, 896), "+ Shampoo $60", f(FB, 28), WHITE, EMERALD) + 16
    x = pill(d, (x, 896), "+ Wax $50", f(FB, 28), INK, AMBER) + 16
    pill(d, (x, 896), "+ Pet Hair $30", f(FB, 28), WHITE, (8, 145, 178))
    footer(d, W, H)
    im.save(f"{OUT}/fb_cardetail_1080.png")


def wide_banner():
    W, H = 1200, 628
    im = Image.new("RGB", (W, H), INK)
    photo = cover(Image.open(f"{MERCH}/ts_cab.jpg"), 560, H)
    im.paste(photo, (W - 560, 0))
    grad = Image.new("L", (560, 1), 0)
    for i in range(560):
        grad.putpixel((i, 0), max(0, 235 - int(i / 560 * 235)))
    dark = Image.new("RGB", (560, H), INK)
    im.paste(dark, (W - 560, 0), grad.resize((560, H)))
    d = ImageDraw.Draw(im)
    logo = LOGO.resize((120, int(120 * LOGO.height / LOGO.width)))
    im.paste(logo, (44, 36), logo)
    d.text((180, 52), "ORISEI", font=f(FB, 44), fill=WHITE)
    d.text((180 + d.textlength("ORISEI ", font=f(FB, 44)), 52), "TRUCK CLEANING", font=f(FB, 44), fill=AMBER)
    d.text((180, 108), "TWIN CITIES · MOBILE · INSURED", font=f(FM, 22), fill=CYAN)
    d.text((44, 200), "SEMI CABS. FLEETS. CARS.", font=f(FB, 52), fill=WHITE)
    d.text((44, 264), "WE COME TO YOU.", font=f(FB, 52), fill=AMBER)
    rows = [("Semi cab deep clean", "$175", AMBER), ("Bi-weekly yard lock-in", "$130", (8, 145, 178)),
            ("Full car detail", "$150", EMERALD)]
    y = 356
    for label, price, color in rows:
        d.text((44, y), label, font=f(FR, 30), fill=WHITE)
        pw = d.textlength(price, font=f(FB, 30))
        d.rounded_rectangle([560 - pw - 44, y - 6, 560 - 8, y + 40], radius=23, fill=color)
        d.text((560 - pw - 26, y), price, font=f(FB, 30), fill=WHITE if color != AMBER else INK)
        y += 62
    d.rectangle([0, H - 78, W, H], fill=AMBER)
    d.text((44, H - 62), "(763) 443-4459", font=f(FB, 36), fill=INK)
    t = "oriseifreightsolutions.com/wash"
    d.text((W - 44 - d.textlength(t, font=f(FB, 30)), H - 58), t, font=f(FB, 30), fill=INK)
    im.save(f"{OUT}/ad_wide_1200x628.png")


fleet_square()
car_square()
wide_banner()
print("ads built")
