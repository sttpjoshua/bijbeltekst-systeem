"""Opdrachten vanuit de Bediening-kaart op het dashboard (via GitHub Actions, taak 'bediening').

Gebruik: python3 src/bediening.py '{"actie": "pauze", "waarde": true}'
"""
import json, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S

PLATFORMEN = ("instagram", "facebook")


def wanneer():
    """Na een wijziging in het aantal: vanaf wanneer geldt het?"""
    if dt.datetime.now().hour < 21:
        return ". Ontbrekende posts voor morgen worden vanavond rond 21:00 gemaakt"
    return ". Dit geldt vanaf overmorgen (de avondcontrole voor morgen is al geweest)"


def vind(posts, pid):
    for p in posts:
        if p["id"] == pid:
            return p
    raise SystemExit(f"Post {pid} niet gevonden")


def main(raw):
    o = json.loads(raw or "{}")
    a = o.get("actie")
    cfg = S.laad("config.json")
    posts = S.laad("data/posts.json", [])
    melding = None

    if a == "pauze":
        cfg["pauze"] = bool(o["waarde"])
        melding = "Pauze aangezet: er gaat niets meer online" if cfg["pauze"] else "Pauze uitgezet: het systeem post weer"
    elif a == "posts_per_dag":
        n = max(1, min(int(o["waarde"]), cfg.get("max_posts_per_dag", 3)))
        cfg["posts_per_dag"] = n
        melding = f"Posts per dag ingesteld op {n}" + wanneer()
    elif a == "platform":
        plat, aan = o["platform"], bool(o["aan"])
        if plat not in PLATFORMEN:
            raise SystemExit("Onbekend platform")
        act = [x for x in cfg["platformen_actief"] if x != plat] + ([plat] if aan else [])
        if not act:
            raise SystemExit("Minstens één platform moet aan blijven; gebruik anders de pauzeknop")
        cfg["platformen_actief"] = [x for x in PLATFORMEN if x in act] + [x for x in act if x not in PLATFORMEN]
        melding = f"{plat.capitalize()} {'aangezet' if aan else 'uitgezet'}"
    elif a == "max_aandeel_beeld":
        v = max(0.0, min(float(o["waarde"]), 0.5))
        cfg["max_aandeel_beeld"] = round(v, 2)
        melding = f"Maximaal aandeel foto's: {round(v * 100)}%"
    elif a == "verkenning":
        v = max(0.1, min(float(o["waarde"]), 0.4))
        cfg["verkenning"] = round(v, 2)
        melding = f"Experimenteren ingesteld op {round(v * 100)}%"
    elif a == "overslaan":
        p = vind(posts, o["post"])
        if p["status"] not in ("gerenderd", "wacht_op_tekst"):
            raise SystemExit("Deze post kan niet meer overgeslagen worden")
        p["status"] = "afgekeurd"
        melding = f"Post {p['id']} ({p['ref']}) overgeslagen"
    elif a == "tijd":
        p = vind(posts, o["post"])
        u, m = map(int, o["tijd"].split(":"))
        p["variabelen"]["tijdslot"] = f"{u:02d}:{m:02d}"
        if o.get("datum"):
            p["datum"] = dt.date.fromisoformat(o["datum"]).isoformat()
        melding = f"Post {p['id']} verplaatst naar {p['datum']} {p['variabelen']['tijdslot']}"
    elif a == "nu_posten":
        p = vind(posts, o["post"])
        if p["status"] != "gerenderd":
            raise SystemExit("Alleen posts die klaarstaan kunnen nu gepost worden")
        nu = dt.datetime.now()
        p["datum"] = nu.date().isoformat()
        p["variabelen"]["tijdslot"] = (nu - dt.timedelta(minutes=1)).strftime("%H:%M")
        p["handmatig_tijdstip"] = True
        melding = f"Post {p['id']} ({p['ref']}) wordt nu gepost"
    elif a == "vers_uitsluiten":
        vid = o["vers_id"]
        lijst = cfg.setdefault("verzen_uitsluiten", [])
        if vid not in lijst:
            lijst.append(vid)
        melding = f"Vers {o.get('ref', vid)} wordt niet meer gebruikt"
    elif a == "leermodus":
        if o["aan"]:
            dagen = int(o.get("dagen", 14))
            if not cfg.get("leermodus"):
                cfg["leermodus_vorige"] = {k: cfg.get(k) for k in ("posts_per_dag", "max_posts_per_dag", "verkenning")}
            cfg["leermodus"] = True
            cfg["leermodus_tot"] = (dt.date.today() + dt.timedelta(days=dagen)).isoformat()
            cfg["max_posts_per_dag"] = 5
            cfg["posts_per_dag"] = 5
            cfg["verkenning"] = 0.4
            melding = f"Snel leren aangezet tot {cfg['leermodus_tot']}: 5 posts per dag, elke dag leren" + wanneer()
        else:
            S.leermodus_uit(cfg)
            melding = "Snel leren uitgezet, oude instellingen terug"
    elif a == "ander_vers":
        later = cfg.setdefault("verzen_later", {})
        vandaag = dt.date.today().isoformat()
        for k in [k for k, v in later.items() if v < vandaag]:
            del later[k]
        later[o["vers_id"]] = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        melding = f"{o.get('ref', o['vers_id'])} uit de planning gehaald; er komt een ander vers voor in de plaats"
    elif a == "test":
        melding = None  # de workflow draait daarna de verbindingstest
    else:
        raise SystemExit(f"Onbekende opdracht: {a}")

    S.bewaar("config.json", cfg)
    S.bewaar("data/posts.json", posts)
    if melding:
        S.cmd_log("Bediening: " + melding)
        # laat de juiste medewerker in het pixel-kantoor zien dat hij de opdracht heeft uitgevoerd
        agent = {"pauze": "controller", "posts_per_dag": "verskiezer", "verkenning": "verskiezer", "vers_uitsluiten": "verskiezer",
                 "max_aandeel_beeld": "designer", "platform": "dispatcher", "tijd": "dispatcher", "nu_posten": "dispatcher",
                 "leermodus": "analist", "ander_vers": "verskiezer"}.get(a)
        if a == "overslaan":
            agent = "video" if (vind(posts, o["post"])["variabelen"].get("formaat") == "video") else "designer"
        if agent:
            S.activiteit(agent, melding[:70])
    S.cmd_plan()
    S.cmd_dashboard()
    print(melding or "ok")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OPDRACHT", "{}"))
