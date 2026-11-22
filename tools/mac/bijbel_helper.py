"""Bibleverse lokale AI: draait op Joshua's Mac Studio, zonder credits.

Een klein taalmodel (Qwen 2.5 via mlx-lm, eenmalig gedownload) schrijft CONCEPTEN en niets anders:
1. Teksten voor de tekstbank, voor verzen die nog geen tekst hebben (uitleg, betekenis, vandaag, hooks, hashtags).
2. Nieuwe openingszinnen en bruggen voor lichte nieuwsposts, per categorie (nooit voor zwaar nieuws of politiek).
De concepten komen in data/concepten.json. Joshua keurt ze goed in het dashboard; pas dan gebruikt het systeem ze.
Het model kiest en citeert nooit een vers: de verstekst komt uit de repo.

De GitHub-sleutel staat in de sleutelhanger (service "bibleverse-mac"), nooit in een bestand.
Staat de Mac uit, dan gebeurt er niets: het systeem draait gewoon door met de tekstbank die er is.
"""
from __future__ import annotations

import base64
import json
import random
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "sttpjoshua/bijbeltekst-systeem"
API = f"https://api.github.com/repos/{REPO}"
VERSION = "4"
MODEL_BIG = "mlx-community/Qwen2.5-14B-Instruct-4bit"
MODEL_SMALL = "mlx-community/Qwen2.5-7B-Instruct-4bit"
VERZEN_PER_RONDE = 10
MAX_OPEN_CONCEPTEN = 60          # genoeg om door te nemen; daarna wacht de AI tot Joshua goedkeurt
NIEUWS_ELKE_UUR = 6
MAX_NIEUWS_PER_CAT = 8
STATE = Path.home() / "Library/Application Support/Bibleverse/state.json"
STREEP = re.compile("[—–]")
CJK = re.compile("[぀-ヿ㐀-鿿가-힯]")
KEY = None
_model = None
BANK_TAGS = set()


def log(*a):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def token() -> str:
    return subprocess.run(["security", "find-generic-password", "-s", "bibleverse-mac", "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()


def gh(path, method="GET", body=None, raw=False):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        out = r.read()
        return out if raw else (json.loads(out) if out else None)


def lees(pad, standaard):
    try:
        return json.loads(gh(f"/contents/{pad}?ref=main", raw=True))
    except (urllib.error.HTTPError, ValueError):
        return standaard


def schrijf(pad, data, bericht):
    """Schrijft een JSON-bestand terug; bij een gelijktijdige wijziging geeft het False terug (dan haalt de volgende ronde het opnieuw op)."""
    sha = None
    try:
        sha = gh(f"/contents/{pad}?ref=main").get("sha")
    except urllib.error.HTTPError:
        pass
    body = {"message": bericht, "branch": "main",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()).decode()}
    if sha:
        body["sha"] = sha
    try:
        gh(f"/contents/{pad}", "PUT", body)
        return True
    except urllib.error.HTTPError as e:
        if e.code in (409, 422):
            return False
        raise


# ---------- taalcontrole (src/taalcontrole.py, elke ronde vers van GitHub) ----------
_taal = None


def taal():
    """Laadt src/taalcontrole.py uit de repo (spelling, verzonnen woorden, hashtags). Lukt dat niet: None."""
    global _taal
    if _taal is not None:
        return _taal or None
    try:
        import wordfreq  # noqa: F401
    except ImportError:
        log("taalcontrole: wordfreq installeren (eenmalig)")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "wordfreq"], check=False)
    try:
        code = gh("/contents/src/taalcontrole.py?ref=main", raw=True).decode("utf-8")
        ns = {"__name__": "taalcontrole"}
        exec(compile(code, "taalcontrole.py", "exec"), ns)
        _taal = ns
    except Exception as e:
        log("taalcontrole niet geladen:", repr(e))
        _taal = False
    return _taal or None


# ---------- het model ----------
def ram_gb():
    try:
        return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
    except Exception:
        return 16


def model():
    global _model
    if _model:
        return _model
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        log("taalmodel: mlx-lm installeren (eenmalig)")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "mlx-lm"], check=True)
    from mlx_lm import load
    naam = MODEL_BIG if ram_gb() >= 30 else MODEL_SMALL
    log(f"taalmodel laden: {naam} (de eerste keer wordt het gedownload)")
    _model = (naam, *load(naam))
    return _model


def vraag(system, user, max_tokens=1400, temp=0.6):
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    _, m, tok = model()
    prompt = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                     add_generation_prompt=True, tokenize=False)
    return generate(m, tok, prompt=prompt, max_tokens=max_tokens, sampler=make_sampler(temp=temp), verbose=False)


def als_json(tekst):
    tekst = re.sub(r"```(json)?", "", tekst)
    a, b = tekst.find("{"), tekst.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(tekst[a:b + 1])
        except json.JSONDecodeError:
            return None
    return None


# ---------- controle (dezelfde regels als src/tekstbank.py en src/concepten.py; de cloud controleert opnieuw) ----------
def woorden(t):
    return [w.lower().strip(" .,;:!?’'\"()") for w in t.split()]


def controle(e, vers):
    uit = []
    for veld, lo, hi in (("betekenis", 20, 320), ("toepassing", 20, 320), ("verhaal", 25, 140), ("uitleg", 10, 110),
                         ("zin", 10, 160), ("vraag", 8, 120)):
        n = len(str(e.get(veld) or "").strip())
        if not lo <= n <= hi:
            uit.append(f"{veld} is {n} tekens (moet {lo} tot {hi} zijn)")
    if e.get("vraag") and not str(e["vraag"]).strip().endswith("?"):
        uit.append("vraag moet op ? eindigen")
    h = e.get("hooks") or {}
    for s in ("vraag", "herkenning", "uitdaging", "rustig"):
        if not str(h.get(s) or "").strip():
            uit.append(f"hook '{s}' ontbreekt")
    if not 8 <= len(str(h.get("herkenning") or "")) <= 90:
        uit.append("herkenning moet 8 tot 90 tekens zijn")
    tags = e.get("tags") or []
    if not 3 <= len(tags) <= 5 or any(not re.fullmatch(r"#[0-9A-Za-zÀ-ſ]{2,30}", str(t)) for t in tags):
        uit.append("3 tot 5 hashtags, elk als #woord zonder spaties")
    if str(e.get("kw") or "").lower().strip(" .,;:!?") not in woorden(vers["tekst"]):
        uit.append("kw moet letterlijk een woord uit het vers zijn")
    alles = " ".join(str(v) for v in e.values() if isinstance(v, str)) + " " + " ".join(str(v) for v in h.values())
    if STREEP.search(alles):
        uit.append("geen streepjes (— of –) gebruiken")
    if CJK.search(alles):
        uit.append("alleen Nederlands, geen Chinese of Japanse tekens")
    if str(e.get("betekenis") or "").strip() in vers["tekst"]:
        uit.append("betekenis moet het vers uitleggen, niet herhalen")
    T = taal()
    if T:
        uit += T["problemen"](e, vers["tekst"], BANK_TAGS)
    return uit


SYSTEEM_VERS = """Je schrijft korte Nederlandse teksten bij een bijbelvers voor het Instagramkanaal Bibleverse.
Het vers is uit de Statenvertaling; jij schrijft in gewoon, warm, hedendaags Nederlands (jij/je), zonder kerkelijk jargon.
Regels:
- Leg alleen uit wat het vers zelf zegt. Geen beloftes die er niet staan, geen bijzondere leer, geen oordeel over mensen.
- Geen streepjes (— of –), geen emoji, geen hashtags buiten het veld tags.
- Schrijf nooit zelf een vers of citaat; verwijs alleen naar de inhoud.
- Antwoord met alleen JSON, zonder uitleg ervoor of erna.
Velden:
 kw: één kernwoord, LETTERLIJK een woord uit het vers (zo staat het in het vers, in kleine letters)
 uitleg: het vers in gewone taal, maximaal 110 tekens
 betekenis: 'Wat betekent dit?', 100 tot 300 tekens
 toepassing: 'Vandaag', één concrete, haalbare stap, 60 tot 250 tekens
 verhaal: openingszin die nieuwsgierig maakt, 40 tot 130 tekens
 zin: één korte zin voor onder de post, maximaal 140 tekens
 vraag: één oprechte open vraag aan de lezer, eindigt op ?, maximaal 100 tekens
 hooks: {vraag: korte vraag, herkenning: begint met 'Voor iedereen die' en is maximaal 85 tekens, uitdaging: korte opdracht, rustig: korte rustige zin}
 tags: 3 tot 5 hashtags van één bestaand Nederlands woord of een bijbelboek, bijvoorbeeld ["#rust","#vertrouwen","#bijbeltekst"]; verzin geen samengestelde hashtags
Spel namen zoals in de Nederlandse Bijbel: Paulus, Petrus, Jezus, Mozes, Maria, Jozef, Johannes, Jesaja. Zeg 'dit vers', niet 'deze passage'."""


def voorbeelden(bank, n=3):
    goed = [(k, e) for k, e in bank.items() if e.get("betekenis") and e.get("hooks", {}).get("herkenning") and e.get("verhaal")]
    uit = random.sample(goed, min(n, len(goed)))
    return "\n\n".join("Vers: {}\nJSON: {}".format(
        e["ref"], json.dumps({f: e[f] for f in ("kw", "uitleg", "betekenis", "toepassing", "verhaal", "zin", "vraag", "hooks", "tags")},
                                    ensure_ascii=False)) for k, e in uit)


REEKS_UITLEG = {
    "Advent": "Dit vers hoort bij de reeks Advent (de weken voor Kerst). Schrijf in het licht van Advent: verwachting, wachten en licht richting Kerst.",
    "Kerst": "Dit vers hoort bij Kerst. Schrijf in het licht van de geboorte van Jezus: blijdschap, vrede en God die dichtbij komt.",
    "Nieuwjaar": "Dit vers hoort bij Nieuwjaar. Schrijf in het licht van een nieuw begin.",
}


# ---------- nakijken: het model leest zijn eigen tekst na als strenge eindredacteur ----------
SYSTEEM_NAKIJK = """Je bent een strenge Nederlandse eindredacteur voor een bijbelvers-kanaal op Instagram.
Je krijgt een bijbelvers (Statenvertaling) en teksten die iemand erbij schreef. Controleer elk veld op:
1. Klopt het met wat het vers zegt? Niets erbij verzinnen, niets omdraaien, geen beloftes die er niet staan.
2. Is het natuurlijk, correct Nederlands zoals een Nederlander het zegt? Let op verkeerde woorden
   (bijvoorbeeld 'zijn leven voor een ander neemt' moet 'geeft' zijn, 'wordt aangezet als voorbeeld' moet 'wordt genoemd als voorbeeld' zijn,
   'God is op zijn hoede voor je behoeften' is fout), kromme zinnen ('Groots als Gods liefde is'), anglicismen en houterige formuleringen.
3. Past de herkenningszin (begint met 'Voor iedereen die') echt bij het vers?
4. Is de uitleg in gewone taal en niet gewoon de oude woorden van het vers?
Wees streng: twijfel je, dan is het fout. Verbeter elk fout veld zelf, kort en eenvoudig, in de jij-vorm, zonder streepjes.
Antwoord met alleen JSON: {"fouten": ["veld: wat er mis is", ...], "verbeterd": {"veld": "nieuwe tekst", ...}}.
Hooks verbeter je als "hooks.vraag", "hooks.herkenning", "hooks.uitdaging" of "hooks.rustig". Is alles goed: {"fouten": [], "verbeterd": {}}."""
TEKSTVELDEN = ("uitleg", "betekenis", "toepassing", "verhaal", "zin", "vraag")


def nakijken(e, vers):
    """Laat het model de tekst nalezen. Geeft (lijst fouten, item met verbeteringen)."""
    teksten = {f: e.get(f) for f in TEKSTVELDEN}
    teksten.update({f"hooks.{k}": v for k, v in (e.get("hooks") or {}).items()})
    user = (f"Vers: {vers['ref']}\nTekst: {vers['tekst']}\n\nTeksten om na te kijken:\n"
            f"{json.dumps(teksten, ensure_ascii=False, indent=1)}\nJSON:")
    d = als_json(vraag(SYSTEEM_NAKIJK, user, max_tokens=1200, temp=0.2))
    if not isinstance(d, dict):
        return ["nakijken gaf geen geldig antwoord"], e
    fouten = [str(f) for f in d.get("fouten") or [] if str(f).strip()]
    nieuw = json.loads(json.dumps(e))
    for veld, tekst in (d.get("verbeterd") or {}).items():
        if not isinstance(tekst, str) or not tekst.strip():
            continue
        if veld in TEKSTVELDEN:
            nieuw[veld] = tekst.strip()
        elif veld.startswith("hooks.") and veld[6:] in (nieuw.get("hooks") or {}):
            nieuw["hooks"][veld[6:]] = tekst.strip()
    return fouten, nieuw


def schrijf_vers(vers, bank):
    reeks = REEKS_UITLEG.get(vers.get("reeks", ""), "")
    user = (f"Zo ziet goed werk eruit (voorbeelden van eerdere verzen):\n\n{voorbeelden(bank)}\n\n"
            f"Nu het vers waar je voor schrijft:\nVers: {vers['ref']}\nTekst: {vers['tekst']}\nThema: {vers.get('thema', '')}\n"
            + (f"{reeks}\n" if reeks else "") + "JSON:")
    fouten = []
    for poging in range(3):
        extra = "" if not fouten else "\n\nDe vorige poging had deze fouten, los ze op: " + "; ".join(fouten)
        e = als_json(vraag(SYSTEEM_VERS, user + extra, temp=0.5 + 0.1 * poging))
        if not isinstance(e, dict):
            fouten = ["geef een geldig JSON-object"]
            continue
        e = {k: e.get(k) for k in ("kw", "uitleg", "betekenis", "toepassing", "verhaal", "zin", "vraag", "hooks", "tags")}
        e["ref"] = vers["ref"]
        e = {k: (v.strip() if isinstance(v, str) else v) for k, v in e.items()}
        T = taal()
        if T and isinstance(e.get("tags"), list):
            e["tags"] = T["schoon_tags"](e["tags"], BANK_TAGS)  # verzonnen hashtags eruit, aanvullen tot 3
        fouten = controle(e, vers)
        if fouten:
            continue
        # eindredactie: nakijken, verbeteringen overnemen, en de verbeterde versie nog één keer nakijken
        opm, e2 = nakijken(e, vers)
        if not opm:
            return dict(e, nagekeken=True), []
        log("  nakijken:", "; ".join(opm)[:300])
        if controle(e2, vers):
            fouten = opm
            continue
        opm2, _ = nakijken(e2, vers)
        if not opm2:
            return dict(e2, nagekeken=True), []
        fouten = opm2
    return None, fouten


# ---------- nieuws ----------
SYSTEEM_NIEUWS = """Je schrijft korte Nederlandse zinnen voor een bijbelvers-kanaal dat meeleeft met lichte nieuwsmomenten (weer, feestdagen, sport, drukte).
Elke zin is warm en luchtig, noemt het moment en trekt geen conclusies. Geen politiek, geen zwaar nieuws, geen namen van mensen of partijen.
Geen streepjes (— of –), geen emoji. Antwoord met alleen JSON: {"zinnen": [...], "bruggen": [...]}.
zinnen: 4 openingszinnen van 40 tot 110 tekens. bruggen: 3 korte zinnen van maximaal 45 tekens die uitleggen waarom het vers bij dit moment past."""


SYSTEEM_NAKIJK_ZIN = """Je bent een strenge Nederlandse eindredacteur. Je krijgt korte zinnen voor een bijbelvers-kanaal bij een licht nieuwsmoment.
Een zin is fout als hij geen natuurlijk, correct Nederlands is, onzin of verzonnen woorden bevat, niet bij de categorie past,
een spelfout heeft of vreemd klinkt. Twijfel je, dan is hij fout.
Antwoord met alleen JSON: {"fout": [de foute zinnen, letterlijk overgenomen]}."""


def nieuws_schrijven(cat, vb, bestaand):
    user = (f"Categorie: {cat}\nVoorbeelden openingszinnen: {json.dumps(vb.get('zinnen', []), ensure_ascii=False)}\n"
            f"Voorbeelden bruggen: {json.dumps(vb.get('bruggen', []), ensure_ascii=False)}\nSchrijf nieuwe, andere zinnen in dezelfde toon.")
    d = als_json(vraag(SYSTEEM_NIEUWS, user, max_tokens=900, temp=0.8)) or {}
    # eindredactie: alleen zinnen die natuurlijk Nederlands zijn en kloppen
    alle = [str(t).strip() for soort in ("zinnen", "bruggen") for t in d.get(soort, []) if str(t).strip()]
    if alle:
        oordeel = als_json(vraag(SYSTEEM_NAKIJK_ZIN, json.dumps({"categorie": cat, "zinnen": alle}, ensure_ascii=False) + "\nJSON:",
                                 max_tokens=600, temp=0.2)) or {}
        slecht = {str(t).strip() for t in oordeel.get("fout") or []}
        if not isinstance(oordeel.get("fout"), list):
            slecht = set(alle)  # geen geldig oordeel: niets doorlaten
        for soort in ("zinnen", "bruggen"):
            d[soort] = [t for t in d.get(soort, []) if str(t).strip() not in slecht]
    uit = {"zinnen": [], "bruggen": []}
    for soort, lo, hi in (("zinnen", 25, 120), ("bruggen", 10, 45)):
        for t in d.get(soort, []):
            t = str(t).strip()
            T = taal()
            if T and T["zin_problemen"](t):
                continue
            if lo <= len(t) <= hi and not STREEP.search(t) and not CJK.search(t) and t not in bestaand and t not in uit[soort]:
                uit[soort].append(t)
    return uit


# ---------- werk ----------
def state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def bewaar_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s))


def werk():
    global KEY
    KEY = token()
    cfg = lees("config.json", {})
    if not (cfg.get("lokale_ai") or {}).get("aan", True):
        log("lokale AI staat uit in config.json")
        return
    bank = lees("data/tekstbank.json", {})
    BANK_TAGS.update(t for e in bank.values() for t in e.get("tags") or [])
    conc = lees("data/concepten.json", {})
    conc.setdefault("verzen", {})
    conc.setdefault("afgekeurd", [])
    conc.setdefault("nieuws", {}).setdefault("zinnen", {})
    conc["nieuws"].setdefault("bruggen", {})
    s = state()
    nu = datetime.now(timezone.utc)
    gewijzigd = False
    tellers = {"concepten": 0, "mislukt": 0}

    # 1. verzen zonder tekst (bekende verzen eerst, dan de ontdekkingen uit de hele Bijbel)
    if len(conc["verzen"]) < MAX_OPEN_CONCEPTEN:
        bekend, pool = lees("data/verzen.json", []), lees("data/bijbel_pool.json", [])
        # reeksverzen (Advent, Kerst, Nieuwjaar) eerst, de eerstvolgende reeks vooraan: zonder tekst kan het systeem
        # de reekspost niet zelf maken
        reeksen = sorted(lees("data/reeksen.json", {}).get("reeksen", []), key=lambda r: r.get("van") or "9999")
        vandaag = datetime.now().strftime("%Y-%m-%d")
        reeks = [dict(v, reeks=r["naam"]) for r in reeksen if r.get("verzen") and (r.get("tot") or r.get("van") or "9999") >= vandaag
                 for v in r["verzen"]]
        gezien, wachtrij = set(), []
        for v in reeks + bekend + pool:
            if v["id"] in gezien:
                continue
            gezien.add(v["id"])
            if v["id"] not in bank and v["id"] not in conc["verzen"] and v["id"] not in conc["afgekeurd"]:
                wachtrij.append(v)
        for v in wachtrij[:VERZEN_PER_RONDE]:
            log("schrijven:", v["ref"])
            e, fouten = schrijf_vers(v, bank)
            if e:
                nk = e.pop("nagekeken", False)
                conc["verzen"][v["id"]] = {"e": e, "model": model()[0].split("/")[-1], "t": nu.isoformat(timespec="minutes"),
                                           "nagekeken": nk}
                tellers["concepten"] += 1
                gewijzigd = True
            else:
                tellers["mislukt"] += 1
                log("  mislukt:", "; ".join(fouten))

    # 2. nieuwszinnen (elke paar uur)
    laatste = s.get("nieuws_t")
    if not laatste or (nu - datetime.fromisoformat(laatste)).total_seconds() > NIEUWS_ELKE_UUR * 3600:
        vb = lees("data/nieuws_voorbeelden.json", {})
        extra = lees("data/nieuws_extra.json", {})
        for cat, d in vb.items():
            nu_n = len(conc["nieuws"]["zinnen"].get(cat, []))
            if nu_n >= MAX_NIEUWS_PER_CAT:
                continue
            bestaand = set(d.get("zinnen", []) + d.get("bruggen", []) + (extra.get("zinnen", {}).get(cat, [])) + (extra.get("bruggen", {}).get(cat, [])))
            bestaand |= {q["tekst"] for soort in ("zinnen", "bruggen") for q in conc["nieuws"][soort].get(cat, [])}
            log("nieuwszinnen:", cat)
            nieuw = nieuws_schrijven(cat, d, bestaand)
            for soort in ("zinnen", "bruggen"):
                for t in nieuw[soort]:
                    conc["nieuws"][soort].setdefault(cat, []).append({"tekst": t, "model": model()[0].split("/")[-1], "t": nu.isoformat(timespec="minutes")})
                    gewijzigd = True
        s["nieuws_t"] = nu.isoformat(timespec="minutes")

    if gewijzigd:
        # bij een gelijktijdige wijziging (Joshua keurde net iets goed) nieuw ophalen en samenvoegen
        for _ in range(3):
            if schrijf("data/concepten.json", conc, f"Lokale AI: {tellers['concepten']} nieuwe concepten"):
                break
            nieuw_conc = lees("data/concepten.json", {})
            nieuw_conc.setdefault("verzen", {}).update({k: v for k, v in conc["verzen"].items() if k not in nieuw_conc["verzen"] and k not in nieuw_conc.get("afgekeurd", [])})
            nieuw_conc.setdefault("afgekeurd", [])
            nieuw_conc.setdefault("nieuws", {"zinnen": {}, "bruggen": {}})
            for soort in ("zinnen", "bruggen"):
                for cat, qs in conc["nieuws"][soort].items():
                    have = {q["tekst"] for q in nieuw_conc["nieuws"][soort].get(cat, [])}
                    nieuw_conc["nieuws"][soort].setdefault(cat, []).extend(q for q in qs if q["tekst"] not in have)
            conc = nieuw_conc

    # hartslag: hooguit elke 3 uur, zodat het dashboard laat zien dat het programma leeft
    if gewijzigd or not s.get("hartslag") or (nu - datetime.fromisoformat(s["hartslag"])).total_seconds() > 3 * 3600:
        naam = _model[0].split("/")[-1] if _model else s.get("model", "")
        schrijf("data/lokale_ai.json", {"t": nu.isoformat(timespec="minutes"), "model": naam, "versie": VERSION,
                                        "laatste_ronde": tellers}, "Lokale AI: hartslag")
        s["hartslag"], s["model"] = nu.isoformat(timespec="minutes"), naam
    bewaar_state(s)
    log("klaar:", tellers)


def main():
    try:
        werk()
    except subprocess.CalledProcessError:
        log("Geen GitHub-sleutel in de sleutelhanger (service bibleverse-mac). Zie install.sh.")
    except Exception as e:  # nooit crashen met een rommelige melding; de volgende ronde probeert het opnieuw
        log("fout:", repr(e))


if __name__ == "__main__":
    main()
