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

# Lichte aanleidingen: woorden in de kop, thema's voor het vers, en openingszinnen (geen nieuwstekst)
LICHT = {
    "storm": dict(woorden=["storm", "code oranje", "windstoten", "zware wind", "zeer zware windstoten"],
                  themas=["vrede_rust", "vertrouwen"], zinnen=[
                      "Buiten waait het hard vandaag. Binnen mag het stil worden.",
                      "Storm buiten? Er is een plek waar het rustig blijft.",
                      "De wind trekt aan alles vandaag. Waar houd jij je aan vast?"]),
    "winter": dict(woorden=["sneeuw", "gladheid", "ijzel", "vorst", "natuurijs", "winterweer", "code wit"],
                   themas=["vrede_rust", "dankbaarheid", "hoop"], zinnen=[
                       "Witte daken, gladde wegen. Een goede dag om even stil te staan.",
                       "Het is koud buiten. Tijd voor iets wat je van binnen warm maakt.",
                       "Langzaam aan vandaag. Dat mag."]),
    "hitte": dict(woorden=["hittegolf", "tropisch", "warmste dag", "tropische temperaturen"],
                  themas=["vrede_rust", "dankbaarheid"], zinnen=[
                      "Het is heet vandaag. Zoek de schaduw, en even rust.",
                      "Een warme dag. Neem het rustig, ook van binnen."]),
    "regen": dict(woorden=["regenachtig", "grijze dag", "veel regen", "buien", " regen", "natste", "koudste", "nat weer", "somber weer", "herfstweer"],
                  themas=["hoop", "troost", "vrede_rust"], zinnen=[
                      "Grijze lucht vandaag. Hier is iets van licht.",
                      "Regen tegen het raam. Even binnen blijven bij God."]),
    "sintmaarten": dict(woorden=["sint-maarten", "sint maarten", "lampion"],
                        themas=["hoop", "dankbaarheid", "liefde"], zinnen=[
                            "Vanavond lopen er lampionnen door de straat. Klein licht, maar het maakt verschil.",
                            "Sint-Maarten deelde zijn mantel. Wie kun jij vandaag iets geven?"]),
    "sinterklaas": dict(woorden=["sinterklaas", "intocht", "pakjesavond", "pepernoten"],
                        themas=["dankbaarheid", "liefde"], zinnen=[
                            "Het is de tijd van cadeautjes. Dit is er één die niet ophoudt.",
                            "Iedereen denkt aan cadeaus deze weken. Wat is het mooiste wat jij ooit kreeg?"]),
    "sport": dict(woorden=["wint goud", "wereldkampioen", "europees kampioen", "olympisch kampioen", "oranje wint", "pakt goud"],
                  themas=["dankbaarheid", "moed"], zinnen=[
                      "Heel Nederland juicht vandaag. Ook jij hebt redenen om te juichen.",
                      "Winnen is mooi. Er is iets wat nog meer telt."]),
    "drukte": dict(woorden=["recordfile", "filedrukte", "files", "spitsdrukte", "ns storing", "treinstoring"],
                   themas=["vrede_rust", "wijsheid"], zinnen=[
                       "Vast in de file of op het perron? Dit is voor die minuten.",
                       "Alles staat stil vandaag. Misschien is dat niet eens zo erg."]),
    "examens": dict(woorden=["eindexamen", "examens", "tentamens"],
                    themas=["moed", "vertrouwen"], zinnen=[
                        "Spannende weken voor wie examens heeft. Dit is voor jou.",
                        "Je hebt geleerd, je hebt je best gedaan. De rest mag je loslaten."]),
    "klok": dict(woorden=["wintertijd", "zomertijd", "klok een uur"],
                 themas=["wijsheid", "vrede_rust"], zinnen=[
                     "De klok is verzet. Een goed moment om te denken aan wat je met je tijd doet.",
                     "Een uur erbij of eraf. Tijd is een geschenk."]),
    "koopjes": dict(woorden=["black friday", "cyber monday", "koopjesjagers", "uitverkoop"],
                    themas=["dankbaarheid", "wijsheid"], zinnen=[
                        "Iedereen jaagt op koopjes vandaag. Wat heb je eigenlijk al?",
                        "Overal aanbiedingen. Dit is gratis, en blijft."]),
    "maandag": dict(woorden=["blue monday", "somberste dag"],
                    themas=["hoop", "troost"], zinnen=[
                        "Ze noemen het de somberste dag van het jaar. Hier is iets van hoop.",
                        "Voel je je somber vandaag? Je bent niet de enige."]),
}
# Politiek: nooit automatisch, altijd eerst akkoord van Joshua. Neutraal: nooit een partij, politicus of standpunt kiezen.
POLITIEK_ZINNEN = ["Er wordt veel gesproken en besloten deze dagen. Bid voor wijsheid bij wie leiding geeft.",
                   "Wat er ook gebeurt in Den Haag of in de wereld, dit blijft staan.",
                   "Veel meningen, veel onrust. Even terug naar wat vaststaat."]
ZWAAR_ZINNEN = ["Er gebeurt veel in de wereld dat zwaar is. Even stil, samen.",
                "Soms is het nieuws te zwaar voor woorden. Dan is er dit.",
                "Voor iedereen die vandaag geraakt is door wat er gebeurde."]

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


def indelen(kop):
    """(soort, categorie) of None. soort: 'licht' of 'zwaar'."""
    k = " " + kop.lower() + " "
    if any(w in k for w in ZWAAR_GROOT):
        return ("zwaar", "zwaar")
    if any(w in k for w in POLITIEK):  # ook als er een zwaar woord in staat (bijv. vredesgesprekken over een oorlog)
        return ("politiek", "politiek")
    if any(w in k for w in ZWAAR):  # klein zwaar nieuws (ongeluk, steekpartij): niets mee doen
        return None
    if any(w in k for w in POLITIEK):
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
        try:
            t = dt.datetime.fromisoformat(f"{p['datum']}T{v['tijdslot']}")
        except (ValueError, TypeError):
            continue
        if grens <= t <= nu + dt.timedelta(hours=36):
            kand.append((t, p))
    return min(kand, key=lambda x: x[0])[1] if kand else None


def maak_nieuwspost(item, cat, zwaar, cfg, posts, rnd, na=None):
    """Zet de eerstvolgende carrousel om naar een post met dit nieuws als aanleiding. Geeft de post of None."""
    nu = dt.datetime.now()
    p = _doelpost(posts, nu, na)
    if not p or len(nieuwsposts_op(posts, p["datum"])) >= _cfg(cfg)["max_per_dag"]:
        return None
    bank = tekstbank.laad()
    themas = ["troost", "hoop", "vrede_rust"] if zwaar else (["wijsheid", "vrede_rust", "vertrouwen"] if cat == "politiek" else LICHT[cat]["themas"])
    grens = (dt.date.today() - dt.timedelta(days=cfg["vers_niet_herhalen_dagen"])).isoformat()
    recent = {q["vers_id"] for q in posts if q["datum"] >= grens} | set(cfg.get("verzen_uitsluiten", []))
    vrij = [x for x in S.alle_verzen() if x["id"] in bank and x["id"] not in recent and x["thema"] in themas and bank[x["id"]].get("verhaal")]
    if not vrij:
        return None
    x = rnd.choice(vrij)
    oud = p["ref"]
    p.update({"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"], "vertaling": x.get("vertaling", "SV")})
    v = p["variabelen"]
    for f in ("thema", "boekgroep", "lengte", "bron"):
        v[f] = x[f]
    v["opening"], v["aanleiding"] = "verhaal", "nieuws"
    v["achtergrondbron"] = "verloop" if v.get("achtergrondbron") == "beeld" else v.get("achtergrondbron")
    p["beeld"] = None
    p.setdefault("keuzebron", {}).update({"opening": "nieuws", "aanleiding": "nieuws"})
    tekstbank.vul_post(p, bank[x["id"]], cfg)
    zin = rnd.choice(ZWAAR_ZINNEN if zwaar else (POLITIEK_ZINNEN if cat == "politiek" else LICHT[cat]["zinnen"]))
    p["verhaal_hook"] = zin
    # de openingszin is ook de eerste regel van de caption (zo snapt de lezer waarom dit vers vandaag)
    delen = p["caption"].split("\n\n")
    p["caption"] = "\n\n".join([zin] + delen[1 if p.get("hook") else 0:])
    p["hook"] = zin
    p["nieuws"] = {"categorie": cat, "kop": item["kop"], "bron": item["bron"], "link": item["link"], "zwaar": zwaar}
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


def main(forceer=False):
    cfg = S.laad("config.json")
    n = _cfg(cfg)
    if cfg.get("pauze") or not n["aan"]:
        print("Nieuws staat uit of pauze."); return
    log = S.laad(PAD, [])
    bekend = {x["kop"] for x in log}
    posts = S.laad("data/posts.json", [])
    rnd = random.Random(dt.datetime.now().isoformat(timespec="hours"))
    vandaag = dt.date.today().isoformat()
    recente_cats = {x["categorie"] for x in log if x.get("status") == "gemaakt" and x["t"][:10] >= (dt.date.today() - dt.timedelta(days=3)).isoformat()}
    politiek_vandaag = any(x["categorie"] == "politiek" and x.get("status") in ("voorstel", "gemaakt") and x["t"][:10] == vandaag for x in log)
    zwaar_recent = any(x["categorie"] == "zwaar" and x["t"][:10] >= (dt.date.today() - dt.timedelta(days=2)).isoformat() for x in log)
    nieuw = 0
    for item in ophalen()[:40]:
        if item["kop"] in bekend:
            continue
        r = indelen(item["kop"])
        if not r:
            continue
        soort, cat = r
        entry = dict(item, id=f"n{dt.datetime.now():%m%d%H%M}{nieuw}", categorie=cat, zwaar=soort == "zwaar", status="gezien")
        if soort == "politiek":  # nooit automatisch: één voorstel per dag, Joshua beslist
            if politiek_vandaag:
                continue
            entry["status"] = "voorstel"; politiek_vandaag = True
            S.cmd_log(f"Politiek nieuws ({item['bron']}): \"{item['kop'][:90]}\". Neutrale post erover maken (geen partij of standpunt)? Gaat alleen online met jouw akkoord.",
                      "fout", "nieuws_voorstel", entry["id"])
        elif soort == "zwaar":
            if zwaar_recent:
                continue
            entry["status"] = "voorstel"; zwaar_recent = True
            S.cmd_log(f"Zwaar nieuws ({item['bron']}): \"{item['kop'][:90]}\". Wil je er een troostende post over? Die gaat dan pas 6 uur na het nieuws online.",
                      "fout", "nieuws_voorstel", entry["id"])
        elif cat in recente_cats:
            entry["status"] = "overgeslagen"
        elif len(nieuwsposts_op(posts, vandaag)) >= n["max_per_dag"] or not n["licht_automatisch"]:
            entry["status"] = "voorstel" if not n["licht_automatisch"] else "overgeslagen"
            if entry["status"] == "voorstel":
                S.cmd_log(f"Nieuws als aanleiding ({item['bron']}): \"{item['kop'][:90]}\". Post erover maken?", "fout", "nieuws_voorstel", entry["id"])
        else:
            p = maak_nieuwspost(entry, cat, False, cfg, posts, rnd)
            if p:
                entry.update(status="gemaakt", post=p["id"]); recente_cats.add(cat)
            else:
                entry["status"] = "geen_plek"
        log.append(entry); bekend.add(item["kop"]); nieuw += 1
    S.bewaar(PAD, log[-150:])
    print(nieuw, "nieuwe aanleidingen bekeken")


def maak_voorstel(nid):
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
    p = maak_nieuwspost(e, e["categorie"], e["zwaar"], cfg, posts, random.Random(nid), na)
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
