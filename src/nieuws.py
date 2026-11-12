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

# Lichte aanleidingen. Per soort: woorden in de kop (alleen als signaal), thema's voor het vers, zinnen die het moment bij
# naam noemen (nooit een kop of bron), 'subs' voor specifiekere zinnen bij bepaalde woorden, 'bruggen' voor de uitleg
# (waarom dit vers bij dit moment past) en 'vers_woorden' om een vers te kiezen dat echt bij het onderwerp past.
LICHT = {
    "storm": dict(woorden=["storm", "code oranje", "windstoten", "zware wind", "zeer zware windstoten"],
                  themas=["vrede_rust", "vertrouwen"],
                  zinnen=["Storm vandaag, met veel wind. Waar houd jij je aan vast als het waait?",
                          "Het stormt buiten. Binnen mag het stil worden.",
                          "De storm trekt over het land. Er is iets wat blijft staan."],
                  vers_woorden=["storm", "wind", "golven", "zee", "stilte", "rots", "fundament", "anker"]),
    "winter": dict(woorden=["sneeuw", "gladheid", "ijzel", "vorst", "natuurijs", "winterweer", "code wit"],
                   themas=["vrede_rust", "dankbaarheid", "hoop"],
                   subs=[(["sneeuw"], ["Het sneeuwt. Alles wordt stil en wit, ook in je hoofd mag het even rustig worden."]),
                         (["gladheid", "ijzel"], ["Het is glad op de weg. Rustig aan, ook met je gedachten."]),
                         (["vorst", "natuurijs"], ["Het vriest. Wat maakt jou van binnen warm?"])],
                   zinnen=["Winterweer vandaag. Een goed moment om even stil te staan.",
                           "Het is koud buiten. Tijd voor iets wat je van binnen warm maakt.",
                           "Langzaam aan vandaag. Dat mag."],
                   vers_woorden=["sneeuw", "vorst", "koud", "winter", "ijs", "wit"]),
    "hitte": dict(woorden=["hittegolf", "tropische temperaturen", "warmste dag", "tropisch warm"],
                  themas=["vrede_rust", "dankbaarheid"],
                  zinnen=["Hittegolf: het is heet vandaag. Zoek de schaduw, en even rust.",
                          "Zo warm vandaag. Neem het rustig, ook van binnen.",
                          "Het is bloedheet. Waar vind jij verkoeling?"],
                  vers_woorden=["schaduw", "dorst", "water", "verkwik", "koel", "zon"]),
    "regen": dict(woorden=["regenachtig", "grijze dag", "veel regen", "regenbuien", "regenval", "natste", "koudste", "nat weer", "somber weer", "herfstweer"],
                  themas=["hoop", "troost", "vrede_rust"],
                  zinnen=["Het regent weer. Grijze lucht vandaag, maar hier is iets van licht.",
                          "Nat en grijs buiten. Even binnen blijven bij God.",
                          "Een natte dag. Water dat valt, brengt ook nieuw leven."],
                  vers_woorden=["regen", "water", "wolk", "licht", "dauw", "bron"]),
    "sintmaarten": dict(woorden=["sint-maarten", "sint maarten", "lampion"],
                        themas=["hoop", "dankbaarheid", "liefde"],
                        zinnen=["Sint-Maarten vandaag: lampionnen en snoep. Het verhaal erachter gaat over delen.",
                                "Sint-Maarten deelde zijn mantel. Wie kun jij vandaag iets geven?",
                                "Vanavond lopen er lampionnen door de straat. Klein licht, maar het maakt verschil."],
                        vers_woorden=["licht", "lamp", "kleed", "mantel", "delen", "geven", "arm"]),
    "sinterklaas": dict(woorden=["sinterklaas", "intocht", "pakjesavond", "pepernoten"],
                        themas=["dankbaarheid", "liefde"],
                        subs=[(["intocht", "stoomboot", "aangemeerd", "aankomst", "aanlegplaats"],
                               ["Sinterklaas komt weer naar Nederland. Overal kijken kinderen ernaar uit.",
                                "Het is bijna intocht. Wat is het mooiste cadeau dat je ooit kreeg?"]),
                              (["pakjesavond", "cadeau"], ["Pakjesavond: wat is het mooiste cadeau dat je ooit kreeg?"]),
                              (["pepernoten"], ["De pepernoten liggen weer in de schappen. Het is Sinterklaastijd."])],
                        zinnen=["Sinterklaas is in het land en heel Nederland denkt aan cadeaus. Dit is er één die blijft.",
                                "Het is Sinterklaastijd. Wat is het mooiste wat jij ooit kreeg?",
                                "Pakjes en pepernoten. En een gave die je niet hoeft te verdienen."],
                        vers_woorden=["gave", "gaven", "geven", "geschenk", "vreugd", "kinderen", "blij"]),
    "sport": dict(woorden=["wint goud", "wereldkampioen", "europees kampioen", "olympisch kampioen", "oranje wint", "pakt goud"],
                  themas=["dankbaarheid", "moed"],
                  zinnen=["Er wordt gejuicht om een overwinning vandaag. Ook jij hebt redenen om te juichen.",
                          "Winnen is mooi. Er is iets wat nog meer telt.",
                          "Goud voor de winnaar. En wat krijgt wie volhoudt?"],
                  vers_woorden=["loop", "wedloop", "kroon", "overwin", "strijd", "prijs", "volhoud"]),
    "drukte": dict(woorden=["recordfile", "filedrukte", "files", "spitsdrukte", "ns storing", "treinstoring"],
                   themas=["vrede_rust", "wijsheid"],
                   zinnen=["Files en vertragingen vandaag. Dit is voor die minuten in de auto of op het perron.",
                           "Treinen staan stil, wegen zitten vol. Misschien is dat niet eens zo erg.",
                           "Alles loopt vertraagd vandaag. Een kans om rustig te worden."],
                   vers_woorden=["stil", "rust", "wacht", "geduld", "haast"]),
    "examens": dict(woorden=["eindexamen", "examens", "tentamens"],
                    themas=["moed", "vertrouwen"],
                    zinnen=["Het is examentijd en dat voelt spannend. Dit is voor jou.",
                            "Je hebt geleerd, je hebt je best gedaan. De rest mag je loslaten.",
                            "Examens of niet: wijsheid is meer dan een cijfer."],
                    vers_woorden=["wijsheid", "verstand", "leer", "kennis", "inzicht", "vertrouw"]),
    "klok": dict(woorden=["wintertijd", "zomertijd", "klok een uur"],
                 themas=["wijsheid", "vrede_rust"],
                 zinnen=["De klok is verzet, een uur erbij of eraf. Wat doe jij met je tijd?",
                         "Een uur extra of minder. Tijd is een geschenk.",
                         "Winter- of zomertijd: de dag heeft weer een andere vorm."],
                 vers_woorden=["tijd", "dagen", "jaren", "getij", "eeuw"]),
    "koopjes": dict(woorden=["black friday", "cyber monday", "koopjesjagers", "uitverkoop"],
                    themas=["dankbaarheid", "wijsheid"],
                    zinnen=["Black Friday: overal aanbiedingen. Wat heb je eigenlijk al?",
                            "Iedereen jaagt op koopjes vandaag. Dit is gratis, en blijft.",
                            "Kortingen alom. En de beste dingen zijn niet te koop."],
                    vers_woorden=["schat", "rijk", "geld", "zilver", "goud", "koop", "genoeg"]),
    "maandag": dict(woorden=["blue monday", "somberste dag"],
                    themas=["hoop", "troost"],
                    zinnen=["Blue Monday, de somberste dag van het jaar, zeggen ze. Hier is iets van hoop.",
                            "Voel je je somber vandaag? Je bent niet de enige.",
                            "Een zware maandag? Er is iets wat bij je blijft."],
                    vers_woorden=["hoop", "troost", "vreugd", "blij", "verblijd"]),
}
# Politiek: nooit automatisch, altijd eerst akkoord van Joshua. Neutraal: nooit een partij, politicus of standpunt kiezen.
POLITIEK_ZINNEN = ["Er wordt veel gesproken en besloten deze dagen. Bid voor wijsheid bij wie leiding geeft.",
                   "Wat er ook gebeurt in Den Haag of in de wereld, dit blijft staan.",
                   "Veel meningen, veel onrust. Even terug naar wat vaststaat."]
ZWAAR_ZINNEN = ["Er gebeurt veel in de wereld dat zwaar is. Even stil, samen.",
                "Soms is het nieuws te zwaar voor woorden. Dan is er dit.",
                "Voor iedereen die vandaag geraakt is door wat er gebeurde."]

# Korte bruggen (maximaal 45 tekens): waarom dit vers bij het moment past. In de caption altijd, in de uitleg op het beeld
# alleen als het geheel binnen de 110 tekens blijft.
BRUGGEN = {
    "storm": ["Bij storm: houvast als het waait.", "Als het stormt, kun je hierop rusten."],
    "winter": ["In de winterkou: warmte van binnen.", "Bij vorst en sneeuw: rust en warmte."],
    "hitte": ["Bij hitte: schaduw en verkwikking.", "Te warm? Even op adem komen."],
    "regen": ["Op een natte dag: licht in het grijs.", "Bij grijs weer: kleur van binnen."],
    "sintmaarten": ["Sint-Maarten: delen en een klein licht.", "Een klein licht doet ertoe."],
    "sinterklaas": ["In Sinterklaastijd: wat God geeft.", "Cadeaus zijn mooi, deze gave blijft."],
    "sport": ["Bij een overwinning: wat blijft.", "Winnen is mooi, volhouden telt."],
    "drukte": ["Staat alles stil? Dit is rust.", "Moet je wachten? Sta even stil hierbij."],
    "examens": ["Voor wie spanning voelt: rust.", "Spannend? Dit helpt om los te laten."],
    "klok": ["Nu de klok verzet is: tijd die blijft.", "Over tijd gesproken: dit blijft."],
    "koopjes": ["Midden in de koopjes: wat echt telt.", "Wat is genoeg? Dit geeft antwoord."],
    "maandag": ["Op een sombere dag: hoop die blijft.", "Zwaar? Hier kun je bij schuilen."],
    "politiek": ["Bij alle onrust: wat blijft staan.", "Een vast punt in veel geluid."],
    "zwaar": ["Bij zwaar nieuws: troost die er is.", "Als er geen woorden zijn: dit."],
}

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


def _themas(cat, zwaar):
    return ["troost", "hoop", "vrede_rust"] if zwaar else (["wijsheid", "vrede_rust", "vertrouwen"] if cat == "politiek" else LICHT[cat]["themas"])


def _zinnen(cat, zwaar, kop=""):
    """Openingszinnen die het moment noemen; bij bepaalde woorden in de kop eerst de specifiekere zinnen."""
    if zwaar:
        return ZWAAR_ZINNEN
    if cat == "politiek":
        return POLITIEK_ZINNEN
    k = " " + kop.lower() + " "
    sub = [z for woorden, zinnen in LICHT[cat].get("subs", []) if any(w in k for w in woorden) for z in zinnen]
    return sub + LICHT[cat]["zinnen"] if sub else LICHT[cat]["zinnen"]


def _brug(cat, zwaar, item, vers_id=""):
    """Eén zin voor de uitleg: waarom dit vers bij dit moment past (vast per nieuwsitem en vers)."""
    lijst = BRUGGEN["zwaar" if zwaar else cat]
    return random.Random(item["kop"] + vers_id).choice(lijst)


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
    """Maakt van post p een nieuwspost met vers x en openingszin zin (alleen in het geheugen)."""
    p.update({"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"], "vertaling": x.get("vertaling", "SV")})
    v = p["variabelen"]
    for f in ("thema", "boekgroep", "lengte", "bron"):
        v[f] = x[f]
    v["opening"], v["aanleiding"] = "verhaal", "nieuws"
    v["achtergrondbron"] = "verloop" if v.get("achtergrondbron") == "beeld" else v.get("achtergrondbron")
    p["beeld"] = None
    p.setdefault("keuzebron", {}).update({"opening": "nieuws", "aanleiding": "nieuws"})
    tekstbank.vul_post(p, bank[x["id"]], cfg)
    p["verhaal_hook"] = zin
    # brugzin: waarom dit vers bij dit moment past, in de uitleg (op het beeld) en in de caption
    brug = _brug(cat, zwaar, item, x["id"])
    e = bank[x["id"]]
    zin_e = (e.get("zin") or "").strip()
    if p.get("uitleg") and len(brug) + 1 + len(p["uitleg"]) <= 110:  # de uitleg op het beeld mag niet langer dan 110 tekens zijn
        p["uitleg"] = f"{brug} {p['uitleg']}"
    if zin_e and zin_e in p["caption"]:
        p["caption"] = p["caption"].replace(zin_e, f"{brug} {zin_e}", 1)
    else:
        delen_c = p["caption"].split("\n\n")
        i = next((j for j, d in enumerate(delen_c) if p["ref"] in d), 0)
        delen_c.insert(i + 1, brug)
        p["caption"] = "\n\n".join(delen_c)
    p["nieuws_brug"] = brug
    # de openingszin is ook de eerste regel van de caption (zo snapt de lezer waarom dit vers vandaag)
    delen = p["caption"].split("\n\n")
    p["caption"] = "\n\n".join([zin] + delen[1 if p.get("hook") else 0:])
    p["hook"] = zin
    p["nieuws"] = {"categorie": cat, "kop": item["kop"], "bron": item["bron"], "link": item["link"], "zwaar": zwaar}


def behoud_nieuws(p, n, zin, cfg=None):
    """Na een verse-wissel: de post blijft een nieuwspost (openingszin en brugzin voor het nieuwe vers)."""
    cfg = cfg or S.laad("config.json")
    bank = tekstbank.laad()
    x = next((y for y in S.alle_verzen() if y["id"] == p["vers_id"]), None)
    if not x or p["vers_id"] not in bank:
        p.pop("nieuws", None)
        return False
    item = {"kop": n["kop"], "bron": n.get("bron", ""), "link": n.get("link", "")}
    _vul_nieuws(p, x, zin, item, n["categorie"], n.get("zwaar", False), bank, cfg)
    return True


def maak_opties(item, cat, zwaar, cfg, posts, n=3):
    """Drie voorstellen (ander vers en andere openingszin) met voorvertoning, om uit te kiezen in het dashboard."""
    import copy
    from render import maak_carrousel
    bank = tekstbank.laad()
    vrij = _vrije_verzen(cat, zwaar, cfg, posts, bank)  # best passende eerst
    rnd = random.Random(item["kop"])
    zinnen = list(_zinnen(cat, zwaar, item["kop"]))
    voorkeur = zinnen[:2] if len(zinnen) > len(LICHT.get(cat, {}).get("zinnen", [])) else []  # specifieke zinnen blijven vooraan
    rest = [z for z in zinnen if z not in voorkeur]; rnd.shuffle(rest); zinnen = voorkeur + rest
    basis = _doelpost(posts, dt.datetime.now()) or next((q for q in reversed(posts) if q["variabelen"].get("formaat") == "carrousel"), None)
    if not basis or not vrij:
        return []
    os.makedirs(S.P("docs/media/nieuws"), exist_ok=True)
    uit = []
    for k, x in enumerate(vrij[:n]):
        p = copy.deepcopy(basis)
        p["id"] = f"{item['id']}-{k + 1}"
        zin = zinnen[k % len(zinnen)]
        _vul_nieuws(p, x, zin, item, cat, zwaar, bank, cfg)
        try:
            paden = maak_carrousel(p, S.P(f"docs/media/nieuws/{p['id']}.jpg"))
            eig, naam = cfg["github_repo"].split("/")
            media = [f"https://{eig}.github.io/{naam}/" + os.path.relpath(q, S.P("docs")) for q in paden]
        except Exception as e:
            print("Voorvertoning mislukt:", e); media = []
        uit.append({"vers_id": x["id"], "ref": x["ref"], "tekst": x["tekst"], "zin": zin, "kernwoord": p.get("kernwoord"),
                    "betekenis": p.get("betekenis"), "toepassing": p.get("toepassing"), "brug": p.get("nieuws_brug"), "caption": p["caption"], "media": media})
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
    zinnen_kop = _zinnen(cat, zwaar, item["kop"])
    zin = (zin or "").strip() or rnd.choice(zinnen_kop[:2] if len(zinnen_kop) > len(LICHT.get(cat, {}).get("zinnen", [])) else zinnen_kop)
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


def herzie_alle():
    """Past nieuwsposts die nog niet online staan aan op de nieuwste regels (moment bij naam, passend vers, brugzin).
    Licht nieuws: nieuw vers en nieuwe openingszin. Politiek en zwaar: het vers en de zin die Joshua koos blijven, alleen de brugzin komt erbij."""
    cfg = S.laad("config.json")
    posts = S.laad("data/posts.json", [])
    bank = tekstbank.laad()
    alle = {x["id"]: x for x in S.alle_verzen()}
    nu = dt.datetime.now()
    gedaan, overgeslagen = [], []
    for p in posts:
        n = p.get("nieuws")
        if not n or p["variabelen"].get("aanleiding") != "nieuws" or p.get("gepubliceerd") or p["status"] != "gerenderd":
            continue
        try:
            t = dt.datetime.fromisoformat(f"{p['datum']}T{p['variabelen']['tijdslot']}")
        except (ValueError, TypeError):
            continue
        if t < nu + dt.timedelta(minutes=30):  # staat bijna online: niet meer aanraken
            overgeslagen.append(p["ref"]); continue
        cat, zwaar = n["categorie"], n.get("zwaar", False)
        item = {"kop": n["kop"], "bron": n.get("bron", ""), "link": n.get("link", "")}
        if cat in LICHT and not zwaar:
            rest = [q for q in posts if q is not p]
            vrij = _vrije_verzen(cat, zwaar, cfg, rest, bank)
            if not vrij:
                overgeslagen.append(p["ref"]); continue
            beste = _passend(vrij[0], bank[vrij[0]["id"]], cat, zwaar)
            x = random.Random(p["id"]).choice([y for y in vrij if _passend(y, bank[y["id"]], cat, zwaar) == beste])
            zinnen = _zinnen(cat, zwaar, n["kop"])
            zin = random.Random(p["id"]).choice(zinnen[:2] if len(zinnen) > len(LICHT[cat]["zinnen"]) else zinnen)
        else:
            x = alle.get(p["vers_id"])
            zin = p.get("hook") or random.Random(p["id"]).choice(_zinnen(cat, zwaar, n["kop"]))
            if not x or p["vers_id"] not in bank:
                overgeslagen.append(p["ref"]); continue
        oud = p["ref"]
        _vul_nieuws(p, x, zin, item, cat, zwaar, bank, cfg)
        p["status"] = "klaar_voor_render"
        S.bewaar("data/posts.json", posts)
        try:
            S.cmd_render(p["datum"])
        except SystemExit:
            pass
        posts[:] = S.laad("data/posts.json", [])
        q = next(q for q in posts if q["id"] == p["id"])
        if q["status"] != "gerenderd":
            overgeslagen.append(q["ref"]); continue
        S.cmd_log(f"Nieuwspost aangepast: {oud} is nu {q['ref']} ({cat}): {q['hook'][:70]}")
        gedaan.append(f"{q['ref']} ({q['variabelen']['tijdslot']})")
    S.bewaar("data/posts.json", posts)
    return f"Nieuwsposts aangepast: {', '.join(gedaan) if gedaan else 'geen'}" + (f". Overgeslagen: {', '.join(overgeslagen)}" if overgeslagen else "")


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
        if entry["status"] == "voorstel":
            try:
                entry["opties"] = maak_opties(entry, cat, entry["zwaar"], cfg, posts)
            except Exception as e:
                print("Opties maken mislukt:", e)
            meld_voorstel(entry)
        log.append(entry); bekend.add(item["kop"]); nieuw += 1
    S.bewaar(PAD, log[-150:])
    S.gezond("nieuws", True, f"{nieuw} nieuwe aanleidingen")
    print(nieuw, "nieuwe aanleidingen bekeken")


def meld_voorstel(e):
    """Nieuwsvoorstel naar Telegram: de opties als foto's en een knop per optie."""
    try:
        import whatsapp
    except Exception:
        return
    opt = e.get("opties") or []
    soort = "zwaar nieuws, gaat pas 6 uur na het nieuws online" if e["zwaar"] else ("politiek, altijd neutraal" if e["categorie"] == "politiek" else e["categorie"])
    regels = [f"📰 *Nieuwsvoorstel* ({soort})", f"{e['bron']}: {e['kop']}", ""]
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
    if zin and not 15 <= len(zin) <= 160:
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
