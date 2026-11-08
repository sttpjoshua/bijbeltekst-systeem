"""Maakt een afbeelding (1080x1350) of video (1080x1920, 9 s) van een vers.
Alle ontwerpkeuzes komen binnen als variabelen, zodat het leersysteem ze kan vergelijken.
"""
import os, re, random, subprocess, tempfile, math
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
    # Frisse paletten (naar de voorbeelddesigns in het kantoor)
    "zonsopgang_fris": ("#ffb347", "#a8326b", "#fff8ea", "#fff1c9"),
    "hemelsblauw":     ("#9bd2ff", "#3a86c8", "#ffffff", "#eaf6ff"),
    "diep_paars":      ("#8a5ae0", "#2a1650", "#f4ecff", "#d9c6ff"),
    "zachtroze":       ("#ffe3ea", "#f7a1b8", "#5a2236", "#8c3354"),
    "bosgroen":        ("#58a874", "#1f5a3d", "#f1fff4", "#d8f5c8"),
    "mint":            ("#e3fcf4", "#8fdcc7", "#0f4a3c", "#1f7a63"),
    "perzik":          ("#fff6cc", "#ffc28b", "#5a3008", "#b8571a"),
}

# Verlopen met meer kleuren en een hoek (graden, CSS-stijl: 180 = van boven naar beneden)
VERLOPEN = {
    "zonsopgang_fris": (160, ["#ffb347", "#ff6f61", "#a8326b"], [0, .58, 1]),
    "hemelsblauw":     (180, ["#9bd2ff", "#3a86c8"], [0, 1]),
    "zachtroze":       (200, ["#ffe3ea", "#f7a1b8"], [0, 1]),
    "bosgroen":        (170, ["#58a874", "#1f5a3d"], [0, 1]),
    "mint":            (165, ["#e3fcf4", "#8fdcc7"], [0, 1]),
    "perzik":          (150, ["#fff6cc", "#ffd59e", "#ffb38a"], [0, .5, 1]),
}
RADIAAL = {"diep_paars": ((0.25, 0.15), ["#8a5ae0", "#2a1650"], 0.75)}

LETTERTYPES = {
    # naam: (bestand, variatie of None)
    "playfair":  ("PlayfairDisplay.ttf", b"Regular"),
    "cormorant": ("CormorantGaramond.ttf", b"Medium"),
    "dmserif":   ("DMSerifDisplay-Regular.ttf", None),
    "lora":      ("Lora.ttf", b"Regular"),
    "montserrat": ("Montserrat.ttf", b"SemiBold"),
    "montserrat_zwaar": ("Montserrat.ttf", b"ExtraBold"),
    "cormorant_cursief": ("CormorantGaramond-Italic.ttf", b"Medium Italic"),
    "lora_half": ("Lora.ttf", b"Medium"),
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
    f._bv = (naam, gewicht or var)
    return f

_GEWICHTEN = [b"Thin", b"ExtraLight", b"Light", b"Regular", b"Medium", b"SemiBold", b"Bold", b"ExtraBold", b"Black"]

def _vet(f):
    """Een dikkere versie van hetzelfde lettertype (twee stappen zwaarder). Geeft (font, extra_dikte) terug."""
    naam, g = getattr(f, "_bv", (None, None))
    if not naam or not g:
        return f, max(1, round(f.size * 0.025))  # geen gewichten (DM Serif): iets dikker met een rand
    cursief = g.endswith(b"Italic")
    basis = g.replace(b" Italic", b"").replace(b"Italic", b"Regular") or b"Regular"
    v = ImageFont.truetype(os.path.join(FONTS, LETTERTYPES[naam][0]), f.size)
    namen = v.get_variation_names()
    i = _GEWICHTEN.index(basis) if basis in _GEWICHTEN else 3
    for j in range(min(i + 2, len(_GEWICHTEN) - 1), i, -1):
        kand = _GEWICHTEN[j] + (b" Italic" if cursief else b"")
        if kand in namen:
            v.set_variation_by_name(kand); return v, 0
    return f, max(1, round(f.size * 0.025))

def _klein_font(grootte, gewicht=b"Medium"):
    f = ImageFont.truetype(os.path.join(FONTS, "Montserrat.ttf"), grootte)
    f.set_variation_by_name(gewicht); return f

def achtergrond(b, h, palet, stijl, seed):
    rnd = random.Random(seed)
    boven, onder = _hex(PALETTEN[palet][0]), _hex(PALETTEN[palet][1])
    img = Image.new("RGB", (b, h), boven)
    if stijl == "effen":
        return img
    if stijl in ("diagonaal", "radiaal"):
        return _verloop_plus(b, h, palet, stijl)
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

def _verloop_plus(b, h, palet, stijl):
    """Verloop met meerdere kleuren onder een hoek, of radiaal (zoals de voorbeelddesigns)."""
    try:
        import numpy as np
    except ImportError:  # zonder numpy: gewoon verloop van de eerste naar de laatste kleur
        return achtergrond(b, h, palet, "verloop", 0)
    yy, xx = np.mgrid[0:h, 0:b].astype(np.float32)
    if stijl == "radiaal" and palet in RADIAAL:
        (cx, cy), kleuren, straal = RADIAAL[palet]
        t = np.hypot((xx - cx * b) / b, (yy - cy * h) / b) / straal
        stops = [0, 1]
    else:
        hoek, kleuren, stops = VERLOPEN.get(palet, (180, [PALETTEN[palet][0], PALETTEN[palet][1]], [0, 1]))
        a = math.radians(hoek)
        dx, dy = math.sin(a), -math.cos(a)  # CSS: 180deg = naar beneden
        proj = (xx - b / 2) * dx + (yy - h / 2) * dy
        lengte = abs(b / 2 * dx) + abs(h / 2 * dy)
        t = (proj / lengte + 1) / 2
    t = np.clip(t, 0, 1)
    rgb = [np.array(_hex(k), dtype=np.float32) for k in kleuren]
    uit = np.zeros((h, b, 3), dtype=np.float32)
    for i in range(len(stops) - 1):
        lo, hi = stops[i], stops[i + 1]
        m = (t >= lo) & (t <= hi) if i == len(stops) - 2 else (t >= lo) & (t < hi)
        f = ((t - lo) / max(hi - lo, 1e-6))[..., None]
        uit = np.where(m[..., None], rgb[i] * (1 - f) + rgb[i + 1] * f, uit)
    img = Image.fromarray(uit.astype(np.uint8))
    ruis = Image.effect_noise((b, h), 12).convert("RGB")  # heel lichte korrel tegen banding
    return Image.blend(img, ruis, 0.025)

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


# ---------- Kernwoord ----------
_STOP = set("de het een en of maar want dat die dit deze is zijn was waren zal zult zullen wordt worden heeft hebt hebben ik gij u uw mijn mij me ons onze zij hij hem haar hun hen wij we jullie je jij niet geen ook als in op aan van voor met tot uit door over bij naar om te zo dan nu er al wat wie hoe waar daar hier zich zelf heere here heer god gods jezus christus".split())
_STERK = ["vrede", "liefde", "hoop", "kracht", "licht", "herder", "genade", "trouw", "vreugde", "blijdschap", "rust", "sterk",
          "moed", "leven", "hart", "barmhartigheden", "goedertierenheid", "hulp", "vertrouw", "vertrouwen", "geloof", "waarheid", "nieuw"]

def _kaal(w):
    return re.sub(r"[^\w]", "", w.lower())

def kernwoord(post):
    """Het woord dat uitgelicht wordt: wat de schrijver koos, anders een sterk woord uit het vers."""
    woorden = post["tekst"].split()
    kaal = [_kaal(w) for w in woorden]
    k = _kaal(post.get("kernwoord") or "")
    if k and k in kaal:
        return k
    for s in _STERK:
        if s in kaal:
            return s
    kand = [w for w in kaal if w not in _STOP and len(w) >= 5]
    return max(kand, key=len) if kand else None

def _kernstaat(post, kleur, accent, plain=False):
    """Hoe het kernwoord opvalt: dikker, en in de accentkleur. Lijkt de accentkleur te veel op de tekstkleur,
    dan een diepe tint van de achtergrond (of warm goud op een foto). Nooit een vakje of balk eromheen."""
    st = {"kern": kernwoord(post), "kleur": accent, "plain": plain}
    if sum(abs(x - y) for x, y in zip(kleur[:3], accent[:3])) < 120:
        if post["variabelen"].get("achtergrondbron") == "beeld":
            st["kleur"] = (255, 214, 140, 255)
        else:
            lum = lambda c: (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255
            bg = _hex(PALETTEN[post["variabelen"]["palet"]][1])
            if lum(kleur) < 0.5:  # donkere tekst: de accentkleur krachtiger maken (verder van de tekstkleur af)
                st["kleur"] = tuple(max(0, min(255, int(a + (a - t) * 1.6))) for a, t in zip(accent[:3], kleur[:3])) + (255,)
            elif lum(bg) > 0.3:  # lichte tekst op een kleurige achtergrond: een diepe tint van die achtergrond
                st["kleur"] = tuple(int(c * 0.42) for c in bg) + (255,)
            else:  # lichte tekst op een donkere achtergrond: warm goud
                st["kleur"] = (255, 210, 130, 255)
    return st

def _regel(d, x, y, r, f, kleur, accent, staat, links):
    """Eén regel tekst; het kernwoord (eerste keer) in de accentkleur."""
    w = d.textlength(r, font=f)
    x0 = x if links else x - w / 2
    kern = staat.get("kern")
    ws = r.split(" ")
    if kern and not staat.get("klaar"):
        for i, t in enumerate(ws):
            if _kaal(t) == kern:
                m = re.match(r"^(\W*)(.*?)(\W*)$", t)
                voor = " ".join(ws[:i]) + (" " if i else "") + m.group(1)
                na = m.group(3) + (" " if i < len(ws) - 1 else "") + " ".join(ws[i + 1:])
                fv, rand = _vet(f)
                bw = d.textlength(m.group(2), font=fv) + 2 * rand
                w = d.textlength(voor, font=f) + bw + d.textlength(na, font=f)
                x0 = x if links else x - w / 2
                d.text((x0, y), voor, font=f, fill=kleur, anchor="la")
                x1 = x0 + d.textlength(voor, font=f)
                kk = staat.get("kleur", accent)
                staat["pos"] = {"x": x1 + rand, "y": y, "woord": m.group(2), "font": fv, "rand": rand, "kleur": kk}
                kz = kleur if staat.get("plain") else kk
                d.text((x1 + rand, y), m.group(2), font=fv, fill=kz, anchor="la", stroke_width=rand, stroke_fill=kz)
                d.text((x1 + bw, y), na, font=f, fill=kleur, anchor="la")
                staat["klaar"] = True
                return w
    d.text((x0, y), r, font=f, fill=kleur, anchor="la")
    return w

def stopper_fragment(tekst, kern, max_w=10):
    """Het stukje van het vers rond het kernwoord (tussen leestekens), voor een korte, grote eerste slide."""
    woorden = tekst.split()
    stukken, huidig = [], []
    for i, w in enumerate(woorden):
        huidig.append(i)
        if w[-1] in ",;:.!?":
            stukken.append(huidig); huidig = []
    if huidig:
        stukken.append(huidig)
    idx = next((i for i, w in enumerate(woorden) if _kaal(w) == kern), 0)
    st = next(s for s in stukken if idx in s)
    if len(st) < 4:  # te kort: neem het volgende stuk erbij
        j = stukken.index(st)
        if j + 1 < len(stukken):
            st = st + stukken[j + 1]
    if len(st) > max_w:
        a = max(st[0], min(idx - 3, st[-1] - max_w + 1)); st = list(range(a, a + max_w))
    frag = " ".join(woorden[st[0]:st[-1] + 1])
    if st[-1] < len(woorden) - 1:
        frag = frag.rstrip(",;:.!?")
    if st[0] > 0:
        frag = "\u2026" + frag[0].lower() + frag[1:] if not frag[:2].isupper() else "\u2026" + frag
    if st[-1] < len(woorden) - 1:
        frag += "\u2026"
    return frag

def tekstlaag(b, h, post, ruimte_boven=0, ruimte_onder=0, geo=None, kern_info=None):
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
    if post.get("reeks_label"):
        top += int(h * 0.05)
    bodem = h - ruimte_onder - int(h * (0.15 if v["layout"] == "kader" else 0.11))
    ref_h = int(b * 0.09)
    uitleg_regels, uf = [], None
    if v.get("uitleg_op_beeld") and post.get("uitleg"):
        uf = _klein_font(int(b * 0.03), b"Medium")
        uitleg_regels = _wrap(post["uitleg"], uf, int(max_b * 0.92), d)
        ref_h += int(b * 0.05) + len(uitleg_regels) * int(uf.size * 1.4)
    beschikbaar = bodem - top - ref_h
    grootte = int(b * (0.078 if ruimte_boven else 0.066))
    if post.get("_stopper"):
        grootte = int(b * 0.115)
    elif v["layout"] == "links":  # groter en luchtiger bij korte verzen, zoals de voorbeelden
        grootte = int(grootte * (1.25 if len(tekst) < 80 else 1.08 if len(tekst) < 140 else 0.95))
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

    links = v["layout"] == "links"
    tx, an = (marge, "la") if links else (b // 2, "ma")
    staat = _kernstaat(post, kleur, accent, plain=kern_info is not None)
    for i, r in enumerate(regels):
        w = _regel(d, tx, y0 + i * lh, r, f, kleur + (255,), accent + (255,), staat, links)
        if geo is not None:  # plaats van elke regel, voor het woord-voor-woord verschijnen in video's
            geo.append({"x": tx if links else b // 2 - w / 2, "w": w, "y": y0 + i * lh - int(lh * 0.12), "h": int(lh * 1.12), "tekst": r, "font": f})

    rf = _klein_font(int(b * 0.032), b"SemiBold")
    ry = y0 + blok_h + int(b * 0.05)
    reftekst = (post["ref"] + ("  \u00b7  NBV21" if post.get("vertaling") == "NBV21" else "")).upper()
    if post.get("_stopper"):
        reftekst = post["ref"].upper() + "  \u00b7  LEES VERDER \u2192"
    if links:
        d.text((tx, ry), reftekst, font=rf, fill=accent + (255,), anchor="la")
    else:
        d.line([b // 2 - 40, ry - int(b * 0.02), b // 2 + 40, ry - int(b * 0.02)], fill=accent + (255,), width=3)
        d.text((b // 2, ry), reftekst, font=rf, fill=accent + (255,), anchor="ma")
    if uitleg_regels:
        uy = ry + int(b * 0.075)
        for i, r in enumerate(uitleg_regels):
            d.text((tx, uy + i * int(uf.size * 1.4)), r, font=uf, fill=kleur + (205,), anchor=an)

    if kern_info is not None and staat.get("pos"):
        kern_info.update(staat["pos"])
    if v.get("hook_op_beeld") and post.get("beeld_hook"):
        hf = _klein_font(int(b * 0.034), b"Medium")
        hook_y = ruimte_boven + (int(b * 0.06) + int(h * 0.03) if v["layout"] == "kader" else int(h * (0.03 if ruimte_boven else 0.07)))
        d.text((b // 2, hook_y), post["beeld_hook"], font=hf, fill=kleur + (200,), anchor="ma")
    if post.get("reeks_label"):  # reeks (Advent, Moed voor de week, ...) bovenaan
        _woordmerk(d, b // 2, ruimte_boven + int(h * 0.06), post["reeks_label"], _klein_font(int(b * 0.028), b"Bold"), accent + (255,), int(b * 0.008))
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

def maak_afbeelding(post, pad, bg=None):
    b, h = 1080, 1350
    img = (bg or _bg(post, b, h)).convert("RGBA")
    img.alpha_composite(tekstlaag(b, h, post))
    img.convert("RGB").save(pad, quality=93)
    return pad

def _stukjes(woorden, max_w=6):
    """Verdeelt een vers in korte stukjes (op leestekens, hooguit max_w woorden) die na elkaar verschijnen."""
    uit, huidig = [], []
    for w in woorden:
        huidig.append(w)
        if w[-1] in ",;:.!?" or len(huidig) >= max_w:
            uit.append(huidig); huidig = []
    if huidig:
        uit.append(huidig)
    return uit

def _uitleglaag(post, titel, body, b, h, boven, onder, onderschrift=None, tot=None):
    """Transparante laag voor een uitlegscherm in een video: titel, lopende tekst, bijbelplaats en merk."""
    v = post["variabelen"]
    kleur, accent = _kleuren(post)
    laag = Image.new("RGBA", (b, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(laag)
    marge = int(b * 0.12)
    if v["layout"] == "kader":
        p = int(b * 0.06)
        d.rectangle([p, boven - p, b - p, h - onder + p], outline=accent + (200,), width=3)
    ruimte = h - boven - onder
    _woordmerk(d, b // 2, boven + int(ruimte * 0.08), titel, _klein_font(int(b * 0.034), b"Bold"), accent + (255,), int(b * 0.009))
    grootte = int(b * 0.066)
    while grootte > 28:
        f = _font(v["lettertype"], grootte)
        regels = _wrap(body, f, b - 2 * marge, d)
        lh = int(grootte * 1.38)
        extra = 0
        if onderschrift:
            of = _font(v["lettertype"], int(grootte * 0.9))
            oregels = _wrap(onderschrift, of, b - 2 * marge, d)
            extra = int(lh * 0.8) + len(oregels) * int(grootte * 0.9 * 1.38)
        if lh * len(regels) + extra <= ruimte * 0.62:
            break
        grootte -= 2
    totaal = lh * len(regels) + extra
    y0 = boven + int(ruimte * 0.2) + (int(ruimte * 0.62) - totaal) // 2
    links = v["layout"] == "links"
    staat = _kernstaat(post, kleur, accent)
    alle = [("b", r) for r in regels] + ([("o", r) for r in oregels] if onderschrift else [])
    tot = len(alle) if tot is None else tot
    for i, r in enumerate(regels[:tot]):
        _regel(d, marge if links else b // 2, y0 + i * lh, r, f, kleur + (255,), accent + (255,), staat, links)
    if onderschrift:
        oy = y0 + lh * len(regels) + int(lh * 0.8)
        olh = int(grootte * 0.9 * 1.38)
        for i, r in enumerate(oregels[:max(0, tot - len(regels))]):
            d.text((marge if links else b // 2, oy + i * olh), r, font=of, fill=accent + (255,), anchor="la" if links else "ma")
    rf = _klein_font(int(b * 0.028), b"SemiBold")
    d.text((b // 2, h - onder - int(b * 0.09)), (post["ref"] + ("  \u00b7  NBV21" if post.get("vertaling") == "NBV21" else "")).upper(), font=rf, fill=accent + (220,), anchor="ma")
    _woordmerk(d, b // 2, h - onder - int(b * 0.03), "BIBLEVERSE", _klein_font(int(b * 0.024), b"Bold"), accent + (235,), int(b * 0.009))
    laag.regels = [r for _, r in alle]
    return laag

def _beats(pad, start, duur):
    """Momenten (in seconden) met een duidelijke tel in de muziek, via spectrale flux. Leeg als het niet lukt."""
    try:
        import numpy as np
        sr = 22050
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(duur + 2), "-i", pad,
                              "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, check=True).stdout
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
        hop, n = 512, 1024
        if len(x) < n * 4:
            return []
        fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
        spec = np.abs(np.fft.rfft(fr, axis=1))
        flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(axis=1)
        flux = (flux - flux.mean()) / (flux.std() + 1e-9)
        w = int(0.12 * sr / hop)
        uit = []
        for i in range(w, len(flux) - w):
            if flux[i] > 0.8 and flux[i] == flux[i - w:i + w + 1].max():
                uit.append((i + 1) * hop / sr)
        return uit
    except Exception:
        return []

def maak_video(post, pad, duur=None):
    """Reel. Het vers verschijnt frase voor frase (het eerste stukje staat er meteen); het kernwoord kleurt daarna op.
    Met video_uitleg schuift het beeld als een carrousel door naar "Wat betekent dit?" en "Vandaag" (regel voor regel),
    met een voortgangsbalkje bovenin. Overgangen vallen op een tel in de muziek. Aan het eind keert het beeld terug
    naar precies het beginbeeld, zodat de reel naadloos opnieuw begint. post["cover_ms"] = goed omslagmoment."""
    b, h = 1080, 1920
    BOVEN, ONDER = 220, 380
    v = post["variabelen"]
    uitleg = bool(v.get("video_uitleg") and post.get("betekenis") and post.get("toepassing"))
    kleur, accent = _kleuren(post)
    with tempfile.TemporaryDirectory() as tmp:
        def bewaar(im, naam):
            pth = os.path.join(tmp, naam); im.save(pth); return pth
        def bewaar_laag(im, naam):
            """Transparante laag bijgesneden tot de inhoud: (pad, x, y). Scheelt veel rekenwerk bij het samenvoegen."""
            bb = im.getbbox() or (0, 0, 2, 2)
            return bewaar(im.crop(bb), naam), bb[0], bb[1]
        # achtergrond: drie schermen breed met uitleg, anders één
        strook = _panorama(post, b, h, 3) if uitleg else _bg(post, b, h)
        # vers (kernwoord eerst in tekstkleur) + geometrie per regel
        geo, kern = [], {}
        vol = tekstlaag(b, h, post, ruimte_boven=BOVEN, ruimte_onder=ONDER, geo=geo, kern_info=kern)
        woorden = [w for g in geo for w in g["tekst"].split()]
        stukjes = _stukjes(woorden)
        d = ImageDraw.Draw(Image.new("L", (1, 1)))
        def laag_tot(n):
            masker = Image.new("L", (b, h), 255); md = ImageDraw.Draw(masker); teller = 0
            for g in geo:
                ws = g["tekst"].split()
                if teller + len(ws) <= n:
                    teller += len(ws); continue
                zichtbaar = max(0, n - teller)
                x0 = g["x"] + (d.textlength(" ".join(ws[:zichtbaar]) + " ", font=g["font"]) - g["font"].size * 0.09 if zichtbaar else 0)
                md.rectangle([x0, g["y"], g["x"] + g["w"] + 40, g["y"] + g["h"]], fill=0)
                teller += len(ws)
            alpha = Image.composite(vol.getchannel("A"), Image.new("L", (b, h), 0), masker)
            l = vol.copy(); l.putalpha(alpha); return l
        # tijden van het vers
        tijden, t, n_tot, stuk_van = [], 0.0, 0, []
        for i, st in enumerate(stukjes):
            tijden.append(round(t, 2)); stuk_van += [i] * len(st)
            t += max(0.7, len(st) / 3.0)
        vers_klaar = tijden[-1] + 0.35
        post["cover_ms"] = int((vers_klaar + 0.4) * 1000)  # omslag: het hele vers staat in beeld
        # muziek-tellen voor de overgangen
        beats = _beats(post["muziek_pad"], post.get("muziek_start", 0), 60) if post.get("muziek_pad") else []
        def op_tel(x):
            kand = [bt for bt in beats if x <= bt <= x + 0.7]
            return round(kand[0], 2) if kand else round(x, 2)
        lagen = []  # (pad, x, fade_in, fade_out_or_None, fade_duur)
        n_tot = 0
        for i, st in enumerate(stukjes):
            n_tot += len(st)
            lagen.append([bewaar_laag(laag_tot(n_tot), f"v{i}.png"), 0, tijden[i], "eind" if i > 0 else None, 0.35])
        # kernwoord: kleurt op (met een korte 'pop') zodra zijn stukje er staat
        kern_lagen = []
        if kern.get("woord"):
            kaal = [_kaal(w) for w in woorden]
            k_idx = kaal.index(_kaal(kern["woord"])) if _kaal(kern["woord"]) in kaal else 0
            tk = tijden[stuk_van[k_idx]] + 0.35
            kl = Image.new("RGBA", (b, h), (0, 0, 0, 0)); kd = ImageDraw.Draw(kl)
            kd.text((kern["x"], kern["y"]), kern["woord"], font=kern["font"], fill=kern["kleur"], anchor="la",
                    stroke_width=kern["rand"], stroke_fill=kern["kleur"])
            pop = Image.new("RGBA", (b, h), (0, 0, 0, 0))
            bb = kl.getbbox()
            if bb:
                stuk = kl.crop(bb); sc = 1.14
                groot = stuk.resize((int(stuk.width * sc), int(stuk.height * sc)), Image.LANCZOS)
                cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                pop.alpha_composite(groot, (int(cx - groot.width / 2), int(cy - groot.height / 2)))
            kern_lagen.append([bewaar_laag(kl, "kern.png"), 0, tk, "eind", 0.3])  # aan het eind weer neutraal: zoals het beginbeeld
            kern_lagen.append([bewaar_laag(pop, "pop.png"), 0, tk, ("pop", tk + 0.18), 0.12])
        # tijdlijn
        lees = lambda tekst: len(tekst.split()) / 2.8
        if uitleg:
            vraag = (post.get("caption", "").strip().splitlines() or [""])[-1].strip()
            vraag = vraag if vraag.endswith("?") and len(vraag) <= 90 else None
            T1 = op_tel(vers_klaar + max(1.8, lees(post["tekst"]) * 0.35))
            schermen, t0, overgangen = [], T1 + 0.8, [T1]
            for nr, (titel, body, onder) in enumerate((("WAT BETEKENT DIT?", post["betekenis"], None),
                                                       ("VANDAAG", post["toepassing"], vraag)), start=1):
                volledig = _uitleglaag(post, titel, body, b, h, BOVEN, ONDER, onder)
                regels = volledig.regels
                tl = t0 + 0.1
                for j in range(len(regels) + 1):
                    if j == 0:  # titel (en merk) staan er al tijdens het inschuiven
                        lagen.append([bewaar_laag(_uitleglaag(post, titel, body, b, h, BOVEN, ONDER, onder, tot=0), f"u{nr}_0.png"), nr * b, 0, None, 0.3])
                        continue
                    lagen.append([bewaar_laag(_uitleglaag(post, titel, body, b, h, BOVEN, ONDER, onder, tot=j), f"u{nr}_{j}.png"),
                                  nr * b, round(tl, 2), None, 0.3])
                    tl += max(0.5, lees(regels[j - 1]))
                einde = op_tel(tl + 1.6)
                overgangen.append(einde); t0 = einde + 0.8
            T2, T3 = overgangen[1], overgangen[2]
            terug = T3 + 1.0           # terugschuiven naar het vers (het beginbeeld)
            eind = terug + 0.6         # even het hele vers, daarna terug naar alleen het eerste stukje
            duur = int(math.ceil(eind + 0.5))
        else:
            eind = vers_klaar + max(3.0, lees(post["tekst"]) * 0.6)
            duur = int(min(20, max(9, math.ceil(eind + 0.5))))
            eind = duur - 0.5
        post["duur"] = duur
        # voortgangsbalkje (alleen met uitleg): drie streepjes, het actieve stuk licht op
        balk = []
        if uitleg:
            fasen = [(0, T1 + 0.4), (T1 + 0.4, T2 + 0.4), (T2 + 0.4, terug), (terug, duur + 1)]
            mx, gap, by, bh = int(b * 0.12), 14, BOVEN + 10, 6
            sw = (b - 2 * mx - 2 * gap) / 3
            for k, (van, tot) in enumerate(fasen):
                im = Image.new("RGBA", (b, h), (0, 0, 0, 0)); bd = ImageDraw.Draw(im)
                for j in range(3):
                    x0 = mx + j * (sw + gap)
                    bd.rounded_rectangle([x0, by, x0 + sw, by + bh], radius=3, fill=kleur + ((235,) if j <= k % 3 else (70,)))
                balk.append((bewaar(im, f"balk{k}.png"), van, tot))
        # ffmpeg-opbouw
        fps = 30
        inputs = ["-loop", "1", "-framerate", str(fps), "-t", str(duur), "-i", bewaar(strook.convert("RGB"), "strook.png")]
        filt, vorige, idx = "[0:v]format=rgba[s0]", "s0", 1
        for (pth, bx, by), x, tin, tuit, fd in lagen + kern_lagen:
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", str(duur), "-i", pth]
            f = f"[{idx}:v]format=rgba"
            if tin > 0:
                f += f",fade=t=in:st={tin}:d={fd}:alpha=1"
            if tuit == "eind":
                f += f",fade=t=out:st={eind:.2f}:d=0.45:alpha=1"
            elif isinstance(tuit, tuple):
                f += f",fade=t=out:st={tuit[1]:.2f}:d=0.3:alpha=1"
            filt += f";{f}[l{idx}];[{vorige}][l{idx}]overlay={x + bx}:{by}[s{idx}]"
            vorige = f"s{idx}"; idx += 1
        if uitleg:
            e = lambda a: f"(({a})*({a})*(3-2*({a})))"
            u = lambda T, d: f"(t-{T:.2f})/{d}"
            xexpr = (f"if(lt(t,{T1:.2f}),0,if(lt(t,{T1+0.8:.2f}),{b}*{e(u(T1,0.8))},if(lt(t,{T2:.2f}),{b},"
                     f"if(lt(t,{T2+0.8:.2f}),{b}+{b}*{e(u(T2,0.8))},if(lt(t,{T3:.2f}),{2*b},"
                     f"if(lt(t,{terug:.2f}),{2*b}-{2*b}*{e(u(T3,1.0))},0))))))")
            filt += f";[{vorige}]crop=w={b}:h={h}:x='{xexpr}':y=0[c]"; vorige = "c"
        n = duur * fps
        filt += (f";[{vorige}]zoompan=z='1+0.035*sin(PI*on/{n})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d=1:s={b}x{h}:fps={fps}[z]"); vorige = "z"
        for k, (pth, van, tot) in enumerate(balk):
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", str(duur), "-i", pth]
            filt += f";[{vorige}][{idx}:v]overlay=0:0:enable='between(t,{van:.2f},{tot:.2f})'[b{k}]"
            vorige = f"b{k}"; idx += 1
        filt += f";[{vorige}]format=yuv420p[v]"
        ai = idx
        audio_in = ["-f", "lavfi", "-t", str(duur), "-i", "anullsrc=r=44100:cl=stereo"]
        audio_map = f"{ai}:a"
        m = post.get("muziek_pad")
        if m:
            start = post.get("muziek_start", 0)
            audio_in = ["-ss", str(start), "-t", str(duur), "-i", m]
            afilt = f"[{ai}:a]volume=0.8,afade=t=in:st=0:d=0.3,afade=t=out:st={duur-0.9}:d=0.9[am]"
            amb = post.get("geluid_pad")
            if amb:
                audio_in += ["-ss", "3", "-t", str(duur), "-i", amb]
                afilt = (f"[{ai}:a]volume=0.8,afade=t=in:st=0:d=0.3,afade=t=out:st={duur-0.9}:d=0.9[m1];"
                         f"[{ai+1}:a]volume=0.25,afade=t=in:st=0:d=1,afade=t=out:st={duur-0.9}:d=0.9[g1];"
                         f"[m1][g1]amix=inputs=2:duration=first:normalize=0[am]")
            filt += ";" + afilt
            audio_map = "[am]"
        script = os.path.join(tmp, "filter.txt")
        open(script, "w").write(filt)
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + audio_in + [
               "-filter_complex_script", script, "-map", "[v]", "-map", audio_map,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
               "-c:a", "aac", "-t", str(duur), "-movflags", "+faststart", pad]
        subprocess.run(cmd, check=True)
    return pad


def _tekstslide(post, titel, body, pad, nummer, bg=None):
    """Slide 2 en 3 van een carrousel: titel + lopende tekst in de huisstijl."""
    b, h = 1080, 1350
    v = post["variabelen"]
    pal = PALETTEN[v["palet"]]
    kleur, accent = _kleuren(post) if bg is not None else (_hex(pal[2]), _hex(pal[3]))
    img = (bg or achtergrond(b, h, v["palet"], v["achtergrond"], post["id"] + str(nummer))).convert("RGBA")
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
    links = v["layout"] == "links"
    staat = _kernstaat(post, kleur, accent)
    for i, r in enumerate(regels):
        _regel(d, marge if links else b // 2, y0 + i * lh, r, f, kleur + (255,), accent + (255,), staat, links)
    rf = _klein_font(int(b * 0.026), b"SemiBold")
    d.text((b // 2, int(h * 0.85)), (post["ref"] + ("  \u00b7  NBV21" if post.get("vertaling") == "NBV21" else "")).upper(), font=rf, fill=accent + (220,), anchor="ma")
    hy = h - int(h * (0.115 if v["layout"] == "kader" else 0.085))
    _woordmerk(d, b // 2, hy, "BIBLEVERSE", _klein_font(int(b * 0.024), b"Bold"), accent + (235,), int(b * 0.009))
    if post.get("handle"):
        d.text((b // 2, hy + int(b * 0.034)), post["handle"], font=_klein_font(int(b * 0.022), b"Regular"), fill=kleur + (140,), anchor="ma")
    img.alpha_composite(laag)
    img.convert("RGB").save(pad, quality=93)
    return pad

def _panorama(post, b, h, n=3):
    """Eén doorlopende achtergrond voor alle drie de slides, zodat ze bij het swipen in elkaar overlopen.
    Met een foto: links scherp, naar rechts steeds zachter en rustiger zodat de uitleg goed leesbaar is."""
    v = post["variabelen"]
    B = b * n
    if v.get("achtergrondbron") == "beeld" and post.get("beeld_pad"):
        foto = foto_achtergrond(B, h, post["beeld_pad"], v["palet"])
        zacht = foto.filter(ImageFilter.GaussianBlur(26))
        donker = Image.new("RGB", (B, h), (12, 12, 16))
        zacht = Image.blend(zacht, donker, 0.25)
        masker = Image.new("L", (B, 1))
        for x in range(B):
            t = min(1, max(0, (x - b * 0.8) / (b * 0.6)))
            masker.putpixel((x, 0), int(255 * (t * t * (3 - 2 * t))))
        return Image.composite(zacht, foto, masker.resize((B, h)))
    stijl = v.get("achtergrond", "verloop")
    if stijl in ("diagonaal", "radiaal"):
        return _verloop_plus(B, h, v["palet"], stijl)
    if stijl == "effen":
        return achtergrond(B, h, v["palet"], "effen", post["id"])
    # verticaal verloop of lichtvlekken: horizontaal doorlopend
    return achtergrond(B, h, v["palet"], stijl, post["id"])

def maak_carrousel(post, basis):
    """Slides op één doorlopende achtergrond: (stopper,) vers, betekenis, toepassing. Geeft de lijst met paden terug."""
    b, h = 1080, 1350
    stopper = post["variabelen"].get("opening") == "stopper"
    n = 4 if stopper else 3
    paden = [basis.replace(".jpg", f"-{i}.jpg") for i in range(1, n + 1)]
    pano = _panorama(post, b, h, n)
    delen = [pano.crop((i * b, 0, (i + 1) * b, h)) for i in range(n)]
    eerste = dict(post, variabelen=dict(post["variabelen"], uitleg_op_beeld=False))
    k = 0
    if stopper:
        kern = kernwoord(post)
        maak_afbeelding(dict(eerste, tekst=stopper_fragment(post["tekst"], kern), _stopper=True),
                        paden[0], bg=delen[0])
        k = 1
    maak_afbeelding(eerste, paden[k], bg=delen[k])
    if not stopper:  # klein veeg-teken rechtsonder op slide 1
        im = Image.open(paden[0]).convert("RGBA"); d = ImageDraw.Draw(im)
        acc = _kleuren(post)[1]
        d.text((im.width - 70, im.height - 70), "\u2192", font=_klein_font(44, b"Medium"), fill=acc + (220,), anchor="mm")
        im.convert("RGB").save(paden[0], quality=93)
    _tekstslide(post, "WAT BETEKENT DIT?", post["betekenis"], paden[k + 1], 2, bg=delen[k + 1])
    _tekstslide(post, "VANDAAG", post["toepassing"], paden[k + 2], 3, bg=delen[k + 2])
    return paden


def maak_story(slide1, pad):
    """Story-versie (1080x1920) van slide 1: de slide in het midden op een vervaagde versie van zichzelf."""
    im = Image.open(slide1).convert("RGB")
    b, h = 1080, 1920
    achter = im.resize((int(h * im.width / im.height), h)).crop((0, 0, b, h)) if im.width / im.height < b / h else im.resize((b, int(b * im.height / im.width)))
    achter = achter.resize((b, h)).filter(ImageFilter.GaussianBlur(40))
    achter = Image.blend(achter, Image.new("RGB", (b, h), (0, 0, 0)), 0.25)
    w = int(b * 0.86); kaart = im.resize((w, int(w * im.height / im.width)))
    x, y = (b - w) // 2, (h - kaart.height) // 2 - 40
    schaduw = Image.new("L", (b, h), 0)
    ImageDraw.Draw(schaduw).rounded_rectangle([x + 8, y + 16, x + w + 8, y + kaart.height + 16], 24, fill=120)
    achter.paste((0, 0, 0), (0, 0), schaduw.filter(ImageFilter.GaussianBlur(18)))
    masker = Image.new("L", kaart.size, 0)
    ImageDraw.Draw(masker).rounded_rectangle([0, 0, kaart.width, kaart.height], 24, fill=255)
    achter.paste(kaart, (x, y), masker)
    d = ImageDraw.Draw(achter)
    d.text((b // 2, y + kaart.height + 70), "Nieuwe post · bekijk het profiel", font=_klein_font(36, b"SemiBold"), fill=(255, 255, 255), anchor="ma")
    achter.save(pad, quality=92)
    return pad
