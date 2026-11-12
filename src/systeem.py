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
import json, os, sys, random, subprocess, math, datetime as dt, argparse, statistics, time
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
    # Frisse stijlen (naar de voorbeelddesigns)
    "zonsopgang":  {"palet": "zonsopgang_fris", "lettertype": "lora",              "layout": "links",    "achtergrond": "diagonaal"},
    "hemelsblauw": {"palet": "hemelsblauw",     "lettertype": "montserrat_zwaar",  "layout": "links",    "achtergrond": "diagonaal"},
    "paars":       {"palet": "diep_paars",      "lettertype": "lora",              "layout": "links",    "achtergrond": "radiaal"},
    "roze":        {"palet": "zachtroze",       "lettertype": "cormorant_cursief", "layout": "links",    "achtergrond": "diagonaal"},
    "bosgroen":    {"palet": "bosgroen",        "lettertype": "montserrat_zwaar",  "layout": "links",    "achtergrond": "diagonaal"},
    "mint":        {"palet": "mint",            "lettertype": "dmserif",           "layout": "centraal", "achtergrond": "diagonaal"},
    "perzik":      {"palet": "perzik",          "lettertype": "playfair",          "layout": "citaat",   "achtergrond": "diagonaal"},
}

LICHTE_STIJLEN = ("zonsopgang", "hemelsblauw", "mint", "perzik", "roze", "zand")

DIMENSIES = {
    "huisstijl": list(HUISSTIJLEN),
    "thema": ["troost", "moed", "liefde", "hoop", "vertrouwen", "wijsheid", "humor_herkenbaar",
              "dankbaarheid", "identiteit", "vrede_rust"],
    "hook_stijl": ["vraag", "herkenning", "uitdaging", "rustig", "geen"],
    "formaat": ["video", "carrousel"],  # Joshua: een beeldpost is altijd een carrousel met uitleg
    "uitleg_op_beeld": [True, False],
    "achtergrondbron": ["verloop", "beeld"],
    "boekgroep": ["psalmen", "spreuken", "wijsheid", "profeten", "evangelien", "brieven"],
    "lengte": ["kort", "middel", "lang"],
    "bron": ["bekend", "ontdekking"],
    "vraag_onderaan": [True, False],
    "reel_stijl": ["klassiek", "kinetisch", "beeld", "situatie", "markeren"],  # alleen video; 'situatie' is sinds 11 nov de standaard (config reel_formaat)
    "carrousel_stijl": ["standaard", "markeren"],  # alleen carrousel; 'markeren' = meelees-stijl met markeerstreep (Joshua, 12 nov)
    "reel_kleur": ["abrikoos", "mint", "hemel", "roze", "goud"],  # meelees-reel: kleur en lettertype (Joshua, 12 nov: varianten)
    "reel_plaatsing": ["midden", "boven"],  # situatie-reel: waar de tekst staat (Joshua, 11 nov: deze twee testen)
    "reel_scene": ["natuur", "dichtbij", "onderweg"],  # situatie-reel: soort rustig beeld onder het vers
    "reel_haak": ["geen", "vraag"],  # alleen video: eerst 1,4 s een grote vraag in beeld
    "opening": ["vers", "stopper", "verhaal"],  # carrousel: slide 1 het hele vers, een korte grote 'stopper', of eerst de uitleg als haak ('verhaal eerst')
    "hashtag_stijl": ["mix", "zoekwoord", "zonder"],  # mix = vaste tags uit de tekstbank; zoekwoord = kernwoord, boek en #bijbelvers
    "tijdslot": ["07:30", "12:15", "17:45", "20:30", "22:00"],
}

# Startgewichten die afwijken van 1,0 (Joshua: vooral kleurverloop, foto's als aanvulling)
START_GEWICHT = {("achtergrondbron", "beeld"): 0.6,
                 ("huisstijl", "avond"): 0.35}  # Joshua wil een frisse uitstraling: donker minder vaak

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

def kies_optie(dim, strat, verkenning, rnd, uitsluiten=(), ctx=None):
    """Kiest een optie. Met ctx (statistieken + experiment) via Thompson sampling:
    onderdelen in het weekexperiment worden actief getest, de rest volgt vooral wat al werkt."""
    opties = [o for o in DIMENSIES[dim] if o not in uitsluiten]
    if ctx is not None:
        factor = verkenning / 0.2  # schuif 'experimenteren' op het dashboard bepaalt hoe breed er gezocht wordt
        if ctx.get("leermodus") or dim in ctx["experiment"]:
            return thompson(dim, opties, ctx["stats"], rnd, factor), "experiment"
        return thompson(dim, opties, ctx["stats"], rnd, factor * 0.35), "strategie"
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
    uit = {"beelden": beelden, "muziek": muziek, "geluid": geluid}
    # Momentopname van de voorraad voor het dashboard (GitHub Actions ziet de privé map niet)
    lijst = {"beelden": beelden, "muziek": sorted(f for f in mp3 if f not in geluid), "geluid": geluid}
    if laad("data/materiaal_lijst.json", {}).get("lijst") != lijst:
        bewaar("data/materiaal_lijst.json", {"bijgewerkt": dt.date.today().isoformat(), "lijst": lijst})
    return uit

BRON = {"NBV21": "NBV21 \u00a9 Nederlands-Vlaams Bijbelgenootschap"}

GROEP_NL = {"Psalm": "psalmen", "Spreuken": "spreuken", "Prediker": "wijsheid", "Job": "wijsheid", "Hooglied": "wijsheid",
            "Mattheüs": "evangelien", "Markus": "evangelien", "Lukas": "evangelien", "Johannes": "evangelien"}
PROFETEN = {"Jesaja", "Jeremia", "Klaagliederen", "Ezechiël", "Daniël", "Hosea", "Joël", "Amos", "Jona", "Micha", "Nahum",
            "Habakuk", "Sefanja", "Haggaï", "Zacharia", "Maleachi"}
OT_VERHAAL = {"Genesis", "Exodus", "Deuteronomium", "Jozua", "Ruth", "1 Samuël", "2 Samuël", "1 Koningen", "2 Koningen",
              "1 Kronieken", "2 Kronieken", "Nehemia", "Numeri", "Leviticus"}

def boekgroep(ref):
    boek = ref.rsplit(" ", 1)[0]
    if boek in GROEP_NL:
        return GROEP_NL[boek]
    if boek in PROFETEN:
        return "profeten"
    if boek in OT_VERHAAL:
        return "wijsheid"  # de paar losse verhaalverzen tellen mee bij 'wijsheid' (overig OT)
    return "brieven"

def lengteklas(tekst):
    n = len(tekst)
    return "kort" if n < 90 else "middel" if n < 170 else "lang"

_ALLE = None
def alle_verzen():
    """Bekende verzen (handgekozen) + ontdekkingen uit de hele Bijbel + eventuele NBV21-verzen, met kenmerken."""
    global _ALLE
    if _ALLE is None:
        uit, gezien = [], set()
        for v in laad("data/verzen.json", []) + extra_verzen():
            v = dict(v, bron="bekend", kwaliteit=12, boekgroep=boekgroep(v["ref"]), lengte=lengteklas(v["tekst"]))
            uit.append(v); gezien.add(v["id"])
        for v in laad("data/bijbel_pool.json", []):
            if v["id"] not in gezien:
                uit.append(dict(v, bron="ontdekking", boekgroep=v["boekgroep"] if v["boekgroep"] != "verhaal" else "wijsheid"))
        _ALLE = uit
    return _ALLE

def toppers(posts):
    """Verzen die duidelijk beter scoorden; die mogen na 30 dagen al terugkomen."""
    sc = {}
    for p, plat, s in post_scores(posts):
        sc.setdefault(p["vers_id"], []).append(s)
    return {k for k, v in sc.items() if len(v) and sum(v) / len(v) >= 1.3}

def extra_verzen():
    """Verzen uit een moderne vertaling, aangeleverd in de privé repo (verzen_nbv21.csv: ref;tekst;thema)."""
    import csv
    pad = os.path.join(materiaal_map(), "verzen_nbv21.csv")
    if not os.path.exists(pad):
        return []
    uit = []
    with open(pad, encoding="utf-8-sig") as f:
        proef = f.read(2048); f.seek(0)
        sep = ";" if proef.count(";") >= proef.count(",") else ","
        for r in csv.DictReader(f, delimiter=sep):
            ref, tekst = (r.get("ref") or "").strip(), " ".join((r.get("tekst") or "").split())
            if not ref or not tekst or len(tekst) > 260:
                continue
            thema = (r.get("thema") or "").strip().lower().replace(" ", "_")
            if thema not in DIMENSIES["thema"]:
                thema = "hoop"
            uit.append({"id": "NBV21-" + ref.replace(" ", "_"), "ref": ref, "tekst": tekst, "thema": thema,
                        "lengte": len(tekst), "vertaling": "NBV21"})
    return uit

def minst_gebruikt(opties, posts, veld, rnd):
    """Kies de optie die het langst niet gebruikt is (nooit gebruikt eerst), met toeval bij gelijkspel."""
    laatst = {}
    for p in posts:
        if p.get(veld):
            laatst[p[veld]] = max(laatst.get(p[veld], ""), p["datum"])
    opties = list(opties); rnd.shuffle(opties)
    return min(opties, key=lambda o: laatst.get(o, "")) if opties else None

# ---------- Kiezen ----------
def reeks_voor(datum, posts):
    """Hoort er op deze dag een post uit een reeks (Advent, Kerst, maandag moed, zondag vers van de week)?"""
    d = dt.date.fromisoformat(datum)
    for r in laad("data/reeksen.json", {}).get("reeksen", []):
        if r.get("van") and not (r["van"] <= datum <= r.get("tot", r["van"])):
            continue
        if "weekdag" in r and d.weekday() != r["weekdag"]:
            continue
        uit = {"naam": r["naam"], "tijdslot": r["tijdslot"], "thema": r.get("thema"), "vers": None}
        if r.get("verzen"):
            i = (d - dt.date.fromisoformat(r["van"])).days
            uit["vers"] = dict(r["verzen"][i % len(r["verzen"])], bron="bekend", kwaliteit=12)
            uit["label"] = r["label"].replace("{n}", str(i + 1))
        else:
            uit["label"] = r["label"]
        if r.get("beste_van_de_week"):
            grens = (d - dt.timedelta(days=8)).isoformat()
            sc = {}
            for p, plat, s in post_scores(posts):
                if p["datum"] >= grens and not p.get("reeks"):
                    sc.setdefault(p["vers_id"], []).append(s)
            if sc:
                beste = max(sc, key=lambda k: sum(sc[k]) / len(sc[k]))
                v = next((x for x in alle_verzen() if x["id"] == beste), None)
                if v:
                    uit["vers"] = v
        for x in (uit["vers"],):
            if x:
                x.setdefault("boekgroep", boekgroep(x["ref"])); x.setdefault("lengte", lengteklas(x["tekst"])); x.setdefault("bron", "bekend")
        return uit
    return None

def _bank(cfg):
    """De tekstbank als het systeem zelfstandig werkt (config 'zelfstandig'), anders None."""
    if not cfg.get("zelfstandig"):
        return None
    import tekstbank
    return tekstbank.laad()

def _oudste_bankverzen(bank, posts, cfg, n=25):
    """Alle bankverzen zijn recent gebruikt: neem de verzen die het langst geleden zijn geplaatst."""
    laatst = {}
    for q in posts:
        laatst[q["vers_id"]] = max(laatst.get(q["vers_id"], ""), q["datum"])
    weg = set(cfg.get("verzen_uitsluiten", []))
    return sorted([x for x in alle_verzen() if x["id"] in bank and x["id"] not in weg], key=lambda x: laatst.get(x["id"], ""))[:n]

def bank_voorraad(cfg=None, posts=None):
    """Hoeveel bankverzen nog niet in de herhaalperiode zijn gebruikt, en voor hoeveel dagen dat genoeg is."""
    import tekstbank
    cfg = cfg or laad("config.json"); posts = posts if posts is not None else laad("data/posts.json", [])
    bank = tekstbank.laad()
    grens = (dt.date.today() - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {p["vers_id"] for p in posts if p["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    vrij = len([k for k in bank if k not in recent])
    per_dag = max(1, min(cfg["posts_per_dag"], cfg["max_posts_per_dag"]))
    return {"verzen": len(bank), "vrij": vrij, "dagen": vrij // per_dag}

def kies_posts(datum, cfg, strat, posts, verzen, mat, n_start, n, gebruikte_slots, rnd, reeks=True):
    """Kiest n nieuwe posts voor een datum. Raakt geen bestanden aan."""
    grens = (dt.date.fromisoformat(datum) - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {p["vers_id"] for p in posts if p["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    recent |= {k for k, tot in cfg.get("verzen_later", {}).items() if tot >= datum}  # 'ander vers' op het dashboard
    # Toppers mogen na 30 dagen al terug
    grens30 = (dt.date.fromisoformat(datum) - dt.timedelta(days=30)).isoformat()
    top = toppers(posts)
    recent -= {p["vers_id"] for p in posts if p["vers_id"] in top and p["datum"] < grens30
               and not any(q["vers_id"] == p["vers_id"] and q["datum"] >= grens30 for q in posts)}
    gebruikte_slots = set(gebruikte_slots)
    rk = reeks_voor(datum, posts) if reeks else None
    if rk and (any(p.get("reeks") and p["datum"] == datum for p in posts) or rk["tijdslot"] in gebruikte_slots):
        rk = None  # de reekspost van vandaag bestaat al
    ctx = {"stats": optie_stats(posts), "experiment": experiment(cfg, datum), "leermodus": cfg.get("leermodus")}
    stats_fb = optie_stats(posts, "facebook")
    nieuw = []
    for i in range(n):
        v, bron = {}, {}
        for dim in DIMENSIES:
            uit = (gebruikte_slots | ({rk["tijdslot"]} if rk else set())) if dim == "tijdslot" else ()
            v[dim], bron[dim] = kies_optie(dim, strat, cfg["verkenning"], rnd, uit, ctx)
        reekspost = rk if (rk and i == 0) else None
        if reekspost:
            v["tijdslot"], bron["tijdslot"] = reekspost["tijdslot"], "reeks"
            if reekspost.get("thema"):
                v["thema"], bron["thema"] = reekspost["thema"], "reeks"
        gebruikte_slots.add(v["tijdslot"])
        # Facebook krijgt een eigen tijdstip, geleerd uit de Facebook-cijfers
        v["tijdslot_fb"] = thompson("tijdslot", DIMENSIES["tijdslot"], stats_fb, rnd, cfg["verkenning"] / 0.2)
        if v["tijdslot"] < "10:00" and v["huisstijl"] not in LICHTE_STIJLEN:  # ochtend: de lichtste kleuren
            v["huisstijl"], bron["huisstijl"] = rnd.choice(LICHTE_STIJLEN), "ochtend"
        v.update(HUISSTIJLEN[v["huisstijl"]])
        v["hook_op_beeld"] = False  # Joshua wil geen hooktekst op het beeld
        # Aandeel reels (Joshua, 11 nov: ongeveer 60%): bijsturen op de laatste 14 dagen
        doel = cfg.get("reel_aandeel")
        if doel is not None and not (rk and i == 0):
            grens = (dt.date.fromisoformat(datum) - dt.timedelta(days=14)).isoformat()
            rec = [p for p in posts + nieuw if p["datum"] >= grens and p["variabelen"].get("formaat")]
            nu = sum(1 for p in rec if p["variabelen"]["formaat"] == "video") / max(1, len(rec))
            if nu < doel - 0.05:
                v["formaat"], bron["formaat"] = "video", "aandeel reels"
            elif nu > doel + 0.1:
                v["formaat"], bron["formaat"] = "carrousel", "aandeel reels"
        # Foto-achtergrond alleen als er beelden zijn en het maximumaandeel niet bereikt is
        if v["achtergrondbron"] == "beeld":
            grens14 = (dt.date.fromisoformat(datum) - dt.timedelta(days=14)).isoformat()
            recent14 = [p for p in posts + nieuw if p["datum"] >= grens14]
            aandeel = sum(1 for p in recent14 if p["variabelen"].get("achtergrondbron") == "beeld") / max(1, len(recent14))
            if (mat is not None and not mat["beelden"]) or aandeel >= cfg.get("max_aandeel_beeld", 0.33):
                v["achtergrondbron"], bron["achtergrondbron"] = "verloop", "limiet"
        # Uit de hele Bijbel: eerst alles laten kloppen, dan stap voor stap loslaten
        vrij = [x for x in alle_verzen() if x["id"] not in recent]
        bank = _bank(cfg)
        if bank is not None:  # zelfstandig: alleen verzen waarvoor de teksten al klaarstaan
            vrij = [x for x in vrij if x["id"] in bank] or _oudste_bankverzen(bank, posts + nieuw, cfg)
        import tekstbank as _tb
        if v["tijdslot"] < "10:00":  # ochtend: alleen verzen voor een goede start van de dag
            och = [x for x in vrij if x["id"] in _tb.OCHTEND_VERZEN]
            if och:
                vrij = och
        else:  # andere tijdsloten sparen de ochtendverzen, tenzij er niets anders over is
            rest = [x for x in vrij if x["id"] not in _tb.OCHTEND_VERZEN]
            if rest:
                vrij = rest
        if reekspost and reekspost.get("vers") and (bank is None or reekspost["vers"]["id"] in bank):
            vrij = [reekspost["vers"]]  # vaste reeks: dit vers, ook als het eerder gebruikt is
        kandidaten = []
        for velden in (("thema", "boekgroep", "lengte", "bron"), ("thema", "boekgroep", "bron"), ("thema", "bron"),
                       ("thema", "boekgroep"), ("thema",), ("bron",), ()):
            kandidaten = [x for x in vrij if all(x[f] == v[f] for f in velden)]
            if kandidaten:
                break
        kandidaten = kandidaten or vrij or alle_verzen()
        vers = rnd.choices(kandidaten, weights=[x.get("kwaliteit", 6) ** 2 for x in kandidaten])[0]
        for f in ("thema", "boekgroep", "lengte", "bron"):
            v[f] = vers[f]  # wat er echt gepost wordt, telt mee bij het leren
        if v["formaat"] != "carrousel":
            v["opening"], bron["opening"] = None, "n.v.t."  # alleen carrousels hebben een opening
        elif v["opening"] == "stopper" and len(vers["tekst"]) < 70:
            v["opening"], bron["opening"] = "vers", "kort vers"  # een kort vers is zelf al de stopper
        v["aanleiding"] = "kalender" if reekspost else "tijdloos"  # 'nieuws' zet src/nieuws.py
        # vaste regel (Joshua, 8 nov): een reel heeft altijd uitleg, zoals de carrousel
        v["video_uitleg"], bron["video_uitleg"] = (True, "vaste regel") if v["formaat"] == "video" else (None, "n.v.t.")
        if v["formaat"] != "video" or v.get("reel_stijl") != "situatie":
            for d in ("reel_plaatsing", "reel_scene"):
                v[d], bron[d] = None, "n.v.t."
        if v["formaat"] != "carrousel":
            v["carrousel_stijl"], bron["carrousel_stijl"] = None, "n.v.t."
        if v["formaat"] != "video":
            v["reel_stijl"], bron["reel_stijl"], v["reel_haak"], bron["reel_haak"] = None, "n.v.t.", None, "n.v.t."
            if v["formaat"] == "carrousel" and v.get("carrousel_stijl") == "markeren":
                v["opening"], bron["opening"] = "vers", "stijl markeren"  # meteen het vers, zonder stopper
            else:
                v["reel_kleur"], bron["reel_kleur"] = None, "n.v.t."
        elif cfg.get("reel_formaat") == "situatie":  # Joshua, 11 nov: 'herkenbare situatie' met echte video is de standaard
            v["reel_stijl"], bron["reel_stijl"], v["reel_haak"], bron["reel_haak"] = "situatie", "vaste regel", "geen", "n.v.t."
            # Joshua, 12 nov: 'markeren' (markeerstreep over het vers) als test naast de situatie-reel
            if rnd.random() < cfg.get("markeer_aandeel", 0.25):
                v["reel_stijl"], bron["reel_stijl"] = "markeren", "test markeren"
            if v["reel_stijl"] == "markeren":
                for d in ("reel_plaatsing", "reel_scene"):
                    v[d], bron[d] = None, "n.v.t."
            if v["reel_stijl"] != "markeren":
                v["reel_kleur"], bron["reel_kleur"] = None, "n.v.t."
            for d in ("reel_plaatsing", "reel_scene"):
                if v["reel_stijl"] == "situatie" and not v.get(d):
                    v[d], bron[d] = kies_optie(d, strat, cfg["verkenning"], rnd, (), ctx)
        elif not cfg.get("nieuwe_reels"):
            v["reel_stijl"], bron["reel_stijl"], v["reel_haak"], bron["reel_haak"] = "klassiek", "uit", "geen", "uit"
        elif v["reel_stijl"] == "beeld" and (mat is not None and not mat["beelden"]):
            v["reel_stijl"], bron["reel_stijl"] = "kinetisch", "geen foto's"
        recent.add(vers["id"])
        nieuw.append({**({"reeks": reekspost["naam"], "reeks_label": reekspost["label"]} if reekspost else {}),
                      "id": f"{datum}-{n_start + i + 1}", "datum": datum, "status": "wacht_op_tekst",
                      "vers_id": vers["id"], "ref": vers["ref"], "tekst": vers["tekst"],
                      "vertaling": vers.get("vertaling", "SV"),
                      "variabelen": v, "keuzebron": bron,
                      "hook": "", "beeld_hook": "", "caption": "", "hashtags": [],
                      "uitleg": "", "betekenis": "", "toepassing": "", "kernwoord": "", "verhaal_hook": "",
                      "media": None, "media_url": None, "metricool": {}, "stats": {},
                      "beeld": None, "muziek": None, "geluid": None})
    return nieuw

def kies_bestanden(nieuw, posts, mat, rnd):
    """Koppelt foto, muziek en sfeergeluid aan gekozen posts (pas bij het echte kiezen)."""
    for p in nieuw:
        v = p["variabelen"]
        if v["achtergrondbron"] == "beeld" and not mat["beelden"]:
            v["achtergrondbron"], p["keuzebron"]["achtergrondbron"] = "verloop", "limiet"
        p["beeld"] = minst_gebruikt(mat["beelden"], posts + nieuw, "beeld", rnd) if v["achtergrondbron"] == "beeld" else None
        p["muziek"] = minst_gebruikt(mat["muziek"], posts + nieuw, "muziek", rnd) if v["formaat"] == "video" else None
        p["geluid"] = rnd.choice(mat["geluid"]) if mat["geluid"] and v["formaat"] == "video" and v["achtergrondbron"] == "beeld" else None

def cmd_kies(datum):
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    if cfg["pauze"]:
        print("PAUZE staat aan in config.json. Niets gepland."); return
    verzen = laad("data/verzen.json")
    posts = laad("data/posts.json", [])
    rnd = random.Random(f"{datum}-{len(posts)}")
    al_vandaag = [p for p in posts if p["datum"] == datum]
    n = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"]) - len(al_vandaag)
    if n <= 0:
        print("Voor", datum, "zijn al genoeg posts gepland."); return
    mat = materiaal(cfg)
    # Volg de planning die op het dashboard stond, als die nog klopt
    uitgesloten = set(cfg.get("verzen_uitsluiten", [])) | {p["vers_id"] for p in posts} | set(cfg.get("verzen_later", {}))
    gepland = [x for x in laad("data/planning.json", {}).get("posts", []) if x["datum"] == datum]
    slots = {p["variabelen"]["tijdslot"] for p in al_vandaag}
    nieuw = []
    for x in gepland:
        if len(nieuw) >= n or x["vers_id"] in uitgesloten or x["variabelen"]["tijdslot"] in slots:
            continue
        x = json.loads(json.dumps(x)); x["id"] = f"{datum}-{len(al_vandaag) + len(nieuw) + 1}"
        if x["variabelen"].get("formaat") == "afbeelding":
            x["variabelen"]["formaat"] = "carrousel"
        slots.add(x["variabelen"]["tijdslot"]); nieuw.append(x)
    if len(nieuw) < n:
        nieuw += kies_posts(datum, cfg, strat, posts + nieuw, verzen, mat, len(al_vandaag) + len(nieuw), n - len(nieuw), slots, rnd)
    kies_bestanden(nieuw, posts, mat, rnd)
    bewaar("data/posts.json", posts + nieuw)
    activiteit("verskiezer", "Koos " + ", ".join(p["ref"] for p in nieuw))
    print(json.dumps([{k: p[k] for k in ("id", "ref", "tekst", "variabelen")} for p in nieuw], ensure_ascii=False, indent=1))
    print("\nVul nu per post in data/posts.json in: 'hook', 'caption', 'hashtags'; 'uitleg' als uitleg_op_beeld true is; 'betekenis' en 'toepassing' bij formaat carrousel. Zie TAKEN.md.")
    cmd_plan()

def cmd_plan(dagen=7):
    """Voorlopige planning voor de komende dagen, op basis van wat het systeem nu weet.
    Wordt elke nacht en na elke bediening opnieuw gemaakt; de dagelijkse run volgt hem."""
    if not experiment(laad("config.json"), dt.date.today().isoformat()):
        cmd_experiment(stil=True)
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    verzen = laad("data/verzen.json")
    vandaag = dt.date.today()
    plan = []
    if not cfg["pauze"]:
        for d in range(1, dagen + 1):
            datum = (vandaag + dt.timedelta(days=d)).isoformat()
            al = [p for p in posts if p["datum"] == datum and p["status"] not in ("afgekeurd",)]
            n = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"]) - len(al)
            if n <= 0:
                continue
            rnd = random.Random(f"plan-{datum}-{strat.get('versie', 1)}-{cfg['posts_per_dag']}")
            nieuw = kies_posts(datum, cfg, strat, posts + plan, verzen, None, len(al), n,
                               {p["variabelen"]["tijdslot"] for p in al}, rnd)
            plan += nieuw
    bewaar("data/planning.json", {"gemaakt": dt.datetime.now().isoformat(timespec="minutes"),
                                  "strategie_versie": strat.get("versie", 1), "posts": plan})
    print("Planning:", len(plan), "posts voor de komende", dagen, "dagen")

# ---------- Renderen ----------
def render_een(p, cfg, map_rel):
    """Maakt beeld of video van één post (in docs/media/<map_rel>/) en zet hem op 'gerenderd'."""
    from render import maak_afbeelding, maak_video, maak_carrousel
    p["handle"] = cfg.get("handle", "")
    koppel_materiaal(p)
    fmt = p["variabelen"]["formaat"]
    ext = "mp4" if fmt == "video" else "jpg"
    rel = f"docs/media/{map_rel}/{p['id']}.{ext}"
    os.makedirs(os.path.dirname(P(rel)), exist_ok=True)
    if fmt == "carrousel":
        if p["variabelen"].get("carrousel_stijl") == "markeren":
            import reels
            paden = reels.maak_carrousel_markeren(p, P(rel))
        else:
            paden = maak_carrousel(p, P(rel))
        rels = [os.path.relpath(x, ROOT) for x in paden]
        p["media"], p["media_extra"] = rels[0], rels[1:]
    else:
        rs = p["variabelen"].get("reel_stijl") or "klassiek"
        if ext == "mp4" and rs == "markeren":
            import reels
            reels.maak_markeren(p, P(rel))
        elif ext == "mp4" and rs == "situatie":
            import reels, clips
            try:
                gevonden, rust = clips.clips_voor(p)
                if not gevonden:
                    raise RuntimeError("geen passende clips gevonden")
                p["variabelen"]["reel_scene"] = rust
                reels.maak_situatie(p, P(rel), gevonden, p["variabelen"].get("reel_plaatsing") or "midden")
            except Exception as e:  # nooit een gat in de planning: dan een gewone reel
                print("Situatie-reel lukte niet, gewone reel:", e)
                p["variabelen"]["reel_stijl"] = "klassiek"
                p.setdefault("keuzebron", {})["reel_stijl"] = "geen clips"
                for d in ("reel_plaatsing", "reel_scene"):
                    p["variabelen"][d] = None
                maak_video(p, P(rel))
        elif ext == "mp4" and rs != "klassiek":
            import reels
            fotos = []
            if rs == "beeld":
                m = materiaal_map(); alle = materiaal(cfg)["beelden"]
                fotos = [os.path.join(m, f) for f in random.Random(p["id"]).sample(alle, min(3, len(alle)))] if alle else []
                if not fotos:
                    rs = p["variabelen"]["reel_stijl"] = "kinetisch"
            reels.maak_reel(p, P(rel), rs, p["variabelen"].get("reel_haak"), fotos, cfg.get("reel_tempo", 1.0))
        else:
            (maak_video if ext == "mp4" else maak_afbeelding)(p, P(rel))
        p["media"], p["media_extra"] = rel, []
    p["thumb"] = maak_thumb(P(p["media"]), p["id"], (p.get("cover_ms") or 4000) / 1000)
    if fmt == "carrousel":
        from render import maak_story
        p["story"] = os.path.relpath(maak_story(P(p["media"]), P(rel).replace(".jpg", "-story.jpg")), ROOT)
    for k in ("beeld_pad", "muziek_pad", "geluid_pad"):
        p.pop(k, None)
    if cfg.get("github_repo"):
        eig, naam = cfg["github_repo"].split("/")
        url = lambda r: f"https://{eig}.github.io/{naam}/{r[len('docs/'):]}"
        p["media_url"] = url(p["media"])
        p["media_urls"] = [url(r) for r in [p["media"]] + p["media_extra"]]
        p["story_url"] = url(p["story"]) if p.get("story") else None
    p["status"] = "gerenderd"
    p["goedgekeurd"] = None
    print("OK", p["id"], rel)
    if fmt == "video":
        activiteit("video", f"Monteerde video {p['ref']}" + (" met muziek" if p.get("muziek") else ""))
    activiteit("designer", f"Ontwierp {p['ref']} in stijl {p['variabelen'].get('huisstijl', '')}")


def cmd_render(datum):
    from render import maak_afbeelding, maak_video, maak_carrousel
    cfg = laad("config.json")
    posts = laad("data/posts.json", [])
    fouten = 0
    for p in posts:
        if p["datum"] != datum or p["status"] not in ("wacht_op_tekst", "klaar_voor_render", "opnieuw_maken"):
            continue
        if p["status"] == "opnieuw_maken" and not os.path.isdir(materiaal_map()):
            continue  # video of foto-achtergrond: wacht op een run met muziek en foto's
        probleem = valideer_tekst(p, cfg)
        if probleem:
            print("NIET GERENDERD", p["id"], probleem); fouten += 1; continue
        try:
            render_een(p, cfg, datum[:7])
        except Exception as e:
            if p.get("beeld"):  # vaak ligt het aan de foto: probeer het met kleurverloop
                p["beeld"] = None; p["variabelen"]["achtergrondbron"] = "verloop"
                try:
                    render_een(p, cfg, datum[:7])
                    herstel(f"{p['id']}: maken met foto mislukt ({str(e)[:80]})", "opnieuw gemaakt met kleurverloop")
                    continue
                except Exception as e2:
                    e = e2
            p["status"] = "afgekeurd"; fouten += 1
            herstel(f"{p['id']}: beeld kon niet gemaakt worden ({str(e)[:80]})", "post afgekeurd; de noodvoorraad vult het tijdslot op", ok=False)
    bewaar("data/posts.json", posts)
    if fouten:
        sys.exit(1)

def maak_thumb(bron, pid, sec=4):
    """Kleine voorvertoning (216 px breed) die blijft bestaan als de media later wordt opgeruimd."""
    import subprocess
    rel = f"docs/thumbs/{pid}.jpg"
    os.makedirs(P("docs/thumbs"), exist_ok=True)
    if bron.endswith(".mp4"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(sec), "-i", bron, "-frames:v", "1",
                        "-vf", "scale=216:-2", "-q:v", "4", P(rel)], check=True)
    else:
        from PIL import Image
        im = Image.open(bron); im.thumbnail((216, 400)); im.save(P(rel), quality=80)
    return rel[len("docs/"):]

def cmd_opruimen(dagen=30):
    """Verwijdert media van posts die langer dan `dagen` geleden online gingen; de thumb blijft."""
    posts = laad("data/posts.json", [])
    grens = (dt.date.today() - dt.timedelta(days=int(dagen))).isoformat()
    weg, weggehaald = 0, []
    for p in posts:
        if p.get("status") in ("gepubliceerd", "overgeslagen", "fout", "afgekeurd") and p["datum"] < grens and p.get("media"):
            if os.path.exists(P(p["media"])):
                if not p.get("thumb"):
                    p["thumb"] = maak_thumb(P(p["media"]), p["id"])
                os.remove(P(p["media"])); weg += 1
            weggehaald.append(p["media"])
            for extra in (p.get("media_extra", []) or []) + ([p["story"]] if p.get("story") else []):
                weggehaald.append(extra)
                if os.path.exists(P(extra)):
                    os.remove(P(extra))
            p["media"], p["media_extra"] = None, []
    bewaar("data/posts.json", posts)
    if weggehaald:  # tools/media.py verwijdert alleen wat hier bewust staat
        bewaar("data/media_weg.json", laad("data/media_weg.json", []) + weggehaald)
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
            cmd_log(f"{p['id']}: foto niet gevonden, kleurverloop gebruikt", "info")
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
            cmd_log(f"{p['id']}: muziek niet gevonden, video zonder muziek", "fout", code="muziek", post=p["id"])
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
    if p.get("kernwoord") and p["kernwoord"].lower().strip(" .,;:!?") not in [w.lower().strip(" .,;:!?\u2019'\"") for w in p["tekst"].split()]:
        return "kernwoord moet letterlijk één woord uit het vers zijn"
    if p["variabelen"].get("uitleg_op_beeld") and not (0 < len(p.get("uitleg", "")) <= 110):
        return "uitleg ontbreekt of is langer dan 110 tekens"
    if p["variabelen"].get("opening") == "verhaal":
        vh = (p.get("verhaal_hook") or "").strip()
        if not (25 <= len(vh) <= 140):
            return "verhaal_hook ontbreekt of heeft niet 25 tot 140 tekens (opening 'verhaal')"
        if "\u2014" in vh:
            return "gebruik geen lange streep"
    if p["variabelen"]["formaat"] == "carrousel" or p["variabelen"].get("video_uitleg"):
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
    if p.get("vertaling") in BRON and "NBV21" not in p["caption"]:
        return "bronvermelding NBV21 ontbreekt in de caption"
    if p["tekst"][:40] not in p["caption"]:
        return "caption moet de verstekst letterlijk bevatten"
    if p["variabelen"].get("vraag_onderaan") is True and not p["caption"].rstrip().endswith("?"):
        return "vraag_onderaan staat aan: eindig de caption met een oprechte, open vraag"
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
            k: r.get(k) for k in ("views", "reach", "likes", "comments", "shares", "saves", "follows", "avg_watch_ms")}
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
            # kijkduur: gemiddeld bekeken deel van de video (alleen video, als Instagram het meldt)
            kijk = None
            if p["variabelen"].get("formaat") == "video" and s.get("avg_watch_ms"):
                kijk = min(1.5, s["avg_watch_ms"] / 1000 / max(5, p.get("duur", 9)))
            per_platform.setdefault(plat, []).append((p, ratio, bereik, kijk))
    uit = []
    for plat, rijen in per_platform.items():
        bereiken = [b for _, _, b, _ in rijen]
        med_r = statistics.median([r for _, r, _, _ in rijen]) or 1e-6
        med_b = statistics.median(bereiken) or 1
        kijks = [k for _, _, _, k in rijen if k]
        med_k = statistics.median(kijks) if kijks else None
        for p, r, b, k in rijen:
            # Mix: 70% interactie-kwaliteit, 30% bereik (algoritme vond het goed);
            # bij video met kijkduur: 50% interactie, 20% bereik, 30% kijkduur
            if k and med_k:
                score = 0.5 * (r / med_r) + 0.2 * (b / med_b) + 0.3 * (k / med_k)
            else:
                score = 0.7 * (r / med_r) + 0.3 * (b / med_b)
            # Uitschieters dempen: boven 1,5 telt de rest maar half mee, en maximaal 3
            if score > 1.5:
                score = 1.5 + (score - 1.5) * 0.5
            uit.append((p, plat, min(score, 3.0)))
    return uit

# ---------- Slimmer kiezen: Thompson sampling, weekexperiment, per platform ----------
WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]

def optie_stats(posts, platform=None):
    """{dimensie: {optie: [scores]}}; per post het gemiddelde over platformen (of één platform)."""
    per_post = {}
    for p, plat, sc in post_scores(posts):
        if platform and plat != platform:
            continue
        per_post.setdefault(p["id"], (p, []))[1].append(sc)
    uit = {}
    for p, scs in per_post.values():
        gem = sum(scs) / len(scs)
        v = dict(p["variabelen"])
        v["weekdag"] = WEEKDAGEN[dt.date.fromisoformat(p["datum"]).weekday()]
        if platform == "facebook" and v.get("tijdslot_fb"):
            v["tijdslot"] = v["tijdslot_fb"]
        for dim, o in v.items():
            if o is None:  # niet van toepassing (bijv. opening bij een video)
                continue
            uit.setdefault(dim, {}).setdefault(str(o), []).append(gem)
    return uit

def posterior(vals, k0=2.0):
    """Gemiddelde en onzekerheid van een optie (begint bij 1,0 = gemiddeld)."""
    n = len(vals)
    gem = (sum(vals) + k0 * 1.0) / (n + k0)
    sd = statistics.pstdev(vals) if n > 1 else 0.5
    return gem, max(0.2, sd) / math.sqrt(n + k0)

def thompson(dim, opties, stats, rnd, factor=1.0):
    """Trek per optie een mogelijke score uit wat we weten; de hoogste wint.
    Onzekere opties krijgen zo vanzelf kansen, duidelijk slechtere steeds minder."""
    best, bw = None, -1e9
    for o in opties:
        gem, sd = posterior(stats.get(dim, {}).get(str(o), []))
        w = rnd.gauss(gem, sd * factor)
        if w > bw:
            best, bw = o, w
    return best

def experiment(cfg, datum):
    """Het weekexperiment: welke 2 dingen worden deze week bewust getest. Verloopt na 7 dagen."""
    e = cfg.get("experiment") or {}
    if e.get("tot", "") >= datum and e.get("dims"):
        return e["dims"]
    return []

def cmd_experiment(stil=False):
    """Kiest het experiment voor de komende week: de 2 onderdelen waar het systeem het minst zeker over is."""
    cfg = laad("config.json")
    stats = optie_stats(laad("data/posts.json", []))
    kandidaten = [d for d in DIMENSIES if d not in ("tijdslot",)]
    def onzeker(d):
        sds = [posterior(stats.get(d, {}).get(str(o), []))[1] for o in DIMENSIES[d]]
        return sum(sds) / len(sds) * math.log(1 + len(DIMENSIES[d]))
    vorige = set((cfg.get("experiment") or {}).get("dims", []))
    keuze = sorted(kandidaten, key=lambda d: (d in vorige, -onzeker(d)))[:2]
    van = dt.date.today()
    cfg["experiment"] = {"dims": keuze, "van": van.isoformat(), "tot": (van + dt.timedelta(days=6)).isoformat()}
    bewaar("config.json", cfg)
    namen = {"huisstijl": "stijl", "thema": "thema", "hook_stijl": "soort hook", "formaat": "carrousel of video",
             "uitleg_op_beeld": "uitleg op beeld", "achtergrondbron": "foto of kleur", "boekgroep": "Bijbelboek",
             "lengte": "lengte van het vers", "bron": "bekend of onbekend vers", "vraag_onderaan": "vraag onderaan", "opening": "eerste slide (hele vers, stopper of verhaal eerst)", "reel_stijl": "reelstijl", "reel_haak": "vraag als haak in reel", "hashtag_stijl": "soort hashtags", "reel_plaatsing": "plek van de tekst in de reel", "reel_scene": "soort rustbeeld in de reel", "video_uitleg": "video met uitleg"}
    tekst = "Experiment deze week: " + " en ".join(namen.get(d, d) for d in keuze)
    cmd_log(tekst)
    if not stil:
        print(tekst)
    return keuze

# ---------- Leren ----------
def leermodus_uit(cfg):
    """Zet snel leren uit en herstelt de instellingen van daarvoor."""
    vorige = cfg.pop("leermodus_vorige", None) or {}
    cfg["leermodus"] = False
    cfg.pop("leermodus_tot", None)
    cfg.pop("leermodus_start", None)
    cfg["max_posts_per_dag"] = vorige.get("max_posts_per_dag") or 3
    cfg["posts_per_dag"] = min(vorige.get("posts_per_dag") or 1, cfg["max_posts_per_dag"])
    cfg["verkenning"] = vorige.get("verkenning") or 0.2

def check_leermodus():
    """Na de einddatum gaat snel leren vanzelf uit. Geeft True als de modus (nog) aan staat."""
    cfg = laad("config.json")
    if not cfg.get("leermodus"):
        return False
    if cfg.get("leermodus_tot", "9999") < dt.date.today().isoformat():
        leermodus_uit(cfg)
        bewaar("config.json", cfg)
        cmd_log("Snel leren afgelopen: terug naar de normale instellingen")
        return False
    return True

def cmd_leer():
    cfg = laad("config.json")
    strat = vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    scores = post_scores(posts)
    vandaag = dt.date.today().isoformat()
    if len({p["id"] for p, _, _ in scores}) < cfg["min_posts_voor_leren"]:
        print("Nog te weinig gemeten posts om te leren:", len(scores)); return
    K = 4  # demping: een optie met weinig metingen blijft dicht bij 1.0
    # Bij snel leren wordt elke dag geleerd, met kleinere stappen (ongeveer 0,4 per week in totaal)
    max_stap = 0.06 if cfg.get("leermodus") else cfg["max_gewicht_verschuiving_per_week"]
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
    activiteit("analist", f"Weekanalyse: strategie v{strat['versie']}")
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
        per = {}
        for plat, mom in p.get("stats", {}).items():
            s = beste_meting(mom)
            per[plat] = {k: s.get(k) for k in ("views", "reach", "likes", "comments", "shares", "saves", "follows")}
            per[plat]["t"] = s.get("t")
            for k in ("views", "reach", "likes", "comments", "shares", "saves"):
                tot[k] = tot.get(k, 0) + (s.get(k) or 0)
        lijst.append({"id": p["id"], "datum": p["datum"], "ref": p["ref"], "tekst": p["tekst"], "hook": p.get("hook", ""),
                      "status": p["status"], "variabelen": p["variabelen"], "vers_id": p.get("vers_id"), "goedgekeurd": p.get("goedgekeurd"), "reeks": p.get("reeks"), "reeks_label": p.get("reeks_label"), "reserve_ref": (p.get("reserve") or {}).get("ref") if (p.get("reserve") or {}).get("caption") else None,
                      "caption": p.get("caption", ""), "uitleg": p.get("uitleg", ""), "media": p.get("media"), "media_url": p.get("media_url"), "media_urls": p.get("media_urls"), "thumb": p.get("thumb"),
                      "platformen": list(p.get("gepubliceerd", {}).keys()),
                      "links": {k: v.get("url") for k, v in p.get("gepubliceerd", {}).items()}, "totaal": tot, "per_platform": per, "score": sc.get(p["id"], {}),
                      "pub": {k: v.get("t") for k, v in p.get("gepubliceerd", {}).items()}, "gemist": p.get("gemist", []), "nood": p.get("nood", False), "nieuws": p.get("nieuws"),
                      "online": min((g["t"] for g in p.get("gepubliceerd", {}).values()), default=None)})
    rapporten = sorted(os.listdir(P("rapporten"))) if os.path.isdir(P("rapporten")) else []
    extra = dashboard_extra(cfg, posts)
    data = {"gegenereerd": dt.datetime.now().isoformat(timespec="minutes"), "repo": cfg.get("github_repo", ""),
            "config": {k: cfg.get(k) for k in ("pauze", "kanaalnaam", "posts_per_dag", "max_posts_per_dag", "verkenning", "platformen_actief", "max_aandeel_beeld", "verzen_uitsluiten", "leermodus", "leermodus_tot", "goedkeuren", "experiment", "stories", "zelfstandig", "nieuwe_reels", "reel_tempo", "reel_formaat", "reel_aandeel")},
            "strategie": strat, "posts": lijst,
            "leergeschiedenis": laad("data/leergeschiedenis.json", []),
            "laatste_rapport": laad(f"rapporten/{rapporten[-1]}") if rapporten else None,
            "logboek": laad("data/logboek.json", [])[-60:],
            "recente_fouten": [l for l in laad("data/logboek.json", [])
                               if l.get("soort") == "fout" and not l.get("opgelost") and l["t"] >= (dt.datetime.now() - dt.timedelta(hours=48)).isoformat(timespec="minutes")],
            "versen_totaal": len(laad("data/verzen.json", [])),
            **extra,
            "planning": [{k: x.get(k) for k in ("datum", "ref", "tekst", "vers_id", "variabelen", "keuzebron", "reeks", "reeks_label")}
                         for x in laad("data/planning.json", {}).get("posts", [])]}
    bewaar("docs/data.json", data)
    schrijf_status(cfg, strat, posts, data["recente_fouten"])
    print("docs/data.json bijgewerkt:", len(lijst), "posts")

def beste_meting(mom):
    """Meest actuele cijfers: 7 dagen als die er is, anders de tussentijdse, anders 24 uur."""
    return mom.get("7d") or mom.get("laatst") or mom.get("24u") or {}

NAMEN_OPTIES = {"afbeelding": "afbeeldingen", "video": "video's", "carrousel": "carrousels", "verloop": "kleurverloop",
                "beeld": "foto-achtergrond", True: "met uitleg", False: "zonder uitleg"}

def dashboard_extra(cfg, posts):
    """Extra blokken voor het dashboard: gezondheid, groei, weekvergelijking, inzichten, snel leren, voorraad."""
    nu = dt.datetime.now()
    # Week tegen vorige week (op publicatiedatum)
    def week(van, tot):
        w = {"posts": 0, "reach": 0, "views": 0, "likes": 0, "comments": 0, "saves": 0, "shares": 0}
        for p in posts:
            if p["status"] != "gepubliceerd" or not (van <= p["datum"] < tot):
                continue
            w["posts"] += 1
            for mom in p.get("stats", {}).values():
                m = beste_meting(mom)
                for k in list(w)[1:]:
                    w[k] += m.get(k) or 0
        return w
    d = lambda n: (nu.date() - dt.timedelta(days=n)).isoformat()
    morgen = (nu.date() + dt.timedelta(days=1)).isoformat()
    weken = {"deze": week(d(6), morgen), "vorige": week(d(13), d(6))}
    # Inzichten: gemiddelde score per optie, met aantal metingen
    per_post = {}
    for p, plat, sc in post_scores(posts):
        per_post.setdefault(p["id"], (p, []))[1].append(sc)
    inzichten = []
    for dim in DIMENSIES:
        groepen = {}
        for p, scores in per_post.values():
            o = p["variabelen"].get(dim)
            groepen.setdefault(json.dumps(o), []).append(sum(scores) / len(scores))
        opties = sorted(({"optie": json.loads(k), "gem": round(sum(v) / len(v), 2), "n": len(v)} for k, v in groepen.items()),
                        key=lambda x: -x["gem"])
        inzichten.append({"dimensie": dim, "opties": opties, "metingen": sum(x["n"] for x in opties)})
    # Snel leren
    gemeten = sum(1 for p in per_post.values())
    snel = None
    if cfg.get("leermodus"):
        start = cfg.get("leermodus_start") or nu.date().isoformat()
        snel = {"start": start, "tot": cfg.get("leermodus_tot"),
                "dag": (nu.date() - dt.date.fromisoformat(start)).days + 1,
                "dagen": max(1, (dt.date.fromisoformat(cfg["leermodus_tot"]) - dt.date.fromisoformat(start)).days),
                "online": sum(1 for p in posts if p["status"] == "gepubliceerd" and p["datum"] >= start),
                "gemeten": sum(1 for p, _ in per_post.values() if p["datum"] >= start)}
    # Voorraad
    verzen = laad("data/verzen.json", [])
    gebruikt = {p["vers_id"] for p in posts if p["status"] not in ("afgekeurd",)}
    grens = (nu.date() - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {p["vers_id"] for p in posts if p["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    per_thema = {}
    for v in alle_verzen():
        t = per_thema.setdefault(v["thema"], {"totaal": 0, "beschikbaar": 0, "nooit": 0})
        t["totaal"] += 1
        t["beschikbaar"] += v["id"] not in recent
        t["nooit"] += v["id"] not in gebruikt
    mat = laad("data/materiaal_lijst.json", {})
    lijst = mat.get("lijst", {})
    gebruik = lambda veld, namen: sorted(({"naam": os.path.basename(n), "keer": sum(1 for p in posts if p.get(veld) == n)} for n in namen),
                                          key=lambda x: -x["keer"])
    voorraad = {"verzen": per_thema, "verzen_totaal": len(alle_verzen()), "nbv21": len(extra_verzen()),
                "kandidaten": len(laad("data/bijbel_kandidaten.json", [])), "bekend": sum(1 for v in alle_verzen() if v["bron"] == "bekend"), "ontdekking": sum(1 for v in alle_verzen() if v["bron"] == "ontdekking"),
                "per_dag": cfg["posts_per_dag"],
                "muziek": gebruik("muziek", lijst.get("muziek", [])), "beelden": gebruik("beeld", lijst.get("beelden", [])),
                "materiaal_bijgewerkt": mat.get("bijgewerkt")}
    def opties_van(stats, dim):
        return sorted(({"optie": k, "gem": round(posterior(v)[0], 2), "n": len(v)} for k, v in stats.get(dim, {}).items()),
                      key=lambda x: -x["gem"])
    st_all, st_ig, st_fb = optie_stats(posts), optie_stats(posts, "instagram"), optie_stats(posts, "facebook")
    extra_inz = {"weekdag": opties_van(st_all, "weekdag"), "tijd_ig": opties_van(st_ig, "tijdslot"),
                 "tijd_fb": opties_van(st_fb, "tijdslot"), "formaat_ig": opties_van(st_ig, "formaat"), "formaat_fb": opties_van(st_fb, "formaat")}
    reacties = laad("data/reacties.json", [])
    return {"reacties": [r for r in reacties if r["status"] in ("nieuw", "voorgesteld")][:40] + [r for r in reacties if r["status"] not in ("nieuw", "voorgesteld")][:10],
            "inzichten_extra": extra_inz, "reeksen": [{k: r.get(k) for k in ("naam", "label", "van", "tot", "weekdag", "tijdslot")} for r in laad("data/reeksen.json", {}).get("reeksen", [])],
            "gezondheid": laad("data/gezondheid.json", {}), "groei": laad("data/groei.json", []),
            "weken": weken, "inzichten_data": inzichten, "min_posts_voor_leren": cfg.get("min_posts_voor_leren", 6),
            "gemeten_posts": gemeten, "snel_leren": snel, "voorraad": voorraad,
            "herstel": [h for h in laad("data/herstel.json", []) if h["t"] >= (nu - dt.timedelta(days=7)).isoformat()][::-1][:30],
            "nood": {"klaar": len(nood_klaar()), "doel": NOOD_DOEL},
            "tekstbank": {**bank_voorraad(cfg), "zelfstandig": bool(cfg.get("zelfstandig"))},
            "tekstbank_lijst": _bank_lijst(cfg, posts),
            "nieuws": {"instelling": {**{"aan": True, "max_per_dag": 2, "licht_automatisch": True}, **(cfg.get("nieuws") or {})},
                       "recent": [{k: x.get(k) for k in ("id", "t", "bron", "kop", "link", "categorie", "zwaar", "status", "post", "opties")}
                                  for x in laad("data/nieuws.json", [])[-25:]][::-1]},
            "verzoeken": laad("data/verzoeken.json", [])[-20:][::-1],
            "overleg": laad("data/overleg.json", [])[-1:],
            "whatsapp": {**{"direct": True, "dagelijks": True, "wekelijks": True, "uitschieter": True}, **(cfg.get("whatsapp") or {})}}

def kantoor_extra(cfg, posts):
    """Extra's voor het pixel-kantoor: gezondheidslampjes, volgersbord, post van de week, snel leren."""
    nu = dt.datetime.now()
    uren = lambda t: (nu - dt.datetime.fromisoformat(t[:16])).total_seconds() / 3600 if t else 1e9
    g = laad("data/gezondheid.json", {})
    def taak(k, naam, max_u):
        x = g.get(k)
        if not x or (not x.get("ok") and not x.get("fout")):
            return {"naam": naam, "kleur": "grijs", "tekst": "nog niet gemeld"}
        if x.get("laatst_ok") is False:
            return {"naam": naam, "kleur": "rood", "tekst": "mislukt"}
        return {"naam": naam, "kleur": "groen" if uren(x.get("ok")) <= max_u else "oranje", "tekst": "ok" if uren(x.get("ok")) <= max_u else "te lang stil"}
    def sleutel(k, naam):
        x = g.get(k) or {}
        if not x.get("verloopt"):
            return {"naam": naam, "kleur": "grijs", "tekst": "onbekend"}
        if x.get("geldig") is False:
            return {"naam": naam, "kleur": "rood", "tekst": "ongeldig"}
        if x["verloopt"] == "nooit":
            return {"naam": naam, "kleur": "groen", "tekst": "verloopt nooit"}
        d = (dt.date.fromisoformat(x["verloopt"]) - nu.date()).days
        return {"naam": naam, "kleur": "rood" if d < 14 else "oranje" if d < 30 else "groen", "tekst": f"nog {d} dagen"}
    lampen = []
    for k, naam in (("instagram", "Instagram"), ("facebook", "Facebook")):
        if k not in cfg.get("platformen_actief", []):
            lampen.append({"naam": naam, "kleur": "grijs", "tekst": "uit"}); continue
        x = g.get(k)
        lampen.append({"naam": naam, "kleur": "grijs" if not x else "rood" if x.get("laatst_ok") is False else "groen",
                       "tekst": "nog niets geplaatst" if not x else "mislukt" if x.get("laatst_ok") is False else "ok"})
    lampen += [taak("dagelijks", "Dagelijkse taak", 27), taak("avondcontrole", "Avondcontrole", 27),
               taak("statistieken", "Statistieken", 30), sleutel("sleutel_instagram", "Sleutel IG"), sleutel("sleutel_facebook", "Sleutel FB")]
    groei = [x for x in laad("data/groei.json", []) if x.get("instagram") is not None or x.get("facebook") is not None]
    tot = lambda x: (x.get("instagram") or 0) + (x.get("facebook") or 0)
    week = next((x for x in groei if x["datum"] >= (nu.date() - dt.timedelta(days=7)).isoformat()), groei[0] if groei else None)
    volgers = {"ig": groei[-1].get("instagram") if groei else None, "fb": groei[-1].get("facebook") if groei else None,
               "totaal": tot(groei[-1]) if groei else None, "week": (tot(groei[-1]) - tot(week)) if groei and len(groei) > 1 else None,
               "reeks": [tot(x) for x in groei[-14:]]}
    # Post van de week: hoogste score (of bereik) van de afgelopen 7 dagen
    sc = {}
    for p, plat, s in post_scores(posts):
        sc.setdefault(p["id"], []).append(s)
    grens = (nu.date() - dt.timedelta(days=7)).isoformat()
    kand = [p for p in posts if p["status"] == "gepubliceerd" and p["datum"] >= grens]
    bereik = lambda p: sum((beste_meting(m).get("reach") or beste_meting(m).get("views") or 0) for m in p.get("stats", {}).values())
    kand.sort(key=lambda p: (sum(sc[p["id"]]) / len(sc[p["id"]]) if p["id"] in sc else -1, bereik(p)), reverse=True)
    top = None
    if kand and (kand[0]["id"] in sc or bereik(kand[0])):
        p = kand[0]
        top = {"ref": p["ref"], "thumb": p.get("thumb") or p.get("media_url"), "bereik": bereik(p),
               "score": round(sum(sc[p["id"]]) / len(sc[p["id"]]), 2) if p["id"] in sc else None, "formaat": p["variabelen"]["formaat"]}
    snel = None
    if cfg.get("leermodus"):
        start = dt.date.fromisoformat(cfg.get("leermodus_start") or nu.date().isoformat())
        dagen = max(1, (dt.date.fromisoformat(cfg["leermodus_tot"]) - start).days)
        snel = {"dag": min(dagen, (nu.date() - start).days + 1), "dagen": dagen, "tot": cfg["leermodus_tot"]}
    return {"lampen": lampen, "volgers": volgers, "top_post": top, "snel_leren": snel}

def schrijf_status(cfg, strat, posts, fouten):
    """docs/status.json voor het pixel-kantoor. Toestanden worden in de browser bepaald op basis van tijd."""
    nu = dt.datetime.now()
    act = laad("data/activiteit.json", {})
    agents = {k: dict(v) for k, v in act.items()}
    if fouten:
        agents["controller"] = {"t": fouten[-1]["t"], "task": fouten[-1]["tekst"][:70], "state": "error"}
    elif "controller" not in agents:
        agents["controller"] = {"t": nu.isoformat(timespec="seconds"), "task": "Alles werkt", "state": "done"}
    vandaag = nu.date().isoformat()
    grens7 = (nu - dt.timedelta(days=7)).date().isoformat()
    per_plat, bereik7 = {}, 0
    for p in posts:
        for plat, mom in p.get("stats", {}).items():
            st = mom.get("7d") or mom.get("24u") or {}
            r = st.get("reach") or st.get("views") or 0
            per_plat[plat] = per_plat.get(plat, 0) + r
            if p["datum"] >= grens7:
                bereik7 += r
    volgende = sorted((p["datum"] + "T" + p["variabelen"]["tijdslot"] + ":00") for p in posts if p["status"] == "gerenderd")
    tijden = strat["gewichten"].get("tijdslot", {})
    beste = max(tijden, key=tijden.get) if strat.get("bijgewerkt") and tijden else "nog onbekend"
    inz = strat.get("inzichten") or []
    status = {
        "updated": nu.isoformat(timespec="seconds"),
        "agents": agents,
        "stats": {"posts_today": sum(1 for p in posts if p["datum"] == vandaag and p["status"] == "gepubliceerd"),
                  "posts_total": sum(1 for p in posts if p["status"] == "gepubliceerd"),
                  "reach_7d": bereik7, "best_time": beste, "next_post": volgende[0] if volgende else None},
        "learned": inz[-1]["tekst"] if inz else "Na de eerste week met cijfers vertelt de Analist hier wat werkt.",
        "platforms": {k: per_plat.get(k, 0) for k in ("instagram", "facebook", "youtube", "tiktok")},
        "platforms_actief": cfg.get("platformen_actief", []),
        "log": [{"t": l["t"][11:16], "msg": l["tekst"][:110]} for l in reversed(laad("data/logboek.json", [])[-12:])],
        **kantoor_extra(cfg, posts),
    }
    bewaar("docs/status.json", status)

def activiteit(agent, taak, staat="done"):
    """Laatste actie per medewerker in het pixel-kantoor (docs/kantoor.html)."""
    a = laad("data/activiteit.json", {})
    a[agent] = {"t": dt.datetime.now().isoformat(timespec="seconds"), "task": taak, "state": staat}
    bewaar("data/activiteit.json", a)

def gezond(naam, ok=True, detail=""):
    """Laatste gelukte en mislukte keer per onderdeel (dashboard: gezondheidsbalk)."""
    g = laad("data/gezondheid.json", {})
    x = g.setdefault(naam, {})
    nu = dt.datetime.now().isoformat(timespec="minutes")
    x["ok" if ok else "fout"] = nu
    x["laatst_ok"] = bool(ok)
    x["detail"] = str(detail)[:160]
    bewaar("data/gezondheid.json", g)

def cmd_log(tekst, soort="info", code=None, post=None):
    """Logregel. Bij fouten: 'code' bepaalt welke knoppen het dashboard toont, 'post' welke post het betreft."""
    log = laad("data/logboek.json", [])
    regel = {"t": dt.datetime.now().isoformat(timespec="seconds"), "soort": soort, "tekst": tekst}
    if code:
        regel["code"] = code
    if post:
        regel["post"] = post
    log.append(regel)
    bewaar("data/logboek.json", log[-500:])
    if soort == "fout" and (code in ("post_mislukt", "post_gemist", "te_weinig", "nood_op", "rechten", "tekstbank", "maken") or tekst.startswith("ACTIE VOOR JOU")):
        try:  # direct een seintje via Telegram (wordt verstuurd door de volgende GitHub-run), met knoppen om het meteen op te lossen
            import whatsapp
            k = {"post_mislukt": [[["🔁 Opnieuw proberen", {"actie": "post_opnieuw", "post": post}], ["Noodpost ervoor in de plaats", {"actie": "post_nood", "post": post}]]],
                 "post_gemist": [[["📤 Alsnog posten", {"actie": "post_opnieuw", "post": post}], ["Noodposts op lege plekken", {"actie": "nood_inzetten"}]]],
                 "te_weinig": [[["Noodposts inzetten", {"actie": "nood_inzetten"}], ["Posts nu laten maken", {"actie": "posts_maken"}]]],
                 "maken": [[["Opnieuw proberen", {"actie": "posts_maken"}], ["Noodposts inzetten", {"actie": "nood_inzetten"}]]],
                 "rechten": [[["Verbinding testen", {"actie": "test"}]]],
                 }.get(code, [])
            if post is None:
                k = [r for r in k if not any(o.get("post", 1) is None for _, o in r)]
            k.append([["✓ Opgelost", {"actie": "fout_opgelost", "t": regel["t"]}]])
            whatsapp.zet_in_wachtrij(("🚨 *Bibleverse: " + ("actie voor jou" if tekst.startswith("ACTIE VOOR JOU") else "probleem") + "*\n")
                                     + tekst.replace("ACTIE VOOR JOU:", "").strip()[:500], "direct", knoppen=k)
        except Exception as e:
            print("WhatsApp-wachtrij:", e)

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

def cmd_vervang(pid, reden=""):
    """Vers van een post past niet los van de context: nooit meer gebruiken en een ander vers met dezelfde kenmerken kiezen."""
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    p = next((x for x in posts if x["id"] == pid), None)
    if not p or p["status"] not in ("wacht_op_tekst", "gerenderd"):
        sys.exit("Post niet gevonden of al online")
    cfg.setdefault("verzen_uitsluiten", [])
    if p["vers_id"] not in cfg["verzen_uitsluiten"]:
        cfg["verzen_uitsluiten"].append(p["vers_id"])
    af = laad("data/pool_afgekeurd.json", [])
    if p["vers_id"] not in af:
        bewaar("data/pool_afgekeurd.json", af + [p["vers_id"]])
    bewaar("config.json", cfg)
    oud = p["ref"]
    rest = [x for x in posts if x["id"] != pid]
    nieuw = kies_posts(p["datum"], cfg, strat, rest, laad("data/verzen.json"), None, 0, 1, set(), random.Random(pid + oud), reeks=False)[0]
    v = nieuw["variabelen"]
    for f in ("thema", "boekgroep", "lengte", "bron"):
        p["variabelen"][f] = v[f]
    p.update({k: nieuw[k] for k in ("vers_id", "ref", "tekst", "vertaling")})
    p.update({"status": "wacht_op_tekst", "hook": "", "caption": "", "hashtags": [], "uitleg": "", "betekenis": "", "toepassing": ""})
    bewaar("data/posts.json", posts)
    cmd_log(f"{oud} vervangen door {p['ref']} ({reden or 'past niet los van de context'})")
    print(json.dumps({k: p[k] for k in ("id", "ref", "tekst", "variabelen")}, ensure_ascii=False, indent=1))

def cmd_reserve(datum):
    """Kiest per post van DATUM een reservevers (zelfde kenmerken) zodat 'ander vers' op het dashboard meteen kan.
    Daarna vult Claude in data/posts.json per post onder 'reserve' de teksten in (zelfde velden als de post)."""
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    gebruikt = {p["vers_id"] for p in posts} | {p.get("reserve", {}).get("vers_id") for p in posts}
    uit = []
    for p in posts:
        if p["datum"] != datum or p["status"] not in ("gerenderd", "wacht_op_tekst", "klaar_voor_render") or p.get("reserve", {}).get("caption"):
            continue
        if p.get("reeks") in ("Advent", "Kerst", "Nieuwjaar"):
            continue  # vaste reeksverzen krijgen geen reserve
        cfg2 = dict(cfg, verzen_uitsluiten=list(set(cfg.get("verzen_uitsluiten", [])) | gebruikt))
        alt = kies_posts(datum, cfg2, strat, posts, laad("data/verzen.json"), None, 0, 1, set(), random.Random("reserve" + p["id"]), reeks=False)[0]
        r = {k: alt[k] for k in ("vers_id", "ref", "tekst", "vertaling")}
        r.update({f: alt["variabelen"][f] for f in ("thema", "boekgroep", "lengte", "bron")})
        r.update({"hook": "", "caption": "", "hashtags": [], "uitleg": "", "betekenis": "", "toepassing": ""})
        p["reserve"] = r
        gebruikt.add(r["vers_id"])
        uit.append({"post": p["id"], "formaat": p["variabelen"]["formaat"], "hook_stijl": p["variabelen"]["hook_stijl"],
                    "uitleg_op_beeld": p["variabelen"].get("uitleg_op_beeld"), "reserve": r["ref"], "tekst": r["tekst"]})
    bewaar("data/posts.json", posts)
    print(json.dumps(uit, ensure_ascii=False, indent=1))
    print("\nVul per post onder 'reserve' in: hook, caption, hashtags, en bij carrousel betekenis en toepassing (zelfde regels als TAKEN.md).")

def cmd_kandidaten(n=60):
    """Toont nog niet beoordeelde verzen uit de hele Bijbel (voor de wekelijkse keuring)."""
    for x in laad("data/bijbel_kandidaten.json", [])[:int(n)]:
        print(f"{x['id']} | {x['ref']} | {x['thema']} | {x['tekst']}")

def cmd_keur(oordeel, ids):
    """keur goed ID ID ... of keur af ID ID ...: past de pool aan en bouwt hem opnieuw."""
    pad = "data/pool_goedgekeurd.json" if oordeel == "goed" else "data/pool_afgekeurd.json"
    lijst = laad(pad, [])
    lijst += [i for i in ids if i not in lijst]
    bewaar(pad, lijst)
    subprocess.run([sys.executable, P("tools/bouw_bijbel.py")], check=True)
    print(len(ids), "verzen", "goedgekeurd" if oordeel == "goed" else "afgekeurd")

def cmd_opgelost():
    """Markeert alle huidige fouten in het logboek als opgelost (verdwijnen uit de rode balk)."""
    log = laad("data/logboek.json", [])
    n = 0
    for l in log:
        if l.get("soort") == "fout" and not l.get("opgelost"):
            l["opgelost"] = True; n += 1
    bewaar("data/logboek.json", log)
    print(n, "fouten als opgelost gemarkeerd")

def cmd_check():
    cfg = laad("config.json"); verzen = laad("data/verzen.json")
    ok = True
    for k in ("github_repo", "handle"):
        if not cfg.get(k):
            print("ONTBREEKT in config:", k); ok = False
    print(len(verzen), "versen;", "pauze:", cfg["pauze"])
    sys.exit(0 if ok else 1)

def cmd_aanvullen(alleen_check=False):
    """Video's zonder muziek (gemaakt in een run zonder bibleverse-materiaal) alsnog muziek geven en opnieuw maken.
    Draait in GitHub Actions met MATERIAAL_PAT. Met 'check': exit 0 als er iets aan te vullen is, anders 1."""
    posts = laad("data/posts.json", [])
    vandaag = dt.date.today().isoformat()
    nodig = [p for p in posts if p["datum"] >= vandaag and p["status"] in ("gerenderd", "gepland", "klaar_voor_render")
             and p["variabelen"].get("formaat") == "video" and not p.get("muziek") and not p.get("gemist")]
    if alleen_check:
        print(len(nodig), "video's zonder muziek"); sys.exit(0 if nodig else 1)
    if not nodig:
        return
    mat = materiaal(laad("config.json"))
    if not mat["muziek"]:
        print("Geen muziek beschikbaar; niets aangevuld"); return
    rnd = random.Random(vandaag)
    for p in nodig:
        p["muziek"] = minst_gebruikt(mat["muziek"], posts, "muziek", rnd)
        p["status"] = "opnieuw_maken"
    bewaar("data/posts.json", posts)
    for d in sorted({p["datum"] for p in nodig}):
        cmd_render(d)
    activiteit("video", f"Muziek toegevoegd aan {len(nodig)} video('s): " + ", ".join(p["ref"] for p in nodig))
    cmd_log(f"Muziek alsnog toegevoegd aan {len(nodig)} video('s)", "info")
    cmd_dashboard()

# ---------- Zelfherstel ----------
NOOD_DOEL = 6

def herstel(probleem, actie, ok=True):
    """Legt vast wat het systeem zelf heeft opgelost (dashboard: Zelfherstel; kantoor: de Controller)."""
    h = laad("data/herstel.json", [])
    h.append({"t": dt.datetime.now().isoformat(timespec="minutes"), "probleem": probleem, "actie": actie, "ok": ok})
    bewaar("data/herstel.json", h[-200:])
    activiteit("controller", ("Zelf opgelost: " if ok else "Opgevangen: ") + actie, "done" if ok else "error")
    cmd_log(f"Zelfherstel: {probleem} \u2192 {actie}", "info")

def nood_klaar():
    return [n for n in laad("data/noodvoorraad.json", []) if n["status"] == "gerenderd"]

def noodinzet(nu):
    """Staan er vandaag minder posts klaar dan ingesteld? Zet dan posts uit de noodvoorraad op de vrije tijdsloten."""
    if nu.hour < 6:
        return 0
    cfg = laad("config.json")
    if cfg.get("pauze"):
        return 0
    posts = laad("data/posts.json", [])
    d = nu.date().isoformat()
    vandaag = [p for p in posts if p["datum"] == d]
    actief = [p for p in vandaag if p["status"] in ("gerenderd", "gepubliceerd", "gepland", "fout")]
    tekort = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"]) - len(actief)
    if tekort <= 0:
        return 0
    bezet = {p["variabelen"].get("tijdslot") for p in actief}
    grens = (nu + dt.timedelta(minutes=20)).strftime("%H:%M")
    vrij = [t for t in DIMENSIES["tijdslot"] if t not in bezet and t >= grens]
    voorraad = laad("data/noodvoorraad.json", [])
    gezet = 0
    for slot in vrij[:tekort]:
        kl = [n for n in voorraad if n["status"] == "gerenderd"]
        if not kl:
            cmd_log("Noodvoorraad is op: er staan vandaag te weinig posts klaar.", "fout", code="nood_op")
            break
        n = kl[0]; voorraad.remove(n)
        n = dict(n, id=f"{d}-n{slot.replace(':', '')}", datum=d, status="gerenderd", nood=True, goedgekeurd=True)
        n["variabelen"] = dict(n["variabelen"], tijdslot=slot, tijdslot_fb=None)
        n["keuzebron"] = dict(n.get("keuzebron", {}), tijdslot="nood")
        posts.append(n); gezet += 1
        herstel(f"Geen post klaar voor {d} {slot}", f"noodpost {n['ref']} ingezet om {slot}")
    if gezet:
        bewaar("data/posts.json", posts); bewaar("data/noodvoorraad.json", voorraad)
    return gezet

def standaard_opties(tekst):
    """Drie nette antwoordopties die meteen klaarstaan voor een nieuwe reactie. Claude vervangt ze in de
    volgende run door antwoorden op maat (veld 'opties'). Bij twijfel: warm, kort, zonder discussie."""
    t = (tekst or "").lower()
    if any(w in t for w in ("bid", "gebed", "ziek", "verdriet", "moeilijk", "zwaar", "overleden", "angst", "bang")):
        return ["Wat fijn dat je dit deelt. We bidden met je mee 🤍",
                "Dank je dat je dit met ons deelt. Je staat er niet alleen voor, God is dichtbij.",
                "We denken aan je en bidden voor je. Veel sterkte 🙏"]
    if "?" in t:
        return ["Goede vraag! Dank je dat je meedenkt 🙏",
                "Mooie vraag. Wat denk jij er zelf over?",
                "Dank je voor je vraag. Lees het hele hoofdstuk eens, dat geeft vaak extra licht op het vers."]
    return ["Amen 🙏 Fijn dat dit vers je raakt.",
            "Dank je wel! Gods zegen voor vandaag 🤍",
            "Mooi dat je meeleest. Fijne dag!"]

def cmd_verzoek(vid=None, status=None, *antwoord):
    """Verzoeken uit het dashboard ('Vraag Claude'). Zonder argumenten: toon open verzoeken.
    Met argumenten: verzoek ID op status 'bezig' of 'klaar' zetten, met een kort antwoord voor Joshua."""
    v = laad("data/verzoeken.json", [])
    if not vid:
        for x in v:
            if x["status"] in ("wacht", "bezig"):
                print(x["id"], x["status"], "|", x["tekst"])
        return
    for x in v:
        if x["id"] == vid:
            x["status"] = status
            if antwoord:
                x["antwoord"] = " ".join(antwoord)
            x["bijgewerkt"] = dt.datetime.now().isoformat(timespec="minutes")
    bewaar("data/verzoeken.json", v)
    if status == "klaar":
        activiteit("controller", "Verzoek van Joshua afgehandeld")

def cmd_overleg(*tekst):
    """Tussentijds overleg vastleggen (verschijnt op het whiteboard in de vergaderruimte).
    Geef de punten als losse argumenten; begin een voorstel met 'Voorstel:'."""
    o = laad("data/overleg.json", [])
    o.append({"t": dt.datetime.now().isoformat(timespec="minutes"), "punten": [x for x in tekst if x.strip()]})
    bewaar("data/overleg.json", o[-12:])
    activiteit("analist", "Tussentijds overleg gehouden")

def cmd_nood(actie="status"):
    """Noodvoorraad: kant-en-klare posts voor als een dagelijkse run mislukt.
    status | aanvullen (lege posts erbij tot NOOD_DOEL; Claude schrijft de teksten) | render"""
    cfg = laad("config.json")
    voorraad = laad("data/noodvoorraad.json", [])
    if actie == "status":
        print(f"{len([n for n in voorraad if n['status'] == 'gerenderd'])} klaar, "
              f"{len([n for n in voorraad if n['status'] == 'wacht_op_tekst'])} wachten op tekst (doel {NOOD_DOEL})")
        return
    if actie == "aanvullen":
        posts = laad("data/posts.json", [])
        gebruikt = {p.get("vers_id") for p in posts} | {n.get("vers_id") for n in voorraad}
        uitgesloten = set(cfg.get("verzen_uitsluiten", []))
        kand = [v for v in alle_verzen() if v["bron"] == "bekend" and v["lengte"] != "lang"
                and v["id"] not in gebruikt and v["ref"] not in uitgesloten]
        bank = _bank(cfg)
        if bank is not None:  # zelfstandig: alleen verzen waarvan de teksten in de tekstbank staan
            kand = [v for v in kand if v["id"] in bank] or [v for v in alle_verzen() if v["id"] in bank and v["id"] not in gebruikt]
        rnd = random.Random(dt.datetime.now().isoformat())
        rnd.shuffle(kand)
        frisse = ["zonsopgang", "hemelsblauw", "paars", "roze", "bosgroen", "mint", "perzik", "zand"]
        nieuw = 0
        while len(voorraad) < NOOD_DOEL and kand:
            v = kand.pop()
            st = frisse[(len(voorraad) + rnd.randrange(8)) % len(frisse)]
            var = dict(HUISSTIJLEN[st], huisstijl=st, thema=v.get("thema"), hook_stijl="geen", formaat="carrousel",
                       uitleg_op_beeld=False, achtergrondbron="verloop", boekgroep=v["boekgroep"], lengte=v["lengte"],
                       bron=v["bron"], vraag_onderaan=True, opening="vers", tijdslot=None, hook_op_beeld=False)
            voorraad.append({"id": f"nood-{dt.date.today().strftime('%Y%m%d')}-{len(voorraad) + 1}-{rnd.randrange(1000)}",
                             "status": "wacht_op_tekst", "vers_id": v["id"], "ref": v["ref"], "tekst": v["tekst"],
                             "vertaling": v.get("vertaling", "SV"), "variabelen": var,
                             "keuzebron": {k: "nood" for k in DIMENSIES}, "hook": "", "beeld_hook": "", "caption": "",
                             "hashtags": [], "uitleg": "", "betekenis": "", "toepassing": "", "kernwoord": "", "verhaal_hook": "",
                             "media": None, "media_extra": [], "beeld": None, "muziek": None, "geluid": None,
                             "metricool": {}, "stats": {}})
            nieuw += 1
        bewaar("data/noodvoorraad.json", voorraad)
        print(nieuw, "lege noodposts toegevoegd; schrijf hun teksten in data/noodvoorraad.json en draai: nood render")
        return
    if actie == "auto":  # zonder Claude: aanvullen, teksten uit de tekstbank, renderen
        if len([n for n in voorraad if n["status"] == "gerenderd"]) >= NOOD_DOEL:
            print("Noodvoorraad is vol"); return
        cmd_nood("aanvullen")
        import tekstbank
        bank, voorraad = tekstbank.laad(), laad("data/noodvoorraad.json", [])
        for n in voorraad:
            if n["status"] == "wacht_op_tekst" and n["vers_id"] in bank:
                tekstbank.vul_post(n, bank[n["vers_id"]], cfg)
        bewaar("data/noodvoorraad.json", voorraad)
        cmd_nood("render")
        klaar = len(nood_klaar())
        gezond("nood", klaar >= NOOD_DOEL, f"noodvoorraad {klaar}/{NOOD_DOEL}")
        if klaar:
            cmd_log(f"Noodvoorraad zelf aangevuld uit de tekstbank: {klaar} van {NOOD_DOEL} klaar")
        return
    if actie == "render":
        n_ok = 0
        for n in voorraad:
            if n["status"] not in ("wacht_op_tekst", "klaar_voor_render"):
                continue
            probleem = valideer_tekst(n, cfg)
            if probleem:
                print("NIET GERENDERD", n["id"], probleem); continue
            render_een(n, cfg, "nood"); n_ok += 1
        bewaar("data/noodvoorraad.json", voorraad)
        print(n_ok, "noodposts gemaakt;", len([n for n in voorraad if n["status"] == "gerenderd"]), "klaar")

def _bankvers_voor(p, posts, bank, cfg, rnd):
    """Post zonder bankteksten (bijv. uit een oude planning): ander vers uit de bank met hetzelfde thema."""
    grens = (dt.date.fromisoformat(p["datum"]) - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {q["vers_id"] for q in posts if q["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    vrij = [x for x in alle_verzen() if x["id"] in bank and x["id"] not in recent] or _oudste_bankverzen(bank, posts, cfg)
    if not vrij:
        return False
    zelfde = [x for x in vrij if x["thema"] == p["variabelen"]["thema"]] or vrij
    x = rnd.choice(zelfde)
    p.update({k: x[k] for k in ("ref", "tekst")}); p["vers_id"] = x["id"]; p["vertaling"] = x.get("vertaling", "SV")
    for f in ("thema", "boekgroep", "lengte", "bron"):
        p["variabelen"][f] = x[f]
    if p["variabelen"].get("opening") == "stopper" and len(x["tekst"]) < 70:
        p["variabelen"]["opening"] = "vers"
    return True

def automaak_dagen(cfg=None, posts=None):
    """Dagen (morgen en overmorgen) waarvoor nog niet genoeg posts klaarstaan."""
    cfg = cfg or laad("config.json"); posts = posts if posts is not None else laad("data/posts.json", [])
    nodig = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"])
    uit = []
    for k in (1, 2):
        d = (dt.date.today() + dt.timedelta(days=k)).isoformat()
        klaar = [p for p in posts if p["datum"] == d and p["status"] in ("gerenderd", "gepubliceerd", "goedgekeurd", "deels")]
        if len(klaar) < nodig or any(p["datum"] == d and p["status"] == "wacht_op_tekst" for p in posts):
            uit.append(d)
    return uit

def _bank_lijst(cfg, posts):
    """Voor het dashboard: alle verzen in de tekstbank met herkenningszin, laatst geplaatst en of ze uit staan."""
    import tekstbank
    bank = tekstbank.laad() or {}
    uit = set(cfg.get("verzen_uitsluiten", []))
    laatst, aantal = {}, {}
    for p in posts:
        v = p.get("vers_id")
        if v:
            laatst[v] = max(laatst.get(v, ""), p["datum"]); aantal[v] = aantal.get(v, 0) + 1
    return [{"id": k, "ref": e.get("ref", k), "kw": e.get("kw", ""), "herkenning": (e.get("hooks") or {}).get("herkenning", ""),
             "uit": k in uit, "laatst": laatst.get(k), "n": aantal.get(k, 0)} for k, e in bank.items()]

def cmd_hashtags_testen():
    """Geplande posts (vanaf morgen, nog niet geplaatst) verdelen over de drie hashtag-stijlen, zodat de test meteen start."""
    import tekstbank
    cfg, posts = laad("config.json"), laad("data/posts.json", [])
    bank = tekstbank.laad() or {}
    morgen = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    opties = DIMENSIES["hashtag_stijl"]
    n = 0
    for p in sorted(posts, key=lambda x: (x["datum"], x["id"])):
        e = bank.get(p.get("vers_id"))
        if (p["datum"] < morgen or p["status"] not in ("gerenderd", "goedgekeurd") or p.get("gepubliceerd") or not e
                or p["variabelen"].get("hashtag_stijl")):
            continue
        st = opties[n % len(opties)]
        p["variabelen"]["hashtag_stijl"] = st
        p.setdefault("keuzebron", {})["hashtag_stijl"] = "test"
        p["hashtags"] = tekstbank.hashtags_voor(e, p, st, cfg)
        n += 1
    bewaar("data/posts.json", posts)
    print(f"{n} geplande posts verdeeld over {', '.join(opties)}")

def cmd_reels_vernieuwen():
    """Geplande reels (vanaf morgen, nog niet geplaatst) opnieuw laten maken in het huidige reelformaat."""
    cfg, posts = laad("config.json"), laad("data/posts.json", [])
    strat = vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    morgen = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    import tekstbank
    bank = tekstbank.laad()
    bank = bank.get("verzen", bank) if isinstance(bank, dict) else {}
    n = 0
    for p in posts:
        v = p["variabelen"]
        if p["datum"] < morgen or v.get("formaat") != "video" or p["status"] not in ("gerenderd", "goedgekeurd", "opnieuw_maken") or p.get("gepubliceerd"):
            continue
        if cfg.get("reel_formaat") != "situatie" or (v.get("reel_stijl") == "situatie" and p["status"] != "opnieuw_maken"):
            continue
        rnd = random.Random(p["id"] + "situatie")
        v["reel_stijl"], v["reel_haak"] = "situatie", "geen"
        p.setdefault("keuzebron", {})["reel_stijl"] = "vaste regel"
        for d in ("reel_plaatsing", "reel_scene"):
            v[d], p["keuzebron"][d] = kies_optie(d, strat, cfg["verkenning"], rnd)
        e = bank.get(p["vers_id"]) or {}
        if not p.get("reel_herkenning") and (e.get("hooks") or {}).get("herkenning"):
            p["reel_herkenning"] = e["hooks"]["herkenning"]
        if not p.get("uitleg") and not p.get("reel_uitleg") and e.get("uitleg"):
            p["reel_uitleg"] = e["uitleg"]
        p["status"] = "opnieuw_maken"; n += 1
    bewaar("data/posts.json", posts)
    print(f"{n} reels gaan opnieuw gemaakt worden")

def cmd_ochtend_vernieuwen():
    """Geplande 07:30-posts (vanaf morgen, nog niet geplaatst) krijgen een ochtendvers en ochtendstijl."""
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    morgen = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    import tekstbank
    n = 0
    for p in sorted(posts, key=lambda x: x["datum"]):
        v = p["variabelen"]
        if p["datum"] < morgen or v.get("tijdslot", "99") >= "10:00" or p.get("reeks") or p.get("gepubliceerd"):
            continue
        if p["status"] not in ("gerenderd", "goedgekeurd", "wacht_op_tekst", "opnieuw_maken"):
            continue
        if p["vers_id"] not in tekstbank.OCHTEND_VERZEN:
            rest = [x for x in posts if x is not p]
            nieuw = None
            for poging in range(30):
                c = kies_posts(p["datum"], cfg, strat, rest, laad("data/verzen.json"), None, 0, 1, {"12:15", "17:45", "20:30", "22:00"},
                               random.Random(f"{p['id']}ochtend{poging}"), reeks=False)[0]
                if c["variabelen"]["tijdslot"] < "10:00" and c["vers_id"] in tekstbank.OCHTEND_VERZEN:
                    nieuw = c; break
            if not nieuw:
                continue
            p.update({k: nieuw[k] for k in ("vers_id", "ref", "tekst", "vertaling")})
            for f in ("thema", "boekgroep", "lengte", "bron"):
                v[f] = nieuw["variabelen"][f]
            p.update({"hook": "", "caption": "", "hashtags": [], "uitleg": "", "betekenis": "", "toepassing": "",
                      "media": None, "media_extra": [], "thumb": None})
        if v.get("formaat") == "carrousel" and v.get("huisstijl") not in LICHTE_STIJLEN:
            v["huisstijl"] = random.Random(p["id"] + "licht").choice(LICHTE_STIJLEN)
            v.update(HUISSTIJLEN[v["huisstijl"]])
            p.setdefault("keuzebron", {})["huisstijl"] = "ochtend"
        v["tijdslot"] = "07:30"
        p["status"] = "wacht_op_tekst"; n += 1
        print(p["datum"], p["ref"], v.get("formaat"))
    bewaar("data/posts.json", posts)
    print(f"{n} ochtendposts gaan opnieuw gemaakt worden")

def cmd_markeren_inplannen(*ids_kleuren):
    """Zet geplande reels (nog niet geplaatst) om naar de meelees-reel. Argumenten: id:kleur, bijv. 2026-11-14-2:mint.
    Een id met kleur 'situatie' gaat juist terug naar de herkenbare situatie-reel."""
    cfg, strat = laad("config.json"), vul_strategie_aan(laad("strategie.json") or nieuwe_strategie())
    posts = laad("data/posts.json", [])
    import tekstbank
    bank = tekstbank.laad(); bank = bank.get("verzen", bank)
    for x in ids_kleuren:
        pid, kleur = x.split(":")
        p = next((q for q in posts if q["id"] == pid), None)
        if not p or p.get("gepubliceerd") or p["variabelen"].get("formaat") not in ("video", "carrousel"):
            print("overgeslagen", pid); continue
        v = p["variabelen"]; kb = p.setdefault("keuzebron", {})
        if v.get("formaat") == "carrousel":
            v["carrousel_stijl"], v["reel_kleur"], v["opening"] = "markeren", kleur, "vers"
            kb["carrousel_stijl"] = kb["reel_kleur"] = "ingepland"
            if p["status"] != "wacht_op_tekst":
                p["status"] = "opnieuw_maken"
            print(pid, p["ref"], "carrousel markeren", kleur); continue
        if kleur == "situatie":
            rr = random.Random(pid + "situatie")
            v["reel_stijl"], v["reel_haak"], v["reel_kleur"] = "situatie", "geen", None
            for d in ("reel_plaatsing", "reel_scene"):
                v[d], kb[d] = kies_optie(d, strat, cfg["verkenning"], rr)
            kb["reel_stijl"], kb["reel_kleur"] = "vaste regel", "n.v.t."
            p["reel_herkenning"] = (bank.get(p["vers_id"], {}).get("hooks") or {}).get("herkenning", "")
        else:
            v["reel_stijl"], v["reel_haak"], v["reel_kleur"] = "markeren", "geen", kleur
            for d in ("reel_plaatsing", "reel_scene"):
                v[d] = None
            kb["reel_stijl"], kb["reel_kleur"] = "ingepland", "ingepland"
        p["status"] = "opnieuw_maken"
        print(pid, p["ref"], v["reel_stijl"], v.get("reel_kleur"))
    bewaar("data/posts.json", posts)

def cmd_automaak(modus=""):
    """Zelfstandig posts maken, zonder Claude: kiezen, teksten uit de tekstbank, renderen.
    'check' geeft exit 0 als er werk is (voor GitHub Actions)."""
    import tekstbank
    cfg = laad("config.json")
    if cfg.get("pauze") or not cfg.get("zelfstandig"):
        if modus == "check":
            sys.exit(1)
        print("Pauze staat aan of 'zelfstandig' staat uit."); return
    dagen = [modus] if modus and modus != "check" else automaak_dagen(cfg)
    if modus == "check":
        vandaag = dt.date.today().isoformat()
        opnieuw = any(p["status"] == "opnieuw_maken" and p["datum"] >= vandaag for p in laad("data/posts.json", []))
        sys.exit(0 if dagen or opnieuw or len(nood_klaar()) < NOOD_DOEL else 1)
    bank = tekstbank.laad()
    activiteit("controller", "Zelfstandig posts maken voor " + ", ".join(dagen) if dagen else "Alles staat klaar", "busy" if dagen else "done")
    gemaakt, mislukt = 0, []
    for d in dagen:
        cmd_kies(d)
        posts = laad("data/posts.json", [])
        rnd = random.Random("bank" + d)
        grens14 = (dt.date.fromisoformat(d) - dt.timedelta(days=14)).isoformat()
        vermijd = {q.get("hook", "").split(": ", 1)[-1].strip() for q in posts if q["datum"] >= grens14 and q.get("hook")}
        for p in posts:
            if p["datum"] != d or p["status"] != "wacht_op_tekst":
                continue
            if p["vers_id"] not in bank and not _bankvers_voor(p, posts, bank, cfg, rnd):
                mislukt.append(p["id"]); continue
            tekstbank.vul_post(p, bank[p["vers_id"]], cfg, vermijd)
            vermijd.add(p.get("hook", "").split(": ", 1)[-1].strip())
            probleem = valideer_tekst(p, cfg)
            if probleem:  # bankitem klopt niet bij deze post: probeer een ander vers
                if _bankvers_voor(p, posts, bank, cfg, rnd):
                    tekstbank.vul_post(p, bank[p["vers_id"]], cfg, vermijd)
                    probleem = valideer_tekst(p, cfg)
            if probleem:
                mislukt.append(f"{p['id']} ({probleem})")
        bewaar("data/posts.json", posts)
        try:
            cmd_render(d)
        except SystemExit:
            pass
        gemaakt += len([p for p in laad("data/posts.json", []) if p["datum"] == d and p["status"] == "gerenderd"])
    # posts die opnieuw gemaakt moeten worden (bijv. reels in een nieuwe stijl)
    vandaag = dt.date.today().isoformat()
    for d in sorted({p["datum"] for p in laad("data/posts.json", []) if p["status"] == "opnieuw_maken" and p["datum"] >= vandaag} - set(dagen)):
        try:
            cmd_render(d)
        except SystemExit:
            pass
    if mislukt:
        cmd_log("Zelfstandig maken lukte niet voor: " + ", ".join(mislukt) + ". De noodvoorraad vangt lege plekken op.", "fout", "te_weinig")
    if dagen:
        cmd_log(f"Zelfstandig {gemaakt} posts klaargezet voor {', '.join(dagen)} (teksten uit de tekstbank).")
    v = bank_voorraad(cfg)
    if v["dagen"] < 10:
        cmd_log(f"Tekstbank bijna op: nog genoeg nieuwe verzen voor ongeveer {v['dagen']} dagen ({v['vrij']} van {v['verzen']}). "
                "Daarna herhaalt het systeem de oudste verzen.", "fout", "tekstbank")
    activiteit("controller", "Posts klaargezet uit de tekstbank")
    gezond("maken", not mislukt, f"{gemaakt} posts klaargezet" + (f", {len(mislukt)} mislukt" if mislukt else ""))
    cmd_plan()

def cmd_tekstbank(actie="status"):
    """status | check | zaai (bestaande handgeschreven posts in de bank zetten)"""
    import tekstbank
    bank = tekstbank.laad()
    verzen = {x["id"]: x for x in alle_verzen()}
    if actie == "zaai":
        n = 0
        for p in laad("data/posts.json", []) + laad("data/noodvoorraad.json", []):
            if p["vers_id"] in bank:
                continue
            e = tekstbank.uit_post(p)
            if e and not tekstbank.problemen(p["vers_id"], e, p["tekst"]):
                bank[p["vers_id"]] = e; n += 1
        tekstbank.bewaar(bank); print(n, "verzen uit bestaande posts toegevoegd")
    elif actie == "check":
        fout = 0
        for k, e in bank.items():
            pr = tekstbank.problemen(k, e, verzen[k]["tekst"] if k in verzen else None)
            if k not in verzen:
                pr.append("vers_id onbekend")
            elif e.get("ref") != verzen[k]["ref"]:
                pr.append(f"ref {e.get('ref')} hoort {verzen[k]['ref']} te zijn")
            if pr:
                fout += 1; print(k, "|", "; ".join(pr))
        print(len(bank), "verzen,", fout, "met problemen")
        if fout:
            sys.exit(1)
    print(json.dumps(bank_voorraad(), ensure_ascii=False))

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("cmd"); a.add_argument("args", nargs="*")
    a.add_argument("--datum", default=dt.date.today().isoformat())
    x = a.parse_args()
    {"kies": lambda: cmd_kies(x.datum), "render": lambda: cmd_render(x.datum), "plan": lambda: cmd_plan(),
        "gezond": lambda: gezond(x.args[0], True, " ".join(x.args[1:])),
        "vervang": lambda: cmd_vervang(x.args[0], " ".join(x.args[1:])),
        "kandidaten": lambda: cmd_kandidaten(*(x.args[:1] or [60])),
        "reserve": lambda: cmd_reserve(x.datum),
        "experiment": lambda: cmd_experiment(),
        "keur": lambda: cmd_keur(x.args[0], x.args[1:]),
     "registreer": lambda: cmd_registreer(*x.args), "stats": lambda: cmd_stats(x.args[0]),
     "leer": cmd_leer, "dashboard": cmd_dashboard, "check": cmd_check,
     "log": lambda: cmd_log(*x.args), "vers": lambda: cmd_vers(*x.args), "opruimen": lambda: cmd_opruimen(*x.args), "opgelost": cmd_opgelost,
     "verzoek": lambda: cmd_verzoek(*x.args),
     "overleg": lambda: cmd_overleg(*x.args),
     "nood": lambda: cmd_nood(*(x.args[:1] or ["status"])),
     "automaak": lambda: cmd_automaak(*(x.args[:1] or [""])),
     "reels_vernieuwen": lambda: cmd_reels_vernieuwen(),
     "ochtend_vernieuwen": lambda: cmd_ochtend_vernieuwen(),
     "markeren_inplannen": lambda: cmd_markeren_inplannen(*x.args),
     "hashtags_testen": lambda: cmd_hashtags_testen(),
     "tekstbank": lambda: cmd_tekstbank(*(x.args[:1] or ["status"])),
     "aanvullen": lambda: cmd_aanvullen(bool(x.args and x.args[0] == "check"))}[x.cmd]()
