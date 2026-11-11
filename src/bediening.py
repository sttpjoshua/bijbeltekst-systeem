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
        p["variabelen"]["tijdslot_fb"] = p["variabelen"]["tijdslot"]  # handmatig verplaatst: beide platformen tegelijk
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
        p["variabelen"]["tijdslot_fb"] = p["variabelen"]["tijdslot"]
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
        if p["status"] not in ("gerenderd", "wacht_op_tekst", "opnieuw_maken"):
            raise SystemExit("Deze post kan niet meer aangepast worden")
        if p["status"] == "opnieuw_maken":
            p["status"] = "gerenderd"  # wordt hieronder opnieuw gemaakt (of weer in de wachtrij gezet)
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
        import tekstbank
        e = tekstbank.laad().get(p["vers_id"]) if cfg.get("zelfstandig") else None
        if e:  # zelfstandig: teksten uit de bank en meteen opnieuw maken
            tekstbank.vul_post(p, e, cfg)
            p["status"] = "klaar_voor_render" if (p["variabelen"]["formaat"] != "video" and p["variabelen"].get("achtergrondbron") != "beeld") or materiaal_er() else "opnieuw_maken"
            S.bewaar("data/posts.json", posts)
            if p["status"] == "klaar_voor_render":
                try:
                    S.cmd_render(p["datum"])
                except SystemExit:
                    pass
            posts, cfg = S.laad("data/posts.json", []), S.laad("config.json")
            melding = f"Ander vers gekozen: {p['ref']} (teksten uit de tekstbank" + (", meteen opnieuw gemaakt)" if vind(posts, o["post"])["status"] == "gerenderd" else "; het beeld wordt bij de volgende run gemaakt)")
        else:
            melding = f"Ander vers gekozen: {p['ref']}. De teksten en het beeld worden bij de avondcontrole (20:47) gemaakt"
    elif a == "fouten_opgelost":
        S.cmd_opgelost()
        melding = "Openstaande fouten als opgelost gemarkeerd"
    elif a == "reactie_liken":
        reacties = S.laad("data/reacties.json", [])
        r = next((x for x in reacties if x["id"] == o["reactie"]), None)
        if not r:
            raise SystemExit("Reactie niet gevonden")
        import publiceer
        try:
            publiceer.reactie_liken(r)
            r["geliked"] = True
            melding = f"Reactie van {r['naam']} geliked"
        except Exception as e:
            recht = "instagram_manage_engagement" if r["platform"] == "instagram" else "pages_manage_engagement"
            S.cmd_log(f"ACTIE VOOR JOU: liken van reacties op {r['platform']} lukt nog niet. Voeg het recht {recht} toe aan de app en maak het token opnieuw aan "
                      f"(zelfde stappen als bij de reactierechten). Melding van Meta: {str(e)[:150]}", "fout", code="rechten")
            melding = "Liken lukte niet: recht ontbreekt (zie melding)"
        S.bewaar("data/reacties.json", reacties)
    elif a in ("reactie_plaatsen", "reactie_negeren"):
        reacties = S.laad("data/reacties.json", [])
        r = next((x for x in reacties if x["id"] == o["reactie"]), None)
        if not r:
            raise SystemExit("Reactie niet gevonden")
        if a == "reactie_plaatsen":
            tekst = (o.get("tekst") or r.get("voorstel") or "").strip()
            if not tekst or "—" in tekst:
                raise SystemExit("Geen geldige antwoordtekst")
            import publiceer
            publiceer.reactie_plaatsen(r, tekst)
            r.update(status="geplaatst", antwoord=tekst, geplaatst=dt.datetime.now().isoformat(timespec="minutes"))
            melding = f"Antwoord geplaatst bij {r['naam']} ({r['ref']})"
        else:
            r["status"] = "genegeerd"
            melding = f"Reactie van {r['naam']} gemarkeerd als afgehandeld"
        S.bewaar("data/reacties.json", reacties)
    elif a == "fout_opgelost":
        log = S.laad("data/logboek.json", [])
        n = 0
        for l in log:
            if l.get("t") == o["t"] and l.get("soort") == "fout":
                l["opgelost"] = True; n += 1
        S.bewaar("data/logboek.json", log)
        melding = "Fout als opgelost gemarkeerd" if n else None
    elif a == "post_opnieuw":
        import publiceer as PB
        p = vind(posts, o["post"])
        if p["status"] == "gepubliceerd":
            raise SystemExit("Deze post staat al online")
        if not p.get("media"):
            raise SystemExit("Het beeld van deze post is al opgeruimd; kies 'Vervangen door noodpost'")
        p["status"], p["fouten"], p["gemist"] = "gerenderd", 0, []
        p.pop("wacht_media", None)
        nu = dt.datetime.now(PB.TZ)
        if PB.tijdstip(p) <= nu:
            p["datum"] = nu.date().isoformat()
            p["variabelen"]["tijdslot"] = p["variabelen"]["tijdslot_fb"] = (nu - dt.timedelta(minutes=1)).strftime("%H:%M")
            p["handmatig_tijdstip"] = True
            melding = f"{p['ref']} wordt nu opnieuw geprobeerd"
        else:
            melding = f"{p['ref']} staat weer klaar voor {p['variabelen']['tijdslot']}"
    elif a == "post_nood":
        import publiceer as PB
        p = vind(posts, o["post"])
        if p["status"] == "gepubliceerd":
            raise SystemExit("Deze post staat al online")
        voorraad = S.laad("data/noodvoorraad.json", [])
        kl = [n for n in voorraad if n["status"] == "gerenderd"]
        if not kl:
            raise SystemExit("De noodvoorraad is leeg. Gebruik 'Vraag Claude' om hem aan te vullen.")
        n = kl[0]; voorraad.remove(n)
        nu = dt.datetime.now(PB.TZ)
        datum, slot = p["datum"], p["variabelen"]["tijdslot"]
        if PB.tijdstip(p) <= nu:
            datum, slot = nu.date().isoformat(), (nu - dt.timedelta(minutes=1)).strftime("%H:%M")
        p["status"] = "afgekeurd"
        n = dict(n, id=f"{datum}-n{slot.replace(':', '')}", datum=datum, status="gerenderd", nood=True, goedgekeurd=True)
        n["variabelen"] = dict(n["variabelen"], tijdslot=slot, tijdslot_fb=None)
        posts.append(n)
        S.bewaar("data/noodvoorraad.json", voorraad)
        S.herstel(f"{p['ref']} vervangen (door jou)", f"noodpost {n['ref']} om {slot}")
        melding = f"{p['ref']} vervangen door noodpost {n['ref']} om {slot}"
    elif a == "nood_inzetten":
        import publiceer as PB
        S.bewaar("data/posts.json", posts)
        k = S.noodinzet(dt.datetime.now(PB.TZ))
        posts = S.laad("data/posts.json", [])
        melding = f"{k} noodpost(s) ingezet op de lege tijdsloten van vandaag" if k else "Er waren geen lege tijdsloten meer vandaag"
    elif a == "muziek_toevoegen":
        if not materiaal_er():
            raise SystemExit("Muziek is niet bereikbaar: controleer MATERIAAL_PAT")
        S.bewaar("data/posts.json", posts)
        S.cmd_aanvullen()
        posts = S.laad("data/posts.json", [])
        melding = "Video's zonder muziek zijn opnieuw gemaakt met muziek"
    elif a == "statistieken_nu":
        import publiceer as PB
        PB.verse_cijfers(posts)
        try:
            PB.volgers_en_tokens()
        except Exception as e:
            print("Volgers:", e)
        melding = "Cijfers en volgers opgehaald"
    elif a == "reacties_nu":
        import publiceer as PB
        n = PB.reacties_ophalen(posts)
        melding = "Reacties opgehaald" + (f": {n} nieuw" if isinstance(n, int) else "")
    elif a == "zelftest_nu":
        import subprocess
        r = subprocess.run([sys.executable, "tools/zelftest.py"], capture_output=True, text=True)
        melding = "Zelftest: " + ((r.stdout or r.stderr).strip().splitlines() or ["klaar"])[-1][:120]
    elif a in ("nieuws_maken", "nieuws_negeren"):
        import nieuws
        melding = nieuws.maak_voorstel(o["id"]) if a == "nieuws_maken" else nieuws.negeer(o["id"])
        if a == "nieuws_negeren" or melding.startswith("Nieuwspost"):
            log = S.laad("data/logboek.json", [])
            for l in log:
                if l.get("code") == "nieuws_voorstel" and l.get("post") == o["id"]:
                    l["opgelost"] = True
            S.bewaar("data/logboek.json", log)
        posts, cfg = S.laad("data/posts.json", []), S.laad("config.json")
    elif a == "nieuws_instelling":
        n = cfg.setdefault("nieuws", {})
        n[o["sleutel"]] = o["waarde"]
        namen = {"aan": "nieuwsposts", "licht_automatisch": "licht nieuws automatisch", "max_per_dag": "maximaal per dag"}
        melding = f"Nieuws: {namen.get(o['sleutel'], o['sleutel'])} {o['waarde'] if o['sleutel'] == 'max_per_dag' else ('aan' if o['waarde'] else 'uit')}"
    elif a == "nieuwe_reels":
        cfg["nieuwe_reels"] = bool(o.get("aan"))
        melding = "Nieuwe reelstijlen " + ("aan: het systeem test klassiek, kinetisch en bewegend beeld, met en zonder vraag als haak" if cfg["nieuwe_reels"] else "uit: alleen de klassieke reel")
    elif a == "reel_tempo":
        cfg["reel_tempo"] = float(o["waarde"])
        melding = f"Tempo nieuwe reels: {dict([(0.8,'langzaam'),(1.0,'rustig'),(1.25,'vlot'),(1.6,'snel')]).get(cfg['reel_tempo'], cfg['reel_tempo'])} (geldt voor reels die vanaf nu gemaakt worden)"
    elif a == "posts_maken":
        melding = "Posts maken gestart: het systeem maakt de ontbrekende posts voor morgen en overmorgen (duurt 10 tot 20 minuten)"
    elif a == "zelfstandig":
        cfg["zelfstandig"] = bool(o.get("aan"))
        melding = "Zelfstandig maken staat " + ("aan: posts worden gemaakt uit de tekstbank, zonder Claude" if cfg["zelfstandig"] else "uit: Claude maakt de posts")
    elif a == "run":
        melding = "Controle gestart: alles wat klaarstaat gaat nu online"
    elif a == "verzoek":
        tekst = (o.get("tekst") or "").strip()[:1500]
        if not tekst:
            raise SystemExit("Leeg verzoek")
        v = S.laad("data/verzoeken.json", [])
        v.append({"id": dt.datetime.now().strftime("%Y%m%d%H%M%S"), "t": dt.datetime.now().isoformat(timespec="minutes"),
                  "tekst": tekst, "status": "wacht", "antwoord": "", "soort": o.get("soort", "vraag")})
        S.bewaar("data/verzoeken.json", v[-100:])
        melding = "Overleg aangevraagd: Claude maakt een tussentijdse analyse" if o.get("soort") == "overleg" else "Verzoek voor Claude in de wachtrij gezet"
    elif a == "verzoek_weg":
        v = S.laad("data/verzoeken.json", [])
        for x in v:
            if x["id"] == o["id"] and x["status"] == "wacht":
                x["status"] = "geannuleerd"
        S.bewaar("data/verzoeken.json", v)
        melding = "Verzoek ingetrokken"
    elif a == "whatsapp_instelling":
        w = cfg.setdefault("whatsapp", {})
        w[o["soort"]] = bool(o["aan"])
        namen = {"direct": "directe meldingen", "dagelijks": "dagoverzicht", "wekelijks": "weekverslag", "uitschieter": "uitschieters"}
        melding = f"WhatsApp: {namen.get(o['soort'], o['soort'])} {'aan' if o['aan'] else 'uit'}"
    elif a == "whatsapp_test":
        import whatsapp
        whatsapp.zet_in_wachtrij("👋 Testbericht van Bibleverse. De meldingen werken!", "test",
                                 "test:" + dt.datetime.now().isoformat(timespec="seconds"))
        melding = "WhatsApp-testbericht klaargezet"
    elif a == "test_materiaal":
        ok = materiaal_er()
        n = len(S.materiaal(cfg)["muziek"]) if ok else 0
        melding = f"Muziek en foto's in GitHub: {'beschikbaar (' + str(n) + ' nummers)' if ok else 'NIET beschikbaar, controleer MATERIAAL_PAT'}"
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
                 "andere_stijl": "designer", "post_ander_vers": "verskiezer", "fouten_opgelost": "controller", "reactie_plaatsen": "community", "reactie_negeren": "community", "reactie_liken": "community",
                 "fout_opgelost": "controller", "post_opnieuw": "dispatcher", "post_nood": "controller", "nood_inzetten": "controller",
                 "muziek_toevoegen": "video", "statistieken_nu": "analist", "reacties_nu": "community", "zelftest_nu": "controller",
                 "run": "dispatcher", "verzoek": "controller", "posts_maken": "verskiezer", "zelfstandig": "controller", "nieuws_maken": "verskiezer", "nieuws_negeren": "verskiezer", "nieuws_instelling": "verskiezer", "nieuwe_reels": "video", "reel_tempo": "video", "whatsapp_test": "controller", "whatsapp_instelling": "controller"}.get(a)
        if a == "overslaan":
            agent = "video" if (vind(posts, o["post"])["variabelen"].get("formaat") == "video") else "designer"
        if agent:
            S.activiteit(agent, melding[:70])
    S.cmd_plan()
    S.cmd_dashboard()
    print(melding or "ok")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OPDRACHT", "{}"))
