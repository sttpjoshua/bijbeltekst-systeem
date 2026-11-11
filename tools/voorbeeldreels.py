"""Maakt voorbeeldreels 'herkenbare situatie' met echte Coverr-clips (in GitHub, met COVERR_KEY).
Uitvoer: docs/media/voorbeelden/*.mp4 en data/voorbeeldreels.json (welke clips, of de sleutel werkte)."""
import copy, json, os, random, sys, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import systeem as S, tekstbank as T, reels, clips

rapport = {"sleutel": bool(os.environ.get("COVERR_KEY")), "test": None, "reels": []}
try:
    h = clips.zoek("sunrise")
    rapport["test"] = f"ok: {len(h)} clips gevonden voor 'sunrise'"
except Exception as e:
    rapport["test"] = "mislukt: " + str(e)[:300]
print(rapport["test"])
bank = T.laad(); V = {v["id"]: v for v in S.alle_verzen()}
cfg = S.laad("config.json"); mat = S.materiaal(cfg)
basis = next(p for p in reversed(S.laad("data/posts.json", [])) if p["variabelen"]["formaat"] == "video")
voorbeelden = [("Proverbs-20-13-13", "natuur", "boven"), ("Matthew-6-34-34", "dichtbij", "midden"),
               ("Matthew-11-28-28", "onderweg", "boven"), ("Psalms-56-4-4", "natuur", "midden")]
os.makedirs(S.P("docs/media/voorbeelden"), exist_ok=True)
for i, (vid, scene, pl) in enumerate(voorbeelden):
    x, e = V[vid], bank[vid]
    p = copy.deepcopy(basis)
    p.update(id=f"voorbeeld-{i + 1}", ref=x["ref"], tekst=x["tekst"], vers_id=vid)
    p["variabelen"].update(thema=x["thema"], reel_scene=scene)
    S.bewaar("data/clips_gebruikt.json", [])  # voorbeelden: alles mag
    T.vul_post(p, e, cfg)
    muz = random.Random(i).choice(mat["muziek"]) if mat["muziek"] else None
    if muz:
        p["muziek_pad"] = os.path.join(S.materiaal_map(), muz); p["muziek_start"] = 12
    try:
        c, rust = clips.clips_voor(p, random.Random(vid))
        uit = S.P(f"docs/media/voorbeelden/situatie-{i + 1}-{scene}-{pl}.mp4")
        reels.maak_situatie(p, uit, c, pl)
        rapport["reels"].append({"bestand": os.path.relpath(uit, S.P(".")), "ref": x["ref"], "scene": scene, "plaatsing": pl,
                                 "clips": S.laad("data/clips_gebruikt.json", [])[-len(c):], "duur": p.get("duur")})
    except Exception as ex:
        traceback.print_exc()
        rapport["reels"].append({"ref": x["ref"], "fout": str(ex)[:300]})
S.bewaar("data/voorbeeldreels.json", rapport)
print(json.dumps(rapport, ensure_ascii=False, indent=1))
