"""Echte videoclips voor reels (punt 5, 'herkenbare situatie'), via de gratis Coverr-API.

Geheim in GitHub: COVERR_KEY. De clips worden alleen gedownload om de reel te maken; ze komen nooit in de
openbare repo (alleen de gemaakte reel). data/clips_gebruikt.json onthoudt welke clips al zijn gebruikt,
zodat hetzelfde beeld niet snel terugkomt.
"""
import json, os, random, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S

API = "https://api.coverr.co"
MAP = os.environ.get("CLIPS_MAP", os.path.join(os.path.dirname(S.P(".")), "bibleverse-clips"))

# Scènesoorten: per soort zoektermen (Engels, zo zoekt Coverr). 'situatie' = herkenbaar moment (opening),
# de andere soorten zijn rustige beelden onder het vers.
SCENES = {
    "situatie": {
        "algemeen": ["woman looking out window", "man thinking", "person walking alone city", "commuter train window",
                     "person on phone at night", "tired woman desk", "student studying night", "man sitting on bench"],
        "troost": ["sad woman window", "person sitting alone", "rain on window", "man head in hands"],
        "vrede_rust": ["busy city crowd", "traffic jam", "stressed office worker", "alarm clock morning"],
        "moed": ["runner early morning", "person climbing", "woman looking at sea", "man standing on cliff"],
        "dankbaarheid": ["family dinner", "friends laughing", "coffee morning kitchen", "people hugging"],
        "liefde": ["couple holding hands", "mother and child", "friends hug", "old couple walking"],
        "hoop": ["sunrise window", "person watching sunrise", "child running field", "light through clouds"],
        "vertrouwen": ["person waiting station", "woman looking at horizon", "man walking forest path", "hands praying"],
        "wijsheid": ["reading book", "writing notebook", "old man thinking", "chess game"],
        "identiteit": ["woman mirror", "portrait smiling", "person looking at camera", "teenager thinking"],
        "humor_herkenbaar": ["snooze alarm bed", "spilled coffee", "cat lazy", "dog sleeping", "person procrastinating phone"],
    },
    "natuur": ["sunrise", "ocean", "forest", "lake", "wheat field", "sunset", "clouds", "mountains"],
    "dichtbij": ["candle", "coffee", "flowers", "hands", "book", "rain drops", "tea"],
    "onderweg": ["cycling", "train window", "rain window", "walking rain", "city night", "road trip"],
}


# Herkenningszin -> zoektermen. De eerste regel die past, wint; anders de lijst van het thema.
KOPPEL = [
    (r"snooze|wekker|opstaan|ochtendmens|vroeg op|uit bed", ["alarm clock", "waking up", "morning bed"]),
    (r"piekeren|wakker lag|slapen|nacht|23:00|malen", ["insomnia", "night bed", "awake night"]),
    (r"moe|uitgeput|op is|op bent|geen kracht|te veel|teveel", ["tired", "exhausted", "stress"]),
    (r"file|druk|haast|stress|agenda|to-do", ["traffic", "stress", "busy street"]),
    (r"trein|perron|onderweg|reis", ["train", "commute", "bus stop"]),
    (r"bang|angst|spannend|eng", ["anxious", "worried", "nervous"]),
    (r"verdriet|huil|rouw|mist|gebroken|pijn", ["sad", "crying", "grief"]),
    (r"alleen|eenzaam|onzichtbaar|vergeten", ["alone", "lonely", "solitude"]),
    (r"studeer|studie|examen|tentamen|leren", ["studying", "student", "homework"]),
    (r"werk|collega|baas|kantoor|maandag", ["office", "working laptop", "meeting"]),
    (r"koffie", ["coffee"]),
    (r"buurman|visite|vriend|samen|groepsapp", ["friends", "neighbors", "talking"]),
    (r"ruzie|boos|discussie|reageren|mail", ["argument", "angry", "frustrated"]),
    (r"lachen|grappig|blij", ["laughing", "smiling"]),
    (r"smoes|uitstellen|klusje|later", ["procrastination", "couch", "lazy"]),
    (r"dankbaar|cadeau|goed ging", ["family dinner", "smiling", "gratitude"]),
    (r"nieuw|begin|eerste dag", ["door", "new job", "road"]),
    (r"keuze|kiezen|beslissing|weet niet", ["crossroads", "thinking", "decision"]),
]
NIET = ("animat", "cartoon", " 3d", "3d ", "cgi", "render", "illustrat", "ai generated", "ai-generated", "generative", "motion graphic")


def _vraag(pad, params):
    key = os.environ.get("COVERR_KEY", "").strip()
    if not key:
        raise RuntimeError("geen COVERR_KEY")
    url = f"{API}{pad}?" + urllib.parse.urlencode(params)
    fouten = []
    # Coverr noemt in de documentatie geen vaste plek voor de sleutel: probeer de gangbare manieren
    for kop, extra in (({"Authorization": f"Bearer {key}"}, {}), ({}, {"api_key": key}), ({"Authorization": key}, {})):
        u = url + ("&" + urllib.parse.urlencode(extra) if extra else "")
        try:
            req = urllib.request.Request(u, headers={**kop, "User-Agent": "bibleverse/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            fouten.append(str(e)[:80])
    raise RuntimeError("Coverr gaf geen antwoord: " + " | ".join(fouten))


def _download(h, pad):
    """Haalt de clip op. Probeert de gewone, de download- en de voorvertoningslink, met en zonder sleutel."""
    key = os.environ.get("COVERR_KEY", "").strip()
    urls = h.get("urls") or {}
    fouten = []
    for soort in ("mp4", "mp4_download", "mp4_preview"):
        u = urls.get(soort)
        if not u:
            continue
        for kop in ({"User-Agent": "Mozilla/5.0 (bibleverse)"}, {"User-Agent": "Mozilla/5.0 (bibleverse)", "Authorization": f"Bearer {key}"},
                    {"User-Agent": "Mozilla/5.0 (bibleverse)", "Referer": "https://coverr.co/"}):
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers=kop), timeout=90) as r, open(pad, "wb") as f:
                    f.write(r.read())
                if os.path.getsize(pad) > 50000:
                    try:  # Coverr vraagt om downloads te melden (telt mee voor de makers)
                        req = urllib.request.Request(f"{API}/videos/{h['id']}/stats/downloads", method="PATCH",
                                                     headers={"Authorization": f"Bearer {key}", "User-Agent": "bibleverse/1.0"})
                        urllib.request.urlopen(req, timeout=15).read()
                    except Exception:
                        pass
                    return soort
            except Exception as e:
                fouten.append(f"{soort}: {str(e)[:40]}")
    if os.path.exists(pad):
        os.remove(pad)
    raise RuntimeError("; ".join(fouten[:6]))


ZOEKLOG = {}


def zoek(term, n=12):
    d = _vraag("/videos", {"query": term, "page_size": n, "urls": "true", "sort": "popular"})
    hits = d.get("hits", [])
    # staand beeld heeft voorkeur, verder lang genoeg
    def getal(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0
    def echt(h):  # geen animatie of AI-beelden
        t = " ".join([str(h.get("title") or ""), str(h.get("description") or ""), " ".join(map(str, h.get("tags") or []))]).lower()
        return not any(w in t for w in NIET)
    hits = [h for h in hits if getal(h.get("duration")) >= 4 and (h.get("urls") or {}).get("mp4") and echt(h)]
    hits.sort(key=lambda h: (not h.get("is_vertical"), -getal(h.get("downloads"))))
    ZOEKLOG[term] = len(hits)
    return hits


def kies(soort, thema, rnd, gebruikt, zin=""):
    """Eén clip van een scènesoort; vermijdt recent gebruikte clips. Geeft (pad, info) of (None, None).
    Bij 'situatie' bepaalt de herkenningszin de zoektermen (KOPPEL); anders het thema."""
    import re
    eerst = []
    if soort == "situatie" and zin:
        for patroon, termen in KOPPEL:
            if re.search(patroon, zin.lower()):
                eerst = list(termen); rnd.shuffle(eerst); break
    rest = SCENES[soort].get(thema, []) + SCENES[soort].get("algemeen", []) if soort == "situatie" else list(SCENES[soort])
    rnd.shuffle(rest)
    opties = eerst + [t for t in rest if t not in eerst]
    for term in opties[:5]:
        try:
            hits = [h for h in zoek(term) if h["id"] not in gebruikt]
        except Exception as e:
            print("Zoeken mislukt:", e); continue
        if not hits:
            continue
        h = hits[min(len(hits) - 1, rnd.randrange(3))]
        os.makedirs(MAP, exist_ok=True)
        pad = os.path.join(MAP, f"{h['id']}.mp4")
        if not os.path.exists(pad):
            try:
                _download(h, pad)
            except Exception as e:
                print("Download mislukt:", h["id"], e); continue
        return pad, {"id": h["id"], "term": term, "titel": h.get("title"), "staand": h.get("is_vertical")}
    return None, None


def clips_voor(post, rnd=None):
    """Twee clips voor een reel: een herkenbare situatie en een rustig beeld (natuur, dichtbij of onderweg)."""
    rnd = rnd or random.Random(post["id"])
    log = S.laad("data/clips_gebruikt.json", [])
    gebruikt = {x["id"] for x in log[-150:]}
    thema = post["variabelen"].get("thema", "algemeen")
    rust = post["variabelen"].get("reel_scene") or rnd.choice(["natuur", "dichtbij", "onderweg"])
    zin = post.get("reel_herkenning") or post.get("verhaal_hook") or post.get("hook") or ""
    a, ia = kies("situatie", thema, rnd, gebruikt, zin)
    if ia:
        gebruikt.add(ia["id"])
    b, ib = kies(rust, thema, rnd, gebruikt)
    nieuw = [dict(i, post=post["id"]) for i in (ia, ib) if i]
    S.bewaar("data/clips_gebruikt.json", (log + nieuw)[-400:])
    return [p for p in (a, b) if p], rust


if __name__ == "__main__":  # test: python3 src/clips.py "sunrise"
    for h in zoek(sys.argv[1] if len(sys.argv) > 1 else "sunrise")[:5]:
        print(h["id"], h.get("title"), h.get("aspect_ratio"), h.get("is_vertical"), h.get("duration"))
