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


# =====================================================================
# Herkenbare situatie (nieuwe aanpak, 11 nov): echte video, het HELE vers in één keer in beeld.
# =====================================================================
PLAATSING = {"onder": 0.70, "midden": 0.47, "boven": 0.25}  # Joshua (11 nov): midden en boven, die worden getest


def _band(plaatsing):
    """Donkere laag achter de tekst, zodat witte tekst op elk videobeeld leesbaar is."""
    import numpy as np
    y = np.linspace(0, 1, H)[:, None]
    if plaatsing == "onder":
        a = np.clip((y - 0.42) / 0.40, 0, 1) ** 1.3 * 190
    elif plaatsing == "boven":
        a = np.clip((0.58 - y) / 0.40, 0, 1) ** 1.3 * 190
    else:
        a = 70 + 90 * np.exp(-((y - 0.47) / 0.22) ** 2)
    a = np.repeat(a, B, axis=1).astype("uint8")
    laag = Image.new("RGBA", (B, H), (8, 8, 12, 0))
    laag.putalpha(Image.fromarray(a, "L"))
    return laag


def _schaduw(im, r=10, sterkte=0.6):
    sch = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sch.putalpha(im.split()[3].filter(ImageFilter.GaussianBlur(r)).point(lambda a: int(a * sterkte)))
    sch.alpha_composite(im)
    return sch


def _tekstvlak(post, regels_spec, plaatsing):
    """regels_spec: lijst van (soort, tekst). soort: label | hook | vers | uitleg | ref | merk. Geeft een RGBA-beeld van het hele scherm."""
    v = post["variabelen"]
    serif = v.get("lettertype", "playfair")
    wit, goud = (250, 248, 242, 255), (255, 212, 140, 255)
    laag = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(laag)
    blokken = []
    for soort, tekst in regels_spec:
        if soort == "vers":
            g = 74
            while True:
                f = R._font(serif, g); rg = R._wrap(tekst, f, int(B * 0.82), d)
                if len(rg) * g * 1.3 <= H * 0.42 or g <= 40:
                    break
                g -= 4
            blokken.append(("vers", rg, f, int(g * 1.3)))
        elif soort in ("hook", "uitleg"):
            f = R._font("montserrat" if soort == "hook" else serif, 72 if soort == "hook" else 58)
            rg = R._wrap(tekst, f, int(B * 0.82), d)
            blokken.append((soort, rg, f, int(f.size * 1.3)))
        else:
            f = R._klein_font({"label": 30, "ref": 34, "merk": 26}[soort], b"SemiBold" if soort != "merk" else b"Medium")
            if soort == "ref":
                blokken.append(("ruimte", [""], f, 26))
            blokken.append((soort, [tekst], f, int(f.size * 1.9)))
    hoogte = sum(lh * len(rg) for _, rg, _, lh in blokken)
    y = int(H * PLAATSING[plaatsing] - hoogte / 2)
    staat = R._kernstaat(post, wit[:3], goud[:3])
    for soort, rg, f, lh in blokken:
        for r in rg:
            if soort == "vers":
                R._regel(d, B // 2, y, r, f, wit, goud, staat, False)
            elif soort == "ruimte":
                pass
            else:
                kl = goud if soort in ("label", "ref") else wit
                d.text((B // 2, y), r, font=f, fill=kl, anchor="ma")
            y += lh
    return _schaduw(laag)


def maak_situatie(post, pad, clips, plaatsing="onder"):
    """Reel 'herkenbare situatie': clip 1 met een herkenbare zin, dan een rustige clip met het hele vers,
    de uitleg en een eindbeeld. clips: 1 of 2 lokale mp4's. Geeft het pad terug."""
    import tempfile
    v = post["variabelen"]
    if not clips:
        raise RuntimeError("geen clips")
    a, b = clips[0], clips[-1]
    hook = (post.get("reel_herkenning") or post.get("verhaal_hook") or post.get("hook") or "").strip()
    uitleg = (post.get("uitleg") or post.get("reel_uitleg") or "").strip()
    t1 = 3.8 if hook else 0.0
    lees = max(5.5, min(11.0, len(post["tekst"]) / 13 + 2.0))
    t_uit = 4.8 if uitleg else 0.0
    t_eind = 2.4
    duur = round(t1 + lees + t_uit + t_eind, 2)
    tmp = tempfile.mkdtemp()
    band = _band(plaatsing)
    segs = []  # (png, start, duur)
    def png(naam, spec, extra_band=True):
        im = band.copy() if extra_band else Image.new("RGBA", (B, H), (0, 0, 0, 0))
        im.alpha_composite(_tekstvlak(post, spec, plaatsing))
        p = os.path.join(tmp, naam + ".png"); im.save(p); return p
    if hook:
        segs.append((png("hook", [("hook", hook)]), 0.0, t1))
    segs.append((png("vers", [("vers", post["tekst"]), ("ref", post["ref"].upper())]), t1, lees))
    if uitleg:
        segs.append((png("uitleg", [("label", "WAT BETEKENT DIT?"), ("uitleg", uitleg)]), t1 + lees, t_uit))
    eind = Image.new("RGBA", (B, H), (8, 8, 12, 150))
    eind.alpha_composite(_tekstvlak(post, [("ref", post["ref"].upper()), ("merk", "BIBLEVERSE  ·  @bibleverse_nl")], "midden"))
    pe = os.path.join(tmp, "eind.png"); eind.save(pe)
    segs.append((pe, t1 + lees + t_uit, t_eind))

    vul = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,eq=saturation=0.92:brightness=-0.03"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-stream_loop", "-1", "-t", str(max(t1, 0.5) + 0.5), "-i", a,
           "-stream_loop", "-1", "-t", str(duur - t1 + 0.6), "-i", b]
    for p, s, dd in segs:
        cmd += ["-loop", "1", "-t", str(dd), "-i", p]
    f = [f"[0:v]{vul},trim=0:{max(t1, 0.5)},setpts=PTS-STARTPTS[a]", f"[1:v]{vul},trim=0:{duur - t1 + 0.4},setpts=PTS-STARTPTS[b]"]
    if hook:
        f.append(f"[a][b]xfade=transition=fade:duration=0.45:offset={t1 - 0.45}[bg0]")
    else:
        f.append("[b]null[bg0]")
    vorig = "bg0"
    for i, (p, s, dd) in enumerate(segs):
        k = i + 2
        f.append(f"[{k}:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={max(0, dd - 0.3)}:d=0.3:alpha=1,setpts=PTS-STARTPTS+{s}/TB[t{i}]")
        f.append(f"[{vorig}][t{i}]overlay=eof_action=pass:format=auto[v{i}]")
        vorig = f"v{i}"
    f.append(f"[{vorig}]trim=0:{duur},setpts=PTS-STARTPTS,format=yuv420p[uit]")
    cmd += ["-filter_complex", ";".join(f), "-map", "[uit]"]
    if post.get("muziek_pad"):
        cmd += ["-ss", str(post.get("muziek_start", 0)), "-t", str(duur), "-i", post["muziek_pad"]]
        cmd[cmd.index("-filter_complex") + 1] += f";[{len(segs) + 2}:a]volume=0.85,afade=t=in:st=0:d=0.3,afade=t=out:st={duur - 1.2}:d=1.2[au]"
        cmd += ["-map", "[au]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart", "-t", str(duur), pad]
    # ffmpeg wil alle -i vóór -filter_complex: zet de muziekinput naar voren
    if post.get("muziek_pad"):
        i_m = cmd.index(post["muziek_pad"])
        muz = cmd[i_m - 5:i_m + 1]
        del cmd[i_m - 5:i_m + 1]
        i_f = cmd.index("-filter_complex")
        cmd[i_f:i_f] = muz
    subprocess.run(cmd, check=True)
    post["cover_ms"] = int((t1 + 1.5) * 1000)
    post["duur"] = duur
    return pad



def _streep(d, x0, x1, yc, h, kleur, seed):
    """Markeerstreep met licht scheve, ruwe uiteinden, tot x1."""
    rnd = random.Random(seed)
    j = lambda: rnd.uniform(-5, 5)
    d.polygon([(x0 - 6 + j(), yc - h / 2 + j()), (x1 + 4 + j(), yc - h / 2 + 3 + j()),
               (x1 + 10 + j(), yc + h / 2 + j()), (x0 - 10 + j(), yc + h / 2 - 3 + j())], fill=kleur)


def _achtergrond():
    """Lichte ochtendkleur: crème bovenin naar zacht abrikoos onderin, met een zachte gloed."""
    import numpy as np
    y, x = np.mgrid[0:H, 0:B]
    s = (y / H)[:, :, None]
    boven, onder = np.array([253, 248, 238], float), np.array([250, 228, 205], float)
    a = boven * (1 - s) + onder * s
    gloed = np.exp(-(((x - B * 0.5) / (B * 0.7)) ** 2 + ((y - H * 0.3) / (H * 0.35)) ** 2))[:, :, None]
    a = a + gloed * np.array([4, 3, 0], float)
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def maak_markeren(post, pad):
    """Reel 'meelezen': het vers verschijnt in lichtgrijs en wordt woord voor woord donker, met een zachte kleurvlek
    die onder het woord meeschuift. Rustig tempo (ongeveer 2 woorden per seconde), kernwoord vet en in kleur."""
    import numpy as np
    v = post["variabelen"]
    serif = v.get("lettertype", "playfair")
    inkt, dim, accent = (44, 36, 32, 255), (44, 36, 32, 70), (178, 88, 48, 255)
    strook = (240, 205, 150, 175)
    hook = (post.get("reel_herkenning") or "").strip()
    uitleg = (post.get("uitleg") or post.get("reel_uitleg") or "").strip()
    bg = _achtergrond()
    meet = ImageDraw.Draw(Image.new("RGBA", (B, 10)))
    g = 80
    while True:
        f = R._font(serif, g); rg = R._wrap(post["tekst"], f, int(B * 0.80), meet)
        if len(rg) * g * 1.5 <= H * 0.46 or g <= 44:
            break
        g -= 4
    lh = int(g * 1.5)
    y0 = int(H * 0.40 - len(rg) * lh / 2)
    fv, rand = R._vet(f)
    kern = R._kernstaat(post, inkt[:3], accent[:3]).get("kern")
    kern_klaar = False
    woorden = []  # (tekst, x0, x1, y, is_kern)
    for i, r in enumerate(rg):
        ws = r.split(" ")
        breed, is_k = [], []
        for w in ws:
            k = bool(kern) and not kern_klaar and R._kaal(w) == kern
            if k:
                kern_klaar = True
            is_k.append(k)
            breed.append(meet.textlength(w, font=fv if k else f) + (2 * rand if k else 0))
        spatie = meet.textlength(" ", font=f)
        tot = sum(breed) + spatie * (len(ws) - 1)
        x = B / 2 - tot / 2
        for w, bw, k in zip(ws, breed, is_k):
            woorden.append((w, x, x + bw, y0 + i * lh, k)); x += bw + spatie
    def laag(kleur, kernkleur):
        im = Image.new("RGBA", (B, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for w, xa, xb, yy, k in woorden:
            if k:
                m = re_m.match(w); 
                d.text((xa + rand, yy), w, font=fv, fill=kernkleur, anchor="la", stroke_width=rand, stroke_fill=kernkleur)
            else:
                d.text((xa, yy), w, font=f, fill=kleur, anchor="la")
        return im
    import re as _re
    re_m = _re.compile(r"^(\W*)(.*?)(\W*)$")
    ink_l = laag(inkt, accent)
    ref = Image.new("RGBA", (B, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(ref)
    yb = y0 + len(rg) * lh + 50
    dr.text((B // 2, yb), post["ref"].upper(), font=R._klein_font(36, b"SemiBold"), fill=accent, anchor="ma")
    uit = Image.new("RGBA", (B, H), (0, 0, 0, 0)); du = ImageDraw.Draw(uit)
    if uitleg:
        fu = R._font(serif, 56); ru = R._wrap(uitleg, fu, int(B * 0.80), du)
        yu = int(H * 0.40 - len(ru) * 76 / 2)
        du.text((B // 2, yu - 90), "WAT BETEKENT DIT?", font=R._klein_font(32, b"SemiBold"), fill=accent, anchor="ma")
        for i, r in enumerate(ru):
            du.text((B // 2, yu + i * 76), r, font=fu, fill=inkt, anchor="ma")
    eind = Image.new("RGBA", (B, H), (0, 0, 0, 0)); de = ImageDraw.Draw(eind)
    de.text((B // 2, int(H * 0.40)), post["ref"].upper(), font=R._klein_font(44, b"SemiBold"), fill=accent, anchor="ma")
    de.text((B // 2, int(H * 0.40) + 90), "BIBLEVERSE  ·  @bibleverse_nl", font=R._klein_font(28, b"Medium"), fill=(100, 88, 80, 255), anchor="ma")
    hk = Image.new("RGBA", (B, H), (0, 0, 0, 0)); dh = ImageDraw.Draw(hk)
    if hook:
        fh = R._font(serif, 70); rh = R._wrap(hook, fh, int(B * 0.80), dh)
        for i, r in enumerate(rh):
            dh.text((B // 2, int(H * 0.40) - len(rh) * 46 + i * 92), r, font=fh, fill=inkt, anchor="ma")
    # tempo: ruim 2 woorden per seconde, extra rust bij leestekens
    tempo = 0.52
    starts, tt = [], 0.9
    for w, *_ in woorden:
        starts.append(tt)
        tt += tempo + (0.35 if w.rstrip()[-1:] in ",;:" else 0.55 if w.rstrip()[-1:] in ".!?" else 0) + 0.025 * max(0, len(w) - 6)
    lees = tt + 1.6
    # per regel: begin, eind en breedte van de streep (tijd volgt het leestempo)
    lijnen, wi = [], 0
    for i, r in enumerate(rg):
        n_w = len(r.split(" ")); ws_ = woorden[wi:wi + n_w]
        s0 = starts[wi]; s1 = starts[wi + n_w - 1] + tempo
        lijnen.append((ws_[0][1], ws_[-1][2], ws_[0][3] + g * 0.6, s0, s1)); wi += n_w
    t1 = 3.4 if hook else 0.0
    t_uit = max(5.5, len(uitleg) / 14) if uitleg else 0.0
    t_eind = 2.4
    duur = round(t1 + lees + t_uit + t_eind, 2)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{B}x{H}", "-r", str(FPS), "-i", "-"]
    if post.get("muziek_pad"):
        cmd += ["-ss", str(post.get("muziek_start", 0)), "-t", str(duur), "-i", post["muziek_pad"],
                "-af", f"volume=0.85,afade=t=in:st=0:d=0.3,afade=t=out:st={duur - 1.2}:d=1.2", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(duur), pad]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    def mix(basis, l, a):
        if a <= 0:
            return basis
        if a < 1:
            l = l.copy(); l.putalpha(l.split()[3].point(lambda x: int(x * a)))
        basis = basis.copy(); basis.alpha_composite(l); return basis
    def doos(i):
        w, xa, xb, yy, k = woorden[i]
        return (xa - 16, yy + g * 0.12, xb + 16, yy + g * 1.18)
    n = int(duur * FPS)
    for k in range(n):
        t = k / FPS
        fr = bg
        if t < t1:
            fr = mix(fr, hk, min(1, t / 0.4, (t1 - t) / 0.4 + 0.0001))
        elif t < t1 + lees + 0.3:
            tv = t - t1
            a = min(1, tv / 0.6) * (1.0 if t < t1 + lees else max(0, 1 - (t - t1 - lees) / 0.3))
            st = Image.new("RGBA", (B, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(st)
            for i, (xa, xb, yc, s0, s1) in enumerate(lijnen):
                p = max(0.0, min(1.0, (tv - s0) / max(0.3, s1 - s0)))  # gelijkmatig, op leestempo
                if p > 0:
                    _streep(ds, xa, xa + (xb - xa) * p, yc, g * 1.02, strook, 100 + i)
            laag_nu = Image.alpha_composite(st, ink_l)
            laag_nu.alpha_composite(ref)
            fr = mix(fr, laag_nu, a)
        elif t < t1 + lees + t_uit:
            tu = t - t1 - lees
            fr = mix(fr, uit, min(1, tu / 0.4, (t_uit - tu) / 0.3 + 0.0001))
        else:
            fr = mix(fr, eind, min(1, (t - t1 - lees - t_uit) / 0.4))
        pr.stdin.write(np.asarray(fr.convert("RGB")).tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg mislukt")
    post["cover_ms"] = int((t1 + lees * 0.6) * 1000)
    post["duur"] = duur
    return pad
