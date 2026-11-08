"""Git merge-driver voor de JSON-bestanden van het systeem.
Twee schrijvers tegelijk (GitHub Actions, de geplande Claude-taken, het dashboard) mogen elkaars wijzigingen
niet overschrijven. Dit voegt per post / per sleutel samen in plaats van per regel.
Gebruik (git config): merge.json.driver = python3 tools/json_merge.py %O %A %B %P
"""
import json, sys

STATUS_RANG = {"wacht_op_tekst": 0, "klaar_voor_render": 1, "opnieuw_maken": 1, "gerenderd": 2,
               "afgekeurd": 3, "overgeslagen": 3, "fout": 3, "gepubliceerd": 4}

def lees(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def drieweg(base, ours, theirs):
    """Per sleutel: wie iets veranderde ten opzichte van de basis, wint. Beiden veranderd: diepere merge of 'theirs'."""
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        uit = {}
        for k in list(ours) + [k for k in theirs if k not in ours]:
            if k in ours and k in theirs:
                uit[k] = drieweg(b.get(k), ours[k], theirs[k])
            elif k in ours:
                if k in b and b[k] == ours[k]:
                    continue  # door de ander verwijderd
                uit[k] = ours[k]
            else:
                if k in b and b[k] == theirs[k]:
                    continue
                uit[k] = theirs[k]
        return uit
    if isinstance(ours, list) and isinstance(theirs, list):
        if all(isinstance(x, dict) and "id" in x for x in ours + theirs):
            return lijst_op_id(base if isinstance(base, list) else [], ours, theirs)
        if all(isinstance(x, dict) and "t" in x for x in ours + theirs):  # logboek: alles behouden, op tijd
            gezien, uit = set(), []
            for x in sorted(ours + theirs, key=lambda x: x.get("t", "")):
                k = json.dumps(x, sort_keys=True, ensure_ascii=False)
                if k not in gezien:
                    gezien.add(k); uit.append(x)
            return uit
        return ours + [x for x in theirs if x not in ours]
    return theirs

def lijst_op_id(base, ours, theirs):
    b = {x["id"]: x for x in base}
    o = {x["id"]: x for x in ours}
    t = {x["id"]: x for x in theirs}
    volgorde = [x["id"] for x in ours] + [x["id"] for x in theirs if x["id"] not in o]
    uit = []
    for i in volgorde:
        if i in o and i in t:
            m = drieweg(b.get(i), o[i], t[i])
            # status nooit terugzetten (gepubliceerd blijft gepubliceerd)
            so, st = o[i].get("status"), t[i].get("status")
            if so and st and isinstance(m, dict):
                m["status"] = max(so, st, key=lambda s: STATUS_RANG.get(s, 0)) if so != b.get(i, {}).get("status") and st != b.get(i, {}).get("status") else m.get("status")
            uit.append(m)
        elif i in o:
            if i in b and b[i] == o[i]:
                continue
            uit.append(o[i])
        else:
            if i in b and b[i] == t[i]:
                continue
            uit.append(t[i])
    return uit

def main(base_p, ours_p, theirs_p, pad=""):
    base, ours, theirs = lees(base_p), lees(ours_p), lees(theirs_p)
    if ours is None or theirs is None:
        return 1  # geen geldige JSON: laat git het conflict melden
    uit = drieweg(base, ours, theirs)
    with open(ours_p, "w", encoding="utf-8") as f:
        json.dump(uit, f, ensure_ascii=False, indent=1)
        f.write("\n") if False else None
    return 0

if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
