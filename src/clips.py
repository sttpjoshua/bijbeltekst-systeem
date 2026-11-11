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
    "natuur": ["sunrise clouds", "ocean waves slow", "forest sunlight", "mountain lake", "wheat field wind", "sunset sky", "calm sea"],
    "dichtbij": ["hands holding coffee", "candle flame", "hands open light", "flower close up", "pages of book", "rain drops leaves"],
    "onderweg": ["cycling netherlands", "train window landscape", "rain on car window", "walking in rain", "city lights night"],
}


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


def zoek(term, n=12):
    d = _vraag("/videos", {"query": term, "page_size": n, "urls": "true", "sort": "popular"})
    hits = d.get("hits", [])
    # staand beeld heeft voorkeur, verder lang genoeg
    def getal(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0
    hits = [h for h in hits if getal(h.get("duration")) >= 4 and (h.get("urls") or {}).get("mp4")]
    hits.sort(key=lambda h: (not h.get("is_vertical"), -getal(h.get("downloads"))))
    return hits


def kies(soort, thema, rnd, gebruikt):
    """Eén clip van een scènesoort; vermijdt recent gebruikte clips. Geeft (pad, info) of (None, None)."""
    opties = SCENES[soort].get(thema, []) + SCENES[soort].get("algemeen", []) if soort == "situatie" else list(SCENES[soort])
    rnd.shuffle(opties)
    for term in opties[:4]:
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
            urllib.request.urlretrieve(h["urls"]["mp4"], pad)
        return pad, {"id": h["id"], "term": term, "titel": h.get("title"), "staand": h.get("is_vertical")}
    return None, None


def clips_voor(post, rnd=None):
    """Twee clips voor een reel: een herkenbare situatie en een rustig beeld (natuur, dichtbij of onderweg)."""
    rnd = rnd or random.Random(post["id"])
    log = S.laad("data/clips_gebruikt.json", [])
    gebruikt = {x["id"] for x in log[-150:]}
    thema = post["variabelen"].get("thema", "algemeen")
    rust = post["variabelen"].get("reel_scene") or rnd.choice(["natuur", "dichtbij", "onderweg"])
    a, ia = kies("situatie", thema, rnd, gebruikt)
    if ia:
        gebruikt.add(ia["id"])
    b, ib = kies(rust, thema, rnd, gebruikt)
    nieuw = [dict(i, post=post["id"]) for i in (ia, ib) if i]
    S.bewaar("data/clips_gebruikt.json", (log + nieuw)[-400:])
    return [p for p in (a, b) if p], rust


if __name__ == "__main__":  # test: python3 src/clips.py "sunrise"
    for h in zoek(sys.argv[1] if len(sys.argv) > 1 else "sunrise")[:5]:
        print(h["id"], h.get("title"), h.get("aspect_ratio"), h.get("is_vertical"), h.get("duration"))
