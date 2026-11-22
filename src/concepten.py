"""Concepten van de lokale AI (het Mac-hulpprogramma, tools/mac/bijbel_helper.py).

De AI schrijft alleen concepten. Niets gaat de tekstbank of de nieuwszinnen in zonder goedkeuring van Joshua
in het dashboard (of, later, automatisch als hij dat aanzet en het concept de controle haalt).

data/concepten.json:
  verzen    {vers_id: {"e": bankitem, "model": .., "t": ..}}   concepten voor de tekstbank
  afgekeurd [vers_id, ...]                                     door Joshua afgekeurd, de AI probeert die niet opnieuw
  nieuws    {"zinnen": {cat: [{"tekst","model","t"}]}, "bruggen": {cat: [...]}}
data/nieuws_extra.json (goedgekeurd) {"zinnen": {cat: [tekst]}, "bruggen": {cat: [tekst]}}, gebruikt door nieuws.py
data/lokale_ai.json: hartslag van het Mac-programma (laatst gezien, model, tellers)
"""
import json, os, re

import tekstbank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = os.path.join(ROOT, "data", "concepten.json")
EXTRA = os.path.join(ROOT, "data", "nieuws_extra.json")
VOORBEELD = os.path.join(ROOT, "data", "nieuws_voorbeelden.json")
STREEP = re.compile("[—–]")
CJK = re.compile("[぀-ヿ㐀-鿿가-힯]")


def _json(pad, standaard):
    try:
        return json.load(open(pad, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return standaard


def laad():
    c = _json(PAD, {})
    c.setdefault("verzen", {})
    c.setdefault("afgekeurd", [])
    c.setdefault("nieuws", {}).setdefault("zinnen", {})
    c["nieuws"].setdefault("bruggen", {})
    return c


def bewaar(c):
    json.dump(c, open(PAD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def extra():
    e = _json(EXTRA, {})
    e.setdefault("zinnen", {})
    e.setdefault("bruggen", {})
    return e


def controle(vid, e, vers_tekst=None):
    """Zelfde regels als de tekstbank, plus extra eisen voor tekst die een model schreef."""
    uit = tekstbank.problemen(vid, e, vers_tekst)
    alles = " ".join(str(v) for v in e.values() if isinstance(v, str)) + " " + " ".join((e.get("hooks") or {}).values())
    if CJK.search(alles):
        uit.append("bevat Chinese of Japanse tekens")
    if STREEP.search(alles):
        uit.append("streepje (— of –) gebruikt")
    h = ((e.get("hooks") or {}).get("herkenning") or "").strip()
    if h and not 8 <= len(h) <= 90:
        uit.append(f"herkenningszin: {len(h)} tekens (moet 8 tot 90)")
    for t in e.get("tags") or []:
        if not re.fullmatch(r"#[0-9A-Za-zÀ-ſ]{2,30}", t):
            uit.append(f"hashtag {t!r} is ongeldig")
    if vers_tekst and e.get("betekenis", "").strip() and e["betekenis"].strip() in vers_tekst:
        uit.append("betekenis herhaalt alleen het vers")
    return uit


def goedkeuren(vid):
    """Concept naar de tekstbank. Geeft (gelukt, melding)."""
    import systeem as S
    c = laad()
    k = c["verzen"].get(vid)
    if not k:
        return False, "Dit concept bestaat niet meer"
    vers = next((x for x in S.alle_verzen() if x["id"] == vid), None) or S.reeks_verzen().get(vid)
    if not vers:
        return False, "Dit vers staat niet in de verzenlijst"
    fouten = controle(vid, k["e"], vers["tekst"])
    if fouten:
        return False, "Controle faalt: " + "; ".join(fouten)
    bank = tekstbank.laad()
    if vid in bank:
        c["verzen"].pop(vid)
        bewaar(c)
        return True, "Dit vers stond al in de tekstbank"
    e = dict(k["e"])
    e["ref"] = vers["ref"]
    bank[vid] = e
    tekstbank.bewaar(bank)
    c["verzen"].pop(vid)
    bewaar(c)
    return True, f"{vers['ref']} staat nu in de tekstbank"


def afkeuren(vid):
    c = laad()
    c["verzen"].pop(vid, None)
    if vid not in c["afgekeurd"]:
        c["afgekeurd"].append(vid)
    bewaar(c)


def nieuws_goedkeuren(soort, cat, tekst):
    """soort: 'zinnen' of 'bruggen'. Streepjes en te lange bruggen worden geweigerd."""
    c, x = laad(), extra()
    lijst = c["nieuws"][soort].get(cat, [])
    k = next((q for q in lijst if q["tekst"] == tekst), None)
    if not k:
        return False, "Dit concept bestaat niet meer"
    if STREEP.search(tekst) or CJK.search(tekst) or (soort == "bruggen" and len(tekst) > 45) or not 10 <= len(tekst) <= 140:
        return False, "Controle faalt (lengte of streepje)"
    x[soort].setdefault(cat, [])
    if tekst not in x[soort][cat]:
        x[soort][cat].append(tekst)
    json.dump(x, open(EXTRA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lijst.remove(k)
    bewaar(c)
    return True, "Toegevoegd aan de nieuwszinnen"


def nieuws_afkeuren(soort, cat, tekst):
    c = laad()
    c["nieuws"][soort][cat] = [q for q in c["nieuws"][soort].get(cat, []) if q["tekst"] != tekst]
    bewaar(c)


def voorbeelden_schrijven():
    """Zet de huidige nieuwszinnen per categorie neer, zodat de AI in dezelfde toon schrijft."""
    import nieuws
    uit = {}
    for cat, d in nieuws.LICHT.items():
        uit[cat] = {"zinnen": list(d["zinnen"])[:6], "bruggen": list(nieuws.BRUGGEN.get(cat, []))}
    json.dump(uit, open(VOORBEELD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def dashboard():
    """Voor het dashboard: wat staat er klaar, en hoe gaat het met het Mac-programma."""
    import systeem as S
    c = laad()
    verzen = {x["id"]: x for x in S.alle_verzen()}
    for vid, v in S.reeks_verzen().items():  # Advent en Kerst: ook concepten van de lokale AI
        verzen.setdefault(vid, v)
    lijst = []
    for vid, k in c["verzen"].items():
        v = verzen.get(vid)
        if not v:
            continue
        lijst.append({"id": vid, "ref": v["ref"], "tekst": v["tekst"], "e": k["e"], "t": k.get("t", ""),
                      "fouten": controle(vid, k["e"], v["tekst"])})
    nieuws = [{"soort": s, "cat": cat, "tekst": q["tekst"]}
              for s in ("zinnen", "bruggen") for cat, qs in c["nieuws"][s].items() for q in qs]
    bank = tekstbank.laad()
    zonder = sum(1 for v in verzen.values() if v["id"] not in bank)
    return {"verzen": sorted(lijst, key=lambda x: x["ref"]), "nieuws": nieuws, "zonder_tekst": zonder,
            "mac": _json(os.path.join(ROOT, "data", "lokale_ai.json"), {})}
