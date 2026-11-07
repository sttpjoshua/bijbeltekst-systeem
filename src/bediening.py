"""Opdrachten vanuit de Bediening-kaart op het dashboard (via GitHub Actions, taak 'bediening').

Gebruik: python3 src/bediening.py '{"actie": "pauze", "waarde": true}'
"""
import json, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S

PLATFORMEN = ("instagram", "facebook")


def materiaal_er():
    """Zijn muziek en foto's beschikbaar (in GitHub Actions alleen met het geheim MATERIAAL_PAT)?"""
    ok = os.path.isdir(S.materiaal_map())
    S.gezond("materiaal_actions", ok, "muziek en foto's beschikbaar" if ok else "geen MATERIAAL_PAT")
    return ok


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
            if not cfg.get("leermodus"):
                cfg["leermodus_start"] = dt.date.today().isoformat()
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
    elif a == "goedkeuren_instelling":
        g = cfg.setdefault("goedkeuren", {"aan": False, "zonder_reactie": "posten"})
        if "aan" in o:
            g["aan"] = bool(o["aan"])
        if o.get("zonder_reactie") in ("posten", "overslaan"):
            g["zonder_reactie"] = o["zonder_reactie"]
        melding = ("Goedkeuren aangezet" if g["aan"] else "Goedkeuren uitgezet") + (
            f": zonder reactie wordt een post {'gewoon gepost' if g['zonder_reactie'] == 'posten' else 'overgeslagen'}" if g["aan"] else "")
    elif a == "goedkeuren":
        p = vind(posts, o["post"])
        p["goedgekeurd"] = True
        melding = f"{p['ref']} goedgekeurd"
    elif a == "andere_stijl":
        p = vind(posts, o["post"])
        if p["status"] not in ("gerenderd", "wacht_op_tekst"):
            raise SystemExit("Deze post kan niet meer aangepast worden")
        import random
        fris = [k for k in S.HUISSTIJLEN if k != p["variabelen"].get("huisstijl") and k != "avond"]
        nieuw = o.get("huisstijl") if o.get("huisstijl") in S.HUISSTIJLEN else random.choice(fris)
        p["variabelen"].update(S.HUISSTIJLEN[nieuw]); p["variabelen"]["huisstijl"] = nieuw
        p.setdefault("keuzebron", {})["huisstijl"] = "joshua"
        p["goedgekeurd"] = None
        if p["status"] == "gerenderd":
            beeldpost = p["variabelen"]["formaat"] != "video" and p["variabelen"].get("achtergrondbron") != "beeld"
            if beeldpost or materiaal_er():
                p["status"] = "klaar_voor_render"
                S.bewaar("data/posts.json", posts)
                S.cmd_render(p["datum"])
                posts = S.laad("data/posts.json", [])
                melding = f"{p['ref']} opnieuw gemaakt in stijl {nieuw}"
            else:
                # zonder muziek en foto's in GitHub: wachten op een run die ze wel heeft (14:32 of 20:47)
                nu = dt.datetime.now()
                runs = [nu.replace(hour=u, minute=m, second=0, microsecond=0) + dt.timedelta(days=d)
                        for d in (0, 1) for u, m in ((14, 32), (20, 47))]
                volgende = min(r for r in runs if r > nu)
                tijd = dt.datetime.fromisoformat(p["datum"] + "T" + p["variabelen"]["tijdslot"])
                if tijd <= volgende + dt.timedelta(minutes=20):
                    raise SystemExit(f"{p['ref']} gaat online voordat hij opnieuw gemaakt kan worden (volgende run {volgende:%d-%m %H:%M}). Laat hem zo of sla hem over.")
                p["status"] = "opnieuw_maken"
                melding = f"{p['ref']} krijgt stijl {nieuw}; wordt om {volgende:%H:%M} opnieuw gemaakt"
        else:
            melding = f"{p['ref']} krijgt stijl {nieuw}"
    elif a == "post_ander_vers" and vind(posts, o["post"]).get("reserve", {}).get("caption"):
        p = vind(posts, o["post"])
        r = p.pop("reserve")
        later = cfg.setdefault("verzen_later", {})
        later[p["vers_id"]] = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        oud = p["ref"]
        for k in ("vers_id", "ref", "tekst", "vertaling", "hook", "caption", "hashtags", "uitleg", "betekenis", "toepassing"):
            if k in r:
                p[k] = r[k]
        for f in ("thema", "boekgroep", "lengte", "bron"):
            if f in r:
                p["variabelen"][f] = r[f]
        p["goedgekeurd"] = None
        if p["variabelen"]["formaat"] != "video" and p["variabelen"].get("achtergrondbron") != "beeld" or materiaal_er():
            p["status"] = "klaar_voor_render"
            S.bewaar("data/posts.json", posts); S.bewaar("config.json", cfg)
            S.cmd_render(p["datum"])
            posts, cfg = S.laad("data/posts.json", []), S.laad("config.json")
            melding = f"Ander vers: {oud} vervangen door {p['ref']} (meteen opnieuw gemaakt)"
        else:
            p["status"] = "opnieuw_maken"
            melding = f"Ander vers: {oud} vervangen door {p['ref']}; het beeld wordt bij de volgende run gemaakt"
    elif a == "post_ander_vers":
        p = vind(posts, o["post"])
        S.bewaar("data/posts.json", posts)
        S.cmd_vervang(p["id"], "gekozen door Joshua")
        posts, cfg = S.laad("data/posts.json", []), S.laad("config.json")
        p = vind(posts, o["post"])
        melding = f"Ander vers gekozen: {p['ref']}. De teksten en het beeld worden bij de avondcontrole (20:47) gemaakt"
    elif a == "fouten_opgelost":
        S.cmd_opgelost()
        melding = "Openstaande fouten als opgelost gemarkeerd"
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
                 "leermodus": "analist", "ander_vers": "verskiezer", "goedkeuren": "designer", "goedkeuren_instelling": "designer",
                 "andere_stijl": "designer", "post_ander_vers": "verskiezer", "fouten_opgelost": "controller"}.get(a)
        if a == "overslaan":
            agent = "video" if (vind(posts, o["post"])["variabelen"].get("formaat") == "video") else "designer"
        if agent:
            S.activiteit(agent, melding[:70])
    S.cmd_plan()
    S.cmd_dashboard()
    print(melding or "ok")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OPDRACHT", "{}"))
