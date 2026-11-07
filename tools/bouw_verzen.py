"""Bouwt data/verzen.json uit de publiek-domein Statenvertaling (scrollmapper DutSVV.csv).
Gebruik: python3 tools/bouw_verzen.py pad/naar/DutSVV.csv
"""
import csv, json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from selectie import SELECTIE

NL = {
    "Luke": "Lukas",
    "Acts": "Handelingen",
    "Job": "Job",
    "II Samuel": "2 Samuël",
    "I Timothy": "1 Timotheüs",
    "Titus": "Titus",
    "Hosea": "Hosea",
    "Zechariah": "Zacharia",
    "Numbers": "Numeri",
    "Ruth": "Ruth",
    "II Chronicles": "2 Kronieken",
    "Joel": "Joël",
    "II Thessalonians": "2 Thessalonicenzen",
    "II Peter": "2 Petrus",
    "Jude": "Judas",
    "Malachi": "Maleachi",
    "I Chronicles": "1 Kronieken",
    "Leviticus": "Leviticus",
    "Daniel": "Daniël",
    "Jonah": "Jona",
    "Ezekiel": "Ezechiël",
    "Genesis": "Genesis", "Exodus": "Exodus", "Deuteronomy": "Deuteronomium", "Joshua": "Jozua",
    "I Samuel": "1 Samuël", "Nehemiah": "Nehemia", "Psalms": "Psalm", "Proverbs": "Spreuken",
    "Ecclesiastes": "Prediker", "Song of Solomon": "Hooglied", "Isaiah": "Jesaja", "Jeremiah": "Jeremia",
    "Lamentations": "Klaagliederen", "Micah": "Micha", "Nahum": "Nahum", "Habakkuk": "Habakuk",
    "Zephaniah": "Sefanja", "Matthew": "Mattheüs", "Mark": "Markus", "John": "Johannes",
    "Romans": "Romeinen", "I Corinthians": "1 Korinthe", "II Corinthians": "2 Korinthe",
    "Galatians": "Galaten", "Ephesians": "Efeze", "Philippians": "Filippenzen", "Colossians": "Kolossenzen",
    "I Thessalonians": "1 Thessalonicenzen", "II Timothy": "2 Timotheüs", "Hebrews": "Hebreeën",
    "James": "Jakobus", "I Peter": "1 Petrus", "I John": "1 Johannes", "Revelation of John": "Openbaring",
}

def schoon(t):
    # Opschriften van psalmen weghalen ("Een psalm van David." e.d.)
    t = re.sub(r"^(Een psalm|Een lied|Een gebed|Een onderwijzing|Een gouden kleinood|Voor den opperzangmeester)[^.]*\.\s*", "", t)
    # Hebreeuwse letters als versopschrift (Psalm 119, Klaagliederen e.d.)
    t = re.sub(r"\b(Aleph|Beth|Gimel|Daleth|He|Vav|Zain|Cheth|Teth|Jod|Caph|Lamed|Mem|Nun|Samech|Ain|Pe|Tsade|Koph|Resch|Schin|Thau)\.\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = t.rstrip(":;,")
    if t and t[-1] not in ".!?":
        t += "."
    return t[0].upper() + t[1:]

# Uitgesloten na controle: samengevoegde of verschoven verzen in de bron, te lang, of ongeschikt
UITSLUITEN = {("Psalms",55,23,23),("Psalms",46,11,11),("Nehemiah",8,10,10),("Nehemiah",8,11,11),
              ("Proverbs",25,24,24),("Proverbs",21,9,9),("Proverbs",11,22,22)}
MAX_LENGTE = 260

def main(pad):
    tekst = {}
    for r in csv.DictReader(open(pad, encoding="utf-8")):
        tekst[(r["Book"], int(r["Chapter"]), int(r["Verse"]))] = r["Text"]
    uit, missend = [], []
    for thema, refs in SELECTIE.items():
        for boek, h, v1, v2 in refs:
            if (boek, h, v1, v2) in UITSLUITEN: continue
            delen = [tekst.get((boek, h, v)) for v in range(v1, v2 + 1)]
            if None in delen:
                missend.append((boek, h, v1, v2)); continue
            t = schoon(" ".join(delen))
            if len(t) > MAX_LENGTE:
                missend.append(("te lang", boek, h, v1)); continue
            ref = f"{NL[boek]} {h}:{v1}" + (f"-{v2}" if v2 != v1 else "")
            uit.append({"id": f"{boek}-{h}-{v1}-{v2}".replace(" ", "_"), "ref": ref, "tekst": t,
                        "thema": thema, "lengte": len(t)})
    os.makedirs("data", exist_ok=True)
    json.dump(uit, open("data/verzen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(uit), "versen;", "missend:", missend)
    for v in sorted(uit, key=lambda x: -x["lengte"])[:8]:
        print(v["lengte"], v["ref"])

if __name__ == "__main__":
    main(sys.argv[1])
