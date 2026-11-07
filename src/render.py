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

def foto_achtergrond(b, h, pad, palet):
    """Eigen foto als achtergrond: bijgesneden, gedimd en licht getint in de huisstijlkleur."""
    from PIL import ImageOps, ImageEnhance
    im = Image.open(pad); im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((b * 2, h * 2))
    im = ImageOps.fit(im, (b, h), centering=(0.5, 0.45))
    im = ImageEnhance.Color(im).enhance(0.85)
    tint = Image.new("RGB", (b, h), _hex(PALETTEN[palet][0]))
    im = Image.blend(im, tint, 0.18)
    # verloop van boven licht naar onder donkerder, en overal gedimd voor leesbaarheid
    donker = Image.new("RGB", (b, h), (8, 8, 10))
    masker = Image.linear_gradient("L").resize((b, h)).point(lambda x: int(80 + x * 0.42))
    return Image.composite(donker, im, masker)

def _kleuren(post):
    v = post["variabelen"]
    pal = PALETTEN[v["palet"]]
    if v.get("achtergrondbron") == "beeld":
        return (250, 247, 240), (236, 210, 160)  # lichte tekst op gedimde foto
    return _hex(pal[2]), _hex(pal[3])

def _bg(post, b, h):
    v = post["variabelen"]
    if v.get("achtergrondbron") == "beeld" and post.get("beeld_pad"):
        return foto_achtergrond(b, h, post["beeld_pad"], v["palet"])
    return achtergrond(b, h, v["palet"], v["achtergrond"], post["id"])

def tekstlaag(b, h, post, ruimte_boven=0, ruimte_onder=0):
    """Transparante laag met vers, referentie, optionele hook-regel en handle."""
    v = post["variabelen"]
    kleur, accent = _kleuren(post)
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
    uitleg_regels, uf = [], None
    if v.get("uitleg_op_beeld") and post.get("uitleg"):
        uf = _klein_font(int(b * 0.03), b"Medium")
        uitleg_regels = _wrap(post["uitleg"], uf, int(max_b * 0.92), d)
        ref_h += int(b * 0.05) + len(uitleg_regels) * int(uf.size * 1.4)
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
    d.text((b // 2, ry), (post["ref"] + ("  \u00b7  NBV21" if post.get("vertaling") == "NBV21" else "")).upper(), font=rf, fill=accent + (255,), anchor="ma")
    if uitleg_regels:
        uy = ry + int(b * 0.075)
        for i, r in enumerate(uitleg_regels):
            d.text((b // 2, uy + i * int(uf.size * 1.4)), r, font=uf, fill=kleur + (205,), anchor="ma")

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
    img = _bg(post, b, h).convert("RGBA")
    img.alpha_composite(tekstlaag(b, h, post))
    img.convert("RGB").save(pad, quality=93)
    return pad

def maak_video(post, pad, duur=9):
    """Achtergrond met langzame zoom, tekst vrijwel direct in beeld (sterke eerste seconde). Veilige zones voor Reels/TikTok-interface."""
    b, h = 1080, 1920
    with tempfile.TemporaryDirectory() as tmp:
        bg = _bg(post, int(b * 1.15), int(h * 1.15))
        bgp, txp = os.path.join(tmp, "bg.png"), os.path.join(tmp, "tx.png")
        bg.save(bgp)
        tekstlaag(b, h, post, ruimte_boven=220, ruimte_onder=380).save(txp)
        fps = 30; n = duur * fps
        filt = (f"[0:v]scale={int(b*1.15)}:{int(h*1.15)},zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={n}:s={b}x{h}:fps={fps}[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1[tx];"
                f"[bg][tx]overlay=0:0,fade=t=out:st={duur-0.6}:d=0.6,format=yuv420p[v]")
        audio_in = ["-f", "lavfi", "-t", str(duur), "-i", "anullsrc=r=44100:cl=stereo"]
        audio_map = "2:a"
        m = post.get("muziek_pad")
        if m:
            start = post.get("muziek_start", 0)
            audio_in = ["-ss", str(start), "-t", str(duur), "-i", m]
            afilt = f"[2:a]volume=0.8,afade=t=in:st=0:d=0.6,afade=t=out:st={duur-1.2}:d=1.2[am]"
            amb = post.get("geluid_pad")
            if amb:
                audio_in += ["-ss", "3", "-t", str(duur), "-i", amb]
                afilt = (f"[2:a]volume=0.8,afade=t=in:st=0:d=0.6,afade=t=out:st={duur-1.2}:d=1.2[m1];"
                         f"[3:a]volume=0.25,afade=t=in:st=0:d=1,afade=t=out:st={duur-1.2}:d=1.2[g1];"
                         f"[m1][g1]amix=inputs=2:duration=first:normalize=0[am]")
            filt += ";" + afilt
            audio_map = "[am]"
        # Achtergrond als één frame: zoompan maakt daar zelf `n` frames van (snel en exact 9 s)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", bgp,
               "-loop", "1", "-framerate", str(fps), "-t", str(duur), "-i", txp] + audio_in + [
               "-filter_complex", filt, "-map", "[v]", "-map", audio_map,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
               "-c:a", "aac", "-t", str(duur), "-movflags", "+faststart", pad]
        subprocess.run(cmd, check=True)
    return pad


def _tekstslide(post, titel, body, pad, nummer):
    """Slide 2 en 3 van een carrousel: titel + lopende tekst in de huisstijl."""
    b, h = 1080, 1350
    v = post["variabelen"]
    pal = PALETTEN[v["palet"]]
    kleur, accent = _hex(pal[2]), _hex(pal[3])
    img = achtergrond(b, h, v["palet"], v["achtergrond"], post["id"] + str(nummer)).convert("RGBA")  # tekstslides altijd met verloop
    laag = Image.new("RGBA", (b, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(laag)
    marge = int(b * 0.14)
    if v["layout"] == "kader":
        p = int(b * 0.06)
        d.rectangle([p, p, b - p, h - p], outline=accent + (200,), width=3)
    tf = _klein_font(int(b * 0.03), b"Bold")
    _woordmerk(d, b // 2, int(h * 0.16), titel, tf, accent + (255,), int(b * 0.008))
    grootte = int(b * 0.058)
    while grootte > 26:
        f = _font(v["lettertype"], grootte)
        regels = _wrap(body, f, b - 2 * marge, d)
        lh = int(grootte * 1.38)
        if lh * len(regels) <= h * 0.55:
            break
        grootte -= 2
    y0 = int(h * 0.27) + (int(h * 0.55) - lh * len(regels)) // 2
    for i, r in enumerate(regels):
        d.text((b // 2, y0 + i * lh), r, font=f, fill=kleur + (255,), anchor="ma")
    rf = _klein_font(int(b * 0.026), b"SemiBold")
    d.text((b // 2, int(h * 0.85)), (post["ref"] + ("  \u00b7  NBV21" if post.get("vertaling") == "NBV21" else "")).upper(), font=rf, fill=accent + (220,), anchor="ma")
    hy = h - int(h * (0.115 if v["layout"] == "kader" else 0.085))
    _woordmerk(d, b // 2, hy, "BIBLEVERSE", _klein_font(int(b * 0.024), b"Bold"), accent + (235,), int(b * 0.009))
    if post.get("handle"):
        d.text((b // 2, hy + int(b * 0.034)), post["handle"], font=_klein_font(int(b * 0.022), b"Regular"), fill=kleur + (140,), anchor="ma")
    img.alpha_composite(laag)
    img.convert("RGB").save(pad, quality=93)
    return pad

def maak_carrousel(post, basis):
    """Drie slides: vers, betekenis, toepassing. Geeft de lijst met paden terug."""
    paden = [basis.replace(".jpg", f"-{i}.jpg") for i in (1, 2, 3)]
    eerste = dict(post, variabelen=dict(post["variabelen"], uitleg_op_beeld=False))
    maak_afbeelding(eerste, paden[0])
    # klein veeg-teken rechtsonder op slide 1
    im = Image.open(paden[0]).convert("RGBA"); d = ImageDraw.Draw(im)
    acc = _kleuren(post)[1]
    d.text((im.width - 70, im.height - 70), "\u2192", font=_klein_font(44, b"Medium"), fill=acc + (220,), anchor="mm")
    im.convert("RGB").save(paden[0], quality=93)
    _tekstslide(post, "WAT BETEKENT DIT?", post["betekenis"], paden[1], 2)
    _tekstslide(post, "VANDAAG", post["toepassing"], paden[2], 3)
    return paden
