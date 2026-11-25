"""Het karakter (intern 'noor'): de persoonlijke stem van het kanaal. Haar naam komt NOOIT op een post, in een caption,
een bio of een bericht; alleen de stem. Zie KARAKTER.md voor de canon.

data/noor.json: {vers_id: {"verhaal","zin","vraag","herkenning", optioneel "betekenis","toepassing"}}
Toon "noor" is alleen mogelijk voor verzen die hier staan; de rest valt terug op de standaardtoon.
"""
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = os.path.join(ROOT, "data", "noor.json")

# Persoonlijke openingsregels per moment van de dag. Elke regel heeft hoogstens een persoonlijk detail uit de canon.
OCHTEND = ["Goedemorgen. Het is nog donker en mijn koffie is al half leeg.",
           "Goedemorgen. Ik ben alweer vroeg wakker, dus ik deel dit vers vast met je.",
           "Het is nog stil in huis. Dit vers ligt al een tijdje bij me.",
           "Eerste koffie, eerste vers van de dag.",
           "Ik zit met mijn koffie en dit vers, voor de rest van de stad wakker is."]
MIDDAG_WERK = ["Even pauze. Dit vers kwam vanochtend bij me terug.",
               "Lunchpauze, telefoon in de hand. Dit wilde ik even met je delen.",
               "Een moment tussen het werk door, en dit vers."]
MIDDAG_VRIJ = ["Even tussendoor. Dit vers wilde ik met je delen.", "Rustig middagmoment, en dit vers erbij."]
AVOND_FIETS_WERK = ["Ik fiets net naar huis, met mijn rammelende spatbord. Dit vers fietste mee.",
                    "Onderweg naar huis dacht ik aan dit vers."]
AVOND_FIETS_VRIJ = ["Ik ben nog even buiten geweest. Dit vers liep met me mee.", "De avond begint. Dit vers hoort erbij."]
AVOND = ["Ik zit op de bank met dit vers. Ik wilde het even met je delen.",
         "De dag is bijna om en dit vers is nog niet klaar met mij."]
NACHT = ["Voor ik ga slapen, dit.", "Nog één ding voor ik het licht uitdoe."]
DAG = {4: ["Het is vrijdag en ik heb een vrije dag. Dit vers had ik nodig.", "Vrijdag, mijn vrije dag. Tijd voor een vers en een wandeling."],
       5: ["Een rommelige zaterdag, en dit vers midden in de chaos."],
       6: ["Zondag. Mijn moeder belt straks, en dit vers ligt al klaar."]}
SEIZOEN = {"winter": ["Het is donker en nat buiten. Dit vers voelt warm.", "Soep op het fornuis en dit vers erbij."],
           "advent": ["Advent. De stad is druk en ik zoek de stilte."],
           "lente": ["Het wordt weer licht. Mijn planten leven langzaam op."],
           "zomer": ["Ik fiets langs het water. Dit vers fietste mee."],
           "herfst": ["Regen tegen het raam. Een goed moment voor dit vers."]}


def seizoen(d):
    if d.month == 12:
        return "advent"
    return {1: "winter", 2: "winter", 11: "winter", 3: "lente", 4: "lente", 5: "lente", 6: "zomer", 7: "zomer", 8: "zomer",
            9: "herfst", 10: "herfst"}[d.month]


def laad():
    try:
        return json.load(open(PAD, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def beschikbaar(vers_id):
    return vers_id in laad()


def samenvoegen(e, vers_id):
    """Bankitem met Noors teksten erover heen (alleen de velden die zij heeft). None als dit vers nog geen Noor-teksten heeft."""
    n = laad().get(vers_id)
    if not n:
        return None
    m = dict(e)
    for k in ("verhaal", "zin", "vraag", "betekenis", "toepassing"):
        if (n.get(k) or "").strip():
            m[k] = n[k].strip()
    h = dict(m.get("hooks") or {})
    if (n.get("herkenning") or "").strip():
        h["herkenning"] = n["herkenning"].strip()
    if (n.get("vraag") or "").strip():
        h["vraag"] = n["vraag"].strip()
    m["hooks"] = h
    return m


def _kies(lijst, sleutel):
    return lijst[sum(map(ord, sleutel)) % len(lijst)]


def opener(p):
    """Persoonlijke openingsregel die klopt met tijdslot, weekdag en seizoen (de canon). Vast per post."""
    d = dt.date.fromisoformat(p["datum"])
    slot = (p.get("variabelen") or {}).get("tijdslot") or "12:15"
    werkdag = d.weekday() <= 3
    sleutel = p["id"] + p["datum"]
    # bijzondere dag of seizoen in ongeveer 2 van de 5 posts
    if sum(map(ord, sleutel)) % 5 < 2:
        if d.weekday() in DAG:
            return _kies(DAG[d.weekday()], sleutel)
        if slot >= "17:45" or slot < "10:00":
            return _kies(SEIZOEN[seizoen(d)], sleutel)
    if slot < "10:00":
        return _kies(OCHTEND, sleutel)
    if slot < "17:00":
        return _kies(MIDDAG_WERK if werkdag else MIDDAG_VRIJ, sleutel)
    if slot < "19:00":
        return _kies(AVOND_FIETS_WERK if werkdag else AVOND_FIETS_VRIJ, sleutel)
    if slot < "21:30":
        return _kies(AVOND, sleutel)
    return _kies(NACHT, sleutel)


# ---------- controle ----------
# Tegenstrijdig met de canon: wordt geblokkeerd (de tekst komt niet door).
def _seizoenswoorden(tekst, d):
    uit = []
    t = tekst.lower()
    s = seizoen(d)
    if re.search(r"\b(kerst|advent)\b", t) and d.month != 12:
        uit.append("kerst of advent buiten december")
    if re.search(r"\bzomer", t) and s != "zomer":
        uit.append("zomer buiten de zomer")
    if re.search(r"\b(sneeuw|ijskoud|kaarsen)\b", t) and s not in ("winter", "advent"):
        uit.append("winterwoord buiten de winter")
    return uit


def tegenstrijdig(p, tekst):
    """Controle van de persoonlijke tekst (niet het vers) op tegenstrijdigheden met de canon."""
    d = dt.date.fromisoformat(p["datum"])
    slot = (p.get("variabelen") or {}).get("tijdslot") or "12:15"
    t = tekst.lower()
    uit = []
    if re.search(r"\bkoffie\b", t) and slot >= "10:00":
        uit.append("koffie buiten de ochtend")
    if re.search(r"\b(donker|zonsopkomst)\b", t) and slot >= "10:00" and not re.search(r"\b(winter|avond)\b", t) and slot < "17:45":
        uit.append("donker op een lichte tijd van de dag")
    wd = d.weekday()
    if re.search(r"\bzondag\b", t) and wd != 6:
        uit.append("zondag op een andere dag")
    if re.search(r"\bvrije dag\b|\bvrijdag\b", t) and wd != 4:
        uit.append("vrije dag of vrijdag op een andere dag")
    if re.search(r"\bzaterdag\b", t) and wd != 5:
        uit.append("zaterdag op een andere dag")
    if re.search(r"\b(werk|kantoor|bureau|deadline)\b", t) and wd >= 4:
        uit.append("werk op een vrije dag")
    if re.search(r"\b(vader|broer|vriend|vriendje|partner|man|vrouw|kinderen|kind|baby|zoon|dochter|oma overleed)\b", t):
        uit.append("familie of relatie buiten de vaste feiten")
    if re.search(r"\bik ben (een )?(echt|echte)\b|\bje kent mij\b", t):
        uit.append("beweert een echt mens te zijn")
    uit += _seizoenswoorden(t, d)
    # de naam nooit zichtbaar
    if re.search(r"\bnoor\b", t):
        uit.append("haar naam mag nooit zichtbaar zijn")
    return uit


# Gevoelig: wordt NIET geblokkeerd, maar gaat nooit automatisch online. Het komt eerst bij Joshua ter goedkeuring.
GEVOELIG = r"\b(ziek|ziekte|kanker|overleden|overlijden|rouw|verlies|scheiding|gescheiden|schuld|schulden|therapie|depressie|burn-?out|" \
           r"genezing|genezen|wonder|wonderen|partij|kabinet|verkiezing|abortus|euthanasie|oorlog|aanslag|slachtoffer|dood|doden)\b"


def gevoelig(tekst):
    """Geeft de gevonden woorden terug (leeg = niet gevoelig)."""
    return sorted({m.group(0).lower() for m in re.finditer(GEVOELIG, tekst.lower())})


def persoonlijke_tekst(p):
    """Alles wat het karakter zelf schreef in deze post (zonder het vers en de uitleg uit de bank)."""
    return " ".join(str(x) for x in (p.get("hook"), p.get("verhaal_hook"), p.get("reel_herkenning"), p.get("reel_vraag")) if x)


def controleer_post(p):
    """Zet op de post: noor_problemen (blokkeert) en goedkeuring_nodig (gevoelig). Geeft (problemen, gevoelige_woorden)."""
    tekst = persoonlijke_tekst(p) + " " + (p.get("caption") or "").replace(p.get("tekst", "\0"), "")
    problemen = tegenstrijdig(p, tekst)
    woorden = gevoelig(tekst + " " + (p.get("nieuws") or {}).get("kop", "")) if (p.get("nieuws") or p["variabelen"].get("toon") == "noor") else []
    return problemen, woorden
