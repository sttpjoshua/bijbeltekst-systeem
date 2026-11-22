"""Taalcontrole voor teksten die een taalmodel schreef (lokale AI op de Mac, zie tools/mac/bijbel_helper.py).

Vangt wat de gewone controle niet ziet:
  - verkeerd gespelde Bijbelnamen en feestdagen ("Pauwels" in plaats van Paulus, "Sinterklas")
  - bekende verkeerde woorden ("Gods vrede regent over ons" in plaats van regeert)
  - woorden die in het Nederlands niet bestaan ("aangewakend"), als wordfreq geïnstalleerd is
  - hashtags die niet in de tekstbank voorkomen en geen gewoon Nederlands woord zijn ("#vredetrots")
Het Mac-programma haalt dit bestand bij elke ronde van GitHub op, dus verbeteringen hier gelden meteen.
Dit bestand gebruikt alleen de standaardbibliotheek (wordfreq is optioneel).
"""
import difflib
import re

NAMEN = """Paulus Petrus Jezus Christus Mozes David Abraham Isaak Jakob Jozef Maria Marta Johannes Jesaja Jeremia Elia
Elisa Salomo Timotheüs Titus Zacharias Simeon Mattheüs Lukas Markus Noach Daniël Jona Ruth Ester Job Habakuk Micha
Bethlehem Jeruzalem Israël Immanuel Emmanuel Kerst Kerstmis Advent Pasen Pinksteren Sinterklaas Sint-Maarten Golgotha
Nazareth Galilea Jordaan Egypte Babel Sion Psalmen Spreuken Prediker Romeinen Korinthe Galaten Efeze Filippenzen
Kolossenzen Hebreeën Jakobus Openbaring Genesis Exodus Deuteronomium Jozua Samuel Klaagliederen Sefanja Nahum Numeri
Hooglied Thessalonicenzen Handelingen Heilige Geest Vader Heere Psalm Zacharia Obadja Haggai Maleachi Hosea Joël Amos
Ezechiël Nehemia Ezra Kronieken Koningen Richteren Leviticus Mattheus Hebreeen Johannes""".split()
# vaak gemaakte fouten (ook Engelse namen): verkeerd -> goed
VERKEERD = {"pauwels": "Paulus", "paul": "Paulus", "jesus": "Jezus", "moses": "Mozes", "mary": "Maria",
            "joseph": "Jozef", "john": "Johannes", "peter": "Petrus", "isaiah": "Jesaja", "christmas": "Kerst",
            "sinterklas": "Sinterklaas", "jeruzalam": "Jeruzalem", "bethlehem": None}
_NAMEN_L = {n.lower() for n in NAMEN}

# vaste fouten die een model vaak maakt: patroon -> uitleg voor de volgende poging
VASTE_FOUTEN = [
    (r"\bregen(t|en|de)\s+(over|in|op|door)\b", "'regent' komt van regen; bedoel je 'regeert'?"),
    (r"\bonverwoestbaar\b", "'onverwoestbaar' klinkt vreemd; zeg 'die niemand je kan afpakken'"),
    (r"\bpassage\b", "zeg 'dit vers' in plaats van 'deze passage'"),
    (r"\bdeze tekst stelt voor\b|\bdit vers stelt voor\b", "'stelt voor' is een anglicisme; zeg 'zegt' of 'laat zien'"),
]

STANDAARD_TAGS = ("#bijbeltekst", "#geloof", "#bemoediging")

try:
    from wordfreq import zipf_frequency as _zipf
except Exception:  # niet geïnstalleerd: de woordcontrole valt dan weg, de rest werkt wel
    _zipf = None


def _woorden(t):
    return re.findall(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)?", t or "")


def bestaat(w):
    """True als het woord Nederlands is (of als dat niet te controleren is). Samenstellingen van twee bekende
    woorden tellen ook (klusjeslijst, studiemoeheid)."""
    if _zipf is None:
        return True
    w = w.lower()
    if len(w) <= 2 or _zipf(w, "nl") > 0 or w in _NAMEN_L:
        return True
    for i in range(4, len(w) - 3):  # beide delen minstens 4 letters, en samen gangbaar genoeg ('aange' + 'wakend' niet)
        a, b = w[:i], w[i:]
        za = max(_zipf(a, "nl"), _zipf(a[:-1], "nl") if a.endswith("s") else 0)  # tussen-s: geloofsfamilie
        zb = _zipf(b, "nl")
        if min(za, zb) >= 2.0 and za + zb >= 6.0:
            return True
    return False


def naamfout(w):
    """Geeft de juiste naam als w er een verkeerde spelling van lijkt (Pauwels -> Paulus), anders None."""
    l = w.lower()
    if VERKEERD.get(l):
        return VERKEERD[l]
    if not w[:1].isupper():
        return None
    if l in _NAMEN_L or (l.endswith("s") and l[:-1] in _NAMEN_L):  # Davids, Gods
        return None
    if _zipf is None or _zipf(l, "nl") >= 2.5:
        return None  # een bestaand woord (Piekeren, Hoogmoed aan het begin van een zin)
    m = difflib.get_close_matches(l, _NAMEN_L, 1, 0.75)
    if m:
        return next(n for n in NAMEN if n.lower() == m[0])
    return None


def tag_goed(t, bekende=()):
    t = str(t).strip()
    if not re.fullmatch(r"#[0-9A-Za-zÀ-ſ]{2,30}", t):
        return False
    l = t.lower()
    if l in {x.lower() for x in bekende} or l in STANDAARD_TAGS or l[1:].lstrip("0123456789") in _NAMEN_L:
        return True
    return _zipf is not None and _zipf(l[1:], "nl") >= 3.0  # één gewoon woord: #mier, #inspiratie


def schoon_tags(tags, bekende=()):
    """Haalt verzonnen hashtags weg en vult aan tot minstens 3."""
    uit = []
    for t in tags or []:
        t = str(t).strip()
        if tag_goed(t, bekende) and t.lower() not in [u.lower() for u in uit]:
            uit.append(t)
    for t in STANDAARD_TAGS:
        if len(uit) >= 3:
            break
        if t not in uit:
            uit.append(t)
    return uit[:5]


def problemen(e, vers_tekst="", bekende_tags=()):
    """Lijst met taalproblemen in een bankitem (leeg = goed). Woorden uit het vers zelf tellen altijd als goed."""
    uit = []
    velden = [str(e.get(f) or "") for f in ("uitleg", "betekenis", "toepassing", "verhaal", "zin", "vraag")]
    velden += [str(h or "") for h in (e.get("hooks") or {}).values()]
    tekst = " ".join(velden)
    in_vers = {w.lower() for w in _woorden(vers_tekst)}
    gemeld = set()
    for w in _woorden(tekst):
        l = w.lower()
        if l in in_vers or l in gemeld:
            continue
        n = naamfout(w)
        if n and n.lower() != l:
            uit.append(f"'{w}' is verkeerd gespeld, het is '{n}'"); gemeld.add(l)
        elif not bestaat(w):
            uit.append(f"'{w}' is geen Nederlands woord"); gemeld.add(l)
    for patroon, uitleg in VASTE_FOUTEN:
        if re.search(patroon, tekst, re.I):
            uit.append(uitleg)
    for t in e.get("tags") or []:
        if not tag_goed(t, bekende_tags):
            uit.append(f"hashtag {t} bestaat niet of is te vaag")
    return uit


def zin_problemen(t):
    """Voor losse nieuwszinnen en bruggen."""
    return problemen({"zin": t})
