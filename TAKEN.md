# Werkinstructies voor de geplande taken

Dit bestand is de handleiding voor Claude bij elke geplande run. Volg het letterlijk. Werk in de projectmap (de clone van de repo uit `config.json` > `github_repo`).

## Vaste regels (nooit overtreden)
- Staat `pauze` op `true` in `config.json`: doe niets behalve `python3 src/systeem.py log "Gepauzeerd, niets gedaan"`, commit, push, stop.
- Nooit iets posten via Metricool of op accounts van STTP Media of klanten. Posten gebeurt alleen via GitHub Actions met de geheimen van de repo.
- Nooit meer dan `max_posts_per_dag` posts per dag.
- Verstekst altijd letterlijk uit de post in `data/posts.json` (Statenvertaling uit `data/verzen.json`, of NBV21 uit `verzen_nbv21.csv` in de privé repo). Nooit een vers zelf typen, aanvullen of "verbeteren", en nooit NBV21-tekst uit je geheugen of van een website halen.
- Heeft een post `"vertaling": "NBV21"`, zet dan direct onder de referentie in de caption: `NBV21 © Nederlands-Vlaams Bijbelgenootschap` (Joshua heeft toestemming van het NBG). Laat bij NBV21-posts `uitleg_op_beeld` gewoon zoals gekozen.
- Geen lange streep (het teken U+2014) in captions of hooks.
- Geen engagement-bait ("typ amen", "deel met 10 mensen", "zegen als je...").
- Respectvol: geen spot met het geloof, geen politiek, geen beloften over gezondheid of geld.
- Bij een fout: `python3 src/systeem.py log "<wat er misging>" fout`, ga door met wat wel kan, en meld het in je eindbericht.
- Commit en push aan het eind van elke run, ook als er iets misging (anders verdwijnt het logboek).

## Teksten schrijven (bij elke post met status `wacht_op_tekst`)
Vul in `data/posts.json` deze velden in:
- `hook`: de eerste zin van de caption, in de stijl uit `variabelen.hook_stijl`:
  - `vraag`: een korte, persoonlijke vraag. "Waar maak jij je vandaag zorgen over?"
  - `herkenning`: een herkenbare situatie. "Voor iedereen die vanochtend al moe wakker werd."
  - `uitdaging`: een kleine opdracht. "Lees dit twee keer, langzaam."
  - `rustig`: een korte, stille inleiding. "Even dit, voor je verder gaat."
  - `geen`: laat `hook` leeg.
  Voor het thema `humor_herkenbaar` mag de hook licht en grappig zijn ("Die ene collega om 7:00 uur..."), maar nooit spottend over de Bijbel.
- `beeld_hook`: altijd leeg laten. Joshua wil geen hooktekst op het beeld; de hook staat alleen in de caption.
- `caption`: hook (als die er is), witregel, de verstekst letterlijk tussen aanhalingstekens, de referentie, witregel, één korte zin uitleg of toepassing in hedendaags Nederlands (de Statenvertaling is oud taalgebruik; help de lezer). Totaal maximaal 600 tekens.
- `uitleg`: alleen als `variabelen.uitleg_op_beeld` true is. De kern van het vers in gewone, hedendaagse taal, maximaal 110 tekens, zonder aanhalingstekens. Bijvoorbeeld bij "En de vrede Gods heerse in uw harten": "Laat Gods vrede de baas zijn in je hart." Het is uitleg, geen Bijbeltekst: verander de betekenis niet en voeg niets toe.
- `betekenis` en `toepassing`: alleen bij `variabelen.formaat` = carrousel (3 slides). `betekenis`: 2 tot 3 korte zinnen over wat het vers betekent, eenvoudig en trouw aan de tekst (20 tot 320 tekens). `toepassing`: 1 tot 2 zinnen met een concrete, kleine stap voor vandaag (20 tot 320 tekens). Geen preek, geen dwang.
- `hashtags`: 3 tot 5, Nederlands, bv. `#bijbeltekst #geloof #bemoediging #god #jezus`. Wissel af.
Schrijf in het Nederlands, warm en eenvoudig, nooit prekerig. Elke hook anders dan die van de afgelopen 14 dagen (kijk in `data/posts.json`).

## Dagelijkse run
Het online zetten zelf doet GitHub Actions (`.github/workflows/publiceren.yml`, elk kwartier) en het ophalen van statistieken ook (dagelijks). Deze run maakt alleen de posts van morgen klaar.
1. `git pull --rebase`. Lees `config.json`. Pauze? Zie regels.
   Clone ook de privé repo `sttpjoshua/bibleverse-materiaal` (add_repo, alleen lezen) naast deze repo, dus als map `../bibleverse-materiaal`. Daar staan Joshua's muziek (Epidemic Sound) en foto's. Zet die bestanden NOOIT in deze openbare repo; alleen de afgewerkte post mag hier komen. Ontbreekt de map, dan gebruikt het systeem automatisch kleurverloop en geen muziek, en logt het een fout.
2. Bereken MORGEN (Europe/Amsterdam). `python3 src/systeem.py kies --datum MORGEN`.
3. Schrijf de teksten (zie hierboven) in `data/posts.json`.
4. `python3 src/systeem.py render --datum MORGEN`. Bekijk minstens één gemaakt beeld met Read (bij video: haal een frame op 4 s met ffmpeg). Klopt er iets niet (tekst afgesneden, onleesbaar), zet de status van die post op "afgekeurd" en log het.
5. Kijk in `data/logboek.json` naar fouten van de afgelopen 24 uur (van GitHub Actions). Noem ze in je eindbericht.
6. `python3 src/systeem.py dashboard`, log een regel als "1 post klaargezet voor MORGEN 20:30", dan `git add -A && git commit -m "Posts MORGEN" && git pull --rebase && git push`.

## Wekelijkse run (maandag)
1. `git pull --rebase`.
2. `python3 src/systeem.py leer`. Lees het nieuwste bestand in `rapporten/`.
3. Schrijf 1 tot 3 conclusies in gewone taal in `strategie.json` > `inzichten` als `{"datum": "...", "tekst": "..."}`. Alleen conclusies met genoeg metingen (n van minstens 5). Zeg eerlijk als iets nog onzeker is.
4. Kijk welke versen goed scoorden. Voeg 10 nieuwe versen toe die passen bij de best scorende thema's: `python3 src/systeem.py vers THEMA "EngelseBoeknaam" HOOFDSTUK VERS [TOTVERS]`. Controleer elke toegevoegde tekst: hij moet zelfstandig te begrijpen zijn.
5. Uitbreiden, één stap per week, alleen als het logboek van de afgelopen 7 dagen geen fouten heeft:
   - `posts_per_dag`: na de eerste foutloze week naar 2. Later mag het naar 3 als de gemiddelde score van de laatste week niet daalt. Nooit hoger dan `max_posts_per_dag`.
   - Een nieuw platform zet je alleen aan als `src/publiceer.py` het ondersteunt en de geheimen ervoor bestaan. Anders log je dat het klaarstaat voor Joshua.
6. Daalt het totale bereik twee weken op rij met meer dan 30%: zet `verkenning` op 0.3 en log een waarschuwing.
7. `python3 src/systeem.py dashboard`, log een samenvatting, commit, `git pull --rebase`, push.

## Bediening via het dashboard
Joshua kan vanaf het dashboard pauzeren, posts per dag (1-3), platformen, foto-aandeel en experimenteren aanpassen, en klaarstaande posts verplaatsen, nu posten, overslaan (status "afgekeurd") of een vers uitsluiten (config "verzen_uitsluiten"). Respecteer die keuzes: draai ze niet terug, kies nooit een uitgesloten vers, en verander de tijd niet van posts die hij handmatig heeft verplaatst. Verhoog posts_per_dag niet automatisch als Joshua hem zelf lager heeft gezet (zie logboek "Bediening:").

## Snel leren
Staat `leermodus` op true in config.json, dan maak je elke dag `posts_per_dag` (5) posts klaar, één per tijdslot, elk met een eigen hook en tekst. Pas posts_per_dag, max_posts_per_dag en verkenning dan niet aan; het systeem zet ze na `leermodus_tot` zelf terug. Het dagelijks leren gebeurt automatisch na het ophalen van de statistieken.
