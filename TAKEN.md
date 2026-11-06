# Werkinstructies voor de geplande taken

Dit bestand is de handleiding voor Claude bij elke geplande run. Volg het letterlijk. Werk in de projectmap (de clone van de repo uit `config.json` > `github_repo`).

## Vaste regels (nooit overtreden)
- Staat `pauze` op `true` in `config.json`: doe niets behalve `python3 src/systeem.py log "Gepauzeerd, niets gedaan"`, commit, push, stop.
- Alleen posten op het Metricool-merk met `metricool_blog_id` uit `config.json`. Nooit op een ander merk (dat zijn klanten van STTP Media).
- Nooit meer dan `max_posts_per_dag` posts per dag.
- Verstekst altijd letterlijk uit `data/verzen.json` (Statenvertaling). Nooit een vers zelf typen of "verbeteren".
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
- `beeld_hook`: alleen als `variabelen.hook_op_beeld` true is. Maximaal 42 tekens. Mag dezelfde gedachte zijn als de hook, korter.
- `caption`: hook (als die er is), witregel, de verstekst letterlijk tussen aanhalingstekens, de referentie, witregel, één korte zin uitleg of toepassing in hedendaags Nederlands (de Statenvertaling is oud taalgebruik; help de lezer). Totaal maximaal 600 tekens.
- `hashtags`: 3 tot 5, Nederlands, bv. `#bijbeltekst #geloof #bemoediging #god #jezus`. Wissel af.
Schrijf in het Nederlands, warm en eenvoudig, nooit prekerig. Elke hook anders dan die van de afgelopen 14 dagen (kijk in `data/posts.json`).

## Dagelijkse run
1. `git pull`. Lees `config.json`. Pauze? Zie regels.
2. Bereken MORGEN (Europe/Amsterdam). `python3 src/systeem.py kies --datum MORGEN`.
3. Schrijf de teksten (zie hierboven) in `data/posts.json`.
4. `python3 src/systeem.py render --datum MORGEN`. Bekijk minstens één gemaakt beeld met Read (bij video: haal een frame op 4 s met ffmpeg). Klopt er iets niet (tekst afgesneden, onleesbaar), verwijder de post uit `data/posts.json` en log het.
5. `git add -A && git commit -m "Posts MORGEN" && git push`. Controleer daarna met `curl -sI <media_url>` dat elke media_url 200 geeft (wacht zo nodig even).
6. Plan elke post in Metricool met `createScheduledPost` (blogId uit config):
   - `publicationDate`: MORGEN + `variabelen.tijdslot`, tijdzone Europe/Amsterdam. Datum mag niet in het verleden liggen.
   - `media`: [media_url]. `text`: caption + witregel + hashtags.
   - `draft`: true als `review_modus` true is, anders false. `autoPublish`: true.
   - Alleen de netwerken in `platformen_actief`, per netwerk de juiste data:
     - instagram: `{"type": "REEL"}` bij video, `{"type": "POST"}` bij afbeelding.
     - tiktok: `{"privacyOption": "PUBLIC_TO_EVERYONE"}` (afbeelding wordt een fotopost).
     - youtube: alleen bij video: `{"title": "<ref>: <eerste woorden>", "type": "short", "privacy": "public", "madeForKids": false}`. Bij een afbeelding YouTube overslaan.
     - facebook: `{"type": "REEL"}` bij video, `{"type": "POST"}` bij afbeelding.
     - twitter: `{"tags": []}`; tekst maximaal 280 tekens (gebruik dan alleen hook + referentie + 2 hashtags).
   - Na succes: `python3 src/systeem.py registreer POST_ID NETWERK METRICOOL_ID PLANNER_URL`.
7. Statistieken ophalen (zie hieronder) voor posts van 1 dag geleden (moment `24u`) en 7 dagen geleden (moment `7d`).
8. `python3 src/systeem.py dashboard`, log een regel als "2 posts gepland voor MORGEN (instagram)", commit, push.

## Statistieken ophalen
- Gebruik `getAnalyticsAvailableMetrics` (network instagram, connector posts en reels; tiktok connector posts; enz.) om de juiste metrics te vinden, en `getAnalyticsDataByMetrics` voor de periode.
- Koppel elke gemeten post aan onze post via platform + publicatietijd (binnen 15 minuten van datum + tijdslot) en zo nodig de eerste woorden van de tekst.
- Schrijf een bestand `stats_tmp.json`: lijst van `{post_id, platform, moment, views, reach, likes, comments, shares, saves, follows}` (onbekend = null), en draai `python3 src/systeem.py stats stats_tmp.json`. Verwijder daarna `stats_tmp.json`.

## Wekelijkse run (maandag)
1. Doe stap 1 en 7 van de dagelijkse run (pull, statistieken).
2. `python3 src/systeem.py leer`. Lees het nieuwste bestand in `rapporten/`.
3. Schrijf 1 tot 3 conclusies in gewone taal in `strategie.json` > `inzichten` als `{"datum": "...", "tekst": "..."}`. Alleen conclusies met genoeg metingen (n van minstens 5). Zeg eerlijk als iets nog onzeker is.
4. Kijk welke versen goed scoorden. Voeg 10 nieuwe versen toe die passen bij de best scorende thema's: `python3 src/systeem.py vers THEMA "EngelseBoeknaam" HOOFDSTUK VERS [TOTVERS]`. Controleer elke toegevoegde tekst: hij moet zelfstandig te begrijpen zijn.
5. Uitbreiden, één stap per week, alleen als het logboek van de afgelopen 7 dagen geen fouten heeft:
   - Week 1 klaar en `review_modus` true: zet `review_modus` op false.
   - Daarna: verplaats per week één platform van `platformen_later` naar `platformen_actief`, in deze volgorde: tiktok, youtube, facebook, twitter. Alleen als dat netwerk in Metricool aan het merk gekoppeld is (check `getBrandSettings`); anders log dat het nog niet gekoppeld is.
   - `posts_per_dag` mag naar 3 als de gemiddelde score van de laatste week niet daalt. Nooit hoger dan `max_posts_per_dag`.
6. Daalt het totale bereik twee weken op rij met meer dan 30%: zet `verkenning` op 0.3 en log een waarschuwing.
7. `python3 src/systeem.py dashboard`, log een samenvatting, commit, push.
