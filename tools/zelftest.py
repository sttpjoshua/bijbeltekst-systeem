"""Wekelijkse zelftest: maakt van elke huisstijl een carrousel, twee video's en een story in een tijdelijke map
en controleert of alles klopt. Resultaat komt als 'zelftest' in de gezondheid op het dashboard."""
import os, sys, json, tempfile, subprocess, traceback
HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "src"))
import systeem as S, render as R
from PIL import Image

def post(stijl, formaat, foto=None):
    v = dict(S.HUISSTIJLEN[stijl], huisstijl=stijl, formaat=formaat, achtergrondbron="beeld" if foto else "verloop",
             uitleg_op_beeld=False, hook_op_beeld=False, thema="hoop")
    return {"id": f"zelftest-{stijl}-{formaat}", "ref": "Psalm 23:1", "tekst": "De HEERE is mijn Herder, mij zal niets ontbreken.",
            "handle": "@bibleverse_nl", "variabelen": v, "betekenis": "Een korte uitleg om te testen of alles goed op de slide past.",
            "toepassing": "Een korte toepassing om te testen of ook de derde slide goed wordt gemaakt.", "beeld_pad": foto,
            "reeks_label": "ZELFTEST" if stijl == "mint" else None}

def main():
    fouten, gedaan = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for stijl in S.HUISSTIJLEN:
            try:
                paden = R.maak_carrousel(post(stijl, "carrousel"), os.path.join(tmp, f"{stijl}.jpg"))
                for p in paden:
                    im = Image.open(p)
                    if im.size != (1080, 1350) or os.path.getsize(p) < 15000:
                        fouten.append(f"{stijl}: slide {os.path.basename(p)} klopt niet")
                R.maak_story(paden[0], os.path.join(tmp, f"{stijl}-story.jpg"))
                gedaan += 1
            except Exception as e:
                fouten.append(f"{stijl}: {e}")
        for stijl in ("hemelsblauw", "salie"):
            try:
                pad = os.path.join(tmp, f"{stijl}.mp4")
                R.maak_video(post(stijl, "video"), pad)
                duur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", pad],
                                            capture_output=True, text=True).stdout.strip() or 0)
                if duur < 8 or os.path.getsize(pad) < 100000:
                    fouten.append(f"video {stijl}: te kort of leeg ({duur:.1f} s)")
                gedaan += 1
            except Exception as e:
                fouten.append(f"video {stijl}: {e}")
    ok = not fouten
    S.gezond("zelftest", ok, f"{gedaan} onderdelen gemaakt en gecontroleerd" if ok else "; ".join(fouten)[:160])
    if not ok:
        S.cmd_log("Zelftest vond problemen: " + "; ".join(fouten)[:300], "fout")
    print("Zelftest:", "alles in orde" if ok else fouten)

if __name__ == "__main__":
    main()
