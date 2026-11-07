"""Bouwt data/bijbel_pool.json: alle verzen uit de Statenvertaling (publiek domein) die los kunnen staan,
met automatisch thema, boekgroep en lengte. Gebruik: python3 tools/bouw_bijbel.py"""
import csv, json, re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from bouw_verzen import schoon

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOEKEN = {  # Engelse naam in de bron: (Nederlandse naam, boekgroep)
 "Genesis": ("Genesis", "verhaal"), "Exodus": ("Exodus", "verhaal"), "Deuteronomy": ("Deuteronomium", "verhaal"),
 "Joshua": ("Jozua", "verhaal"), "Ruth": ("Ruth", "verhaal"), "I Samuel": ("1 Samuël", "verhaal"), "II Samuel": ("2 Samuël", "verhaal"),
 "I Kings": ("1 Koningen", "verhaal"), "II Kings": ("2 Koningen", "verhaal"), "I Chronicles": ("1 Kronieken", "verhaal"),
 "II Chronicles": ("2 Kronieken", "verhaal"), "Nehemiah": ("Nehemia", "verhaal"), "Job": ("Job", "wijsheid"),
 "Psalms": ("Psalm", "psalmen"), "Proverbs": ("Spreuken", "spreuken"), "Ecclesiastes": ("Prediker", "wijsheid"),
 "Song of Solomon": ("Hooglied", "wijsheid"), "Isaiah": ("Jesaja", "profeten"), "Jeremiah": ("Jeremia", "profeten"),
 "Lamentations": ("Klaagliederen", "profeten"), "Ezekiel": ("Ezechiël", "profeten"), "Daniel": ("Daniël", "profeten"),
 "Hosea": ("Hosea", "profeten"), "Joel": ("Joël", "profeten"), "Amos": ("Amos", "profeten"), "Jonah": ("Jona", "profeten"),
 "Micah": ("Micha", "profeten"), "Nahum": ("Nahum", "profeten"), "Habakkuk": ("Habakuk", "profeten"),
 "Zephaniah": ("Sefanja", "profeten"), "Haggai": ("Haggaï", "profeten"), "Zechariah": ("Zacharia", "profeten"),
 "Malachi": ("Maleachi", "profeten"),
 "Matthew": ("Mattheüs", "evangelien"), "Mark": ("Markus", "evangelien"), "Luke": ("Lukas", "evangelien"),
 "John": ("Johannes", "evangelien"), "Acts": ("Handelingen", "brieven"), "Romans": ("Romeinen", "brieven"),
 "I Corinthians": ("1 Korinthe", "brieven"), "II Corinthians": ("2 Korinthe", "brieven"), "Galatians": ("Galaten", "brieven"),
 "Ephesians": ("Efeze", "brieven"), "Philippians": ("Filippenzen", "brieven"), "Colossians": ("Kolossenzen", "brieven"),
 "I Thessalonians": ("1 Thessalonicenzen", "brieven"), "II Thessalonians": ("2 Thessalonicenzen", "brieven"),
 "I Timothy": ("1 Timotheüs", "brieven"), "II Timothy": ("2 Timotheüs", "brieven"), "Titus": ("Titus", "brieven"),
 "Hebrews": ("Hebreeën", "brieven"), "James": ("Jakobus", "brieven"), "I Peter": ("1 Petrus", "brieven"),
 "II Peter": ("2 Petrus", "brieven"), "I John": ("1 Johannes", "brieven"), "Jude": ("Judas", "brieven"),
 "Revelation of John": ("Openbaring", "brieven"),
}
# Hoofdstukken waar de Nederlandse en Engelse versnummering verschilt: overslaan, anders klopt de verwijzing niet
VERSCHUIVING = {("Genesis",31),("Genesis",32),("Exodus",7),("Exodus",8),("Exodus",21),("Exodus",22),("Deuteronomy",12),("Deuteronomy",13),
 ("Deuteronomy",22),("Deuteronomy",23),("Deuteronomy",28),("Deuteronomy",29),("I Samuel",20),("I Samuel",21),("I Samuel",23),("I Samuel",24),
 ("II Samuel",18),("II Samuel",19),("I Kings",4),("I Kings",5),("II Kings",11),("II Kings",12),("I Chronicles",6),("II Chronicles",1),("II Chronicles",2),
 ("II Chronicles",13),("II Chronicles",14),("Nehemiah",3),("Nehemiah",4),("Nehemiah",7),("Nehemiah",8),("Nehemiah",9),("Nehemiah",10),
 ("Job",40),("Job",41),("Ecclesiastes",4),("Ecclesiastes",5),("Song of Solomon",6),("Song of Solomon",7),("Isaiah",8),("Isaiah",9),
 ("Isaiah",63),("Isaiah",64),("Jeremiah",8),("Jeremiah",9),("Ezekiel",20),("Ezekiel",21),("Daniel",3),("Daniel",4),("Daniel",5),("Daniel",6),
 ("Hosea",1),("Hosea",2),("Hosea",11),("Hosea",12),("Hosea",13),("Hosea",14),("Joel",2),("Joel",3),("Jonah",1),("Jonah",2),("Micah",4),("Micah",5),
 ("Nahum",1),("Nahum",2),("Zechariah",1),("Zechariah",2),("Malachi",3),("Malachi",4),("Romans",14),("Romans",16),("II Corinthians",13)}

THEMA = {  # trefwoorden in de Statenvertaling-spelling (kleine letters)
 "troost": ["troost", "vertroost", "tranen", "treur", "ellende", "verbroken", "benauwd", "nabij", "verlaat u niet", "niet begeven", "ontferm"],
 "moed": ["vrees niet", "vreest niet", "vreest gij niet", "sterk", "moed", "kracht", "ontzet u niet", "verschrikt", "versaag"],
 "liefde": ["liefde", "liefgehad", "liefhebben", "liefheeft", "bemin", "goedertieren", "barmhartig"],
 "hoop": ["hoop", "hope", "verwacht", "belofte", "beloofd", "nieuw", "toekomst"],
 "vertrouwen": ["vertrouw", "betrouw", "geloof", "toevlucht", "schild", "rotssteen", "burg", "getrouw"],
 "wijsheid": ["wijs", "wijsheid", "verstand", "verstandig", "raad", "kennis", "onderwijs", "tucht"],
 "humor_herkenbaar": ["luiaard", "luie", "zot", "dwaas", "dwaasheid", "spotter", "mier", "slaap", "kijf", "tong"],
 "dankbaarheid": ["loof", "looft", "dank", "prijs", "psalmzing", "zingt", "juich", "verblijd", "vreugde", "blijdschap"],
 "identiteit": ["kinderen gods", "kind gods", "uitverkoren", "geroepen", "zonen", "erfgena", "geschapen", "kostelijk", "bij naam", "mijn volk"],
 "vrede_rust": ["vrede", "rust", "stil", "gerust", "zalig", "veilig", "verkwik"],
}
VERBODEN = ["bloed", "doodslag", "dood", "doden", "dode", "sloeg", "slaan", "verdelg", "hoer", "vervloek", "zwaard", "offer", "besnijd",
 "melaats", "ontucht", "overspel", "verbrand", "brandoffer", "vijanden", "uitroeien", "stenigen", "wraak", "toorn", "verderf", "hel",
 "duivel", "satan", "wee ", "verwoest", "verslagen", "neder", "plaag", "plagen", "vrouwen", "dochteren", "altaren", "afgod", "goddeloze", "dronken", "naakt", "schaamte", "lijk", "beest", "koning van", "zonen van", "dochters van", "zoon van", "kamelen"]
EIGEN_OK = {"HEERE", "Heere", "God", "Gods", "Gode", "Hij", "Hem", "Hem.", "Zijn", "Zijner", "Zijne", "Mijn", "Mijner", "Ik", "Gij", "U", "Uw", "Uwe", "Uwer",
 "Christus", "Jezus", "Geest", "Geestes", "Vader", "Zoon", "Heilige", "Heiligen", "Allerhoogste", "Almachtige", "Die", "Dien", "Dat", "Welke",
 "Zich", "Zichzelven", "Mij", "Denwelken", "Wien", "Wiens", "Rotssteen", "Toevlucht", "Herder", "Heer", "Heiland", "Zaligmaker", "Verlosser",
 "Koning", "Schild", "Sterkte", "Burg", "Hoorn", "Heil", "Licht", "Woord", "Naam", "Lam", "Schepper", "Israëls", "O"}
FRAGMENT = ("Als ", "Welke", "Welken", "Dewijl", "Opdat", "Waarom", "Daarom", "Hetwelk", "Dewelke", "Waardoor", "Gelijk", "Hoewel",
 "Indien", "Nadat", "Wanneer", "Zodat", "Doch als", "Maar als", "En als", "Hierom", "Hiertoe", "Dezelve", "Hij zeide", "Zij zeiden")
GODSNAMEN = ["heere", "god", "heer", "jezus", "christus", "geest", "vader", "hij "]

def lengteklas(n):
    return "kort" if n < 90 else "middel" if n < 170 else "lang"

def main():
    rijen = list(csv.DictReader(open(os.path.join(HIER, "data/DutSVV.csv"), encoding="utf-8")))
    laatste = {}
    for r in rijen:
        k = (r["Book"], int(r["Chapter"]))
        laatste[k] = max(laatste.get(k, 0), int(r["Verse"]))
    pool = []
    for r in rijen:
        b, c, v = r["Book"], int(r["Chapter"]), int(r["Verse"])
        if b not in BOEKEN or (b, c) in VERSCHUIVING or not r["Text"].strip():
            continue
        if v == laatste[(b, c)] and b in ("Psalms", "Lamentations"):
            continue  # laatste vers: in de bron soms samengevoegd met het volgende Nederlandse vers
        try:
            t = schoon(r["Text"])
        except IndexError:
            continue
        if not (30 <= len(t) <= 230):
            continue
        laag = " " + t.lower() + " "
        if any(w in laag for w in VERBODEN):
            continue
        if t.count(":") >= 2 or t.startswith(("En hij zeide", "En zij zeiden", "En Jezus zeide", "Toen", "Daarna", "En het geschiedde")):
            continue  # verhalende of dialoogfragmenten
        scores = {th: sum(laag.count(w) for w in ws) for th, ws in THEMA.items()}
        thema, s = max(scores.items(), key=lambda x: x[1])
        if s == 0:
            continue
        t = re.sub(r"\s*Sela\.?", "", t).strip()
        if t and t[-1] not in ".!?":
            t += "."
        god = any(w in laag for w in GODSNAMEN)
        persoonlijk = bool(re.search(r"\b(gij|u|uw|ulieden|uzelven|mijn ziel|ik|mij|wij|ons|onze)\b", laag))
        woorden = re.findall(r"\b[A-Z][a-zë]+", t[1:])
        namen = [w for w in woorden if w not in EIGEN_OK]
        kwaliteit = (s * 2 + (2 if god else 0) + (2 if persoonlijk else 0) + (1 if 40 <= len(t) <= 150 else 0)
                     - (1 if t.startswith(("En ", "Want ", "Maar ", "Doch ")) else 0)
                     - (3 if t.startswith(FRAGMENT) else 0) - 3 * len(namen)
                     + (1 if BOEKEN[b][1] in ("psalmen", "spreuken") else 0) - (3 if BOEKEN[b][1] == "verhaal" else 0))
        if kwaliteit < 5:
            continue
        nl, groep = BOEKEN[b]
        pool.append({"id": f"{b}-{c}-{v}-{v}".replace(" ", "_"), "ref": f"{nl} {c}:{v}", "tekst": t, "thema": thema,
                     "boekgroep": groep, "lengte": lengteklas(len(t)), "kwaliteit": kwaliteit})
    # Na handmatige controle afgekeurd (en later door de dagelijkse taak via 'vervang')
    pad_af = os.path.join(HIER, "data/pool_afgekeurd.json")
    afgekeurd = set(json.load(open(pad_af))) if os.path.exists(pad_af) else set()
    pad_goed = os.path.join(HIER, "data/pool_goedgekeurd.json")
    goed = set(json.load(open(pad_goed))) if os.path.exists(pad_goed) else set()
    alles = [x for x in pool if x["id"] not in afgekeurd]
    pool = [x for x in alles if x["kwaliteit"] >= 7 or x["id"] in goed]
    # Kandidaten: nog niet beoordeeld; de wekelijkse taak keurt er telkens een stapel en de pool groeit mee
    kandidaten = sorted((x for x in alles if x["kwaliteit"] < 7 and x["id"] not in goed), key=lambda x: -x["kwaliteit"])
    json.dump(kandidaten, open(os.path.join(HIER, "data/bijbel_kandidaten.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(kandidaten), "kandidaten nog te beoordelen")
    json.dump(pool, open(os.path.join(HIER, "data/bijbel_pool.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    import collections
    print(len(pool), "verzen in de pool")
    print(collections.Counter(x["thema"] for x in pool))
    print(collections.Counter(x["boekgroep"] for x in pool))

if __name__ == "__main__":
    main()
