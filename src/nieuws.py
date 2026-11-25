"""Nieuws als aanleiding voor een post (punt 4).

Drie keer per dag (rond 7, 12 en 17 uur) leest GitHub Actions een paar nieuwsfeeds.
- Koppen worden alleen gebruikt als SIGNAAL: in de post zelf komt nooit nieuwstekst of een kop.
  Op het dashboard staat de kop met bronvermelding, zodat Joshua ziet waarom een post is gemaakt.
- Politiek nieuws wordt nooit automatisch een post: het wordt een voorstel (max 1 per dag), Joshua beslist.
  De post blijft neutraal: geen partij, politicus of standpunt.
- Licht nieuws (weer, Sinterklaas, sport, drukte...) wordt automatisch een post: de eerstvolgende
  carrousel van vandaag of morgen krijgt een vers uit de tekstbank met een passend thema en opent
  met een 'verhaal eerst'-zin die bij de aanleiding past.
- Zwaar nieuws (rampen, aanslagen, doden) wordt nooit automatisch geplaatst: het wordt een voorstel
  op het dashboard (en WhatsApp). Ook na goedkeuring gaat zo'n post pas 6 uur na het nieuws online.
- Maximaal config.nieuws.max_per_dag nieuwsposts per dag; dezelfde soort aanleiding niet vaker dan eens per 3 dagen.
"""
import datetime as dt, email.utils, json, os, random, re, sys, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S
import tekstbank

FEEDS = [("NOS", "https://feeds.nos.nl/nosnieuwsalgemeen"),
         ("NOS", "https://feeds.nos.nl/nosnieuwsbinnenland"),
         ("NU.nl", "https://www.nu.nl/rss/Algemeen")]

POLITIEK = ["regering", "kabinet", "minister", "verkiezing", "partij", "tweede kamer", "eerste kamer", "coalitie", "premier",
            "president", "formatie", "motie", "kamerlid", "pvv", "vvd", "d66", "cda", "bbb", "groenlinks", "nsc",
            "trump", "poetin", "navo", "demonstratie", "protest", "stikstof", "asiel", "migratie",
            "vredesgesprek", "vredesoverleg", "vredesakkoord", "staakt-het-vuren", "bestand ", "oekraïne", "rusland",
            "gaza", "israël", "iran", "sancties", "top in", "benelux-top", "eu-top"]
ZWAAR = ["orkaan", "tsunami", "dodelijk", "doden", "dode ", "omgekomen", "aanslag", "ramp", "oorlog", "slachtoffer", "vermoord",
         "schietpartij", "overleden", "explosie", "aardbeving", "overstroming", "neergestort", "gijzeling",
         "vermist", "steekpartij", "brand ", "zwaargewond", "kinderen dood"]
# Zwaar nieuws dat groot genoeg is om een voorstel waard te zijn (de rest wordt genegeerd)
# (geen 'oorlog': lopende oorlogen staan dagelijks in het nieuws, ook in achtergrondverhalen)
ZWAAR_GROOT = ["aanslag", "ramp", "aardbeving", "overstroming", "neergestort", "orkaan", "tsunami"]

# Aanleidingen (nieuws als moment, vanuit de persoonlijke stem; zie KARAKTER.md). Per soort: woorden in de kop (alleen als
# signaal), thema's voor het vers en 'vers_woorden' om een vers te kiezen dat echt bij het onderwerp past.
# De tekst zelf (de openingszin) schrijft het lokale AI-model op de Mac van Joshua; de kop komt nooit in de post.
LICHT = {'storm': {'woorden': ['storm', 'code oranje', 'windstoten', 'zware wind', 'zeer zware windstoten'], 'themas': ['vrede_rust', 'vertrouwen'], 'vers_woorden': ['storm', 'wind', 'golven', 'zee', 'stilte', 'rots', 'fundament', 'anker']},
    'winter': {'woorden': ['sneeuw', 'gladheid', 'ijzel', 'vorst', 'natuurijs', 'winterweer', 'code wit'], 'themas': ['vrede_rust', 'dankbaarheid', 'hoop'], 'vers_woorden': ['sneeuw', 'vorst', 'koud', 'winter', 'ijs', 'wit']},
    'hitte': {'woorden': ['hittegolf', 'tropische temperaturen', 'warmste dag', 'tropisch warm'], 'themas': ['vrede_rust', 'dankbaarheid'], 'vers_woorden': ['schaduw', 'dorst', 'water', 'verkwik', 'koel', 'zon']},
    'regen': {'woorden': ['regenachtig', 'grijze dag', 'veel regen', 'regenbuien', 'regenval', 'natste', 'koudste', 'nat weer', 'somber weer', 'herfstweer'], 'themas': ['hoop', 'troost', 'vrede_rust'], 'vers_woorden': ['regen', 'water', 'wolk', 'licht', 'dauw', 'bron']},
    'sintmaarten': {'woorden': ['sint-maarten', 'sint maarten', 'lampion'], 'themas': ['hoop', 'dankbaarheid', 'liefde'], 'vers_woorden': ['licht', 'lamp', 'kleed', 'mantel', 'delen', 'geven', 'arm']},
    'sinterklaas': {'woorden': ['sinterklaas', 'intocht', 'pakjesavond', 'pepernoten'], 'themas': ['dankbaarheid', 'liefde'], 'vers_woorden': ['gave', 'gaven', 'geven', 'geschenk', 'vreugd', 'kinderen', 'blij']},
    'sport': {'woorden': ['wint goud', 'wereldkampioen', 'europees kampioen', 'olympisch kampioen', 'oranje wint', 'pakt goud'], 'themas': ['dankbaarheid', 'moed'], 'vers_woorden': ['loop', 'wedloop', 'kroon', 'overwin', 'strijd', 'prijs', 'volhoud']},
    'drukte': {'woorden': ['recordfile', 'filedrukte', 'files', 'spitsdrukte', 'ns storing', 'treinstoring'], 'themas': ['vrede_rust', 'wijsheid'], 'vers_woorden': ['stil', 'rust', 'wacht', 'geduld', 'haast']},
    'examens': {'woorden': ['eindexamen', 'examens', 'tentamens'], 'themas': ['moed', 'vertrouwen'], 'vers_woorden': ['wijsheid', 'verstand', 'leer', 'kennis', 'inzicht', 'vertrouw']},
    'klok': {'woorden': ['wintertijd', 'zomertijd', 'klok een uur'], 'themas': ['wijsheid', 'vrede_rust'], 'vers_woorden': ['tijd', 'dagen', 'jaren', 'getij', 'eeuw']},
    'koopjes': {'woorden': ['black friday', 'cyber monday', 'koopjesjagers', 'uitverkoop'], 'themas': ['dankbaarheid', 'wijsheid'], 'vers_woorden': ['schat', 'rijk', 'geld', 'zilver', 'goud', 'koop', 'genoeg']},
    'maandag': {'woorden': ['blue monday', 'somberste dag'], 'themas': ['hoop', 'troost'], 'vers_woorden': ['hoop', 'troost', 'vreugd', 'blij', 'verblijd']}}

PAD = "data/nieuws.json"


def _cfg(cfg):
    n = {"aan": True, "max_per_dag": 2, "licht_automatisch": True}
    n.update(cfg.get("nieuws") or {})
    return n


def ophalen():
    """Lijst van (bron, kop, link, tijd) uit de feeds. Fouten per feed worden genegeerd."""
    uit, gezien = [], set()
    for bron, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bibleverse-bot/1.0"})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
        except Exception as e:
            print("Feed mislukt:", bron, str(e)[:80]); continue
        for item in root.iter("item"):
            kop = (item.findtext("title") or "").strip()
            if not kop or kop.lower() in gezien:
                continue
            gezien.add(kop.lower())
            try:
                t = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "")
            except (TypeError, ValueError):
                t = dt.datetime.now(dt.timezone.utc)
            uit.append({"bron": bron, "kop": kop, "link": item.findtext("link") or "", "t": t.isoformat(timespec="minutes")})
    return uit


# Korte woorden (nsc, navo, iran) alleen aan het begin van een woord, en geen 'partij' in steek-/vechtpartij:
# eerder werden 'marathonschaatsster', 'Winschoten' en 'miljardenschikking' als politiek gezien (zat 'nsc' in).
_NIET_POLITIEK = ["steekpartij", "schietpartij", "vechtpartij", "knokpartij", "feestpartij", "partijtje"]


def _politiek(k):
    for w in _NIET_POLITIEK:
        k = k.replace(w, " ")
    for w in POLITIEK:
        if len(w.strip()) <= 4:
            if re.search(r"(?<![a-zà-ÿ0-9])" + re.escape(w), k):
                return True
        elif w in k:
            return True
    return False


def indelen(kop):
    """(soort, categorie) of None. soort: 'licht' of 'zwaar'."""
    k = " " + kop.lower() + " "
    if any(w in k for w in ZWAAR_GROOT):
        return ("zwaar", "zwaar")
    if _politiek(k):  # ook als er een zwaar woord in staat (bijv. vredesgesprekken over een oorlog)
        return ("politiek", "politiek")
    if any(w in k for w in ZWAAR):  # klein zwaar nieuws (ongeluk, steekpartij): niets mee doen
        return None
    if _politiek(k):
        return ("politiek", "politiek")
    for cat, r in LICHT.items():
        if any(w in k for w in r["woorden"]):
            return ("licht", cat)
    return None


def _doelpost(posts, nu, na=None):
    """Eerstvolgende carrousel van vandaag of morgen die nog niet online is, minstens 90 minuten vooruit."""
    grens = max(nu + dt.timedelta(minutes=90), na or nu)
    kand = []
    for p in posts:
        v = p["variabelen"]
        if p["status"] != "gerenderd" or v.get("formaat") != "carrousel" or p.get("reeks") or v.get("aanleiding") == "nieuws":
            continue
        if p.get("gepubliceerd"):  # al op een platform online (bijv. Facebook eerder dan Instagram): niet meer vervangen
            continue
        try:
            t = dt.datetime.fromisoformat(f"{p['datum']}T{v['tijdslot']}")
            if v.get("tijdslot_fb"):  # Facebook heeft een eigen tijdstip; het vroegste telt
                t = min(t, dt.datetime.fromisoformat(f"{p['datum']}T{v['tijdslot_fb']}"))
        except (ValueError, TypeError):
            continue
        if grens <= t <= nu + dt.timedelta(hours=36):
            kand.append((t, p))
    return min(kand, key=lambda x: x[0])[1] if kand else None


def _themas(cat, zwaar):
    return ["troost", "hoop", "vrede_rust"] if zwaar else (["wijsheid", "vrede_rust", "vertrouwen"] if cat == "politiek" else LICHT[cat]["themas"])


def _passend(x, e, cat, zwaar):
    """Hoe goed past dit vers bij het onderwerp: zoekwoorden in de vers- en uitlegtekst, plus het thema."""
    if zwaar or cat == "politiek":
        return 0
    woorden = LICHT[cat].get("vers_woorden", [])
    tekst = x["tekst"].lower()
    uitleg = " ".join(str(e.get(f, "")) for f in ("kw", "uitleg", "betekenis")).lower()
    return 2 * sum(w in tekst for w in woorden) + sum(w in uitleg for w in woorden) + (1 if x["thema"] in _themas(cat, zwaar) else 0)


def _vrije_verzen(cat, zwaar, cfg, posts, bank):
    grens = (dt.date.today() - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {q["vers_id"] for q in posts if q["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    kand = [x for x in S.alle_verzen() if x["id"] in bank and x["id"] not in recent and bank[x["id"]].get("verhaal")]
    # een vers past als het thema klopt of als het over het onderwerp zelf gaat; de best passende eerst
    kand = [x for x in kand if x["thema"] in _themas(cat, zwaar) or _passend(x, bank[x["id"]], cat, zwaar) >= 2]
    random.Random(f"{cat}{dt.date.today()}").shuffle(kand)  # gelijke scores: wisselend per dag
    return sorted(kand, key=lambda x: -_passend(x, bank[x["id"]], cat, zwaar))


def _vul_nieuws(p, x, zin, item, cat, zwaar, bank, cfg):
    """Maakt van post p een nieuwspost met vers x en de openingszin zin (alleen in het geheugen).
    De openingszin is geschreven in de persoonlijke stem (zie KARAKTER.md) en komt van het lokale AI-model;
    de nieuwskop komt nooit in de post. Er is geen brugzin meer: de persoonlijke zin doet dat zelf."""
    p.update({"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"], "vertaling": x.get("vertaling", "SV")})
    v = p["variabelen"]
    for f in ("thema", "boekgroep", "lengte", "bron"):
        v[f] = x[f]
    v["opening"], v["aanleiding"], v["toon"] = "verhaal", "nieuws", "noor"
    v["achtergrondbron"] = "verloop" if v.get("achtergrondbron") == "beeld" else v.get("achtergrondbron")
    p["beeld"] = None
    p.setdefault("keuzebron", {}).update({"opening": "nieuws", "aanleiding": "nieuws", "toon": "nieuws"})
    tekstbank.vul_post(p, bank[x["id"]], cfg)
    p["verhaal_hook"] = zin
    # de openingszin is ook de eerste regel van de caption (zo snapt de lezer waarom dit vers vandaag)
    delen = p["caption"].split("\n\n")
    p["caption"] = "\n\n".join([zin] + delen[1 if p.get("hook") else 0:])
    p["hook"] = zin
    p["nieuws"] = {"categorie": cat, "kop": item["kop"], "bron": item["bron"], "link": item["link"], "zwaar": zwaar}
    # Joshua keurde dit voorstel al goed, dus geen tweede goedkeuring voor gevoelige woorden
    p.pop("goedkeuring_nodig", None); p.pop("noor_gevoelig", None)


def behoud_nieuws(p, n, zin, cfg=None):
    """Na een verse-wissel: de post blijft een nieuwspost (met dezelfde persoonlijke openingszin)."""
    cfg = cfg or S.laad("config.json")
    bank = tekstbank.laad()
    x = next((y for y in S.alle_verzen() if y["id"] == p["vers_id"]), None)
    if not x or p["vers_id"] not in bank:
        p.pop("nieuws", None)
        return False
    item = {"kop": n["kop"], "bron": n.get("bron", ""), "link": n.get("link", "")}
    _vul_nieuws(p, x, zin, item, n["categorie"], n.get("zwaar", False), bank, cfg)
    return True


def maak_opties(item, cat, zwaar, cfg, posts):
    """Voorstellen met voorvertoning: per kandidaatvers de openingszin die het lokale AI-model schreef (item['concept'])."""
    import copy
    from render import maak_carrousel
    bank = tekstbank.laad()
    alle = {x["id"]: x for x in S.alle_verzen()}
    basis = _doelpost(posts, dt.datetime.now()) or next((q for q in reversed(posts) if q["variabelen"].get("formaat") == "carrousel"), None)
    if not basis:
        return []
    os.makedirs(S.P("docs/media/nieuws"), exist_ok=True)
    uit = []
    for k, (vid, zin) in enumerate((item.get("concept") or {}).items()):
        x = alle.get(vid)
        if not x or vid not in bank:
            continue
        p = copy.deepcopy(basis)
        p["id"] = f"{item['id']}-{k + 1}"
        _vul_nieuws(p, x, zin, item, cat, zwaar, bank, cfg)
        try:
            paden = maak_carrousel(p, S.P(f"docs/media/nieuws/{p['id']}.jpg"))
            eig, naam = cfg["github_repo"].split("/")
            media = [f"https://{eig}.github.io/{naam}/" + os.path.relpath(q, S.P("docs")) for q in paden]
        except Exception as e:
            print("Voorvertoning mislukt:", e); media = []
        uit.append({"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"], "zin": zin, "kernwoord": p.get("kernwoord"),
                    "betekenis": p.get("betekenis"), "toepassing": p.get("toepassing"), "caption": p["caption"], "media": media})
    return uit


def maak_nieuwspost(item, cat, zwaar, cfg, posts, rnd, na=None, vers_id=None, zin=None):
    """Zet de eerstvolgende carrousel om naar een post met dit nieuws als aanleiding. Geeft de post of None.
    vers_id en zin: de keuze van Joshua (anders kiest het systeem zelf)."""
    nu = dt.datetime.now()
    p = _doelpost(posts, nu, na)
    if not p or len(nieuwsposts_op(posts, p["datum"])) >= _cfg(cfg)["max_per_dag"]:
        return None
    bank = tekstbank.laad()
    alle = {x["id"]: x for x in S.alle_verzen()}
    if vers_id and vers_id in alle and vers_id in bank:
        x = alle[vers_id]
    else:
        vrij = _vrije_verzen(cat, zwaar, cfg, posts, bank)
        if not vrij:
            return None
        top = [y for y in vrij if _passend(y, bank[y["id"]], cat, zwaar) == _passend(vrij[0], bank[vrij[0]["id"]], cat, zwaar)]
        x = rnd.choice(top)  # uit de best passende verzen
    oud = p["ref"]
    zin = (zin or "").strip()
    if not zin:
        return None  # zonder persoonlijke zin geen nieuwspost
    _vul_nieuws(p, x, zin, item, cat, zwaar, bank, cfg)
    p["status"] = "klaar_voor_render"
    S.bewaar("data/posts.json", posts)
    try:
        S.cmd_render(p["datum"])
    except SystemExit:
        pass
    posts[:] = S.laad("data/posts.json", [])
    p = next(q for q in posts if q["id"] == p["id"])
    if p["status"] != "gerenderd":
        return None
    S.cmd_log(f"Nieuwspost: {oud} vervangen door {p['ref']} (aanleiding: {cat}, {item['bron']})")
    S.activiteit("verskiezer", f"Nieuwspost gemaakt: {p['ref']}")
    return p


def nieuwsposts_op(posts, datum):
    return [p for p in posts if p["datum"] == datum and p["variabelen"].get("aanleiding") == "nieuws"]


CONCEPTEN = "data/nieuws_concepten.json"   # alleen het Mac-programma schrijft hier: {nieuws_id: {"zinnen": {vers_id: zin}, "t": ...}}


def kandidaat_verzen(cat, zwaar, cfg, posts, bank, n=3):
    """De verzen waaruit het lokale AI-model er een kiest om een persoonlijke zin voor te schrijven (het model verzint nooit een vers)."""
    return [{"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"]} for x in _vrije_verzen(cat, zwaar, cfg, posts, bank)[:n]]


def main(forceer=False):
    """Nieuws vanuit de persoonlijke stem. Alles gaat via een voorstel; niets komt automatisch online.
    1. kop binnenhalen, indelen, kandidaatverzen kiezen: status 'schrijven' (het Mac-programma schrijft de openingszinnen)
    2. zinnen van het Mac-programma gevonden: voorvertoning maken en Joshua laten kiezen: status 'voorstel'
    3. te oude items laten vervallen (Mac uit, of Joshua reageerde niet)."""
    cfg = S.laad("config.json")
    n = _cfg(cfg)
    if cfg.get("pauze") or not n["aan"]:
        print("Nieuws staat uit of pauze."); return
    log = S.laad(PAD, [])
    bekend = {x["kop"] for x in log}
    posts = S.laad("data/posts.json", [])
    bank = tekstbank.laad()
    nu = dt.datetime.now(dt.timezone.utc)
    vandaag = dt.date.today().isoformat()
    concepten = S.laad(CONCEPTEN, {})

    # 3. vervallen
    for x in log:
        t = dt.datetime.fromisoformat(x["t"]) if x.get("t") else nu
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        uren = (nu - t).total_seconds() / 3600
        if x.get("status") == "schrijven" and uren > 14:
            x["status"] = "verlopen"   # het Mac-programma kwam er niet aan toe (Mac uit?)
        elif x.get("status") == "voorstel" and uren > 30:
            x["status"] = "verlopen"

    # 2. zinnen van het Mac-programma verwerken
    nieuw_voorstel = 0
    for x in log:
        if x.get("status") != "schrijven" or x["id"] not in concepten:
            continue
        x["concept"] = concepten[x["id"]].get("zinnen") or {}
        try:
            x["opties"] = maak_opties(x, x["categorie"], x["zwaar"], cfg, posts)
        except Exception as e:
            print("Opties maken mislukt:", e); x["opties"] = []
        if not x["opties"]:
            x["status"] = "geen_plek"; continue
        x["status"] = "voorstel"
        soort = "zwaar nieuws, gaat pas 6 uur na het nieuws online" if x["zwaar"] else ("politiek" if x["categorie"] == "politiek" else x["categorie"])
        S.cmd_log(f"Nieuws ({soort}, {x['bron']}): \"{x['kop'][:90]}\". Voorstel in de persoonlijke stem staat klaar; gaat alleen online met jouw akkoord.",
                  "fout", "nieuws_voorstel", x["id"])
        meld_voorstel(x); nieuw_voorstel += 1

    # 1. nieuwe koppen
    recente_cats = {x["categorie"] for x in log if x.get("status") in ("schrijven", "voorstel", "gemaakt") and x.get("t", "")[:10] >= (dt.date.today() - dt.timedelta(days=3)).isoformat()}
    vandaag_n = sum(1 for x in log if x.get("status") in ("schrijven", "voorstel", "gemaakt") and x.get("t", "")[:10] == vandaag)
    politiek_vandaag = any(x["categorie"] == "politiek" and x.get("status") in ("schrijven", "voorstel", "gemaakt") and x.get("t", "")[:10] == vandaag for x in log)
    zwaar_recent = any(x["categorie"] == "zwaar" and x.get("t", "")[:10] >= (dt.date.today() - dt.timedelta(days=2)).isoformat() for x in log)
    nieuw = 0
    for item in ophalen()[:40]:
        if item["kop"] in bekend or vandaag_n >= max(2, n["max_per_dag"]):
            continue
        r = indelen(item["kop"])
        if not r:
            continue
        soort, cat = r
        entry = dict(item, id=f"n{dt.datetime.now():%m%d%H%M}{nieuw}", categorie=cat, zwaar=soort == "zwaar", status="gezien")
        entry.setdefault("t", nu.isoformat(timespec="minutes"))
        if (soort == "politiek" and politiek_vandaag) or (soort == "zwaar" and zwaar_recent) or (soort == "licht" and cat in recente_cats):
            entry["status"] = "overgeslagen"
        else:
            kand = kandidaat_verzen(cat, entry["zwaar"], cfg, posts, bank)
            if not kand:
                entry["status"] = "geen_plek"
            else:
                entry.update(status="schrijven", kandidaten=kand)
                vandaag_n += 1
                if soort == "politiek": politiek_vandaag = True
                if soort == "zwaar": zwaar_recent = True
                recente_cats.add(cat)
        log.append(entry); bekend.add(item["kop"]); nieuw += 1
    S.bewaar(PAD, log[-150:])
    S.gezond("nieuws", True, f"{nieuw} nieuwe aanleidingen, {nieuw_voorstel} voorstellen")
    print(nieuw, "nieuwe aanleidingen bekeken,", nieuw_voorstel, "voorstellen klaargezet")


def meld_voorstel(e):
    """Nieuwsvoorstel naar Telegram: de opties als foto's en een knop per optie."""
    try:
        import whatsapp
    except Exception:
        return
    opt = e.get("opties") or []
    soort = "zwaar nieuws, gaat pas 6 uur na het nieuws online" if e["zwaar"] else ("politiek, altijd neutraal" if e["categorie"] == "politiek" else e["categorie"])
    regels = [f"📰 *Nieuwsvoorstel* ({soort}), in de persoonlijke stem", f"{e['bron']}: {e['kop']}", ""]
    for k, o in enumerate(opt):
        regels.append(f"*Optie {k + 1}:* {o['ref']}\nOpening: \"{o['zin']}\"")
    if not opt:
        regels.append("Het systeem kiest zelf een passend vers.")
    regels.append("\nKies een optie, of pas de openingszin aan in het dashboard.")
    knoppen = [[[f"Optie {k + 1}", {"actie": "nieuws_maken", "id": e["id"], "keuze": k}] for k in range(len(opt))]] if opt \
        else [[["Post erover maken", {"actie": "nieuws_maken", "id": e["id"]}]]]
    knoppen.append([["Negeren", {"actie": "nieuws_negeren", "id": e["id"]}]])
    fotos = [f"docs/media/nieuws/{e['id']}-{k + 1}-1.jpg" for k in range(len(opt))]
    whatsapp.zet_in_wachtrij("\n".join(regels), "direct", "nieuws:" + e["id"], knoppen=knoppen, fotos=fotos)


def maak_voorstel(nid, keuze=None, zin=None):
    """Joshua keurt een voorstel goed (dashboard): maak de post, bij zwaar nieuws pas 6 uur na het nieuws."""
    cfg = S.laad("config.json")
    log = S.laad(PAD, [])
    e = next((x for x in log if x["id"] == nid), None)
    if not e or e["status"] != "voorstel":
        return "Voorstel niet gevonden of al afgehandeld"
    posts = S.laad("data/posts.json", [])
    na = None
    if e["zwaar"]:
        na = dt.datetime.fromisoformat(e["t"]).astimezone().replace(tzinfo=None) + dt.timedelta(hours=6)
    opt = (e.get("opties") or [])
    gekozen = opt[int(keuze)] if keuze is not None and str(keuze).isdigit() and int(keuze) < len(opt) else {}
    zin = (zin or "").strip() or gekozen.get("zin")
    if not zin:
        return "Kies een optie of typ zelf een openingszin"
    if not 15 <= len(zin) <= 160:
        return "De openingszin moet tussen 15 en 160 tekens zijn"
    p = maak_nieuwspost(e, e["categorie"], e["zwaar"], cfg, posts, random.Random(nid), na, gekozen.get("vers_id"), zin)
    if not p:
        return "Geen geschikte carrousel gevonden in de komende 36 uur; het voorstel blijft staan"
    e.update(status="gemaakt", post=p["id"])
    S.bewaar(PAD, log)
    return f"Nieuwspost klaargezet: {p['ref']} op {p['datum']} om {p['variabelen']['tijdslot']}"


def negeer(nid):
    log = S.laad(PAD, [])
    for x in log:
        if x["id"] == nid and x["status"] == "voorstel":
            x["status"] = "genegeerd"
    S.bewaar(PAD, log)
    return "Voorstel genegeerd"


if __name__ == "__main__":
    main()
