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
STANDAARD = {"direct": True, "dagelijks": True, "wekelijks": True, "uitschieter": True}

def instellingen():
    return {**STANDAARD, **(S.laad("config.json").get("whatsapp") or {})}

def zet_in_wachtrij(tekst, soort="direct", sleutel=None):
    """Bericht klaarzetten. 'sleutel' voorkomt dat hetzelfde bericht twee keer wordt gestuurd."""
    q = S.laad("data/wa_wachtrij.json", [])
    sleutel = sleutel or (soort + ":" + tekst[:80])
    if any(m.get("sleutel") == sleutel for m in q):
        return
    st = S.laad("data/wa_status.json", {})
    if sleutel in st.get("verstuurd", [])[-200:]:
        return
    q.append({"t": dt.datetime.now(TZ).isoformat(timespec="minutes"), "soort": soort, "tekst": tekst, "sleutel": sleutel})
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

def stuur(tekst):
    if kanaal() == "telegram":
        import html, re
        opmaak = re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", html.escape(tekst[:3900], quote=False))  # WhatsApp-*vet* wordt Telegram-vet
        _tg("sendMessage", chat_id=tg_chat(), text=opmaak, parse_mode="HTML", disable_web_page_preview=True,
            reply_markup={"inline_keyboard": [[{"text": "Dashboard openen", "url": DASH}]]})
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
    q = S.laad("data/wa_wachtrij.json", [])
    stil = nu.strftime("%H:%M") >= "22:30" or nu.strftime("%H:%M") < "07:30"
    te_sturen = [m for m in q if inst.get(m["soort"], True) or m["soort"] == "test"]
    if stil:
        te_sturen = [m for m in te_sturen if m["soort"] == "test"]
    if te_sturen and not kanaal():
        print("Meldingen nog niet gekoppeld (TG_TOKEN of WA_PHONE/WA_KEY ontbreken); berichten blijven 2 dagen in de wachtrij")
        te_sturen = []
    if te_sturen:
        try:
            stuur("\n\n".join(m["tekst"] for m in te_sturen)[:3500])
            S.gezond("whatsapp", True, f"{len(te_sturen)} bericht(en) verstuurd")
            verstuurd = st.setdefault("verstuurd", [])
            verstuurd += [m["sleutel"] for m in te_sturen]
            st["verstuurd"] = verstuurd[-200:]
            q = [m for m in q if m not in te_sturen]
        except Exception as e:
            S.gezond("whatsapp", False, str(e)[:200])
            print("Melding versturen mislukt:", e)
    # wat uitgezet is of te oud (2 dagen), niet eeuwig bewaren
    grens = (nu - dt.timedelta(days=2)).isoformat(timespec="minutes")
    q = [m for m in q if m["t"] >= grens and (inst.get(m["soort"], True) or m["soort"] == "test")]
    S.bewaar("data/wa_wachtrij.json", q)
    S.bewaar("data/wa_status.json", st)

if __name__ == "__main__":
    main()
