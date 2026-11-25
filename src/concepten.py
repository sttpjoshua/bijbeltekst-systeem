"""Concepten van de lokale AI (het Mac-hulpprogramma, tools/mac/bijbel_helper.py).

De AI schrijft alleen concepten. Niets gaat de tekstbank of de nieuwszinnen in zonder goedkeuring van Joshua
in het dashboard (of, later, automatisch als hij dat aanzet en het concept de controle haalt).

data/concepten.json:
  verzen    {vers_id: {"e": bankitem, "model": .., "t": ..}}   concepten voor de tekstbank
  afgekeurd [vers_id, ...]                                     door Joshua afgekeurd, de AI probeert die niet opnieuw
  noor      {vers_id: {"verhaal","zin","vraag","herkenning","model","t"}}   persoonlijke teksten (het karakter), na goedkeuring in data/noor.json
Nieuwsconcepten staan apart in data/nieuws_concepten.json (alleen het Mac-programma schrijft), en gaan via het nieuwsvoorstel.
data/lokale_ai.json: hartslag van het Mac-programma (laatst gezien, model, tellers)
"""
import json, os, re

import tekstbank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = os.path.join(ROOT, "data", "concepten.json")
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
    c.setdefault("noor", {})
    return c


def bewaar(c):
    json.dump(c, open(PAD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def bank_tags():
    """Alle hashtags die al in de tekstbank staan (die zijn door mensen gekozen en dus goed)."""
    return {t for e in tekstbank.laad().values() for t in e.get("tags") or []}


def controle(vid, e, vers_tekst=None):
    """Zelfde regels als de tekstbank, plus extra eisen voor tekst die een model schreef."""
    uit = tekstbank.problemen(vid, e, vers_tekst)
    try:  # spelling, verzonnen woorden en hashtags (src/taalcontrole.py, dezelfde controle als op de Mac)
        import taalcontrole
        uit += taalcontrole.problemen(e, vers_tekst or "", bank_tags())
    except Exception:
        pass
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


NOOR_VELDEN = ("verhaal", "zin", "vraag", "herkenning")
NOOR_LENGTE = {"verhaal": (15, 200), "zin": (20, 200), "vraag": (8, 120), "herkenning": (8, 90)}


def noor_problemen(e):
    uit = []
    for v in NOOR_VELDEN:
        t = str(e.get(v, "")).strip()
        lo, hi = NOOR_LENGTE[v]
        if not lo <= len(t) <= hi:
            uit.append(f"{v}: {len(t)} tekens (moet {lo} tot {hi})")
        if STREEP.search(t) or CJK.search(t):
            uit.append(f"{v}: streepje of vreemde tekens")
        if re.search(r"\bnoor\b", t, re.I):
            uit.append(f"{v}: de naam mag nooit in een tekst staan")
    return uit


def noor_goedkeuren(vid):
    c = laad()
    k = c["noor"].get(vid)
    if not k:
        return False, "Dit concept bestaat niet meer"
    fouten = noor_problemen(k)
    if fouten:
        return False, "Controle faalt: " + "; ".join(fouten)
    pad = os.path.join(ROOT, "data", "noor.json")
    d = _json(pad, {})
    d[vid] = {v: str(k[v]).strip() for v in NOOR_VELDEN}
    json.dump(d, open(pad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c["noor"].pop(vid)
    bewaar(c)
    return True, "Persoonlijke teksten staan klaar voor dit vers"


def noor_afkeuren(vid):
    c = laad()
    c["noor"].pop(vid, None)
    bewaar(c)


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
    noor = [{"id": vid, "ref": verzen[vid]["ref"], "tekst": verzen[vid]["tekst"], "e": {v: k.get(v, "") for v in NOOR_VELDEN},
             "fouten": noor_problemen(k)} for vid, k in c["noor"].items() if vid in verzen]
    bank = tekstbank.laad()
    zonder = sum(1 for v in verzen.values() if v["id"] not in bank)
    return {"verzen": sorted(lijst, key=lambda x: x["ref"]), "noor": sorted(noor, key=lambda x: x["ref"]), "zonder_tekst": zonder,
            "mac": _json(os.path.join(ROOT, "data", "lokale_ai.json"), {})}
