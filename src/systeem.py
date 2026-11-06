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
DIMENSIES = {
    "palet": ["nacht", "zand", "salie", "zonsopgang", "zwart_goud", "oceaan", "roze_avond", "wit"],
    "lettertype": ["playfair", "cormorant", "dmserif", "lora", "montserrat"],
    "layout": ["centraal", "citaat", "kader"],
    "achtergrond": ["effen", "verloop", "licht"],
    "thema": ["troost", "moed", "liefde", "hoop", "vertrouwen", "wijsheid", "humor_herkenbaar",
              "dankbaarheid", "identiteit", "vrede_rust"],
    "hook_stijl": ["vraag", "herkenning", "uitdaging", "rustig", "geen"],
    "hook_op_beeld": [True, False],
    "formaat": ["afbeelding", "video"],
    "tijdslot": ["07:30", "12:15", "17:45", "20:30", "22:00"],
}

def nieuwe_strategie():
    return {"versie": 1, "bijgewerkt": None,
            "gewichten": {d: {str(o): 1.0 for o in opts} for d, opts in DIMENSIES.items()},
            "metingen": {d: {str(o): 0 for o in opts} for d, opts in DIMENSIES.items()},
            "inzichten": []}

def _terug(d, s):
    """String uit json terug naar het juiste type."""
    for o in DIMENSIES[d]:
        if str(o) == s:
            return o
    return s

def kies_optie(dim, strat, verkenning, rnd, uitsluiten=()):
    opties = [o for o in DIMENSIES[dim] if o not in uitsluiten]
    if rnd.random() < verkenning:
        return rnd.choice(opties), "verkenning"
    g = strat["gewichten"][dim]
    gew = [max(0.05, g.get(str(o), 1.0)) ** 2 for o in opties]  # kwadraat: winnaars krijgen voorrang
    return rnd.choices(opties, weights=gew)[0], "strategie"

# ---------- Kiezen ----------
def cmd_kies(datum):
    cfg, strat = laad("config.json"), laad("strategie.json") or nieuwe_strategie()
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
    nieuw = []
    for i in range(n):
        v, bron = {}, {}
        for dim in DIMENSIES:
            uit = gebruikte_slots if dim == "tijdslot" else ()
            v[dim], bron[dim] = kies_optie(dim, strat, cfg["verkenning"], rnd, uit)
        gebruikte_slots.add(v["tijdslot"])
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
                      "media": None, "media_url": None, "metricool": {}, "stats": {}})
    bewaar("data/posts.json", posts + nieuw)
    print(json.dumps([{k: p[k] for k in ("id", "ref", "tekst", "variabelen")} for p in nieuw], ensure_ascii=False, indent=1))
    print("\nVul nu per post 'hook', 'beeld_hook' (als hook_op_beeld true is), 'caption' en 'hashtags' in data/posts.json in.")

# ---------- Renderen ----------
def cmd_render(datum):
    from render import maak_afbeelding, maak_video
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
        ext = "mp4" if p["variabelen"]["formaat"] == "video" else "jpg"
        rel = f"docs/media/{datum[:7]}/{p['id']}.{ext}"
        os.makedirs(os.path.dirname(P(rel)), exist_ok=True)
        (maak_video if ext == "mp4" else maak_afbeelding)(p, P(rel))
        p["media"] = rel
        if cfg.get("github_repo"):
            eig, naam = cfg["github_repo"].split("/")
            p["media_url"] = f"https://{eig}.github.io/{naam}/{rel[len('docs/'):]}"
        p["status"] = "gerenderd"
        print("OK", p["id"], rel)
    bewaar("data/posts.json", posts)
    if fouten:
        sys.exit(1)

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
            uit.append((p, plat, min(score, 5.0)))
    return uit

# ---------- Leren ----------
def cmd_leer():
    cfg = laad("config.json")
    strat = laad("strategie.json") or nieuwe_strategie()
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
        lijst.append({"id": p["id"], "datum": p["datum"], "ref": p["ref"], "tekst": p["tekst"], "hook": p["hook"],
                      "status": p["status"], "variabelen": p["variabelen"], "media": p.get("media"), "media_url": p.get("media_url"),
                      "platformen": list(p.get("gepubliceerd", {}).keys()),
                      "links": {k: v.get("url") for k, v in p.get("gepubliceerd", {}).items()}, "totaal": tot, "score": sc.get(p["id"], {})})
    rapporten = sorted(os.listdir(P("rapporten"))) if os.path.isdir(P("rapporten")) else []
    data = {"gegenereerd": dt.datetime.now().isoformat(timespec="minutes"), "repo": cfg.get("github_repo", ""),
            "config": {k: cfg.get(k) for k in ("pauze", "kanaalnaam", "posts_per_dag", "verkenning", "platformen_actief")},
            "strategie": strat, "posts": lijst,
            "leergeschiedenis": laad("data/leergeschiedenis.json", []),
            "laatste_rapport": laad(f"rapporten/{rapporten[-1]}") if rapporten else None,
            "logboek": laad("data/logboek.json", [])[-60:],
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
     "log": lambda: cmd_log(*x.args), "vers": lambda: cmd_vers(*x.args)}[x.cmd]()
