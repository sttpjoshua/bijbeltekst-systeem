"""Draait in GitHub Actions. Zet posts online als hun tijd gekomen is en haalt statistieken op.

  python3 src/publiceer.py posten       elk kwartier: publiceer wat klaarstaat
  python3 src/publiceer.py statistieken  dagelijks: 24u- en 7d-cijfers ophalen
  python3 src/publiceer.py token         controleert en ververst het Instagram-token

Geheimen (GitHub > Settings > Secrets and variables > Actions):
  IG_USER_ID   het Instagram-account-ID
  IG_TOKEN     long-lived Instagram User access token (Instagram Login)
  GH_PAT       optioneel: fine-grained token met 'Secrets: write' op deze repo, om IG_TOKEN automatisch te verversen
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import systeem as S

API_IG = "https://graph.instagram.com/v23.0"   # tokens van "Instagram login" (beginnen met IG)
API_FB = "https://graph.facebook.com/v23.0"    # tokens van "Unified/Facebook login" en system users (beginnen met EAA)
API = API_IG
TZ = ZoneInfo("Europe/Amsterdam")
TE_LAAT = dt.timedelta(hours=8)  # GitHub-cron loopt soms uren achter; pas daarna overslaan

def http(method, url, params=None):
    data = None
    if params and method == "GET":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{e.code}: {body[:400]}")

def env():
    global API
    uid, tok = os.environ.get("IG_USER_ID", "").strip(), os.environ.get("IG_TOKEN", "").strip()
    if not uid or not tok:
        raise SystemExit("IG_USER_ID of IG_TOKEN ontbreekt in de GitHub-secrets")
    API = API_IG if tok.startswith("IG") else API_FB
    return uid, tok

def caption(p):
    tekst = p["caption"].strip()
    if p.get("hashtags"):
        tekst += "\n\n" + " ".join(p["hashtags"])
    return tekst[:2200]

def wacht_klaar(cid, tok):
    for _ in range(40):
        st = http("GET", f"{API}/{cid}", {"fields": "status_code,status", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram verwerking mislukt: {st}")
        time.sleep(6)
    raise RuntimeError("Instagram verwerking duurde te lang")

def alt_teksten(p):
    """Alt-tekst per slide: helpt mensen met een schermlezer en laat Instagram/Facebook begrijpen waar de post over gaat."""
    eerste = f"Tekstbeeld van Bibleverse met het Bijbelvers {p['ref']}: {p['tekst']}"
    if p.get("reeks_label"):
        eerste = f"{p['reeks_label'].title()}. " + eerste
    uit = [eerste]
    if p.get("betekenis"):
        uit.append(f"Uitleg bij {p['ref']}, Wat betekent dit: {p['betekenis']}")
    if p.get("toepassing"):
        uit.append(f"Toepassing bij {p['ref']}, Vandaag: {p['toepassing']}")
    return [a[:1000] for a in uit]

def met_alt(methode, url, params, veld, alt):
    """Probeert met alt-tekst; geeft Meta een fout op dat veld, dan nog een keer zonder (de post gaat altijd voor)."""
    if alt:
        try:
            return http(methode, url, dict(params, **{veld: alt}))
        except Exception as e:
            if "alt" not in str(e).lower() and "param" not in str(e).lower():
                raise
    return http(methode, url, params)

def publiceer_instagram(p, uid, tok):
    if p["variabelen"]["formaat"] == "carrousel":
        kinderen = []
        alts = alt_teksten(p)
        for i, url in enumerate(p["media_urls"]):
            kid = met_alt("POST", f"{API}/{uid}/media", {"image_url": url, "is_carousel_item": "true", "access_token": tok},
                          "alt_text", alts[i] if i < len(alts) else alts[0])["id"]
            wacht_klaar(kid, tok); kinderen.append(kid)
        cid = http("POST", f"{API}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kinderen),
                                                  "caption": caption(p), "access_token": tok})["id"]
        wacht_klaar(cid, tok)
        mid = http("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})["id"]
        info = http("GET", f"{API}/{mid}", {"fields": "permalink", "access_token": tok})
        return mid, info.get("permalink")
    video = p["variabelen"]["formaat"] == "video"
    params = {"caption": caption(p), "access_token": tok}
    if video:
        params.update({"media_type": "REELS", "video_url": p["media_url"], "share_to_feed": "true"})
        if p.get("cover_ms"):
            params["thumb_offset"] = str(p["cover_ms"])  # omslag in het raster: het moment dat het hele vers in beeld staat
    else:
        params["image_url"] = p["media_url"]
    cid = (http("POST", f"{API}/{uid}/media", params) if video
           else met_alt("POST", f"{API}/{uid}/media", params, "alt_text", alt_teksten(p)[0]))["id"]
    # wachten tot Instagram het bestand verwerkt heeft
    for _ in range(40):
        st = http("GET", f"{API}/{cid}", {"fields": "status_code,status", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram verwerking mislukt: {st}")
        time.sleep(6)
    else:
        raise RuntimeError("Instagram verwerking duurde te lang")
    mid = http("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})["id"]
    info = http("GET", f"{API}/{mid}", {"fields": "permalink,timestamp", "access_token": tok})
    return mid, info.get("permalink")

def publiceer_story(p, uid, tok):
    """Zet de post ook als story op Instagram (meer bereik bij bestaande volgers). Fouten zijn niet erg."""
    if p["variabelen"]["formaat"] == "video":
        params = {"media_type": "STORIES", "video_url": p["media_url"]}
    elif p.get("story_url"):
        params = {"media_type": "STORIES", "image_url": p["story_url"]}
    else:
        return None
    cid = http("POST", f"{API}/{uid}/media", dict(params, access_token=tok))["id"]
    wacht_klaar(cid, tok)
    return http("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})["id"]

# ---------- Facebook-pagina ----------
_PAGE_TOKEN = {}

def page_token(tok):
    """Paginatoken afleiden van het systeemgebruiker-token (zelfde geheim als Instagram)."""
    pid = os.environ.get("FB_PAGE_ID", "").strip()
    if not pid:
        raise RuntimeError("FB_PAGE_ID ontbreekt in de GitHub-secrets")
    tok = os.environ.get("FB_TOKEN", "").strip() or tok  # aparte Facebook-app/token als die er is
    if pid not in _PAGE_TOKEN:
        r = http("GET", f"{API_FB}/{pid}", {"fields": "access_token,name", "access_token": tok})
        if not r.get("access_token"):
            raise RuntimeError("Geen paginatoken: heeft bibleverse-bot volledige controle over de pagina?")
        _PAGE_TOKEN[pid] = r["access_token"]
    return pid, _PAGE_TOKEN[pid]

def http_headers(url, headers, data=b""):
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode(errors='replace')[:400]}")

def publiceer_facebook(p, tok):
    pid, ptok = page_token(tok)
    fmt = p["variabelen"]["formaat"]
    tekst = caption(p)
    if fmt == "afbeelding":
        r = met_alt("POST", f"{API_FB}/{pid}/photos", {"url": p["media_url"], "message": tekst, "access_token": ptok},
                    "alt_text_custom", alt_teksten(p)[0])
        pk = r.get("post_id") or r["id"]
    elif fmt == "carrousel":
        alts = alt_teksten(p)
        ids = [met_alt("POST", f"{API_FB}/{pid}/photos", {"url": u, "published": "false", "access_token": ptok},
                       "alt_text_custom", alts[i] if i < len(alts) else alts[0])["id"]
               for i, u in enumerate(p["media_urls"])]
        params = {"message": tekst, "access_token": ptok}
        for i, fid in enumerate(ids):
            params[f"attached_media[{i}]"] = json.dumps({"media_fbid": fid})
        pk = http("POST", f"{API_FB}/{pid}/feed", params)["id"]
    else:  # video als Reel
        start = http("POST", f"{API_FB}/{pid}/video_reels", {"upload_phase": "start", "access_token": ptok})
        vid = start["video_id"]
        http_headers(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/v23.0/{vid}",
                     {"Authorization": f"OAuth {ptok}", "file_url": p["media_url"]})
        http("POST", f"{API_FB}/{pid}/video_reels", {"upload_phase": "finish", "video_id": vid,
                                                     "video_state": "PUBLISHED", "description": tekst, "access_token": ptok})
        pk = vid
    return pk, f"https://www.facebook.com/{pk}"

def stats_facebook(p, fb, tok):
    _, ptok = page_token(tok)
    if p["variabelen"]["formaat"] == "video":
        uit = {}
        try:
            r = http("GET", f"{API_FB}/{fb['id']}/video_insights", {"access_token": ptok})
            for x in r.get("data", []):
                waarde = (x.get("values") or [{}])[0].get("value")
                if x["name"] in ("blue_reels_play_count", "fb_reels_total_plays"):
                    uit["views"] = waarde
                elif x["name"] == "post_impressions_unique":
                    uit["reach"] = waarde
                elif x["name"] == "post_video_social_actions":
                    if isinstance(waarde, dict):
                        uit.update({"likes": waarde.get("REACTION"), "comments": waarde.get("COMMENT"), "shares": waarde.get("SHARE")})
        except RuntimeError:
            pass
        return uit
    r = http("GET", f"{API_FB}/{fb['id']}", {"fields": "reactions.summary(true).limit(0),comments.summary(true).limit(0),shares",
                                             "access_token": ptok})
    uit = {"likes": r.get("reactions", {}).get("summary", {}).get("total_count"),
           "comments": r.get("comments", {}).get("summary", {}).get("total_count"),
           "shares": (r.get("shares") or {}).get("count", 0)}
    try:
        i = http("GET", f"{API_FB}/{fb['id']}/insights", {"metric": "post_impressions_unique", "access_token": ptok})
        uit["reach"] = (i["data"][0]["values"] or [{}])[0].get("value")
    except Exception:
        pass
    return uit

def tijdstip(p, plat="instagram"):
    """Tijdstip per platform: Facebook heeft een eigen, apart geleerd tijdstip (tijdslot_fb)."""
    d = dt.date.fromisoformat(p["datum"])
    slot = p["variabelen"].get("tijdslot_fb") if plat == "facebook" and p["variabelen"].get("tijdslot_fb") else p["variabelen"]["tijdslot"]
    u, m = map(int, slot.split(":"))
    return dt.datetime(d.year, d.month, d.day, u, m, tzinfo=TZ)

def controleer_aantal(cfg, posts, nu):
    """Vanaf 06:00: staan er voor vandaag genoeg posts? Vanaf 21:30: staan er voor morgen genoeg? Anders een fout op het dashboard."""
    nodig = min(cfg["posts_per_dag"], cfg["max_posts_per_dag"])
    controles = []
    if nu.hour >= 6:
        controles.append(nu.date())
    if nu.hour > 21 or (nu.hour == 21 and nu.minute >= 30):
        controles.append(nu.date() + dt.timedelta(days=1))
    log = S.laad("data/logboek.json", [])[-300:]
    for dag in controles:
        d = dag.isoformat()
        teken = f"Te weinig posts voor {d}"
        if any(x["tekst"].startswith(teken) for x in log):
            continue
        n = sum(1 for p in posts if p["datum"] == d and p["status"] in ("gerenderd", "gepubliceerd", "fout"))
        if n < nodig:
            if len(S.nood_klaar()) >= nodig - n:
                S.cmd_log(f"{teken}: {n} klaar, {nodig} ingesteld. De noodvoorraad vult de lege tijdsloten automatisch op.", "info")
            else:
                S.cmd_log(f"{teken}: {n} klaar, {nodig} ingesteld, en de noodvoorraad is te klein.", "fout", code="te_weinig")
            S.cmd_dashboard()

def media_online(p):
    """Staan alle beelden van deze post al op GitHub Pages? (Na een nieuwe commit duurt dat soms een paar minuten.)"""
    for u in p.get("media_urls") or ([p["media_url"]] if p.get("media_url") else []):
        try:
            req = urllib.request.Request(u, method="HEAD")
            if urllib.request.urlopen(req, timeout=15).status != 200:
                return False
        except Exception:
            return False
    return True

def cmd_posten():
    cfg = S.laad("config.json")
    if cfg["pauze"]:
        print("Pauze staat aan"); return
    nu = dt.datetime.now(TZ)
    try:
        if S.noodinzet(nu):
            S.cmd_dashboard()
    except Exception as e:
        print("Noodinzet mislukt:", e)
    posts = S.laad("data/posts.json", [])
    vandaag_online = sum(1 for p in posts if p["datum"] == nu.date().isoformat() and p["status"] == "gepubliceerd")
    controleer_aantal(cfg, posts, nu)
    if nu.minute < 15 and 7 <= nu.hour <= 23:
        try:
            if reacties_ophalen(posts):
                S.cmd_dashboard()
        except Exception as e:
            print("Reacties ophalen mislukt:", e)
    if nu.hour in (10, 13, 16, 19, 22) and nu.minute < 15:
        try:
            verse_cijfers(posts)
            S.bewaar("data/posts.json", posts)
            S.cmd_dashboard()
        except Exception as e:
            print("Tussentijdse cijfers mislukt:", e)
    try:
        S.bewaar("data/posts.json", posts)  # eerst opslaan: vroege_cijfers leest en schrijft het bestand zelf
        vroege_cijfers(nu)
        posts[:] = S.laad("data/posts.json", [])  # anders overschrijft deze oude lijst de nieuwe metingen weer
    except Exception as e:
        print("Eerste-uurcijfers mislukt:", str(e)[:160])
    klaar = [p for p in posts if p["status"] == "gerenderd"
             and any(tijdstip(p, pl) <= nu for pl in cfg["platformen_actief"])]
    if not klaar:
        print("Niets te doen"); return
    uid, tok = env()
    fouten = 0
    for p in sorted(klaar, key=tijdstip):
        if all(nu - tijdstip(p, pl) > TE_LAAT for pl in cfg["platformen_actief"]):
            p["status"] = "overgeslagen"
            S.cmd_log(f"{p['id']} ({p['ref']}) niet geplaatst: het tijdstip is meer dan 8 uur gemist", "fout", code="post_gemist", post=p["id"]); continue
        g = cfg.get("goedkeuren") or {}
        if g.get("aan") and g.get("zonder_reactie") == "overslaan" and p.get("goedgekeurd") is not True:
            print(p["id"], "wacht op goedkeuring"); continue  # na 8 uur zonder goedkeuring vervalt hij hierboven vanzelf
        if vandaag_online >= cfg["max_posts_per_dag"]:
            p["status"] = "overgeslagen"
            S.cmd_log(f"{p['id']} overgeslagen: daglimiet bereikt", "info"); continue
        if not media_online(p):
            if nu - tijdstip(p) < dt.timedelta(minutes=45):
                if not p.get("wacht_media"):
                    p["wacht_media"] = True
                    S.herstel(f"{p['id']}: beeld staat nog niet online", "wacht een kwartier en probeert het dan opnieuw")
                S.bewaar("data/posts.json", posts); continue
        for plat in cfg["platformen_actief"]:
            if plat in p.get("gepubliceerd", {}) or plat in p.get("gemist", []) or tijdstip(p, plat) > nu:
                continue
            if nu - tijdstip(p, plat) > TE_LAAT:
                p.setdefault("gemist", []).append(plat)  # dit platform is gemist; de andere gaan door
                S.cmd_log(f"{p['id']} ({p['ref']}) niet geplaatst op {plat}: tijdstip gemist", "fout", code="post_gemist", post=p["id"]); continue
            try:
                if plat == "instagram":
                    mid, link = publiceer_instagram(p, uid, tok)
                    if cfg.get("stories", True):
                        try:
                            if publiceer_story(p, uid, tok):
                                S.cmd_log(f"{p['id']} ook als story geplaatst")
                        except Exception as e:
                            S.cmd_log(f"{p['id']} story mislukt (post zelf staat wel online): {str(e)[:120]}")
                elif plat == "facebook":
                    mid, link = publiceer_facebook(p, tok)
                else:
                    continue  # YouTube en TikTok volgen na hun keuring
                p.setdefault("gepubliceerd", {})[plat] = {"id": mid, "url": link, "t": dt.datetime.now(TZ).isoformat(timespec="minutes")}
                S.cmd_log(f"{p['id']} online op {plat}: {p['ref']}")
                S.activiteit("dispatcher", f"Postte {p['ref']} op {plat}")
                S.gezond(plat, True, f"{p['ref']} geplaatst")
            except Exception as e:
                p["fouten"] = p.get("fouten", 0) + 1
                if p["fouten"] < 3:  # meestal een tijdelijke storing bij Meta: volgende kwartier opnieuw
                    S.herstel(f"{p['id']} op {plat} mislukt ({str(e)[:100]})",
                              f"poging {p['fouten']} van 3; probeert het over een kwartier opnieuw")
                    continue
                S.cmd_log(f"{p['id']} ({p['ref']}) op {plat} mislukt na 3 pogingen: {str(e)[:200]}", "fout", code="post_mislukt", post=p["id"]); fouten += 1
                S.activiteit("dispatcher", f"Post op {plat} mislukt", "error")
                S.gezond(plat, False, str(e))
                p["status"] = "fout"
        ondersteund = [x for x in cfg["platformen_actief"] if x in ("instagram", "facebook")]
        klaar_overal = all(x in p.get("gepubliceerd", {}) or x in p.get("gemist", []) for x in ondersteund)
        if p["status"] != "fout" and (klaar_overal or (p.get("gepubliceerd") and p.get("fouten", 0) >= 3)):
            p["status"] = "gepubliceerd"; vandaag_online += 1
        # anders blijft de status 'gerenderd' en probeert de volgende run het ontbrekende platform opnieuw
        S.bewaar("data/posts.json", posts)  # na elke post opslaan
    S.cmd_dashboard()
    if fouten:
        sys.exit(f"{fouten} fout(en) bij publiceren, zie logboek")

METRICS = ["reach", "likes", "comments", "shares", "saved", "views", "follows", "ig_reels_avg_watch_time"]

def insights(mid, tok):
    """Vraagt de metrics op; sommige zijn niet voor elk mediatype beschikbaar, dan één voor één."""
    def vraag(ms):
        r = http("GET", f"{API}/{mid}/insights", {"metric": ",".join(ms), "access_token": tok})
        return {x["name"]: (x.get("values") or [{}])[0].get("value", x.get("total_value", {}).get("value")) for x in r.get("data", [])}
    try:
        return vraag(METRICS)
    except RuntimeError:
        uit = {}
        for m in METRICS:
            try:
                uit.update(vraag([m]))
            except RuntimeError:
                pass
        return uit

def verse_cijfers(posts):
    """Actuele cijfers van posts jonger dan 7 dagen (alleen voor het dashboard; het leren gebruikt 24u en 7d)."""
    uid, tok = env()
    nu = dt.datetime.now(TZ)
    n = 0
    for p in posts:
        for plat, g in p.get("gepubliceerd", {}).items():
            if nu - dt.datetime.fromisoformat(g["t"]) > dt.timedelta(days=7):
                continue
            try:
                m = insights(g["id"], tok) if plat == "instagram" else stats_facebook(p, g, tok) if plat == "facebook" else None
            except Exception:
                continue
            if m:
                p.setdefault("stats", {}).setdefault(plat, {})["laatst"] = {
                    "t": nu.isoformat(timespec="minutes"), "views": m.get("views"), "reach": m.get("reach"),
                    "likes": m.get("likes"), "comments": m.get("comments"), "shares": m.get("shares"),
                    "saves": m.get("saved"), "follows": m.get("follows"), "avg_watch_ms": m.get("ig_reels_avg_watch_time")}
                n += 1
    return n

def volgers_en_tokens():
    """Dagelijks: aantal volgers (voor de groeilijn) en hoe lang de sleutels nog geldig zijn."""
    uid, tok = env()
    vandaag = dt.datetime.now(TZ).date().isoformat()
    rij = {"datum": vandaag}
    try:
        r = http("GET", f"{API}/{uid}", {"fields": "followers_count,media_count", "access_token": tok})
        rij["instagram"] = r.get("followers_count"); rij["ig_posts"] = r.get("media_count")
        S.gezond("instagram_lezen", True, f"{r.get('followers_count')} volgers")
    except Exception as e:
        S.gezond("instagram_lezen", False, str(e))
    if os.environ.get("FB_PAGE_ID", "").strip():
        try:
            pid, ptok = page_token(tok)
            r = http("GET", f"{API_FB}/{pid}", {"fields": "followers_count,fan_count", "access_token": ptok})
            rij["facebook"] = r.get("followers_count") or r.get("fan_count")
        except Exception as e:
            S.gezond("facebook_lezen", False, str(e))
    groei = [x for x in S.laad("data/groei.json", []) if x["datum"] != vandaag] + [rij]
    S.bewaar("data/groei.json", groei[-400:])
    # Hoe lang zijn de sleutels nog geldig? (0 = verloopt nooit)
    g = S.laad("data/gezondheid.json", {})
    for naam, t in (("sleutel_instagram", tok), ("sleutel_facebook", os.environ.get("FB_TOKEN", "").strip())):
        if not t or not t.startswith("EAA"):
            continue
        try:
            d = http("GET", f"{API_FB}/debug_token", {"input_token": t, "access_token": t}).get("data", {})
            exp = d.get("expires_at") or 0
            g.setdefault(naam, {})["verloopt"] = "nooit" if exp == 0 else dt.datetime.fromtimestamp(exp, TZ).date().isoformat()
            g[naam]["geldig"] = bool(d.get("is_valid"))
            g[naam]["ok" if d.get("is_valid") else "fout"] = dt.datetime.now().isoformat(timespec="minutes")
            g[naam]["laatst_ok"] = bool(d.get("is_valid"))
            if exp and 0 <= (dt.datetime.fromtimestamp(exp, TZ).date() - dt.date.today()).days <= 7:
                S.cmd_log(f"ACTIE VOOR JOU: de {naam.replace('sleutel_', '').capitalize()}-sleutel verloopt op "
                          f"{dt.datetime.fromtimestamp(exp, TZ).strftime('%d-%m')}. Vernieuw hem op tijd (zie de stappen in het dashboard).", "fout", "rechten")
        except Exception as e:
            g.setdefault(naam, {})["detail"] = str(e)[:160]
    S.bewaar("data/gezondheid.json", g)

# ---------- Reacties ----------
def lokaal(t):
    """Tijd van Meta (UTC, bv. 2026-11-08T17:11:00+0000) naar Nederlandse tijd 'YYYY-MM-DDTHH:MM'."""
    try:
        return dt.datetime.strptime(t[:19] + t[19:].replace(":", ""), "%Y-%m-%dT%H:%M:%S%z").astimezone(TZ).isoformat(timespec="minutes")[:16]
    except Exception:
        return t[:16]

def reacties_ophalen(posts):
    """Haalt reacties op posts van de afgelopen 14 dagen op (Instagram en Facebook) in data/reacties.json.
    Hiervoor zijn extra rechten nodig: instagram_manage_comments (en voor Facebook pages_read_user_content)."""
    uid, tok = env()
    nu = dt.datetime.now(TZ)
    oud = {r["id"]: r for r in S.laad("data/reacties.json", [])}
    nieuw_aantal, fout = 0, None
    for p in posts:
        for plat, g in p.get("gepubliceerd", {}).items():
            if nu - dt.datetime.fromisoformat(g["t"]) > dt.timedelta(days=14):
                continue
            try:
                if plat == "instagram":
                    r = http("GET", f"{API}/{g['id']}/comments", {"fields": "id,text,username,timestamp,replies{id,text,username}", "access_token": tok})
                    rijen = [(c["id"], c.get("text", ""), c.get("username", ""), c.get("timestamp", ""),
                              any(x.get("username") == "bibleverse_nl" for x in (c.get("replies") or {}).get("data", []))) for c in r.get("data", [])]
                elif plat == "facebook":
                    pid, ptok = page_token(tok)
                    r = http("GET", f"{API_FB}/{g['id']}/comments", {"fields": "id,message,from,created_time,comments{from}", "access_token": ptok})
                    rijen = [(c["id"], c.get("message", ""), (c.get("from") or {}).get("name", "iemand"), c.get("created_time", ""),
                              any((x.get("from") or {}).get("id") == pid for x in (c.get("comments") or {}).get("data", []))) for c in r.get("data", [])]
                else:
                    continue
            except Exception as e:
                fout = str(e)[:160]; continue
            for cid, tekst, naam, t, beantwoord in rijen:
                if naam == "bibleverse_nl":
                    continue
                r0 = oud.get(cid)
                if r0:
                    if beantwoord and r0["status"] != "geplaatst":
                        r0["status"] = "geplaatst"
                    continue
                oud[cid] = {"id": cid, "platform": plat, "post": p["id"], "ref": p["ref"], "media_id": g["id"], "tekst": tekst,
                            "naam": naam, "t": lokaal(t), "status": "geplaatst" if beantwoord else "nieuw", "voorstel": "",
                            "opties": S.standaard_opties(tekst)}
                nieuw_aantal += 1
    # afgehandelde reacties na 3 dagen weghalen (de repo is openbaar; bewaar niet meer dan nodig)
    grens = (nu - dt.timedelta(days=3)).isoformat(timespec="minutes")
    houd = [r for r in oud.values() if r["status"] in ("nieuw", "voorgesteld") or r.get("geplaatst", r["t"]) >= grens]
    S.bewaar("data/reacties.json", sorted(houd, key=lambda r: r["t"], reverse=True)[:300])
    S.gezond("reacties", fout is None, fout or f"{nieuw_aantal} nieuwe reacties")
    try:  # nieuwe reacties naar Telegram, met de antwoordopties als knoppen
        import whatsapp
        nieuw = [r for r in houd if r["status"] == "nieuw" and not r.get("gemeld")]
        if len(nieuw) > 5:
            whatsapp.zet_in_wachtrij(f"💬 *{len(nieuw)} nieuwe reacties* wachten op antwoord. De nieuwste: {nieuw[0]['naam']}: \"{nieuw[0]['tekst'][:120]}\"",
                                     "reacties", "reacties:" + nieuw[0]["id"])
        else:
            for r in nieuw:
                opt = (r.get("opties") or [])[:3]
                regels = [f"💬 *Nieuwe reactie* van {r['naam']} op {r['ref']} ({r['platform']}):", f"\"{r['tekst'][:400]}\""]
                if opt:
                    regels += ["", "Antwoordopties:"] + [f"{i + 1}. {t}" for i, t in enumerate(opt)]
                knoppen = [[[f"Plaats {i + 1}", {"actie": "reactie_plaatsen", "reactie": r["id"], "tekst": t}] for i, t in enumerate(opt)]] if opt else []
                knoppen.append([["♡ Liken", {"actie": "reactie_liken", "reactie": r["id"]}], ["Negeren", {"actie": "reactie_negeren", "reactie": r["id"]}]])
                whatsapp.zet_in_wachtrij("\n".join(regels), "reacties", "reactie:" + r["id"], knoppen=knoppen)
        for r in nieuw:
            r["gemeld"] = True
        S.bewaar("data/reacties.json", sorted(houd, key=lambda r: r["t"], reverse=True)[:300])
    except Exception as e:
        print("Reacties melden mislukt:", e)
    if nieuw_aantal:
        S.activiteit("community", f"{nieuw_aantal} nieuwe reactie{'s' if nieuw_aantal > 1 else ''} gevonden")
    return nieuw_aantal

def reactie_plaatsen(r, tekst):
    uid, tok = env()
    if r["platform"] == "instagram":
        http("POST", f"{API}/{r['id']}/replies", {"message": tekst, "access_token": tok})
    else:
        pid, ptok = page_token(tok)
        http("POST", f"{API_FB}/{r['id']}/comments", {"message": tekst, "access_token": ptok})

def reactie_liken(r):
    """Hartje op een reactie. Instagram: recht instagram_manage_engagement (sinds april 2026);
    Facebook: pages_manage_engagement."""
    uid, tok = env()
    if r["platform"] == "instagram":
        http("POST", f"{API}/{r['id']}/likes", {"access_token": tok})
    else:
        pid, ptok = page_token(tok)
        http("POST", f"{API_FB}/{r['id']}/likes", {"access_token": ptok})

def vroege_cijfers(nu):
    """Meting van het eerste uur (60 tot 180 minuten na plaatsing): een vroeg signaal, zodat het systeem sneller leert."""
    posts = S.laad("data/posts.json", [])
    todo = []
    for p in posts:
        for plat, ig in p.get("gepubliceerd", {}).items():
            leeftijd = nu - dt.datetime.fromisoformat(ig["t"])
            if "1u" not in p.get("stats", {}).get(plat, {}) and dt.timedelta(minutes=60) <= leeftijd < dt.timedelta(minutes=180):
                todo.append((p, plat, ig))
    if not todo:
        return
    uid, tok = env()
    rij = []
    for p, plat, ig in todo:
        try:
            m = insights(ig["id"], tok) if plat == "instagram" else stats_facebook(p, ig, tok) if plat == "facebook" else None
        except Exception as e:
            print("Eerste uur", p["id"], plat, str(e)[:100]); continue
        if not m:
            continue
        rij.append({"post_id": p["id"], "platform": plat, "moment": "1u",
                    "views": m.get("views"), "reach": m.get("reach"), "likes": m.get("likes"),
                    "comments": m.get("comments"), "shares": m.get("shares"), "saves": m.get("saved"),
                    "follows": m.get("follows"), "avg_watch_ms": m.get("ig_reels_avg_watch_time")})
    if rij:
        json.dump(rij, open(S.P("stats_tmp.json"), "w"))
        S.cmd_stats(S.P("stats_tmp.json"))
        os.remove(S.P("stats_tmp.json"))
        S.cmd_log(f"Eerste-uurcijfers van {len(rij)} posts vastgelegd")

def cmd_statistieken():
    uid, tok = env()
    posts = S.laad("data/posts.json", [])
    nu = dt.datetime.now(TZ)
    rij = []
    for p, plat, ig in [(p, pl, g) for p in posts for pl, g in p.get("gepubliceerd", {}).items()]:
        leeftijd = nu - dt.datetime.fromisoformat(ig["t"])
        st = p.get("stats", {}).get(plat, {})
        moment = None
        if leeftijd >= dt.timedelta(days=7) and "7d" not in st and leeftijd < dt.timedelta(days=14):
            moment = "7d"
        elif leeftijd >= dt.timedelta(hours=20) and "24u" not in st and leeftijd < dt.timedelta(days=7):
            moment = "24u"
        if not moment:
            continue
        try:
            if plat == "instagram":
                m = insights(ig["id"], tok)
            elif plat == "facebook":
                m = stats_facebook(p, ig, tok)
            else:
                continue
        except Exception as e:
            S.cmd_log(f"Statistieken {p['id']} ({plat}) mislukt: {str(e)[:160]}", "fout", code="statistieken"); continue
        rij.append({"post_id": p["id"], "platform": plat, "moment": moment,
                    "views": m.get("views"), "reach": m.get("reach"), "likes": m.get("likes"),
                    "comments": m.get("comments"), "shares": m.get("shares"), "saves": m.get("saved"),
                    "follows": m.get("follows"), "avg_watch_ms": m.get("ig_reels_avg_watch_time")})
    if rij:
        json.dump(rij, open(S.P("stats_tmp.json"), "w"))
        S.cmd_stats(S.P("stats_tmp.json"))
        os.remove(S.P("stats_tmp.json"))
        S.cmd_log(f"Statistieken opgehaald voor {len(rij)} posts")
        S.activiteit("analist", f"Las cijfers van {len(rij)} posts")
    try:
        verse_cijfers(posts := S.laad("data/posts.json", []))
        S.bewaar("data/posts.json", posts)
    except Exception as e:
        S.cmd_log(f"Actuele cijfers ophalen mislukt: {str(e)[:160]}", "fout", code="statistieken")
    try:
        volgers_en_tokens()
    except Exception as e:
        S.cmd_log(f"Volgers ophalen mislukt: {str(e)[:160]}", "fout", code="statistieken")
    try:
        reacties_ophalen(S.laad("data/posts.json", []))
    except Exception as e:
        print("Reacties ophalen mislukt:", e)
    S.gezond("statistieken", True, f"{len(rij)} nieuwe metingen")
    try:
        S.cmd_opruimen(30)
    except Exception as e:
        S.cmd_log(f"Opruimen mislukt: {e}", "fout")
    leer_st = S.laad("data/gezondheid.json", {}).get("leren") or {}
    snel = S.check_leermodus()
    wekelijks = dt.date.today().weekday() == 0 and (leer_st.get("ok") or "")[:10] != dt.date.today().isoformat()
    if snel or wekelijks:  # snel leren: elke dag; daarna elke maandag (zonder Claude)
        try:
            S.cmd_leer()
            S.cmd_log("Snel leren: strategie bijgewerkt met de cijfers van gisteren" if snel else "Wekelijks leren: strategie bijgewerkt met de cijfers van afgelopen week")
            S.gezond("leren", True, "dagelijks (snel leren)" if snel else "wekelijks")
        except Exception as e:
            S.cmd_log(f"Leren mislukt: {e}", "fout")
            S.gezond("leren", False, str(e)[:200])
    S.cmd_plan()
    S.cmd_dashboard()

def cmd_token():
    """Ververst het long-lived token (60 dagen geldig). Zonder GH_PAT alleen een waarschuwing."""
    uid, tok = env()
    if API == API_FB:
        # Facebook/system-user token: niet te verversen, wel controleren of het werkt
        info = http("GET", f"{API}/{uid}", {"fields": "username", "access_token": tok})
        S.cmd_log(f"Verbinding met Instagram werkt (@{info.get('username')})")
        S.activiteit("controller", "Controleerde de verbindingen")
        try:
            rechten = [x["permission"] for x in http("GET", f"{API}/me/permissions", {"access_token": tok}).get("data", [])
                       if x.get("status") == "granted"]
        except Exception:
            rechten = []
        if rechten:
            mist = [r for r in ("instagram_basic", "instagram_content_publish", "instagram_manage_insights") if r not in rechten]
            if mist:
                S.cmd_log("Token mist rechten: " + ", ".join(mist) + ". Wel aanwezig: " + ", ".join(sorted(rechten)), "fout", code="rechten")
            else:
                S.cmd_log("Token heeft alle rechten, ook voor statistieken")
        if os.environ.get("FB_PAGE_ID", "").strip():
            try:
                pid, ptok = page_token(tok)
                naam = http("GET", f"{API_FB}/{pid}", {"fields": "name", "access_token": ptok}).get("name")
                S.cmd_log(f"Verbinding met Facebook-pagina werkt ({naam})")
            except Exception as e:
                S.cmd_log(f"Facebook-verbinding mislukt: {str(e)[:300]}", "fout", code="verbinding")
        # praktijktest: statistieken van de laatste post opvragen (als die er is)
        try:
            media = http("GET", f"{API}/{uid}/media", {"fields": "id", "limit": 1, "access_token": tok}).get("data", [])
            if media:
                m = insights(media[0]["id"], tok)
                S.cmd_log("Statistieken lezen werkt" if m else "Statistieken lezen gaf geen gegevens terug", "info" if m else "fout")
        except Exception as e:
            S.cmd_log(f"Statistieken lezen mislukt: {str(e)[:160]}", "fout", code="statistieken")
        try:
            volgers_en_tokens()
        except Exception as e:
            S.cmd_log(f"Volgers ophalen mislukt: {str(e)[:160]}", "fout", code="statistieken")
        S.cmd_dashboard(); return
    r = http("GET", "https://graph.instagram.com/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": tok})
    dagen = int(r.get("expires_in", 0)) // 86400
    nieuw = r.get("access_token")
    pat = os.environ.get("GH_PAT")
    if nieuw and nieuw != tok and pat:
        zet_secret("IG_TOKEN", nieuw, pat)
        S.cmd_log(f"Instagram-token ververst, geldig voor {dagen} dagen")
    elif nieuw and nieuw != tok:
        S.cmd_log("Instagram-token kon niet automatisch worden opgeslagen (GH_PAT ontbreekt). Vervang IG_TOKEN binnen 50 dagen.", "fout")
    else:
        S.cmd_log(f"Instagram-token gecontroleerd, nog {dagen} dagen geldig")
    S.cmd_dashboard()

def zet_secret(naam, waarde, pat):
    """Versleutelt en schrijft een repository-secret via de GitHub API (vereist PyNaCl)."""
    from base64 import b64encode
    from nacl import encoding, public
    repo = os.environ["GITHUB_REPOSITORY"]
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=h)
    key = json.load(urllib.request.urlopen(req))
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    enc = b64encode(box.encrypt(waarde.encode())).decode()
    body = json.dumps({"encrypted_value": enc, "key_id": key["key_id"]}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/{naam}", data=body, headers=h, method="PUT")
    urllib.request.urlopen(req)

if __name__ == "__main__":
    {"posten": cmd_posten, "statistieken": cmd_statistieken, "token": cmd_token}[sys.argv[1]]()
