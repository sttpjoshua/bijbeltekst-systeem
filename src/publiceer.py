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

def publiceer_instagram(p, uid, tok):
    video = p["variabelen"]["formaat"] == "video"
    params = {"caption": caption(p), "access_token": tok}
    if video:
        params.update({"media_type": "REELS", "video_url": p["media_url"], "share_to_feed": "true"})
    else:
        params["image_url"] = p["media_url"]
    cid = http("POST", f"{API}/{uid}/media", params)["id"]
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

def tijdstip(p):
    d = dt.date.fromisoformat(p["datum"])
    u, m = map(int, p["variabelen"]["tijdslot"].split(":"))
    return dt.datetime(d.year, d.month, d.day, u, m, tzinfo=TZ)

def cmd_posten():
    cfg = S.laad("config.json")
    if cfg["pauze"]:
        print("Pauze staat aan"); return
    nu = dt.datetime.now(TZ)
    posts = S.laad("data/posts.json", [])
    vandaag_online = sum(1 for p in posts if p["datum"] == nu.date().isoformat() and p["status"] == "gepubliceerd")
    klaar = [p for p in posts if p["status"] == "gerenderd" and tijdstip(p) <= nu]
    if not klaar:
        print("Niets te doen"); return
    uid, tok = env()
    fouten = 0
    for p in sorted(klaar, key=tijdstip):
        if nu - tijdstip(p) > TE_LAAT:
            p["status"] = "overgeslagen"
            S.cmd_log(f"{p['id']} overgeslagen: tijdstip gemist", "fout"); continue
        if vandaag_online >= cfg["max_posts_per_dag"]:
            p["status"] = "overgeslagen"
            S.cmd_log(f"{p['id']} overgeslagen: daglimiet bereikt", "fout"); continue
        for plat in cfg["platformen_actief"]:
            if plat in p.get("gepubliceerd", {}):
                continue
            try:
                if plat == "instagram":
                    mid, link = publiceer_instagram(p, uid, tok)
                else:
                    continue  # andere platformen volgen later
                p.setdefault("gepubliceerd", {})[plat] = {"id": mid, "url": link, "t": dt.datetime.now(TZ).isoformat(timespec="minutes")}
                S.cmd_log(f"{p['id']} online op {plat}: {p['ref']}")
            except Exception as e:
                p["fouten"] = p.get("fouten", 0) + 1
                S.cmd_log(f"{p['id']} {plat} mislukt: {e}", "fout"); fouten += 1
                if p["fouten"] >= 3:
                    p["status"] = "fout"
        if p.get("gepubliceerd") and p["status"] != "fout":
            p["status"] = "gepubliceerd"; vandaag_online += 1
        S.bewaar("data/posts.json", posts)  # na elke post opslaan
    S.cmd_dashboard()
    if fouten:
        sys.exit(f"{fouten} fout(en) bij publiceren, zie logboek")

METRICS = ["reach", "likes", "comments", "shares", "saved", "views", "follows"]

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

def cmd_statistieken():
    uid, tok = env()
    posts = S.laad("data/posts.json", [])
    nu = dt.datetime.now(TZ)
    rij = []
    for p in posts:
        ig = p.get("gepubliceerd", {}).get("instagram")
        if not ig:
            continue
        leeftijd = nu - dt.datetime.fromisoformat(ig["t"])
        st = p.get("stats", {}).get("instagram", {})
        moment = None
        if leeftijd >= dt.timedelta(days=7) and "7d" not in st and leeftijd < dt.timedelta(days=14):
            moment = "7d"
        elif leeftijd >= dt.timedelta(hours=20) and "24u" not in st and leeftijd < dt.timedelta(days=7):
            moment = "24u"
        if not moment:
            continue
        try:
            m = insights(ig["id"], tok)
        except Exception as e:
            S.cmd_log(f"Statistieken {p['id']} mislukt: {e}", "fout"); continue
        rij.append({"post_id": p["id"], "platform": "instagram", "moment": moment,
                    "views": m.get("views"), "reach": m.get("reach"), "likes": m.get("likes"),
                    "comments": m.get("comments"), "shares": m.get("shares"), "saves": m.get("saved"),
                    "follows": m.get("follows")})
    if rij:
        json.dump(rij, open(S.P("stats_tmp.json"), "w"))
        S.cmd_stats(S.P("stats_tmp.json"))
        os.remove(S.P("stats_tmp.json"))
        S.cmd_log(f"Statistieken opgehaald voor {len(rij)} posts")
    try:
        S.cmd_opruimen(30)
    except Exception as e:
        S.cmd_log(f"Opruimen mislukt: {e}", "fout")
    S.cmd_dashboard()

def cmd_token():
    """Ververst het long-lived token (60 dagen geldig). Zonder GH_PAT alleen een waarschuwing."""
    uid, tok = env()
    if API == API_FB:
        # Facebook/system-user token: niet te verversen, wel controleren of het werkt
        info = http("GET", f"{API}/{uid}", {"fields": "username", "access_token": tok})
        S.cmd_log(f"Verbinding met Instagram werkt (@{info.get('username')})")
        try:
            rechten = [x["permission"] for x in http("GET", f"{API}/me/permissions", {"access_token": tok}).get("data", [])
                       if x.get("status") == "granted"]
        except Exception:
            rechten = []
        if rechten:
            mist = [r for r in ("instagram_basic", "instagram_content_publish", "instagram_manage_insights") if r not in rechten]
            if mist:
                S.cmd_log("Token mist rechten: " + ", ".join(mist), "fout")
            else:
                S.cmd_log("Token heeft alle rechten, ook voor statistieken")
        # praktijktest: statistieken van de laatste post opvragen (als die er is)
        try:
            media = http("GET", f"{API}/{uid}/media", {"fields": "id", "limit": 1, "access_token": tok}).get("data", [])
            if media:
                m = insights(media[0]["id"], tok)
                S.cmd_log("Statistieken lezen werkt" if m else "Statistieken lezen gaf geen gegevens terug", "info" if m else "fout")
        except Exception as e:
            S.cmd_log(f"Statistieken lezen mislukt: {str(e)[:160]}", "fout")
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
