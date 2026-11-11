"""Nieuwe reelstijlen (punt 5): sneller, zodat je blijft kijken.

  kinetisch  Het vers knalt woord voor woord (1 tot 3 woorden tegelijk) op de tel van de muziek in beeld,
             groot en vet; het kernwoord staat alleen, extra groot en in kleur. Daarna in hetzelfde tempo
             één zin uitleg ("Betekent:") en een eindbeeld. 9 tot 14 seconden.
  beeld      Bewegend beeld: foto's met snelle zoom en harde cuts per zin; de tekst verschijnt woord voor woord.
  haak=vraag Vóór alles staat 1,4 seconde een grote vraag in beeld ("Ben jij moe?"). Te combineren met beide stijlen.

Frames worden met PIL getekend en rechtstreeks naar ffmpeg gestuurd (geen tussenbestanden).
"""
import math, os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageOps

import render as R

B, H, FPS = 1080, 1920, 30


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _brokken(tekst, kern):
    """Verdeelt het vers in brokjes van 1 tot 3 woorden. Breekt na leestekens; het kernwoord staat alleen."""
    woorden = tekst.split()
    uit, huidig = [], []
    for w in woorden:
        if kern and R._kaal(w) == kern:
            if huidig:
                uit.append(huidig); huidig = []
            uit.append([w]); continue
        huidig.append(w)
        lang = sum(len(x) for x in huidig)
        if re.search(r"[,.;:!?]$", w) or len(huidig) >= 3 or lang >= 16:
            uit.append(huidig); huidig = []
    if huidig:
        uit.append(huidig)
    # heel korte losse woordjes ("en", "de") aan het volgende brokje plakken
    samen = []
    for br in uit:
        if samen and len(samen[-1]) == 1 and len(samen[-1][0]) <= 3 and not (kern and R._kaal(samen[-1][0]) == kern) \
                and not (kern and any(R._kaal(x) == kern for x in br)) and len(br) < 3:
            samen[-1] = samen[-1] + br
        else:
            samen.append(br)
    return [" ".join(b) for b in samen]


def _tekstbeeld(tekst, fontnaam, max_grootte, kleur, max_b=int(B * 0.86), regels_max=2, schaduw=False):
    """Tekst zo groot mogelijk binnen max_b breed en regels_max regels. Geeft een bijgesneden RGBA-beeld."""
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    g = max_grootte
    while True:
        f = R._font(fontnaam, g)
        regels = R._wrap(tekst, f, max_b, d)
        if (len(regels) <= regels_max and all(d.textlength(r, font=f) <= max_b for r in regels)) or g <= 30:
            break
        g -= 6
    lh = int(g * 1.08)
    w = int(max(d.textlength(r, font=f) for r in regels)) + 40
    im = Image.new("RGBA", (w, lh * len(regels) + 40), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    for i, r in enumerate(regels):
        x = (w - d.textlength(r, font=f)) / 2
        if schaduw:
            dd.text((x + 3, 20 + i * lh + 4), r, font=f, fill=(0, 0, 0, 110))
        dd.text((x, 20 + i * lh), r, font=f, fill=kleur)
    if schaduw:
        sch = im.split()[3].filter(ImageFilter.GaussianBlur(8))
        laag = Image.new("RGBA", im.size, (0, 0, 0, 0)); laag.putalpha(sch.point(lambda a: int(a * 0.5)))
        laag.alpha_composite(im); im = laag
    return im.crop(im.getbbox() or (0, 0, 2, 2))


def _plak(frame, im, cx, cy, schaal=1.0, alpha=1.0):
    if schaal != 1.0:
        im = im.resize((max(1, int(im.width * schaal)), max(1, int(im.height * schaal))), Image.BILINEAR)
    if alpha < 1.0:
        a = im.split()[3].point(lambda x: int(x * alpha)); im = im.copy(); im.putalpha(a)
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def _tijden(n, start, per, beats, minimaal=0.34):
    """Starttijden voor n brokjes vanaf 'start', ongeveer 'per' seconden uit elkaar, vastgeklikt op tellen als die er zijn."""
    uit, t = [], start
    for i in range(n):
        if beats and i:
            kand = [x for x in beats if t - 0.12 <= x <= t + 0.16 and x - uit[-1] >= minimaal]
            if kand:
                t = kand[0]
        uit.append(t)
        t += per[i] if isinstance(per, list) else per
    return uit + [t]


def _kleurset(post):
    kleur, accent = R._kleuren(post)
    st = R._kernstaat(post, kleur, accent)
    return kleur + (255,), tuple(st["kleur"][:3]) + (255,), accent + (255,)


def _vraag(post):
    """De vraag voor haak=vraag: de vraag-hook uit de tekstbank, anders de laatste regel van de caption als die een vraag is."""
    h = post.get("reel_vraag") or (post.get("bank_hooks") or {}).get("vraag") or ""
    if not h:
        laatste = (post.get("caption") or "").strip().split("\n")[-1]
        h = laatste if laatste.endswith("?") else ""
    return h


def maak_reel(post, pad, stijl="kinetisch", haak=None, fotos=None, tempo=1.0):
    """Maakt een reel in de nieuwe stijl. fotos: lijst met paden (voor stijl 'beeld'). Geeft het pad terug."""
    rnd = random.Random(post["id"])
    v = post["variabelen"]
    kern = R.kernwoord(post)
    kleur, kernkleur, accent = _kleurset(post)
    licht = sum(kleur[:3]) > 380
    brokken = _brokken(post["tekst"], kern)
    uitleg = (post.get("uitleg") or post.get("reel_uitleg") or post.get("bank_uitleg") or "").strip()
    vraag = _vraag(post) if haak == "vraag" else ""
    beats = R._beats(post["muziek_pad"], post.get("muziek_start", 0), 20) if post.get("muziek_pad") else []

    # ---------- tijdlijn ----------
    # tempo: 1.0 = rustig (standaard), hoger = sneller, lager = langzamer
    tr = 1.0 / max(0.5, min(2.0, tempo))
    t0 = 2.0 * tr if vraag else 0.0
    per = [tr * max(0.62, 0.27 * len(b.split()) + 0.34 + (0.45 if kern and kern in [R._kaal(w) for w in b.split()] else 0)) for b in brokken]
    vt = _tijden(len(brokken), t0 + 0.05, per, beats, minimaal=0.5 * tr)
    ref_t = vt[-1] + 0.25
    u_brok = []
    if uitleg:  # breek op leestekens, en lange stukken in tweeën
        for zin in [z.strip() for z in re.split(r"(?<=[,.;:!?])\s+", uitleg) if z.strip()]:
            ws = zin.split()
            if len(ws) <= 5:
                u_brok.append(zin)
            else:
                h = (len(ws) + 1) // 2; u_brok += [" ".join(ws[:h]), " ".join(ws[h:])]
    ut = _tijden(len(u_brok), ref_t + 1.3 * tr, [tr * max(0.75, 0.27 * len(b.split()) + 0.45) for b in u_brok], beats, minimaal=0.5 * tr) if u_brok else [ref_t + 1.3 * tr]
    eind_t = ut[-1] + 0.15
    duur = round(eind_t + 2.6 * tr, 2)

    # ---------- achtergrond ----------
    if stijl == "beeld" and fotos:
        delen = max(2, min(len(fotos), 3))
        grenzen = [t0] + [vt[len(brokken) * k // delen] for k in range(1, delen)] + [ref_t + 1.3 * tr, duur + 1]
        bgs = []
        for i, fp in enumerate((fotos * 3)[:delen + 1]):
            im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
            im = ImageOps.fit(im, (int(B * 1.18), int(H * 1.18)), centering=(0.5, 0.45))
            donker = Image.new("RGB", im.size, (6, 6, 10))
            bgs.append(Image.blend(im, donker, 0.42 if i < delen else 0.62))
        if vraag:
            bgs.insert(0, bgs[-1]); grenzen.insert(0, 0)
    else:
        basis = R._bg(post, int(B * 1.12), int(H * 1.12))
        bgs, grenzen = [basis], [0, duur + 1]

    def achtergrond(t):
        i = max(0, sum(1 for g in grenzen[1:] if t >= g))
        i = min(i, len(bgs) - 1)
        bg = bgs[i]
        if stijl == "beeld" and fotos:
            seg0 = grenzen[i]; seg1 = grenzen[i + 1] if i + 1 < len(grenzen) else duur
            p = (t - seg0) / max(0.3, seg1 - seg0)
            z = 1.0 + 0.10 * _ease(p * 1.2)  # snelle zoom bij elke cut
            w, h = int(B * 1.18 / z), int(H * 1.18 / z)
            dx = int((bg.width - w) * (0.5 + 0.25 * math.sin(i * 1.7)))
            dy = int((bg.height - h) * 0.5)
            return bg.crop((dx, dy, dx + w, dy + h)).resize((B, H), Image.BILINEAR).convert("RGBA")
        # rustig drijvende achtergrond
        p = t / duur
        dx = int((bg.width - B) * (0.5 + 0.45 * math.sin(p * math.pi * 0.9 - 0.4)))
        dy = int((bg.height - H) * (0.5 + 0.35 * math.cos(p * math.pi * 0.8)))
        return bg.crop((dx, dy, dx + B, dy + H)).convert("RGBA")

    # ---------- tekstbeelden vooraf ----------
    zwaar = "montserrat_zwaar"
    serif = v.get("lettertype", "playfair")
    schaduw = stijl == "beeld" or not licht and v.get("achtergrondbron") == "beeld"
    if stijl == "beeld":
        tekstkleur, kk = (250, 247, 240, 255), (255, 214, 140, 255)
    else:
        tekstkleur, kk = kleur, kernkleur
    brok_im = []
    for br in brokken:
        is_kern = kern and any(R._kaal(w) == kern for w in br.split())
        if stijl == "beeld":
            brok_im.append(_tekstbeeld(br, serif, 150 if is_kern else 118, kk if is_kern else tekstkleur, schaduw=True))
        else:
            brok_im.append(_tekstbeeld(br.upper() if is_kern else br, zwaar, 230 if is_kern else 160, kk if is_kern else tekstkleur,
                                       regels_max=2 if not is_kern else 1))
    ref_im = _tekstbeeld(post["ref"].upper(), "montserrat", 54, accent if stijl != "beeld" else kk, schaduw=schaduw)
    betekent_im = _tekstbeeld("BETEKENT:", "montserrat", 46, accent if stijl != "beeld" else kk, schaduw=schaduw)
    u_im = [_tekstbeeld(b, zwaar if stijl != "beeld" else serif, 112, tekstkleur, schaduw=schaduw) for b in u_brok]
    vraag_im = _tekstbeeld(vraag, zwaar, 170, tekstkleur, regels_max=3, schaduw=schaduw) if vraag else None
    merk_im = _tekstbeeld("BIBLEVERSE", "montserrat", 40, accent if stijl != "beeld" else kk, schaduw=schaduw)
    # eindbeeld: het hele vers klein, met het kernwoord in kleur
    eind = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    ed = ImageDraw.Draw(eind)
    f = R._font(serif, 64); regels = R._wrap(post["tekst"], f, int(B * 0.8), ed)
    while len(regels) * 82 > H * 0.42 and f.size > 40:
        f = R._font(serif, f.size - 4); regels = R._wrap(post["tekst"], f, int(B * 0.8), ed)
    lh = int(f.size * 1.3); y0 = int(H * 0.40) - lh * len(regels) // 2
    staat = R._kernstaat(post, tekstkleur[:3], kk[:3])
    for i, r in enumerate(regels):
        R._regel(ed, B // 2, y0 + i * lh, r, f, tekstkleur, kk, staat, False)
    if schaduw:
        sch = Image.new("RGBA", (B, H), (0, 0, 0, 0)); sch.putalpha(eind.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda a: int(a * 0.55)))
        sch.alpha_composite(eind); eind = sch

    # ---------- frames ----------
    cy = int(H * 0.47)
    n = int(duur * FPS)
    cover = None
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{B}x{H}", "-r", str(FPS), "-i", "-"]
    if post.get("muziek_pad"):
        cmd += ["-ss", str(post.get("muziek_start", 0)), "-t", str(duur), "-i", post["muziek_pad"],
                "-af", f"volume=0.85,afade=t=in:st=0:d=0.15,afade=t=out:st={duur - 0.8}:d=0.8", "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(duur), pad]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for k in range(n):
            t = k / FPS
            fr = achtergrond(t)
            # voortgangslijntje bovenaan (zin om af te kijken)
            ImageDraw.Draw(fr).rectangle([0, 0, int(B * t / duur), 7], fill=accent[:3] + (200,))
            if vraag and t < t0:
                s = 1.0 + 0.08 * (1 - _ease(t / 0.25))
                _plak(fr, vraag_im, B / 2, cy, s, _ease(t / 0.12))
            elif t < ref_t:
                i = max(0, sum(1 for x in vt[:-1] if t >= x) - 1)
                if t >= vt[0]:
                    dt_ = t - vt[i]
                    is_kern = kern and any(R._kaal(w) == kern for w in brokken[i].split())
                    s = 1.0 + (0.22 if is_kern else 0.12) * (1 - _ease(dt_ / (0.22 if is_kern else 0.16)))
                    _plak(fr, brok_im[i], B / 2, cy, s, _ease(dt_ / 0.08))
                    if is_kern and cover is None:
                        cover = int((vt[i] + 0.3) * 1000)
            elif t < ut[0] - 0.05 or not u_brok:
                if t < eind_t:
                    a = _ease((t - ref_t) / 0.15)
                    _plak(fr, ref_im, B / 2, cy - 10, 1.0 + 0.06 * (1 - a), a)
            if u_brok and ut[0] - 0.05 <= t < eind_t:
                _plak(fr, betekent_im, B / 2, cy - 190, 1.0, 1.0)
                i = max(0, sum(1 for x in ut[:-1] if t >= x) - 1)
                dt_ = t - ut[i]
                _plak(fr, u_im[i], B / 2, cy + 10, 1.0 + 0.1 * (1 - _ease(dt_ / 0.16)), _ease(dt_ / 0.08))
            if t >= eind_t:
                a = _ease((t - eind_t) / 0.35)
                e = eind.copy(); e.putalpha(e.split()[3].point(lambda x: int(x * a)))
                fr.alpha_composite(e)
                _plak(fr, ref_im, B / 2, int(H * 0.40) + lh * len(regels) // 2 + 70, 1.0, a)
            _plak(fr, merk_im, B / 2, H - 230, 1.0, 0.9)
            proc.stdin.write(fr.convert("RGB").tobytes())
    finally:
        proc.stdin.close(); proc.wait()
    post["cover_ms"] = cover or int((t0 + 1.0) * 1000)
    post["duur"] = duur
    return pad
