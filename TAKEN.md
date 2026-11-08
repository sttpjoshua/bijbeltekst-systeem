# Werkinstructies voor de geplande taken

> **Eerst na het clonen:** `sh tools/git_instellen.sh` (JSON-bestanden worden dan per post samengevoegd bij `git pull --rebase`, zodat je geen wijzigingen van GitHub Actions of het dashboard overschrijft). Gebruik nooit `-X theirs` of `--force`.

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
- `kernwoord`: altijd invullen. Eén woord dat letterlijk in het vers staat (zoals het daar staat) en de kern draagt, bijvoorbeeld "Herder", "vrede", "hulp" of "nieuw". Liefst een woord met gevoel of beeld, niet "HEERE" of "God". Dit woord krijgt de accentkleur op het beeld. Bij `variabelen.opening` = stopper komt het stukje van het vers rond dit woord groot op slide 1 te staan, dus kies een woord in het sterkste deel van het vers.
- `betekenis` en `toepassing`: alleen bij `variabelen.formaat` = carrousel (3 slides). `betekenis`: 2 tot 3 korte zinnen over wat het vers betekent, eenvoudig en trouw aan de tekst (20 tot 320 tekens). `toepassing`: 1 tot 2 zinnen met een concrete, kleine stap voor vandaag (20 tot 320 tekens). Geen preek, geen dwang.
- `hashtags`: 3 tot 5, Nederlands, bv. `#bijbeltekst #geloof #bemoediging #god #jezus`. Wissel af.
Schrijf in het Nederlands, warm en eenvoudig, nooit prekerig. Elke hook anders dan die van de afgelopen 14 dagen (kijk in `data/posts.json`).

## Dagelijkse run
Het online zetten zelf doet GitHub Actions (`.github/workflows/publiceren.yml`, elk kwartier) en het ophalen van statistieken ook (dagelijks). Deze run maakt de posts van MORGEN én OVERMORGEN klaar (twee dagen buffer: als een run een keer mislukt, staat er toch genoeg klaar). Voor MORGEN zijn de meeste posts meestal al gemaakt; vul alleen aan wat ontbreekt.
1. `git pull --rebase`. Lees `config.json`. Pauze? Zie regels.
   Clone ook de privé repo `sttpjoshua/bibleverse-materiaal` (add_repo, alleen lezen) naast deze repo, dus als map `../bibleverse-materiaal`. Daar staan Joshua's muziek (Epidemic Sound) en foto's. Zet die bestanden NOOIT in deze openbare repo; alleen de afgewerkte post mag hier komen. Ontbreekt de map, dan gebruikt het systeem automatisch kleurverloop en geen muziek, en logt het een fout.
2. Bereken MORGEN en OVERMORGEN (Europe/Amsterdam). Doe stap 2 t/m 5 voor elk van beide dagen: `python3 src/systeem.py kies --datum DATUM` (vult alleen ontbrekende posts aan).
3. Schrijf de teksten (zie hierboven) in `data/posts.json`.
4. `python3 src/systeem.py render --datum DATUM`. Bekijk minstens één gemaakt beeld met Read (bij video: haal een frame op 4 s met ffmpeg). Klopt er iets niet (tekst afgesneden, onleesbaar), zet de status van die post op "afgekeurd" en log het.
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

## Planning
`data/planning.json` is het voorlopige plan voor 7 dagen dat op het dashboard staat. `kies` volgt dat plan automatisch voor de gekozen datum (vers, formaat, stijl, tijd), zodat wat Joshua ziet ook gebeurt. Maak na elke wijziging de planning opnieuw: `python3 src/systeem.py plan` (kies doet dat zelf al).

## Avondcontrole (elke avond rond 21:00)
Doel: zorgen dat er voor MORGEN en OVERMORGEN precies zoveel posts klaarstaan als `posts_per_dag` in config.json (bijvoorbeeld omdat Joshua na de dagelijkse run iets via Bediening heeft veranderd).
1. Staat `pauze` op true: stop meteen, doe niets.
2. Staan er posts (van morgen of vandaag) met status "opnieuw_maken" of "wacht_op_tekst": maak die af (teksten schrijven waar nodig) en render ze met `python3 src/systeem.py render --datum DATUM`. Tel daarna voor MORGEN en voor OVERMORGEN de posts in `data/posts.json` met status "gerenderd" of "wacht_op_tekst". Is dat aantal gelijk aan of hoger dan `posts_per_dag`, en heeft geen enkele post status "wacht_op_tekst": meld alleen de gezondheid (zie "Gezondheid melden"), commit en push, en stop.
3. Anders, per dag waar iets ontbreekt: `python3 src/systeem.py kies --datum DATUM` (vult alleen de ontbrekende posts aan en volgt de planning), schrijf de teksten volgens "Teksten schrijven", en render met `python3 src/systeem.py render --datum DATUM`. Bekijk minstens één beeld. Log wat je deed met `python3 src/systeem.py log "Avondcontrole: ..."`, draai `python3 src/systeem.py dashboard`, commit en push.

## Gezondheid melden (voor de balk bovenaan het dashboard)
- Dagelijkse run: draai aan het eind `python3 src/systeem.py gezond dagelijks "N posts voor MORGEN en OVERMORGEN klaargezet"` en daarna `python3 src/systeem.py dashboard`, vóór de commit.
- Avondcontrole: draai ALTIJD `python3 src/systeem.py gezond avondcontrole "alles klopte"` (of "N posts aangevuld") en `python3 src/systeem.py dashboard`, en commit en push dat, ook als er niets aangevuld hoefde te worden. Dat is één kleine commit per avond.
- Wekelijkse run: `python3 src/systeem.py gezond wekelijks "analyse gedaan"`.
- Verzen bijvullen: bij 5 posts per dag raakt de voorraad sneller op (een vers mag 60 dagen niet terugkomen). Staat op het dashboard bij Voorraad "minder dan 21 dagen", voeg dan in de dagelijkse run 10 verzen toe zoals beschreven bij de wekelijkse run.

## Verzen uit de hele Bijbel
Het systeem kiest uit bekende verzen (`data/verzen.json`) en ontdekkingen uit de hele Statenvertaling (`data/bijbel_pool.json`). Het leert ook welk Bijbelboek (boekgroep), welke lengte en bekend of ontdekking het best werkt.
- Dagelijkse run en avondcontrole: lees na `kies` elk gekozen vers. Is het los van de context onduidelijk, negatief, geweld, oordeel over anderen, of klopt de verwijzing kennelijk niet bij de tekst: `python3 src/systeem.py vervang POST-ID "korte reden"`. Dan wordt het vers nooit meer gekozen en krijgt de post een ander vers met dezelfde kenmerken. Herhaal tot alle verzen goed zijn, en schrijf pas dan de teksten.
- Wekelijkse run: keur 80 kandidaten. `python3 src/systeem.py kandidaten 80` toont ze (id | verwijzing | thema | tekst). Goed is: losstaand begrijpelijk, bemoedigend, wijs of herkenbaar, en past bij een breed publiek. Draai `python3 src/systeem.py keur goed ID ID ...` en `python3 src/systeem.py keur af ID ID ...` (alle 80 beoordelen). Dit vervangt het toevoegen van 10 losse verzen.

## Goedkeuren en opnieuw maken
Joshua kan in het kantoor (📥 Goedkeuren) posts goedkeuren, een andere stijl kiezen, een ander vers kiezen of overslaan. Een andere stijl voor een afbeelding of carrousel wordt meteen in GitHub Actions opnieuw gemaakt. Video's en posts met foto-achtergrond krijgen status "opnieuw_maken", en een ander vers geeft status "wacht_op_tekst": die maak je ALTIJD af in zowel de dagelijkse run (14:32) als de avondcontrole (20:47), voor vandaag en morgen: teksten schrijven waar nodig en `python3 src/systeem.py render --datum DATUM`. Respecteer `goedkeuren` in config.json: verander die instelling nooit zelf.

## Formaat
Joshua wil geen losse afbeeldingen meer: een beeldpost is altijd een carrousel (vers, "Wat betekent dit?", "Vandaag"), dus altijd met `betekenis` en `toepassing`. Het systeem test alleen nog carrousel tegen video.

## Carrousels: doorlopende achtergrond (vaste regel)
Elke carrousel heeft één doorlopende achtergrond over de drie slides (render.py `_panorama`). Met een foto: slide 1 scherp, daarna zacht vervagend en rustiger. Verander dit nooit naar losse achtergronden per slide.

## Reserveverzen (voor "ander vers" in het kantoor)
Na het schrijven en renderen van de posts (dagelijkse run, en avondcontrole als er posts bij kwamen): `python3 src/systeem.py reserve --datum DATUM` (voor MORGEN en OVERMORGEN). Vul daarna in `data/posts.json` bij elke post onder `reserve` de velden hook, caption, hashtags en kernwoord, en bij carrousel betekenis en toepassing in, volgens dezelfde regels als de post zelf (caption begint met de hook en bevat het vers letterlijk en de verwijzing). Lees het reservevers ook na; past het los niet, haal de `reserve` dan weg en draai `reserve` opnieuw. Joshua kan dan in het kantoor met één klik naar het reservevers wisselen; het beeld wordt dan direct in GitHub gemaakt.

## Strategie (vaste regels sinds 8 november)
- **Kiezen gaat via Thompson sampling met een weekexperiment.** `config.json` › `experiment` zegt welke 2 onderdelen deze week bewust getest worden; het systeem kiest automatisch een nieuw experiment als het oude is verlopen (bij `plan`). Verander de keuzes van het systeem niet met de hand.
- **Facebook heeft een eigen tijdstip** (`variabelen.tijdslot_fb`), apart geleerd.
- **Vraag onderaan:** staat `vraag_onderaan` op true, eindig de caption met één oprechte, open vraag die bij het vers past (bijvoorbeeld "Welk woord raakt jou vandaag?"). Geen "typ amen", "tag iemand" of andere trucjes. Staat hij op false: geen vraag aan het eind.
- **Reeksen** (`data/reeksen.json`): Advent (29 nov t/m 24 dec, 07:30, label "ADVENT · DAG n"), Kerst (25-26 dec), Nieuwjaar (1 jan), elke maandag "Moed voor de week" (07:30) en elke zondag "Vers van de week" (12:15, het best scorende vers van de afgelopen week). Bij een reekspost noem je de reeks in de caption (bijvoorbeeld "Advent, dag 3:" of "Moed voor de week:") en schrijf je de uitleg in het licht van de reeks (Advent: verwachting en licht richting Kerst).
- **Stories:** elke post gaat automatisch ook als story op Instagram (`stories` in config).
- **Video's:** het vers verschijnt stukje voor stukje; de lengte past zich aan (9 tot 18 seconden). Niets aan te doen in de teksten.
- Na snel leren gaat het systeem terug naar **2 posts per dag**.

## Reacties (Community-manager)
`data/reacties.json` bevat reacties op de posts. Bij elke dagelijkse run en avondcontrole: schrijf voor elke reactie met status "nieuw" een antwoord in `voorstel` en zet de status op "voorgesteld". Joshua keurt het goed in het kantoor (Community-manager) en dan wordt het geplaatst.
- Kort (1 tot 2 zinnen), warm, persoonlijk, in het Nederlands, in de jij-vorm. Ga in op wat de persoon schrijft. Hooguit één emoji.
- Een gebedsverzoek of verdriet: meelevend, zonder preek ("Wat verdrietig, we bidden met je mee 🤍"). Bij signalen van acuut gevaar (zelfbeschadiging of zelfdoding): schrijf een rustig, zorgzaam antwoord dat verwijst naar 113 Zelfmoordpreventie (0800-0113, gratis) en zet in `notitie` "aandacht Joshua".
- Geen discussies over leerstellige kwesties, politiek of andere kerken; bij een kritische of trollende reactie: `voorstel` leeg, status "voorgesteld" en `notitie` "beter negeren".
- Geen engagement-bait, geen links, geen lange streep, niets beloven namens Joshua.
