"""WhatsApp-updates voor Joshua via CallMeBot (gratis, alleen tekst).

Alles wat een bericht wil sturen, zet het in data/wa_wachtrij.json (ook Claude-runs en de bediening).
Dit script draait na elke GitHub Actions-run en:
  1. maakt het dagoverzicht (vanaf 21:30), het weekverslag (maandag vanaf 13:00) en uitschieter-meldingen aan;
  2. verstuurt de wachtrij, behalve tussen 22:30 en 07:30 (dan blijft het tot de ochtend staan).
Kanaal: Telegram (geheim TG_TOKEN, de sleutel van je eigen bot via @BotFather) heeft voorrang;
anders WhatsApp via CallMeBot (geheimen WA_PHONE en WA_KEY).
Telegram: na het aanmaken van de bot stuurt Joshua hem één keer /start; het systeem onthoudt dan zelf
het chatnummer (data/telegram.json). Daarna luistert de bot naar niemand anders.
Instellingen in config.json onder "whatsapp": direct, dagelijks, wekelijks, uitschieter (true/false).
"""
import os, sys, json, urllib.request, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S

TZ = ZoneInfo("Europe/Amsterdam")
DASH = "https://sttpjoshua.github.io/bijbeltekst-systeem/"
STANDAARD = {"direct": True, "reacties": True, "dagelijks": True, "wekelijks": True, "uitschieter": True}

def instellingen():
    return {**STANDAARD, **(S.laad("config.json").get("whatsapp") or {})}

def zet_in_wachtrij(tekst, soort="direct", sleutel=None, knoppen=None, fotos=None):
    """Bericht klaarzetten. 'sleutel' voorkomt dat hetzelfde bericht twee keer wordt gestuurd.
    knoppen: rijen van [label, opdracht] (opdracht = zelfde dict als een dashboardknop); alleen in Telegram.
    fotos: paden (vanaf de repo) van afbeeldingen die vooraf als album worden gestuurd."""
    q = S.laad("data/wa_wachtrij.json", [])
    sleutel = sleutel or (soort + ":" + tekst[:80])
    if any(m.get("sleutel") == sleutel for m in q):
        return
    st = S.laad("data/wa_status.json", {})
    if sleutel in st.get("verstuurd", [])[-200:]:
        return
    m = {"t": dt.datetime.now(TZ).isoformat(timespec="minutes"), "soort": soort, "tekst": tekst, "sleutel": sleutel}
    if knoppen:
        m["knoppen"] = knoppen
    if fotos:
        m["fotos"] = fotos
    q.append(m)
    S.bewaar("data/wa_wachtrij.json", q[-50:])

def kanaal():
    if os.environ.get("TG_TOKEN", "").strip():
        return "telegram"
    if os.environ.get("WA_PHONE") and os.environ.get("WA_KEY"):
        return "whatsapp"
    return None

def _tg(methode, **data):
    token = os.environ["TG_TOKEN"].strip()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{methode}",
                                 data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        uit = json.loads(r.read().decode())
    if not uit.get("ok"):
        raise RuntimeError(f"Telegram: {uit.get('description')}")
    return uit["result"]

def tg_chat():
    """Het chatnummer van Joshua: uit het geheim TG_CHAT, uit data/telegram.json, of (eenmalig) uit zijn /start-bericht."""
    if os.environ.get("TG_CHAT", "").strip():
        return os.environ["TG_CHAT"].strip()
    tg = S.laad("data/telegram.json", {})
    if tg.get("chat"):
        return tg["chat"]
    for u in _tg("getUpdates", timeout=0):
        m = u.get("message") or {}
        if m.get("chat", {}).get("type") == "private" and (m.get("text") or "").startswith("/start"):
            S.bewaar("data/telegram.json", {"chat": m["chat"]["id"], "sinds": dt.datetime.now(TZ).isoformat(timespec="minutes")})
            _tg("sendMessage", chat_id=m["chat"]["id"], text="✅ Gekoppeld! Je krijgt hier voortaan de meldingen van Bibleverse.")
            return m["chat"]["id"]
    raise RuntimeError("Telegram-bot gevonden, maar nog geen /start-bericht van jou ontvangen. Stuur je bot /start.")

def _knopregels(knoppen):
    """Zet knoppen om naar Telegram-knoppen; de opdracht zelf blijft bewaard in data/telegram.json."""
    tg = S.laad("data/telegram.json", {})
    kb = tg.setdefault("knoppen", {})
    rijen = []
    for rij in knoppen or []:
        r = []
        for label, opdracht in rij:
            k = f"{len(kb) + 1:x}{dt.datetime.now().strftime('%d%H%M%S')}"[-12:]
            kb[k] = {"o": opdracht, "label": label, "t": dt.datetime.now(TZ).isoformat(timespec="minutes")}
            r.append({"text": label, "callback_data": "k:" + k})
        rijen.append(r)
    tg["knoppen"] = dict(list(kb.items())[-300:])
    S.bewaar("data/telegram.json", tg)
    return rijen + [[{"text": "Dashboard openen", "url": DASH}]]

def _multipart(velden, bestanden):
    import uuid
    grens = uuid.uuid4().hex
    delen = [f'--{grens}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in velden.items()]
    for naam, pad in bestanden:
        delen.append(f'--{grens}\r\nContent-Disposition: form-data; name="{naam}"; filename="{naam}.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
                     + open(pad, "rb").read() + b"\r\n")
    delen.append(f"--{grens}--\r\n".encode())
    return b"".join(delen), f"multipart/form-data; boundary={grens}"

def _tg_fotos(paden):
    """Stuurt tot 10 afbeeldingen als album (uploaden vanaf schijf, want de website is dan nog niet bijgewerkt)."""
    bestanden = [S.P(p) for p in paden if os.path.exists(S.P(p))][:10]
    if not bestanden:
        return
    token = os.environ["TG_TOKEN"].strip()
    if len(bestanden) == 1:
        data, ct = _multipart({"chat_id": tg_chat()}, [("photo", bestanden[0])]); methode = "sendPhoto"
    else:
        media = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(bestanden))]
        data, ct = _multipart({"chat_id": tg_chat(), "media": json.dumps(media)}, [(f"f{i}", p) for i, p in enumerate(bestanden)])
        methode = "sendMediaGroup"
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{methode}", data=data, headers={"Content-Type": ct})
    urllib.request.urlopen(req, timeout=60).read()

def stuur(tekst, knoppen=None, fotos=None):
    if kanaal() == "telegram":
        import html, re
        if fotos:
            try:
                _tg_fotos(fotos)
            except Exception as e:
                print("Foto's sturen mislukt:", e)
        opmaak = re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", html.escape(tekst[:3900], quote=False))  # WhatsApp-*vet* wordt Telegram-vet
        _tg("sendMessage", chat_id=tg_chat(), text=opmaak, parse_mode="HTML", disable_web_page_preview=True,
            reply_markup={"inline_keyboard": _knopregels(knoppen)})
        return
    tel, key = os.environ.get("WA_PHONE", "").strip().lstrip("+"), os.environ.get("WA_KEY", "").strip()
    if not tel or not key:
        raise RuntimeError("geen sleutel: voeg WA_PHONE en WA_KEY toe als geheim in GitHub")
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode({"phone": tel, "text": tekst, "apikey": key})
    with urllib.request.urlopen(url, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    if r.status != 200 or "error" in body.lower()[:300]:
        raise RuntimeError(f"CallMeBot gaf {r.status}: {body[:160]}")

def beste(p):
    m = [S.beste_meting(x) for x in p.get("stats", {}).values()]
    return sum((x.get("reach") or x.get("views") or 0) for x in m if x)

def dagoverzicht(nu):
    posts = S.laad("data/posts.json", [])
    d = nu.date().isoformat()
    online = [p for p in posts if p["datum"] == d and p["status"] == "gepubliceerd"]
    groei = [x for x in S.laad("data/groei.json", []) if x.get("instagram") is not None or x.get("facebook") is not None]
    tot = lambda x: (x.get("instagram") or 0) + (x.get("facebook") or 0)
    vol = f"{tot(groei[-1])}" + (f" ({tot(groei[-1]) - tot(groei[-2]):+d} sinds gisteren)" if len(groei) > 1 else "") if groei else "nog niet geteld"
    reacties = [r for r in S.laad("data/reacties.json", []) if r["status"] in ("nieuw", "voorgesteld")]
    log = S.laad("data/logboek.json", [])
    fouten = [l for l in log if l.get("soort") == "fout" and not l.get("opgelost") and l["t"][:10] == d]
    morgen = sorted((p for p in posts if p["datum"] == (nu.date() + dt.timedelta(days=1)).isoformat() and p["status"] == "gerenderd"),
                    key=lambda p: p["variabelen"]["tijdslot"])
    best = max(online, key=beste, default=None)
    regels = [f"📊 *Bibleverse vandaag* ({nu.strftime('%d-%m')})",
              f"• {len(online)} post{'s' if len(online) != 1 else ''} online" + (f", beste: {best['ref']} ({beste(best)} bereik)" if best and beste(best) else ""),
              f"• Volgers: {vol}"]
    if reacties:
        regels.append(f"• 💬 {len(reacties)} reactie{'s' if len(reacties) != 1 else ''} wacht{'en' if len(reacties) != 1 else ''} op antwoord")
    regels.append(f"• ⚠️ {len(fouten)} probleem{'en' if len(fouten) != 1 else ''} vandaag" if fouten else "• ✅ Geen problemen")
    if morgen:
        regels.append(f"• Morgen: {len(morgen)} posts klaar, de eerste om {morgen[0]['variabelen']['tijdslot']} ({morgen[0]['ref']})")
    else:
        regels.append("• Morgen: nog geen posts klaar")
    regels.append(DASH)
    return "\n".join(regels)

def weekverslag(nu):
    cfg = S.laad("config.json"); posts = S.laad("data/posts.json", [])
    ex = S.dashboard_extra(cfg, posts)
    w = (ex.get("weken") or {}).get("deze") or {}  # de afgelopen 7 dagen
    groei = [x for x in S.laad("data/groei.json", []) if x.get("instagram") is not None or x.get("facebook") is not None]
    tot = lambda x: (x.get("instagram") or 0) + (x.get("facebook") or 0)
    week = next((x for x in groei if x["datum"] >= (nu.date() - dt.timedelta(days=7)).isoformat()), None)
    inz = (S.laad("strategie.json", {}).get("inzichten") or [])[-1:] 
    regels = ["📅 *Bibleverse weekverslag*",
              f"• {w.get('posts', 0)} posts, {w.get('reach') or w.get('views') or 0} bereik",
              f"• {w.get('likes', 0)} likes · {w.get('saves', 0)} keer bewaard · {w.get('shares', 0)} keer gedeeld"]
    if groei:
        regels.append(f"• Volgers: {tot(groei[-1])}" + (f" ({tot(groei[-1]) - tot(week):+d} deze week)" if week else ""))
    if inz:
        regels.append(f"• 💡 {inz[0].get('tekst', '')[:220]}")
    regels.append(DASH)
    return "\n".join(regels)

def uitschieters():
    posts = S.laad("data/posts.json", [])
    gemeten = [beste(p) for p in posts if p["status"] == "gepubliceerd" and beste(p)]
    if len(gemeten) < 5:
        return
    mediaan = sorted(gemeten)[len(gemeten) // 2]
    grens = max(40, mediaan * 3)
    for p in posts:
        b = beste(p)
        if p["status"] == "gepubliceerd" and b >= grens:
            zet_in_wachtrij(f"🚀 *Uitschieter:* {p['ref']} heeft al {b} bereik, ruim {round(b / max(1, mediaan))} keer zoveel als normaal. "
                            f"Misschien een goede kandidaat om te promoten.\n{DASH}", "uitschieter", "uitschieter:" + p["id"])


# ---------- Mijlpalen ----------
VOLGERS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
BEREIK = [100, 500, 1000, 5000, 10000, 50000, 100000]

def mijlpalen(st):
    gehaald = set(st.get("mijlpalen", []))
    groei = S.laad("data/groei.json", [])
    if groei:
        tot = (groei[-1].get("instagram") or 0) + (groei[-1].get("facebook") or 0)
        for m in VOLGERS:
            if tot >= m and f"v{m}" not in gehaald:
                gehaald.add(f"v{m}")
                if m >= 25:  # de eerste kleine stapjes niet melden
                    zet_in_wachtrij(f"🎉 *Mijlpaal:* Bibleverse heeft nu {tot} volgers (Instagram en Facebook samen)!", "uitschieter", f"mijl:v{m}")
    for p in S.laad("data/posts.json", []):
        b = beste(p)
        for m in BEREIK:
            if b >= m and f"b{m}:{p['id']}" not in gehaald and f"b{m}" not in gehaald:
                gehaald |= {f"b{m}", f"b{m}:{p['id']}"}
                zet_in_wachtrij(f"🎉 *Mijlpaal:* voor het eerst een post met meer dan {m} bereik: {p['ref']} ({b}).", "uitschieter", f"mijl:b{m}")
    st["mijlpalen"] = sorted(gehaald)

# ---------- Telegram: knoppen en opdrachten ----------
HULP = ("Ik ben de Bibleverse-bot. Opdrachten:\n/vandaag  wat er vandaag online gaat\n/status  hoe het systeem ervoor staat\n"
        "/pauze  alles stilzetten\n/hervat  weer posten\n\nKnoppen onder mijn berichten werken ook; ik voer ze uit bij de volgende ronde (binnen een kwartier).")

def _antwoord(tekst, knoppen=None):
    import html
    _tg("sendMessage", chat_id=tg_chat(), text=html.escape(tekst, quote=False), parse_mode="HTML", disable_web_page_preview=True,
        reply_markup={"inline_keyboard": _knopregels(knoppen)})

def _vandaag():
    posts = S.laad("data/posts.json", [])
    d = dt.date.today().isoformat()
    rij = sorted((p for p in posts if p["datum"] == d and p["status"] not in ("afgekeurd", "overgeslagen")), key=lambda p: p["variabelen"].get("tijdslot") or "")
    if not rij:
        return "Vandaag staat er niets gepland."
    teken = {"gepubliceerd": "✅", "gerenderd": "⏳", "fout": "⚠️"}
    regels = ["Vandaag:"] + [f"{teken.get(p['status'], '•')} {p['variabelen'].get('tijdslot')}  {p['ref']} ({'reel' if p['variabelen'].get('formaat') == 'video' else 'carrousel'})"
                             + (" 📰" if p.get("nieuws") else "") for p in rij]
    return "\n".join(regels)

def _status():
    cfg = S.laad("config.json")
    log = S.laad("data/logboek.json", [])
    open_ = [l for l in log if l.get("soort") == "fout" and not l.get("opgelost")]
    posts = S.laad("data/posts.json", [])
    klaar = [p for p in posts if p["status"] == "gerenderd"]
    v = S.bank_voorraad(cfg)
    laatst = max((p for p in posts if p["status"] == "gepubliceerd"), key=lambda p: p["datum"] + (p["variabelen"].get("tijdslot") or ""), default=None)
    return "\n".join([
        "⏸ Het systeem staat op PAUZE." if cfg.get("pauze") else "▶ Het systeem draait.",
        f"Laatste post: {laatst['ref']} ({laatst['datum']} {laatst['variabelen'].get('tijdslot')})" if laatst else "Nog niets geplaatst.",
        f"Klaar om te posten: {len(klaar)} posts",
        f"Noodvoorraad: {len(S.nood_klaar())} van {S.NOOD_DOEL}",
        f"Tekstbank: nog ongeveer {v['dagen']} dagen",
        f"⚠️ {len(open_)} open probleem/problemen in het dashboard" if open_ else "✅ Geen open problemen"])

def _voer_uit(o):
    import bediening
    try:
        return "✅ " + (bediening.main(json.dumps(o)) or "Gedaan")
    except SystemExit as e:
        return "❌ " + str(e)
    except Exception as e:
        return "❌ Mislukt: " + str(e)[:200]

def verwerk():
    """Leest nieuwe Telegram-berichten en knopdrukken van Joshua en voert ze uit (alleen in de publiceer-run)."""
    if kanaal() != "telegram":
        return
    try:
        chat = str(tg_chat())
    except Exception as e:
        print("Telegram:", e); return
    updates = _tg("getUpdates", timeout=0)
    if not updates:
        return
    _tg("getUpdates", offset=updates[-1]["update_id"] + 1, timeout=0)  # meteen bevestigen: nooit iets dubbel uitvoeren
    tg = S.laad("data/telegram.json", {})
    for u in updates:
        if "callback_query" in u:
            cq = u["callback_query"]
            if str(cq.get("message", {}).get("chat", {}).get("id")) != chat:
                continue
            k = (cq.get("data") or "")[2:]
            if k == "klaar":
                continue
            knop = tg.get("knoppen", {}).get(k)
            try:
                _tg("answerCallbackQuery", callback_query_id=cq["id"], text="Ontvangen")
            except Exception:
                pass  # te oud: geen probleem
            if not knop:
                _antwoord("Deze knop ken ik niet meer. Kijk even in het dashboard."); continue
            if knop.get("klaar"):
                _antwoord(f"'{knop['label']}' is al gedaan."); continue
            uitkomst = _voer_uit(knop["o"])
            tg = S.laad("data/telegram.json", {}); tg.setdefault("knoppen", {}).setdefault(k, knop)["klaar"] = True
            S.bewaar("data/telegram.json", tg)
            try:
                _tg("editMessageReplyMarkup", chat_id=chat, message_id=cq["message"]["message_id"],
                    reply_markup={"inline_keyboard": [[{"text": "✓ " + knop["label"], "callback_data": "k:klaar"}], [{"text": "Dashboard openen", "url": DASH}]]})
            except Exception:
                pass
            _antwoord(uitkomst)
        elif "message" in u:
            m = u["message"]
            if str(m.get("chat", {}).get("id")) != chat:
                continue
            t = (m.get("text") or "").strip().lower().split("@")[0]
            if t == "/vandaag":
                _antwoord(_vandaag())
            elif t == "/status":
                _antwoord(_status())
            elif t == "/pauze":
                _antwoord("Weet je het zeker? Dan gaat er niets meer online tot je hervat.", [[["⏸ Ja, pauzeren", {"actie": "pauze", "waarde": True}]]])
            elif t == "/hervat":
                _antwoord(_voer_uit({"actie": "pauze", "waarde": False}))
            elif t in ("/start", "/help", "help", "hulp"):
                _antwoord(HULP)
            else:
                _antwoord("Ik begrijp alleen opdrachten en knoppen.\n\n" + HULP)

def main():
    nu = dt.datetime.now(TZ)
    inst = instellingen()
    st = S.laad("data/wa_status.json", {})
    vandaag = nu.date().isoformat()
    if inst["dagelijks"] and nu.strftime("%H:%M") >= "21:30" and st.get("dagelijks") != vandaag:
        zet_in_wachtrij(dagoverzicht(nu), "dagelijks", "dag:" + vandaag); st["dagelijks"] = vandaag
    if inst["wekelijks"] and nu.weekday() == 0 and nu.hour >= 13 and st.get("wekelijks") != vandaag:
        zet_in_wachtrij(weekverslag(nu), "wekelijks", "week:" + vandaag); st["wekelijks"] = vandaag
    if inst["uitschieter"]:
        uitschieters()
        mijlpalen(st)
    if kanaal() == "telegram" and not st.get("menu"):
        try:  # het menu met opdrachten in Telegram (eenmalig)
            _tg("setMyCommands", commands=[{"command": "vandaag", "description": "Wat gaat er vandaag online"},
                                           {"command": "status", "description": "Hoe staat het systeem ervoor"},
                                           {"command": "pauze", "description": "Alles stilzetten"},
                                           {"command": "hervat", "description": "Weer posten"}])
            st["menu"] = True
        except Exception as e:
            print("Menu instellen mislukt:", e)
    q = S.laad("data/wa_wachtrij.json", [])
    stil = nu.strftime("%H:%M") >= "22:30" or nu.strftime("%H:%M") < "07:30"
    te_sturen = [m for m in q if inst.get(m["soort"], True) or m["soort"] == "test"]
    if stil:
        te_sturen = [m for m in te_sturen if m["soort"] == "test"]
    if te_sturen and not kanaal():
        print("Meldingen nog niet gekoppeld (TG_TOKEN of WA_PHONE/WA_KEY ontbreken); berichten blijven 2 dagen in de wachtrij")
        te_sturen = []
    if te_sturen:
        rijk = [m for m in te_sturen if m.get("knoppen") or m.get("fotos")] if kanaal() == "telegram" else []
        gewoon = [m for m in te_sturen if m not in rijk]
        pakketten = ([gewoon] if gewoon else []) + [[m] for m in rijk]
        verstuurd = st.setdefault("verstuurd", [])
        for pak in pakketten:
            try:
                if len(pak) == 1:
                    stuur(pak[0]["tekst"][:3500], pak[0].get("knoppen"), pak[0].get("fotos"))
                else:
                    stuur("\n\n".join(m["tekst"] for m in pak)[:3500])
                verstuurd += [m["sleutel"] for m in pak]
                q = [m for m in q if m not in pak]
                S.gezond("whatsapp", True, f"{len(pak)} bericht(en) verstuurd")
            except Exception as e:
                S.gezond("whatsapp", False, str(e)[:200])
                print("Melding versturen mislukt:", e)
        st["verstuurd"] = verstuurd[-200:]
    # wat uitgezet is of te oud (2 dagen), niet eeuwig bewaren
    grens = (nu - dt.timedelta(days=2)).isoformat(timespec="minutes")
    q = [m for m in q if m["t"] >= grens and (inst.get(m["soort"], True) or m["soort"] == "test")]
    S.bewaar("data/wa_wachtrij.json", q)
    S.bewaar("data/wa_status.json", st)

if __name__ == "__main__":
    if sys.argv[1:] == ["verwerk"]:
        verwerk()
    elif sys.argv[1:] == ["heeft_updates"]:  # exit 0 als er iets te verwerken is
        sys.exit(0 if kanaal() == "telegram" and _tg("getUpdates", timeout=0) else 1)
    else:
        main()
