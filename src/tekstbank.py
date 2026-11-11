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
        "hashtags": list(e["tags"])[: cfg.get("hashtags_max", 5)],
        "uitleg": e["uitleg"] if v.get("uitleg_op_beeld") else "",
        "betekenis": e["betekenis"], "toepassing": e["toepassing"],
        "kernwoord": e["kw"], "verhaal_hook": e.get("verhaal", ""),
        "tekstbron": "tekstbank",
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
