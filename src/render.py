"""Maakt een afbeelding (1080x1350) of video (1080x1920, 9 s) van een vers.
Alle ontwerpkeuzes komen binnen als variabelen, zodat het leersysteem ze kan vergelijken.
"""
import os, random, subprocess, tempfile, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "fonts")

PALETTEN = {
    # naam: (achtergrond boven, achtergrond onder, tekst, accent)
    "nacht":      ("#0f1b2d", "#1d3557", "#f4efe6", "#d4a373"),
    "zand":       ("#efe6d8", "#e2d3bd", "#2b2118", "#9c6644"),
    "salie":      ("#dfe7dc", "#b9c9b3", "#1f2a1f", "#4f6f52"),
    "zonsopgang": ("#f6bd60", "#e76f51", "#2a1a12", "#fff4e0"),
    "zwart_goud": ("#0b0b0b", "#1a1a1a", "#f2e9d8", "#c9a227"),
    "oceaan":     ("#023047", "#219ebc", "#f1faee", "#ffb703"),
    "roze_avond": ("#3d2c4e", "#b56576", "#fff1f3", "#ffcdb2"),
    "wit":        ("#fbfaf7", "#f1eee8", "#1b1b1b", "#b08968"),
}

LETTERTYPES = {
    # naam: (bestand, variatie of None)
    "playfair":  ("PlayfairDisplay.ttf", b"Regular"),
    "cormorant": ("CormorantGaramond.ttf", b"Medium"),
    "dmserif":   ("DMSerifDisplay-Regular.ttf", None),
    "lora":      ("Lora.ttf", b"Regular"),
    "montserrat": ("Montserrat.ttf", b"SemiBold"),
}

def _hex(c):
    c = c.lstrip("#"); return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))

def _font(naam, grootte, gewicht=None):
    bestand, var = LETTERTYPES[naam]
    f = ImageFont.truetype(os.path.join(FONTS, bestand), grootte)
    try:
        if gewicht or var: f.set_variation_by_name(gewicht or var)
    except Exception:
        pass
    return f

def _klein_font(grootte, gewicht=b"Medium"):
    f = ImageFont.truetype(os.path.join(FONTS, "Montserrat.ttf"), grootte)
    f.set_variation_by_name(gewicht); return f

def achtergrond(b, h, palet, stijl, seed):
    rnd = random.Random(seed)
    boven, onder = _hex(PALETTEN[palet][0]), _hex(PALETTEN[palet][1])
    img = Image.new("RGB", (b, h), boven)
    if stijl == "effen":
        return img
    # verticaal verloop
    strook = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        strook.putpixel((0, y), tuple(int(boven[i] + (onder[i] - boven[i]) * t) for i in range(3)))
    img = strook.resize((b, h))
    if stijl == "verloop":
        return img
    # "licht": zachte lichtvlekken plus korrel
    laag = Image.new("RGB", (b, h), (0, 0, 0))
    d = ImageDraw.Draw(laag)
    acc = _hex(PALETTEN[palet][3])
    for _ in range(3):
        r = rnd.randint(int(b * 0.3), int(b * 0.6))
        cx, cy = rnd.randint(0, b), rnd.randint(0, h)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=acc)
    laag = laag.filter(ImageFilter.GaussianBlur(b // 5))
    img = Image.blend(img, Image.composite(laag, img, laag.convert("L")), 0.35)
    ruis = Image.effect_noise((b, h), 18).convert("RGB")
    img = Image.blend(img, ruis, 0.04)
    return img

def _wrap(tekst, font, max_b, draw):
    woorden, regels, huidig = tekst.split(), [], ""
    for w in woorden:
        test = (huidig + " " + w).strip()
        if draw.textlength(test, font=font) <= max_b:
            huidig = test
        else:
            regels.append(huidig); huidig = w
    if huidig: regels.append(huidig)
    return regels

def tekstlaag(b, h, post, ruimte_boven=0, ruimte_onder=0):
    """Transparante laag met vers, referentie, optionele hook-regel en handle."""
    v = post["variabelen"]
    pal = PALETTEN[v["palet"]]
    kleur, accent = _hex(pal[2]), _hex(pal[3])
    laag = Image.new("RGBA", (b, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(laag)
    marge = int(b * (0.16 if v["layout"] == "kader" else 0.12))
    max_b = b - 2 * marge
    tekst = post["tekst"]
    if v.get("hoofdletters"):
        tekst = tekst.upper()

    # Grootste lettergrootte die past in het beschikbare vlak
    extra = int(b * 0.16) if v["layout"] == "citaat" else 0
    if v.get("hook_op_beeld") and post.get("beeld_hook"):
        extra += int(h * 0.08)
    # Vlak voor tekst + referentie: boven (hook/aanhalingsteken) en onder (handle/kader) vrijhouden
    top = ruimte_boven + int(h * 0.07) + extra
    bodem = h - ruimte_onder - int(h * (0.15 if v["layout"] == "kader" else 0.11))
    ref_h = int(b * 0.09)
    beschikbaar = bodem - top - ref_h
    grootte = int(b * (0.078 if ruimte_boven else 0.066))
    while grootte > 26:
        f = _font(v["lettertype"], grootte)
        regels = _wrap(tekst, f, max_b, d)
        lh = int(grootte * 1.32)
        if lh * len(regels) <= beschikbaar:
            break
        grootte -= 2
    blok_h = lh * len(regels)
    y0 = top + (bodem - top - blok_h - ref_h) // 2

    if v["layout"] == "citaat":
        qf = _font("playfair", int(b * 0.22))
        proef = Image.new("L", (b, b))
        ImageDraw.Draw(proef).text((b // 2, b // 2), "“", font=qf, fill=255, anchor="ms")
        ink_onder = proef.getbbox()[3] - b // 2  # onderkant van de inkt t.o.v. de basislijn
        d.text((b // 2, y0 - int(b * 0.025) - ink_onder), "“", font=qf, fill=accent + (210,), anchor="ms")
    if v["layout"] == "kader":
        p = int(b * 0.06)
        d.rectangle([p, ruimte_boven + p, b - p, h - ruimte_onder - p], outline=accent + (200,), width=3)

    for i, r in enumerate(regels):
        d.text((b // 2, y0 + i * lh), r, font=f, fill=kleur + (255,), anchor="ma")

    rf = _klein_font(int(b * 0.032), b"SemiBold")
    ry = y0 + blok_h + int(b * 0.05)
    d.line([b // 2 - 40, ry - int(b * 0.02), b // 2 + 40, ry - int(b * 0.02)], fill=accent + (255,), width=3)
    d.text((b // 2, ry), post["ref"].upper(), font=rf, fill=accent + (255,), anchor="ma")

    if v.get("hook_op_beeld") and post.get("beeld_hook"):
        hf = _klein_font(int(b * 0.034), b"Medium")
        hook_y = ruimte_boven + (int(b * 0.06) + int(h * 0.03) if v["layout"] == "kader" else int(h * (0.03 if ruimte_boven else 0.07)))
        d.text((b // 2, hook_y), post["beeld_hook"], font=hf, fill=kleur + (200,), anchor="ma")
    # Merkblok onderaan: vaste herkenning op elke post (woordmerk + handle)
    hy = h - ruimte_onder - int(h * (0.115 if v["layout"] == "kader" else 0.085))
    _woordmerk(d, b // 2, hy, "BIBLEVERSE", _klein_font(int(b * 0.024), b"Bold"), accent + (235,), int(b * 0.009))
    if post.get("handle"):
        sf = _klein_font(int(b * 0.022), b"Regular")
        d.text((b // 2, hy + int(b * 0.034)), post["handle"], font=sf, fill=kleur + (140,), anchor="ma")
    return laag

def _woordmerk(d, cx, y, tekst, font, kleur, spatie):
    """Tekst met extra letterafstand, gecentreerd rond cx, met een klein punt-accent ervoor."""
    breedtes = [d.textlength(c, font=font) for c in tekst]
    totaal = sum(breedtes) + spatie * (len(tekst) - 1)
    x = cx - totaal / 2
    r = max(3, font.size // 5)
    d.ellipse([x - 4 * r, y + font.size * 0.42 - r, x - 2 * r, y + font.size * 0.42 + r], fill=kleur)
    for c, w in zip(tekst, breedtes):
        d.text((x, y), c, font=font, fill=kleur, anchor="la")
        x += w + spatie

def maak_afbeelding(post, pad):
    b, h = 1080, 1350
    bg = achtergrond(b, h, post["variabelen"]["palet"], post["variabelen"]["achtergrond"], post["id"])
    img = bg.convert("RGBA")
    img.alpha_composite(tekstlaag(b, h, post))
    img.convert("RGB").save(pad, quality=93)
    return pad

def maak_video(post, pad, duur=9):
    """Achtergrond met langzame zoom, tekst die infadet. Veilige zones voor Reels/TikTok-interface."""
    b, h = 1080, 1920
    with tempfile.TemporaryDirectory() as tmp:
        bg = achtergrond(int(b * 1.15), int(h * 1.15), post["variabelen"]["palet"], post["variabelen"]["achtergrond"], post["id"])
        bgp, txp = os.path.join(tmp, "bg.png"), os.path.join(tmp, "tx.png")
        bg.save(bgp)
        tekstlaag(b, h, post, ruimte_boven=220, ruimte_onder=380).save(txp)
        fps = 30; n = duur * fps
        filt = (f"[0:v]scale={int(b*1.15)}:{int(h*1.15)},zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={n}:s={b}x{h}:fps={fps}[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0.6:d=1.2:alpha=1[tx];"
                f"[bg][tx]overlay=0:0,fade=t=out:st={duur-0.6}:d=0.6,format=yuv420p[v]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(duur), "-i", bgp,
               "-loop", "1", "-t", str(duur), "-i", txp,
               "-f", "lavfi", "-t", str(duur), "-i", "anullsrc=r=44100:cl=stereo",
               "-filter_complex", filt, "-map", "[v]", "-map", "2:a",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
               "-c:a", "aac", "-shortest", "-movflags", "+faststart", pad]
        subprocess.run(cmd, check=True)
    return pad
