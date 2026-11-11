"""Beelden en video's staan in een aparte branch 'media' zonder geschiedenis, zodat de repo niet volloopt.
De map docs/media is een git-worktree van die branch.

  python3 tools/media.py koppel        # docs/media klaarzetten (na clonen of in GitHub Actions)
  python3 tools/media.py bewaar        # nieuwe/verwijderde media vastleggen en pushen
  python3 tools/media.py samenpersen   # branch terugbrengen tot één commit (oude versies verdwijnen)
"""
import os, subprocess, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "docs", "media")
BRANCH = "media"

def git(*a, cwd=ROOT, check=True):
    return subprocess.run(["git", *a], cwd=cwd, check=check, capture_output=True, text=True)

def koppel():
    if os.path.exists(os.path.join(MAP, ".git")):
        git("pull", "-q", "--rebase", "origin", BRANCH, cwd=MAP, check=False)
        return
    bestaand = git("ls-remote", "--heads", "origin", BRANCH).stdout.strip()
    tijdelijk = None
    if os.path.isdir(MAP) and os.listdir(MAP):
        tijdelijk = MAP + ".tmp"
        shutil.rmtree(tijdelijk, ignore_errors=True)
        shutil.move(MAP, tijdelijk)
    if bestaand:
        git("fetch", "-q", "origin", f"{BRANCH}:{BRANCH}", check=False)
        git("worktree", "add", "-f", MAP, BRANCH)
    else:
        git("worktree", "add", "-f", "--orphan", "-b", BRANCH, MAP)
    if tijdelijk:  # lokaal gemaakte bestanden behouden
        for root, _, files in os.walk(tijdelijk):
            for f in files:
                bron = os.path.join(root, f)
                doel = os.path.join(MAP, os.path.relpath(bron, tijdelijk))
                os.makedirs(os.path.dirname(doel), exist_ok=True)
                if not os.path.exists(doel):
                    shutil.copy2(bron, doel)
        shutil.rmtree(tijdelijk, ignore_errors=True)
    print("docs/media gekoppeld aan branch", BRANCH)

WEG = os.path.join(ROOT, "data", "media_weg.json")

def bewaar(bericht="Media bijgewerkt"):
    """Legt nieuwe en gewijzigde media vast. Bestanden die lokaal ontbreken worden NIET als verwijderd gezien
    (een onvolledige werkmap mag nooit beelden van geplande posts weggooien). Alleen wat in data/media_weg.json
    staat (bewust opgeruimd door 'systeem.py opruimen') wordt echt verwijderd."""
    import json
    koppel()
    git("add", "--ignore-removal", ".", cwd=MAP)
    try:
        weg = json.load(open(WEG))
    except (FileNotFoundError, ValueError):
        weg = []
    for rel in weg:
        r = rel[len("docs/media/"):] if rel.startswith("docs/media/") else rel
        git("rm", "-q", "--cached", "--ignore-unmatch", r, cwd=MAP, check=False)
    if weg:
        json.dump([], open(WEG, "w"))
    if git("diff", "--cached", "--quiet", cwd=MAP, check=False).returncode == 0:
        print("Geen nieuwe media"); return
    git("-c", "user.name=bijbeltekst-bot", "-c", "user.email=actions@users.noreply.github.com", "commit", "-qm", bericht, cwd=MAP)
    for _ in range(4):
        if git("push", "-q", "origin", f"HEAD:{BRANCH}", cwd=MAP, check=False).returncode == 0:
            print("Media gepusht"); return
        git("pull", "-q", "--rebase", "origin", BRANCH, cwd=MAP, check=False)
    sys.exit("Media pushen mislukt")

def samenpersen():
    """Eén verse commit met alleen de huidige bestanden; oude versies vallen uit de geschiedenis."""
    koppel()
    git("pull", "-q", "--rebase", "origin", BRANCH, cwd=MAP, check=False)
    git("checkout", "-q", "--orphan", "media-nieuw", cwd=MAP)
    git("add", "--ignore-removal", ".", cwd=MAP)
    git("-c", "user.name=bijbeltekst-bot", "-c", "user.email=actions@users.noreply.github.com", "commit", "-qm", "Media (samengeperst)", cwd=MAP)
    git("push", "-q", "--force", "origin", f"HEAD:{BRANCH}", cwd=MAP)
    git("branch", "-f", BRANCH, "HEAD", cwd=MAP, check=False)
    git("checkout", "-q", BRANCH, cwd=MAP, check=False)
    git("branch", "-D", "media-nieuw", cwd=MAP, check=False)
    print("Media-branch samengeperst")

if __name__ == "__main__":
    {"koppel": koppel, "bewaar": lambda: bewaar(*sys.argv[2:3]), "samenpersen": samenpersen}[sys.argv[1]]()
