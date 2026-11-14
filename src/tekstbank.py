"""Tekstbank: alle teksten per vers vooraf geschreven, zodat het systeem zonder Claude posts kan maken.

Per vers (sleutel = vers_id) staat in data/tekstbank.json:
  ref        referentie (controle)
  kw         kernwoord, letterlijk een woord uit het vers
  uitleg     het vers in gewone taal (max 110 tekens), voor uitleg op het beeld
  betekenis  'Wat betekent dit?' (20 tot 320 tekens)
  toepassing 'Vandaag' (20 tot 320 tekens)
  verhaal    openingszin voor 'verhaal eerst' (25 tot 140 tekens)
  zin        één korte zin uitleg of toepassing voor in de caption
  vraag      één oprechte, open vraag (voor 'vraag onderaan')
  hooks      {"vraag": .., "herkenning": .., "uitdaging": .., "rustig": ..}
  tags       3 tot 5 hashtags
Claude vult de bank af en toe aan; GitHub Actions gebruikt hem elke dag (systeem.py automaak).
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = os.path.join(ROOT, "data", "tekstbank.json")
HOOKSTIJLEN = ("vraag", "herkenning", "uitdaging", "rustig")

# Ochtendposts (Joshua, 12 nov): het ochtendslot (04:00, eerder 07:30) krijgt altijd een vers voor een goede start van de dag
OCHTEND_VERZEN = frozenset("""
Lamentations-3-22-23 Psalms-118-24-24 Psalms-143-8-8
Psalms-27-1-1 Psalms-92-2-2 Psalms-100-4-4 Psalms-103-1-1
Psalms-103-2-2 Psalms-107-1-1 Psalms-136-1-1 Psalms-95-2-2
Psalms-9-2-2 Psalms-118-14-14 Psalms-28-7-7 Psalms-16-11-11
Psalms-34-2-2 Psalms-150-6-6 Psalms-46-2-2 Psalms-37-5-5
Psalms-25-9-9 Isaiah-40-31-31 Isaiah-40-29-29 Isaiah-41-13-13
Isaiah-43-1-1 Isaiah-12-2-2 Isaiah-26-3-3 Isaiah-55-12-12
Isaiah-43-4-4 Joshua-1-9-9 Joshua-1-6-6 Deuteronomy-31-6-6
Deuteronomy-31-8-8 Jeremiah-29-11-11 Zephaniah-3-17-17 Nahum-1-7-7
Philippians-4-13-13 Philippians-4-6-7 Romans-8-31-31 Romans-8-37-37
Romans-12-12-12 Romans-5-5-5 Ephesians-6-10-10 Ephesians-2-10-10
Ephesians-5-20-20 I_Corinthians-16-13-13 I_Thessalonians-5-16-18 Colossians-2-7-7
Matthew-5-14-14 Matthew-6-34-34 Matthew-11-28-28 John-14-1-1
John-16-33-33 Hebrews-10-23-23 James-1-17-17 James-1-5-5
II_Corinthians-5-17-17 Revelation_of_John-21-5-5 Proverbs-16-3-3 Habakkuk-3-18-18
Psalms-121-1-2 Psalms-56-4-4 Psalms-118-6-6 Psalms-62-2-2
""".split())
OCHTEND_OPENERS = (
    "Goedemorgen. Een vers voor het begin van je dag.",
    "Goedemorgen. Begin je dag hiermee.",
    "Een nieuwe dag. Neem dit vers mee.",
    "Goedemorgen. Dit is voor jou, vandaag.",
    "Een goede start begint hier.",
    "Goedemorgen. Mag deze dag goed beginnen.",
    "Vandaag is een nieuwe kans. Lees dit eerst.",
)


def ochtend_opener(p):
    """Wisselende ochtendopening, vast per post (zelfde datum geeft dezelfde regel)."""
    return OCHTEND_OPENERS[sum(map(ord, p["datum"])) % len(OCHTEND_OPENERS)]


def is_ochtend(p):
    return (p.get("variabelen") or {}).get("tijdslot", "99") < "10:00"



def laad():
    try:
        return json.load(open(PAD, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def bewaar(bank):
    json.dump(dict(sorted(bank.items())), open(PAD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _woorden(tekst):
    return [w.lower().strip(" .,;:!?’'\"()") for w in tekst.split()]


def problemen(vid, e, vers_tekst=None):
    """Lijst met problemen in één item (leeg = goed)."""
    uit = []
    for veld, lo, hi in (("betekenis", 20, 320), ("toepassing", 20, 320), ("verhaal", 25, 140), ("uitleg", 10, 110),
                         ("zin", 10, 160), ("vraag", 8, 120)):
        n = len((e.get(veld) or "").strip())
        if veld in ("verhaal", "vraag") and n == 0:
            continue  # optioneel: zonder openingszin geen 'verhaal eerst'
        if not lo <= n <= hi:
            uit.append(f"{veld}: {n} tekens (moet {lo} tot {hi})")
    if e.get("vraag") and not e["vraag"].strip().endswith("?"):
        uit.append("vraag eindigt niet op ?")
    if not any((e.get("hooks") or {}).get(s) for s in HOOKSTIJLEN):
        uit.append("geen enkele hook")
    if not 3 <= len(e.get("tags") or []) <= 5:
        uit.append("3 tot 5 hashtags")
    alles = " ".join(str(v) for v in e.values() if isinstance(v, str)) + " ".join((e.get("hooks") or {}).values())
    if "—" in alles:
        uit.append("lange streep gebruikt")
    if vers_tekst is not None and (e.get("kw") or "").lower().strip(" .,;:!?") not in _woorden(vers_tekst):
        uit.append(f"kernwoord '{e.get('kw')}' staat niet letterlijk in het vers")
    return uit


def hashtags_voor(e, p, stijl, cfg):
    """Hashtags volgens de geteste stijl: 'mix' (vaste tags uit de bank), 'zoekwoord' (kernwoord, boek en #bijbelvers) of 'zonder'."""
    import re
    mx = cfg.get("hashtags_max", 5)
    if stijl == "zonder":
        return []
    if stijl == "zoekwoord":
        schoon = lambda t: re.sub(r"[^0-9a-zA-Z\u00c0-\u017f]", "", t).lower()
        boek = re.sub(r"\s+\d+[\d:,.\-\u2013]*$", "", p["ref"])
        thema = {"vrede_rust": "rust", "humor_herkenbaar": "humor"}.get(p["variabelen"].get("thema"), p["variabelen"].get("thema") or e.get("kw", ""))
        tags = ["#bijbelvers", "#" + schoon(thema), "#" + schoon(boek)]
        uit = []
        for t in tags:
            if len(t) > 1 and t not in uit:
                uit.append(t)
        return uit[:mx]
    return list(e["tags"])[:mx]


def vul_post(p, e, cfg, vermijd=()):
    """Vult een post (status wacht_op_tekst) met teksten uit de bank. Geeft True als het lukte.
    vermijd: hooks die de afgelopen 14 dagen al gebruikt zijn (die worden overgeslagen)."""
    v = p["variabelen"]
    hooks = {k: h for k, h in (e.get("hooks") or {}).items() if h and h.strip() not in vermijd}
    stijl = v.get("hook_stijl")
    if stijl != "geen" and not hooks.get(stijl):
        # deze hookstijl staat niet in de bank: neem een andere en leg dat vast (dan leert het systeem eerlijk)
        stijl = next((s for s in HOOKSTIJLEN if hooks.get(s)), "geen")
        v["hook_stijl"] = stijl
        p.setdefault("keuzebron", {})["hook_stijl"] = "tekstbank"
    hook = "" if stijl == "geen" else hooks[stijl].strip()
    if v.get("opening") == "verhaal" and not (e.get("verhaal") or "").strip():
        v["opening"] = "stopper" if len(p["tekst"]) >= 70 else "vers"
        p.setdefault("keuzebron", {})["opening"] = "tekstbank"
    if p.get("reeks_label"):
        label = p["reeks_label"].split("·")[0].strip().capitalize()
        dag = p["reeks_label"].split("·")[1].strip().lower() if "·" in p["reeks_label"] else ""
        hook = f"{label}{', ' + dag if dag else ''}: {hook}" if hook else f"{label}{', ' + dag if dag else ''}."
    if is_ochtend(p):
        hook = ochtend_opener(p)
        if p.get("reeks_label"):
            hook = f"{label}{', ' + dag if dag else ''}. {hook}"
    vers = f"\"{p['tekst']}\"\n{p['ref']}"
    if p.get("vertaling") == "NBV21":
        vers += "\nNBV21 © Nederlands-Vlaams Bijbelgenootschap"
    delen = ([hook] if hook else []) + [vers, e["zin"].strip()]
    if v.get("vraag_onderaan") is True and not (e.get("vraag") or "").strip():
        v["vraag_onderaan"] = False
        p.setdefault("keuzebron", {})["vraag_onderaan"] = "tekstbank"
    if v.get("vraag_onderaan") is True:
        delen.append(e["vraag"].strip())
    caption = "\n\n".join(delen)
    if len(caption) > 600:  # te lang: zonder uitlegzin
        caption = "\n\n".join(d for d in delen if d != e["zin"].strip())
    p.update({
        "hook": hook, "beeld_hook": "", "caption": caption,
        "hashtags": hashtags_voor(e, p, v.get("hashtag_stijl") or "mix", cfg),
        "uitleg": e["uitleg"] if v.get("uitleg_op_beeld") else "",
        "betekenis": e["betekenis"], "toepassing": e["toepassing"],
        "kernwoord": e["kw"], "verhaal_hook": e.get("verhaal", ""),
        "tekstbron": "tekstbank",
        "reel_uitleg": e.get("uitleg", ""), "reel_vraag": (e.get("hooks") or {}).get("vraag", ""),
        "reel_herkenning": (e.get("hooks") or {}).get("herkenning", ""),
    })
    return True


def uit_post(p):
    """Maakt een bankitem van een post die Claude al met de hand schreef (om de bank te zaaien)."""
    if not (p.get("betekenis") and p.get("toepassing") and p.get("kernwoord") and p.get("caption")):
        return None
    delen = [d.strip() for d in p["caption"].split("\n\n")]
    vraag = delen[-1] if delen[-1].endswith("?") and p["ref"] not in delen[-1] else ""
    zin = next((d for d in reversed(delen) if d != vraag and p["ref"] not in d and d != p.get("hook", "").strip()), "")
    stijl = p["variabelen"].get("hook_stijl")
    e = {"ref": p["ref"], "kw": p["kernwoord"], "uitleg": p.get("uitleg") or zin[:110],
         "betekenis": p["betekenis"], "toepassing": p["toepassing"],
         "verhaal": p.get("verhaal_hook") or "", "zin": zin, "vraag": vraag,
         "hooks": {stijl: p["hook"]} if stijl in HOOKSTIJLEN and p.get("hook") else {},
         "tags": p.get("hashtags", [])}
    return e
