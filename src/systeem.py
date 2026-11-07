"""Bijbeltekst-systeem: kiezen, renderen, registreren, leren.

Commando's (vanuit de projectmap):
  python3 src/systeem.py kies [--datum JJJJ-MM-DD]     maakt de wachtrij voor een dag (versen + variabelen)
  python3 src/systeem.py render [--datum ...]          maakt beelden/video's nadat hooks en captions zijn ingevuld
  python3 src/systeem.py registreer ID PLATFORM METRICOOL_ID [URL]
  python3 src/systeem.py stats statsbestand.json       voegt statistieken toe aan posts
  python3 src/systeem.py leer                          werkt strategie.json bij en schrijft een weekrapport
  python3 src/systeem.py dashboard                     schrijft docs/data.json voor het dashboard
  python3 src/systeem.py check                         controleert of alles klopt
"""
import json, os, sys, random, math, datetime as dt, argparse, statistics, time
os.environ["TZ"] = "Europe/Amsterdam"  # alle datums en tijden in Nederlandse tijd
time.tzset()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
P = lambda *a: os.path.join(ROOT, *a)

def laad(pad, standaard=None):
    try:
        return json.load(open(P(pad), encoding="utf-8"))
    except FileNotFoundError:
        return standaard

def bewaar(pad, data):
    os.makedirs(os.path.dirname(P(pad)) or ".", exist_ok=True)
    tmp = P(pad) + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, P(pad))

# ---------- Variabelen die het systeem test ----------
# Vaste huisstijlen: één keuze bepaalt kleur, letter, layout en achtergrond samen.
# Zo test het systeem 3 opties in plaats van honderden combinaties en blijft het account herkenbaar.
HUISSTIJLEN = {
    "avond":  {"palet": "nacht", "lettertype": "playfair",  "layout": "citaat",   "achtergrond": "licht"},
    "zand":   {"palet": "zand",  "lettertype": "dmserif",   "layout": "centraal", "achtergrond": "verloop"},
    "salie":  {"palet": "salie", "lettertype": "cormorant", "layout": "kader",    "achtergrond": "effen"},
}

DIMENSIES = {
    "huisstijl": list(HUISSTIJLEN),
    "thema": ["troost", "moed", "liefde", "hoop", "vertrouwen", "wijsheid", "humor_herkenbaar",
              "dankbaarheid", "identiteit", "vrede_rust"],
    "hook_stijl": ["vraag", "herkenning", "uitdaging", "rustig", "geen"],
    "formaat": ["afbeelding", "video", "carrousel"],
    "uitleg_op_beeld": [True, False],
    "achtergrondbron": ["verloop", "beeld"],
    "tijdslot": ["07:30", "12:15", "17:45", "20:30", "22:00"],
}

# Startgewichten die afwijken van 1,0 (Joshua: vooral kleurverloop, foto's als aanvulling)
START_GEWICHT = {("achtergrondbron", "beeld"): 0.6}

def nieuwe_strategie():
    return {"versie": 1, "bijgewerkt": None,
            "gewichten": {d: {str(o): START_GEWICHT.get((d, str(o)), 1.0) for o in opts} for d, opts in DIMENSIES.items()},
            "metingen": {d: {str(o): 0 for o in opts} for d, opts in DIMENSIES.items()},
            "inzichten": []}

def _terug(d, s):
    """String uit json terug naar het juiste type."""
    for o in DIMENSIES[d]:
        if str(o) == s:
            return o
    return s

def vul_strategie_aan(strat):
    for d, opts in DIMENSIES.items():
        strat["gewichten"].setdefault(d, {})
        strat["metingen"].setdefault(d, {})
        for o in opts:
            strat["gewichten"][d].setdefault(str(o), START_GEWICHT.get((d, str(o)), 1.0))
            strat["metingen"][d].setdefault(str(o), 0)
    return strat

def kies_optie(dim, strat, verkenning, rnd, uitsluiten=()):
    opties = [o for o in DIMENSIES[dim] if o not in uitsluiten]
    if rnd.random() < verkenning:
        return rnd.choice(opties), "verkenning"
    g = strat["gewichten"].get(dim, {})
    gew = [max(0.05, g.get(str(o), 1.0)) ** 2 for o in opties]  # kwadraat: winnaars krijgen voorrang
    return rnd.choices(opties, weights=gew)[0], "strategie"

# ---------- Eigen materiaal (privé repo bibleverse-materiaal) ----------
def materiaal_map():
    return os.environ.get("BIBLEVERSE_MATERIAAL") or os.path.join(os.path.dirname(ROOT), "bibleverse-materiaal")

def materiaal(cfg):
    """Lijsten met bestandsnamen (relatief aan de materiaalmap). Leeg als de map ontbreekt."""
    m = materiaal_map()
    if not os.path.isdir(m):
        return {"beelden": [], "muziek": [], "geluid": []}
    alle = []
    for root, _, files in os.walk(m):
        if ".git" in root:
            continue
        for f in files:
            alle.append(os.path.relpath(os.path.join(root, f), m))
    overslaan = set(cfg.get("beelden_overslaan", []))
    beelden = sorted(f for f in alle if f.lower().endswith((".jpg", ".jpeg", ".png")) and os.path.basename(f) not in overslaan)
    mp3 = sorted(f for f in alle if f.lower().endswith(".mp3"))
    geluid = [f for f in mp3 if os.path.basename(f).startswith(("ES_Ambience", "ES_Water"))]
    december = dt.date.today().month == 12
    muziek = [f for f in mp3 if f not in geluid and (december or "christmas" not in f.lower())]
    return {"beelden": beelden, "muziek": muziek, "geluid": geluid}

def minst_gebruikt(opties, posts, veld, rnd):
    """Kies de optie die het langst niet gebruikt is (nooit gebruikt eerst), met toeval bij gelijkspel."""
    laatst = {}
    for p in posts:
        if p.get(veld):
            laatst[p[veld]] = max(laatst.get(p[veld], ""), p["datum"])
    opties = list(opties); rnd.shuffle(opties)
    return min(opties, key=lambda o: laatst.get(o, "")) if opties else None

# ---------- Kiezen ----------
def cmd_kies(datum):
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    if cfg["pauze"]:
        print("PAUZE staat aan in config.json. Niets gepland."); return
    verzen = laad("data/verzen.json")
    posts = laad("data/posts.json", [])
    rnd = random.Random(f"{datum}-{len(posts)}")
    grens = (dt.date.fromisoformat(datum) - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {p["vers_id"] for p in posts if p["datum"] >= grens}
    al_vandaag = [p for p in posts if p["datum"] == datum]
    n = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"]) - len(al_vandaag)
    if n <= 0:
        print("Voor", datum, "zijn al genoeg posts gepland."); return
    gebruikte_slots = {p["variabelen"]["tijdslot"] for p in al_vandaag}
    mat = materiaal(cfg)
    nieuw = []
    for i in range(n):
        v, bron = {}, {}
        for dim in DIMENSIES:
            uit = gebruikte_slots if dim == "tijdslot" else ()
            v[dim], bron[dim] = kies_optie(dim, strat, cfg["verkenning"], rnd, uit)
        gebruikte_slots.add(v["tijdslot"])
        v.update(HUISSTIJLEN[v["huisstijl"]])
        v["hook_op_beeld"] = False  # Joshua wil geen hooktekst op het beeld
        # Foto-achtergrond alleen als er beelden zijn en het maximumaandeel niet bereikt is
        if v["achtergrondbron"] == "beeld":
            grens14 = (dt.date.fromisoformat(datum) - dt.timedelta(days=14)).isoformat()
            recent14 = [p for p in posts + nieuw if p["datum"] >= grens14]
            aandeel = sum(1 for p in recent14 if p["variabelen"].get("achtergrondbron") == "beeld") / max(1, len(recent14))
            if not mat["beelden"] or aandeel >= cfg.get("max_aandeel_beeld", 0.33):
                v["achtergrondbron"], bron["achtergrondbron"] = "verloop", "limiet"
        kandidaten = [x for x in verzen if x["thema"] == v["thema"] and x["id"] not in recent]
        if not kandidaten:
            kandidaten = [x for x in verzen if x["id"] not in recent] or verzen
        vers = rnd.choice(kandidaten)
        v["thema"] = vers["thema"]
        recent.add(vers["id"])
        pid = f"{datum}-{len(al_vandaag) + i + 1}"
        nieuw.append({"id": pid, "datum": datum, "status": "wacht_op_tekst",
                      "vers_id": vers["id"], "ref": vers["ref"], "tekst": vers["tekst"],
                      "variabelen": v, "keuzebron": bron,
                      "hook": "", "beeld_hook": "", "caption": "", "hashtags": [],
                      "uitleg": "", "betekenis": "", "toepassing": "",
                      "media": None, "media_url": None, "metricool": {}, "stats": {},
                      "beeld": minst_gebruikt(mat["beelden"], posts + nieuw, "beeld", rnd) if v["achtergrondbron"] == "beeld" else None,
                      "muziek": minst_gebruikt(mat["muziek"], posts + nieuw, "muziek", rnd) if v["formaat"] == "video" else None,
                      "geluid": (rnd.choice(mat["geluid"]) if mat["geluid"] and v["formaat"] == "video" and v["achtergrondbron"] == "beeld" else None)})
    bewaar("data/posts.json", posts + nieuw)
    print(json.dumps([{k: p[k] for k in ("id", "ref", "tekst", "variabelen")} for p in nieuw], ensure_ascii=False, indent=1))
    print("\nVul nu per post in data/posts.json in: 'hook', 'caption', 'hashtags'; 'uitleg' als uitleg_op_beeld true is; 'betekenis' en 'toepassing' bij formaat carrousel. Zie TAKEN.md.")

# ---------- Renderen ----------
def cmd_render(datum):
    from render import maak_afbeelding, maak_video, maak_carrousel
    cfg = laad("config.json")
    posts = laad("data/posts.json", [])
    fouten = 0
    for p in posts:
        if p["datum"] != datum or p["status"] not in ("wacht_op_tekst", "klaar_voor_render"):
            continue
        probleem = valideer_tekst(p, cfg)
        if probleem:
            print("NIET GERENDERD", p["id"], probleem); fouten += 1; continue
        p["handle"] = cfg.get("handle", "")
        koppel_materiaal(p)
        fmt = p["variabelen"]["formaat"]
        ext = "mp4" if fmt == "video" else "jpg"
        rel = f"docs/media/{datum[:7]}/{p['id']}.{ext}"
        os.makedirs(os.path.dirname(P(rel)), exist_ok=True)
        if fmt == "carrousel":
            paden = maak_carrousel(p, P(rel))
            rels = [os.path.relpath(x, ROOT) for x in paden]
            p["media"], p["media_extra"] = rels[0], rels[1:]
        else:
            (maak_video if ext == "mp4" else maak_afbeelding)(p, P(rel))
            p["media"], p["media_extra"] = rel, []
        p["thumb"] = maak_thumb(P(p["media"]), p["id"])
        for k in ("beeld_pad", "muziek_pad", "geluid_pad"):
            p.pop(k, None)
        if cfg.get("github_repo"):
            eig, naam = cfg["github_repo"].split("/")
            url = lambda r: f"https://{eig}.github.io/{naam}/{r[len('docs/'):]}"
            p["media_url"] = url(p["media"])
            p["media_urls"] = [url(r) for r in [p["media"]] + p["media_extra"]]
        p["status"] = "gerenderd"
        print("OK", p["id"], rel)
    bewaar("data/posts.json", posts)
    if fouten:
        sys.exit(1)

def maak_thumb(bron, pid):
    """Kleine voorvertoning (216 px breed) die blijft bestaan als de media later wordt opgeruimd."""
    import subprocess
    rel = f"docs/thumbs/{pid}.jpg"
    os.makedirs(P("docs/thumbs"), exist_ok=True)
    if bron.endswith(".mp4"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "4", "-i", bron, "-frames:v", "1",
                        "-vf", "scale=216:-2", "-q:v", "4", P(rel)], check=True)
    else:
        from PIL import Image
        im = Image.open(bron); im.thumbnail((216, 400)); im.save(P(rel), quality=80)
    return rel[len("docs/"):]

def cmd_opruimen(dagen=30):
    """Verwijdert media van posts die langer dan `dagen` geleden online gingen; de thumb blijft."""
    posts = laad("data/posts.json", [])
    grens = (dt.date.today() - dt.timedelta(days=int(dagen))).isoformat()
    weg = 0
    for p in posts:
        if p.get("status") in ("gepubliceerd", "overgeslagen", "fout", "afgekeurd") and p["datum"] < grens and p.get("media"):
            if os.path.exists(P(p["media"])):
                if not p.get("thumb"):
                    p["thumb"] = maak_thumb(P(p["media"]), p["id"])
                os.remove(P(p["media"])); weg += 1
            for extra in p.get("media_extra", []) or []:
                if os.path.exists(P(extra)):
                    os.remove(P(extra))
            p["media"], p["media_extra"] = None, []
    bewaar("data/posts.json", posts)
    if weg:
        cmd_log(f"Opgeruimd: media van {weg} oude posts verwijderd (voorvertoning bewaard)")
    print(weg, "bestanden opgeruimd")

def koppel_materiaal(p):
    """Zet tijdelijke paden naar foto/muziek; valt terug op verloop/stilte als het materiaal ontbreekt."""
    import subprocess, random as _r
    m = materiaal_map()
    if p.get("beeld"):
        pad = os.path.join(m, p["beeld"])
        if os.path.exists(pad):
            p["beeld_pad"] = pad
        else:
            p["variabelen"]["achtergrondbron"] = "verloop"; p["beeld"] = None
            cmd_log(f"{p['id']}: foto niet gevonden (is bibleverse-materiaal gecloned?), verloop gebruikt", "fout")
    if p.get("muziek"):
        pad = os.path.join(m, p["muziek"])
        if os.path.exists(pad):
            p["muziek_pad"] = pad
            try:
                duur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", pad],
                                            capture_output=True, text=True).stdout.strip())
            except ValueError:
                duur = 30
            p["muziek_start"] = round(_r.Random(p["id"]).uniform(min(8, duur * 0.1), max(min(8, duur * 0.1), min(60, duur - 12))), 1)
        else:
            p["muziek"] = None
            cmd_log(f"{p['id']}: muziek niet gevonden, video zonder muziek", "fout")
    if p.get("geluid") and os.path.exists(os.path.join(m, p["geluid"])):
        p["geluid_pad"] = os.path.join(m, p["geluid"])

VERBODEN = ["link in bio", "volg voor meer", "deel dit met 10", "amen als", "typ amen", "zegen als je"]

def valideer_tekst(p, cfg):
    if not p["caption"].strip():
        return "caption ontbreekt"
    if p["variabelen"]["hook_stijl"] != "geen" and not p["hook"].strip():
        return "hook ontbreekt"
    if p["variabelen"]["hook_op_beeld"] and len(p.get("beeld_hook", "")) > 42:
        return "beeld_hook te lang (max 42 tekens)"
    if p["variabelen"]["hook_op_beeld"] and not p.get("beeld_hook", "").strip():
        p["variabelen"]["hook_op_beeld"] = False  # geen beeldhook: dan ook niet tonen
    if p["variabelen"].get("uitleg_op_beeld") and not (0 < len(p.get("uitleg", "")) <= 110):
        return "uitleg ontbreekt of is langer dan 110 tekens"
    if p["variabelen"]["formaat"] == "carrousel":
        for veld in ("betekenis", "toepassing"):
            if not (20 <= len(p.get(veld, "")) <= 320):
                return f"{veld} ontbreekt of heeft niet 20 tot 320 tekens"
    for veld in ("uitleg", "betekenis", "toepassing"):
        if "\u2014" in p.get(veld, ""):
            return "gebruik geen lange streep"
    if len(p["hashtags"]) > cfg["hashtags_max"]:
        return "te veel hashtags"
    laag = p["caption"].lower()
    for v in VERBODEN:
        if v in laag:
            return f"engagement-bait in caption ('{v}')"
    if "—" in p["caption"] or "—" in p["hook"]:
        return "gebruik geen lange streep"
    if p["tekst"][:40] not in p["caption"]:
        return "caption moet de verstekst letterlijk bevatten"
    return None

# ---------- Registreren ----------
def cmd_registreer(pid, platform, mid, url=None):
    posts = laad("data/posts.json", [])
    for p in posts:
        if p["id"] == pid:
            p["metricool"][platform] = {"id": mid, "url": url, "gepland": dt.datetime.now().isoformat(timespec="minutes")}
            p["status"] = "gepland"
            bewaar("data/posts.json", posts); print("OK"); return
    sys.exit(f"Post {pid} niet gevonden")

# ---------- Statistieken ----------
def cmd_stats(pad):
    """Bestand: lijst van {post_id, platform, moment: '24u'|'7d', views, reach, likes, comments, shares, saves}."""
    rij = json.load(open(pad, encoding="utf-8"))
    posts = {p["id"]: p for p in laad("data/posts.json", [])}
    n = 0
    for r in rij:
        p = posts.get(r["post_id"])
        if not p:
            print("onbekend:", r["post_id"]); continue
        p["stats"].setdefault(r["platform"], {})[r.get("moment", "7d")] = {
            k: r.get(k) for k in ("views", "reach", "likes", "comments", "shares", "saves", "follows")}
        if p["status"] == "gepland":
            p["status"] = "gepubliceerd"
        n += 1
    bewaar("data/posts.json", list(posts.values()))
    print(n, "metingen opgeslagen")

def interactie(s):
    g = lambda k: s.get(k) or 0
    return g("likes") + 3 * g("comments") + 4 * g("shares") + 4 * g("saves") + 8 * g("follows")

def post_scores(posts):
    """Relatieve score per post per platform: (interactie/bereik) gedeeld door de mediaan van dat platform.
    1.0 = gemiddeld, 2.0 = twee keer zo goed. Zo zijn platformen met veel en weinig bereik vergelijkbaar."""
    per_platform = {}
    for p in posts:
        for plat, mom in p.get("stats", {}).items():
            s = mom.get("7d") or mom.get("24u")
            if not s:
                continue
            bereik = s.get("reach") or s.get("views") or 0
            if bereik < 20:
                continue
            ratio = interactie(s) / bereik
            per_platform.setdefault(plat, []).append((p, ratio, bereik))
    uit = []
    for plat, rijen in per_platform.items():
        bereiken = [b for _, _, b in rijen]
        med_r = statistics.median([r for _, r, _ in rijen]) or 1e-6
        med_b = statistics.median(bereiken) or 1
        for p, r, b in rijen:
            # Mix: 70% interactie-kwaliteit, 30% bereik (algoritme vond het goed)
            score = 0.7 * (r / med_r) + 0.3 * (b / med_b)
            # Uitschieters dempen: boven 1,5 telt de rest maar half mee, en maximaal 3
            if score > 1.5:
                score = 1.5 + (score - 1.5) * 0.5
            uit.append((p, plat, min(score, 3.0)))
    return uit

# ---------- Leren ----------
def cmd_leer():
    cfg = laad("config.json")
    strat = vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    scores = post_scores(posts)
    vandaag = dt.date.today().isoformat()
    if len({p["id"] for p, _, _ in scores}) < cfg["min_posts_voor_leren"]:
        print("Nog te weinig gemeten posts om te leren:", len(scores)); return
    K = 4  # demping: een optie met weinig metingen blijft dicht bij 1.0
    max_stap = cfg["max_gewicht_verschuiving_per_week"]
    rapport = {"datum": vandaag, "aantal_metingen": len(scores), "dimensies": {}}
    for dim in DIMENSIES:
        per = {}
        for p, plat, s in scores:
            per.setdefault(str(p["variabelen"].get(dim)), []).append(s)
        regel = {}
        for o in DIMENSIES[dim]:
            vals = per.get(str(o), [])
            doel = (sum(vals) + K * 1.0) / (len(vals) + K)
            oud = strat["gewichten"][dim].get(str(o), 1.0)
            nieuw = oud + max(-max_stap, min(max_stap, doel - oud))
            strat["gewichten"][dim][str(o)] = round(max(0.3, min(2.5, nieuw)), 3)
            strat["metingen"][dim][str(o)] = len(vals)
            regel[str(o)] = {"n": len(vals), "gem": round(statistics.mean(vals), 2) if vals else None,
                             "oud": oud, "nieuw": strat["gewichten"][dim][str(o)]}
        rapport["dimensies"][dim] = regel
    strat["bijgewerkt"] = vandaag
    strat["versie"] += 1
    bewaar("strategie.json", strat)
    hist = laad("data/leergeschiedenis.json", [])
    hist.append({"datum": vandaag, "versie": strat["versie"], "gewichten": strat["gewichten"]})
    bewaar("data/leergeschiedenis.json", hist)
    bewaar(f"rapporten/{vandaag}.json", rapport)
    for dim, r in rapport["dimensies"].items():
        top = sorted(r.items(), key=lambda x: -x[1]["nieuw"])[:2]
        print(f"{dim:14s} beste: " + ", ".join(f"{k} ({v['nieuw']}, n={v['n']})" for k, v in top))

# ---------- Dashboard-data ----------
def cmd_dashboard():
    cfg, strat = laad("config.json"), laad("strategie.json") or nieuwe_strategie()
    posts = laad("data/posts.json", [])
    sc = {}
    for p, plat, s in post_scores(posts):
        sc.setdefault(p["id"], {})[plat] = round(s, 2)
    lijst = []
    for p in sorted(posts, key=lambda x: x["id"], reverse=True)[:300]:
        tot = {}
        for plat, mom in p.get("stats", {}).items():
            s = mom.get("7d") or mom.get("24u") or {}
            for k in ("views", "reach", "likes", "comments", "shares", "saves"):
                tot[k] = tot.get(k, 0) + (s.get(k) or 0)
        lijst.append({"id": p["id"], "datum": p["datum"], "ref": p["ref"], "tekst": p["tekst"], "hook": p.get("hook", ""),
                      "status": p["status"], "variabelen": p["variabelen"], "media": p.get("media"), "media_url": p.get("media_url"), "thumb": p.get("thumb"),
                      "platformen": list(p.get("gepubliceerd", {}).keys()),
                      "links": {k: v.get("url") for k, v in p.get("gepubliceerd", {}).items()}, "totaal": tot, "score": sc.get(p["id"], {})})
    rapporten = sorted(os.listdir(P("rapporten"))) if os.path.isdir(P("rapporten")) else []
    data = {"gegenereerd": dt.datetime.now().isoformat(timespec="minutes"), "repo": cfg.get("github_repo", ""),
            "config": {k: cfg.get(k) for k in ("pauze", "kanaalnaam", "posts_per_dag", "verkenning", "platformen_actief")},
            "strategie": strat, "posts": lijst,
            "leergeschiedenis": laad("data/leergeschiedenis.json", []),
            "laatste_rapport": laad(f"rapporten/{rapporten[-1]}") if rapporten else None,
            "logboek": laad("data/logboek.json", [])[-60:],
            "recente_fouten": [l for l in laad("data/logboek.json", [])
                               if l.get("soort") == "fout" and l["t"] >= (dt.datetime.now() - dt.timedelta(hours=48)).isoformat(timespec="minutes")],
            "versen_totaal": len(laad("data/verzen.json", []))}
    bewaar("docs/data.json", data)
    print("docs/data.json bijgewerkt:", len(lijst), "posts")

def cmd_log(tekst, soort="info"):
    log = laad("data/logboek.json", [])
    log.append({"t": dt.datetime.now().isoformat(timespec="minutes"), "soort": soort, "tekst": tekst})
    bewaar("data/logboek.json", log[-500:])

def cmd_vers(thema, boek, h, v1, v2=None):
    """Voegt een vers toe vanuit de Statenvertaling-bron, bv: vers hoop "Psalms" 27 14"""
    sys.path.insert(0, P("tools"))
    import csv
    from bouw_verzen import schoon, NL
    if thema not in DIMENSIES["thema"]:
        sys.exit(f"Onbekend thema {thema}")
    if boek not in NL:
        sys.exit(f"Boeknaam {boek} niet in de lijst; gebruik de Engelse naam uit data/DutSVV.csv en voeg hem toe aan NL in tools/bouw_verzen.py")
    h, v1 = int(h), int(v1); v2 = int(v2 or v1)
    rijen = {(r["Book"], int(r["Chapter"]), int(r["Verse"])): r["Text"] for r in csv.DictReader(open(P("data/DutSVV.csv"), encoding="utf-8")) if r["Book"] == boek}
    delen = [rijen.get((boek, h, v)) for v in range(v1, v2 + 1)]
    if None in delen:
        sys.exit("Vers niet gevonden")
    t = schoon(" ".join(delen))
    if len(t) > 260:
        sys.exit(f"Te lang ({len(t)} tekens)")
    verzen = laad("data/verzen.json")
    vid = f"{boek}-{h}-{v1}-{v2}".replace(" ", "_")
    if any(x["id"] == vid for x in verzen):
        sys.exit("Staat er al in")
    ref = f"{NL[boek]} {h}:{v1}" + (f"-{v2}" if v2 != v1 else "")
    verzen.append({"id": vid, "ref": ref, "tekst": t, "thema": thema, "lengte": len(t)})
    bewaar("data/verzen.json", verzen)
    print("Toegevoegd:", ref, "|", t)

def cmd_check():
    cfg = laad("config.json"); verzen = laad("data/verzen.json")
    ok = True
    for k in ("github_repo", "handle"):
        if not cfg.get(k):
            print("ONTBREEKT in config:", k); ok = False
    print(len(verzen), "versen;", "pauze:", cfg["pauze"])
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("cmd"); a.add_argument("args", nargs="*")
    a.add_argument("--datum", default=dt.date.today().isoformat())
    x = a.parse_args()
    {"kies": lambda: cmd_kies(x.datum), "render": lambda: cmd_render(x.datum),
     "registreer": lambda: cmd_registreer(*x.args), "stats": lambda: cmd_stats(x.args[0]),
     "leer": cmd_leer, "dashboard": cmd_dashboard, "check": cmd_check,
     "log": lambda: cmd_log(*x.args), "vers": lambda: cmd_vers(*x.args), "opruimen": lambda: cmd_opruimen(*x.args)}[x.cmd]()
