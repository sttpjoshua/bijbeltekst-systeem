# Werkinstructies voor de geplande taken

> **Eerst na het clonen:** `sh tools/git_instellen.sh` en `python3 tools/media.py koppel` (beelden en video's staan in de aparte branch `media`; docs/media is daarvan een werkmap). Na het renderen, vóór je commit en pusht: `python3 tools/media.py bewaar`. (Door git_instellen worden JSON-bestanden per post samengevoegd bij `git pull --rebase`, zodat je geen wijzigingen van GitHub Actions of het dashboard overschrijft). Gebruik nooit `-X theirs` of `--force`.

Dit bestand is de handleiding voor Claude bij elke geplande run. Volg het letterlijk. Werk in de projectmap (de clone van de repo uit `config.json` > `github_repo`).

## Vaste regels (nooit overtreden)
- Staat `pauze` op `true` in `config.json`: doe niets behalve `python3 src/systeem.py log "Gepauzeerd, niets gedaan"`, commit, push, stop.
- Nooit iets posten via Metricool of op accounts van STTP Media of klanten. Posten gebeurt alleen via GitHub Actions met de geheimen van de repo.
- Nooit meer dan `max_posts_per_dag` posts per dag.
- Verstekst altijd letterlijk uit de post in `data/posts.json` (Statenvertaling uit `data/verzen.json`, of NBV21 uit `verzen_nbv21.csv` in de privé repo). Nooit een vers zelf typen, aanvullen of "verbeteren", en nooit NBV21-tekst uit je geheugen of van een website halen.
- Heeft een post `"vertaling": "NBV21"`, zet dan direct onder de referentie in de caption: `NBV21 © Nederlands-Vlaams Bijbelgenootschap` (Joshua heeft toestemming van het NBG). Laat bij NBV21-posts `uitleg_op_beeld` gewoon zoals gekozen.
- Geen lange streep (het teken U+2014) in captions of hooks.
- Geen engagement-bait ("typ amen", "deel met 10 mensen", "zegen als je...").
- Respectvol: geen spot met het geloof, politiek alleen neutraal en alleen met akkoord van Joshua (nooit een partij of standpunt), geen beloften over gezondheid of geld.
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
- `verhaal_hook`: alleen als `variabelen.opening` = verhaal ("verhaal eerst"). Slide 1 is dan geen vers maar de uitleg als haak: één of twee korte zinnen (25 tot 140 tekens) die de kern van de uitleg zo zeggen dat je wilt doorswipen naar het vers. Herkenbaar, concreet, geen vraag om likes. Bijvoorbeeld bij Spreuken 15:14: "Je hoofd wordt gevuld met wat je de hele dag binnenlaat. Wat laat jij binnen?" De volgorde wordt: deze zin, de stopper (stukje vers rond het kernwoord), het hele vers, Vandaag. De slide "Wat betekent dit?" vervalt, dus de `verhaal_hook` moet die rol overnemen. Vul `betekenis` wel gewoon in.
- `betekenis` en `toepassing`: bij `variabelen.formaat` = carrousel (3 slides) én bij elke video (vaste regel: reels hebben altijd uitleg) (dan verschijnen ze na het vers als "Wat betekent dit?" en "Vandaag"; de laatste regel van de caption, de vraag, komt onder de toepassing). `betekenis`: 2 tot 3 korte zinnen over wat het vers betekent, eenvoudig en trouw aan de tekst (20 tot 320 tekens). `toepassing`: 1 tot 2 zinnen met een concrete, kleine stap voor vandaag (20 tot 320 tekens). Geen preek, geen dwang.
- `hashtags`: 3 tot 5, Nederlands, bv. `#bijbeltekst #geloof #bemoediging #god #jezus`. Wissel af.
Schrijf in het Nederlands, warm en eenvoudig, nooit prekerig. Elke hook anders dan die van de afgelopen 14 dagen (kijk in `data/posts.json`).

## Zelfherstel (eerste stap van de dagelijkse run en de avondcontrole)
Het systeem lost bekende problemen zelf op (GitHub Actions, elk kwartier): posts die niet doorkomen bij Meta worden tot 3 keer opnieuw geprobeerd, er wordt gewacht als een beeld nog niet online staat, video's zonder muziek krijgen alsnog muziek, en lege tijdsloten van vandaag worden gevuld uit de noodvoorraad (`data/noodvoorraad.json`). Alles wat zo is opgelost staat in `data/herstel.json`. Jouw taak, vóór het gewone werk:
1. Lees in `data/logboek.json` de fouten (soort "fout") die nog niet `opgelost` zijn. Zoek per fout de oorzaak en los die echt op (code, data of planning), test het, en log in gewone taal wat je deed: `python3 src/systeem.py log "Zelf opgelost: ..."`. Daarna `python3 src/systeem.py opgelost`.
   Kan het alleen door Joshua worden opgelost (een recht in Meta, een sleutel, een betaling): log één fout die begint met "ACTIE VOOR JOU:" met precies wat hij moet doen en waar, in gewone taal. Markeer die niet als opgelost.
2. Kijk in `data/herstel.json` of hetzelfde probleem vaker dan twee keer in een week voorkwam. Zo ja: zoek de structurele oorzaak en verhelp die.
3. Noodvoorraad: `python3 src/systeem.py nood status`. Minder dan 6 klaar: `python3 src/systeem.py nood aanvullen`, schrijf voor de nieuwe posts in `data/noodvoorraad.json` hook, caption (eindigt met een vraag), hashtags, kernwoord, betekenis en toepassing volgens "Teksten schrijven" (tijdloos, geen datum of seizoen), en `python3 src/systeem.py nood render`. Bekijk één beeld met Read.

## Verzoeken uit het dashboard ("Vraag Claude")
Joshua stelt vragen en geeft opdrachten via het dashboard; die staan in `data/verzoeken.json`. Bij ELKE run (dagelijks, avondcontrole, wekelijks), direct na Zelfherstel:
1. `python3 src/systeem.py verzoek` toont de open verzoeken.
2. Per verzoek: `python3 src/systeem.py verzoek ID bezig`, voer het uit (binnen de vaste regels), en sluit af met `python3 src/systeem.py verzoek ID klaar "kort antwoord in gewone taal, wat je deed of waarom het niet kan"`. Kan het niet zonder Joshua: zet het op klaar met precies wat hij moet doen.
3. Verzoek met `"soort": "overleg"` (de knop "Team nu bij elkaar roepen" in de vergaderruimte van het kantoor): maak een tussentijdse analyse. Kijk naar de cijfers sinds de start of het laatste overleg (wat werkt, wat niet, wat valt op) en wees eerlijk over te weinig metingen. Leg 3 tot 6 korte punten vast in gewone taal, waarvan minstens één voorstel: `python3 src/systeem.py overleg "punt 1" "punt 2" "Voorstel: ..."`. Ze verschijnen op het whiteboard. Voer een voorstel niet zelf uit als het iets wezenlijks verandert: zet het als voorstel neer, Joshua beslist. Sluit het verzoek af met een samenvatting van één zin.
4. Een verzoek dat de vaste regels zou breken (bijvoorbeeld een auteursrechtelijk beschermde vertaling overnemen): niet uitvoeren, wel uitleggen in het antwoord.

## Dashboard als centraal punt (vaste regel)
Joshua bestuurt en controleert alles vanuit het dashboard. Bij elke nieuwe functie of wijziging: zorg dat hij het in het dashboard kan zien én bedienen (een knop via `src/bediening.py`, of een melding met de juiste knoppen). Elke nieuwe fout krijgt een `code` in `cmd_log` met bijpassende knoppen in `docs/index.html` (ACTIES). Verwijs nooit naar "plak het in de chat": verwijs naar de knop, of naar "Vraag Claude" in het dashboard.

## Tekstbank en zelfstandig maken (sinds 11 november)
Staat `zelfstandig` op true in `config.json`, dan maakt het systeem zelf de posts, zonder Claude: `.github/workflows/maken.yml` (`systeem.py automaak`) kiest elke ochtend de posts voor morgen en overmorgen, vult de teksten in uit `data/tekstbank.json` en rendert ze. Claude hoeft dan geen posts meer te kiezen of te schrijven. Jouw taak is de tekstbank op peil houden.
- `python3 src/systeem.py tekstbank` laat zien hoeveel verzen er nog vrij zijn. Minder dan 30 dagen: vul aan (60 verzen per keer). Ook bij een verzoek "Vul de tekstbank aan".
- Kies verzen die nog niet in de bank of in `data/posts.json` staan, verdeeld over alle thema's, uit `alle_verzen()` (Statenvertaling; nooit NBV21 uit je hoofd). Sla verzen over die los van de context niet goed te begrijpen zijn.
- Per vers (sleutel = vers_id): `ref`, `kw` (kernwoord, letterlijk uit het vers), `uitleg` (max 110), `betekenis` en `toepassing` (20 tot 320), `verhaal` (openingszin voor 'verhaal eerst', 25 tot 140), `zin` (één korte zin voor in de caption), `vraag` (één oprechte, open vraag), `hooks` met alle vier de stijlen `vraag`, `herkenning`, `uitdaging`, `rustig`, en `tags` (3 tot 5). Zelfde schrijfregels als bij "Teksten schrijven". Elke hook uniek in de bank.
- Daarna `python3 src/systeem.py tekstbank check` (moet zonder problemen zijn), commit en push.
- Reeksen: de reeksnaam wordt automatisch voor de hook gezet ("Advent, dag 3: ..."). Voor Advent (29 nov t/m 24 dec) mag je voor de reeksverzen een eigen item maken met uitleg in het licht van Advent.

## Nieuws als aanleiding (sinds 11 november)
`src/nieuws.py` kijkt rond 7, 12 en 17 uur naar NOS en NU.nl. Licht nieuws (weer, Sinterklaas, sport, drukte, examens, klok, koopjes) wordt vanzelf een post: de eerstvolgende carrousel krijgt een vers uit de tekstbank met een passend thema, opening 'verhaal' en een openingszin uit `LICHT` in nieuws.py. Zwaar nieuws (rampen, aanslagen) is altijd een voorstel voor Joshua (dashboard en WhatsApp), en gaat pas 6 uur na het nieuws online. Politiek (sinds 11 nov): ook alleen als voorstel, maximaal 1 per dag, en alleen online met Joshua's akkoord; altijd neutraal, nooit een partij, politicus of standpunt. Maximaal 2 per dag (`config.json` › `nieuws`). In de post zelf komt nooit nieuwstekst of een kop (NOS-voorwaarden: koppen alleen met bronvermelding, niet-commercieel). Bij elk voorstel maakt het systeem 3 opties (ander vers en andere openingszin) met voorvertoning in docs/media/nieuws/; Joshua kiest er één in het dashboard en kan de openingszin aanpassen. Wil je nieuwe soorten aanleidingen toevoegen: alleen in `LICHT`, met woorden, thema's en 2 of 3 openingszinnen die ook los van het nieuws kloppen.

## Wat zonder Claude draait (sinds 11 november)
Posten, posts maken (maken.yml), noodvoorraad aanvullen uit de tekstbank (`systeem.py nood auto`, in maken.yml), leren (elke dag tijdens snel leren, daarna elke maandag in de statistiekenrun), nieuws, statistieken, zelftest en meldingen (Telegram). Claude is alleen nog nodig voor: de tekstbank aanvullen, verzoeken uit het dashboard, persoonlijke reactie-opties en nieuwe functies.

## Dagelijkse run
**Staat `zelfstandig` aan, dan sla je stap 2 t/m 4 over** (het systeem maakt de posts zelf) en doe je alleen: zelfherstel, verzoeken, reacties, de tekstbank controleren en zo nodig aanvullen, en controleren of de posts van morgen goed zijn gemaakt (bekijk er één met Read).
Het online zetten zelf doet GitHub Actions (`.github/workflows/publiceren.yml`, elk kwartier) en het ophalen van statistieken ook (dagelijks). Deze run maakt de posts van MORGEN én OVERMORGEN klaar (twee dagen buffer: als een run een keer mislukt, staat er toch genoeg klaar). Voor MORGEN zijn de meeste posts meestal al gemaakt; vul alleen aan wat ontbreekt.
1. `git pull --rebase`. Lees `config.json`. Pauze? Zie regels. Doe daarna eerst "Zelfherstel" en dan "Verzoeken uit het dashboard".
   Clone ook de privé repo `sttpjoshua/bibleverse-materiaal` (add_repo, alleen lezen) naast deze repo, dus als map `../bibleverse-materiaal`. Daar staan Joshua's muziek (Epidemic Sound) en foto's. Zet die bestanden NOOIT in deze openbare repo; alleen de afgewerkte post mag hier komen. Lukt het clonen niet (bijvoorbeeld omdat add_repo in deze sessie ontbreekt), ga dan gewoon door: het systeem gebruikt dan kleurverloop en maakt video's zonder muziek. GitHub Actions vult de muziek binnen een kwartier automatisch aan (`systeem.py aanvullen`, met het geheim MATERIAAL_PAT). Log dit dus als "info", NIET als fout, en meld het niet als probleem aan Joshua.
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
1. Staat `pauze` op true: stop meteen, doe niets. Anders: doe eerst "Zelfherstel" en "Verzoeken uit het dashboard".
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

## Reels (vaste regel)
Elke reel heeft uitleg: vers frase voor frase, dan "Wat betekent dit?" en "Vandaag" met voortgangsbalkje, omslag op het volle vers, naadloze loop, oplichtend kernwoord en overgangen op de muziek. Dus bij elke video `betekenis` en `toepassing` schrijven.

Nieuwe reelstijlen (src/reels.py, sinds 11 november, aan/uit met `nieuwe_reels` in config en op het dashboard): `kinetisch` (woord voor woord op de tel, kernwoord alleen en groot, daarna "Betekent:" met de `uitleg`), `beeld` (foto's met snelle zoom en harde cuts) en `reel_haak` = vraag (eerst 1,4 s de vraag-hook). Ook deze stijlen hebben uitleg (de korte `uitleg`), dus de vaste regel blijft gelden.

Reel "herkenbare situatie" (standaard sinds 11 november, Joshua akkoord; `reel_formaat` = situatie in config): clip 1 is een echt videobeeld (Coverr) dat past bij `reel_herkenning` (de herkenningshook uit de tekstbank), dan het hele vers op een rustig beeld (`reel_scene`: natuur, dichtbij of onderweg), dan "WAT BETEKENT DIT?" met de `uitleg`, dan het eindbeeld. Tekst staat `midden` of `boven` (`reel_plaatsing`, wordt getest). De clips kiest src/clips.py op relevantie (woorden in titel en tags, zie KOPPEL; geen dieren, hotels of productbeelden); past niets, dan een sfeerbeeld. Clips staan buiten de repo (../bibleverse-clips) en komen nooit in de publieke repo; zoekresultaten worden een week bewaard in data/clips_zoek.json (gratis Coverr: 50 verzoeken per uur). Lukt het niet, dan wordt het een klassieke reel. Aandeel reels: `reel_aandeel` (0,6 = ongeveer 60%, bijgestuurd op de laatste 14 dagen). Geen voice-over, geen hooktekst behalve de herkenningszin.

## Kernwoord: dikker en in kleur, nooit een vakje (vaste regel)
Het kernwoord wordt uitgelicht door het dikker te zetten in een opvallende kleur (zie `_kernstaat` en `_regel` in src/render.py). Nooit een vakje, balk of label eromheen: dat vindt Joshua niet mooi.

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
`data/reacties.json` bevat reacties op de posts. Bij elke dagelijkse run en avondcontrole: schrijf voor elke reactie met status "nieuw" drie antwoordopties op maat in `opties` (een lijst van 3: warm en persoonlijk, kort, en een met een korte bemoediging of verwijzing naar het vers), zet de beste ook in `voorstel` en zet de status op "voorgesteld". Bij een reactie die beter genegeerd kan worden: `opties` leeg. Joshua kiest of past aan in het dashboard (Overzicht › Reacties) of in het kantoor (Community-manager), en dan wordt het geplaatst.
- Kort (1 tot 2 zinnen), warm, persoonlijk, in het Nederlands, in de jij-vorm. Ga in op wat de persoon schrijft. Hooguit één emoji.
- Een gebedsverzoek of verdriet: meelevend, zonder preek ("Wat verdrietig, we bidden met je mee 🤍"). Bij signalen van acuut gevaar (zelfbeschadiging of zelfdoding): schrijf een rustig, zorgzaam antwoord dat verwijst naar 113 Zelfmoordpreventie (0800-0113, gratis) en zet in `notitie` "aandacht Joshua".
- Geen discussies over leerstellige kwesties, politiek of andere kerken; bij een kritische of trollende reactie: `voorstel` leeg, status "voorgesteld" en `notitie` "beter negeren".
- Geen engagement-bait, geen links, geen lange streep, niets beloven namens Joshua.


## Dashboard (11 november, na de reel-update)
- Overzicht: bovenaan "Vandaag" (status, posts van vandaag met tijd en staat), daaronder "Wat moet ik doen?" met nieuwsvoorstellen, reacties, fouten, lege noodvoorraad en lage tekstbank in één lijst. Afgehandelde verzoeken van Claude verdwijnen met "Gelezen" (onthouden in de browser).
- Resultaten: "Deze week" met verschil t.o.v. vorige week, "Wat werkt beter?" (gemiddeld bereik per optie: reel of carrousel, tekst midden of boven, rustbeeld, eerste slide, achtergrond, met zekerheidslabel) en een maandrapport dat je kunt afdrukken of als PDF opslaan.
- Beheer: blok "Tekstbank" (zoeken, filter, vers uit- of aanzetten, herkenningszin aanpassen). Acties `tekstbank_vers` en `tekstbank_hook` in src/bediening.py; uitzetten gebruikt `verzen_uitsluiten`. Een aangepaste herkenningszin geldt voor reels die nog gemaakt worden.
- Telefoon: tabbalk onderaan met iconen en compactere kaarten.

- Hashtags worden getest (11 november, Joshua koos meetesten): dimensie `hashtag_stijl` = `mix` (vaste tags uit de tekstbank, bijna altijd met #bijbeltekst), `zoekwoord` (#bijbelvers, het thema en het bijbelboek) of `zonder`. Het systeem leert welke stijl beter scoort; zie "Wat werkt beter?" op het dashboard. Hashtags zijn volgens Instagram geen bereikmiddel maar context voor zoeken; maximaal 5 per post. `python3 src/systeem.py hashtags_testen` verdeelt geplande posts over de drie stijlen.

## Ochtendposts (12 nov)
Het 07:30-slot is de ochtendpost (Joshua): altijd een vers voor een goede start van de dag (`OCHTEND_VERZEN` in src/tekstbank.py), caption opent met een wisselende Goedemorgen-regel (`OCHTEND_OPENERS`, ook als herkenningsregel in de reel), reels openen met ochtendbeeld (eerste regel in `clips.KOPPEL`), carrousels krijgen een lichte stijl (`LICHTE_STIJLEN`). Andere tijdsloten sparen de ochtendverzen. `python3 src/systeem.py ochtend_vernieuwen` maakt geplande ochtendposts vanaf morgen opnieuw.

## Meelees-reel (12 nov, stijl "markeren")
Reelstijl `markeren` (reels.maak_markeren): lichte ochtendkleur, vers donker op de pagina, beige markeerstreep per regel die op leestempo meeloopt (ongeveer 2 woorden per seconde), kernwoord in kleur, uitleg, eindbeeld; geen echte video nodig. Bewust eigen stijl, niet de papier-met-stift-look van het voorbeeld. Test naast de situatie-reel: `markeer_aandeel` in config.json (standaard 0.25). Het systeem leert via de dimensie reel_stijl.
Ochtendreels (12 nov): begint meteen met het vers, geen groet in beeld (die staat in de caption); ochtendreels is altijd de meelees-reel. Varianten via dimensie `reel_kleur` (abrikoos, mint, hemel, roze, goud; `reels.LOOKS`, elk met eigen lettertype); het systeem leert welke het best werkt.
Correctie (12 nov): de meelees-reel is gewoon een variatie tussen alle reelstijlen, niet specifiek voor de ochtend. Ochtendreels kiezen dus uit alle stijlen; alleen de caption begint met de groet. `python3 src/systeem.py markeren_inplannen <id>:<kleur>` zet geplande reels om (kleur 'situatie' = terug).
Carrousel in de meelees-stijl (12 nov): dimensie `carrousel_stijl` (standaard | markeren), renderer `reels.maak_carrousel_markeren` (doorlopende lichte achtergrond, markeerstreep onder elke regel, kernwoord in kleur, uitleg- en vandaag-slide), kleur/lettertype via `reel_kleur`. Het systeem leert of het beter werkt. Ingepland: 14 nov 12:15 en 15 nov 07:30.

## Leersysteem aangescherpt (12 nov)
- Score per onderdeel: tijdslot, weekdag, hook, formaat, stijlen en kleuren leren vooral van bereik; thema, boek, lengte, bekend/ontdekking, vraag onderaan en uitleg vooral van interactie (src/systeem.py: DOEL_BEREIK, DOEL_INTERACTIE).
- Eerlijker vergelijken: de score wordt gecorrigeerd voor tijdslot en weekdag (gedempt, begrensd op 0,7 tot 1,4).
- Zekerheid: een optie telt pas mee bij `min_metingen_optie` (5) metingen; `oordeel()` geeft weinig data / waarschijnlijk beter / slechter / geen duidelijk verschil; opgeslagen in strategie.json `zekerheid` en getoond bij Inzichten.
- Strikter experiment: `experiment_aantal` (1) onderdeel per week; bij `strikt_experiment` staan hook_stijl, uitleg_op_beeld, achtergrondbron, vraag_onderaan, reel_haak, opening en hashtag_stijl dan bijna vast op wat werkt. Stijl, kleur en thema blijven afwisselen. Tijdens snel leren blijft alles breed.
- Eerste-uurmeting (`1u`): `vroege_cijfers` in publiceer.py, elke 15 minuten, 60 tot 180 minuten na plaatsing. Telt voor de helft mee en wordt apart vergeleken.
- Nieuwe tijdsloten: `cmd_tijd_voorstel` (bij elk nieuw weekexperiment, maximaal om de 14 dagen): scoren twee naastliggende slots boven gemiddeld (min. 4 metingen), dan komt de tijd ertussen als extra slot in config `extra_tijdsloten`. Slecht scorend extra slot (6 metingen, onder 0,9) verdwijnt weer.
