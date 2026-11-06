# Bijbeltekst-systeem

Post automatisch inspirerende Bijbelteksten (Statenvertaling, publiek domein) als afbeelding of korte video via Metricool, en leert elke week van de statistieken welke kleuren, lettertypes, thema's, hooks, formaten en tijdstippen het beste werken.

- **Dashboard:** GitHub Pages vanuit de map `docs/`.
- **Noodstop:** zet `"pauze": true` in `config.json` (bewerken op GitHub en opslaan). De volgende run doet dan niets.
- **Hoe het werkt:** zie `TAKEN.md`. Dagelijks plant een geplande taak de posts voor morgen; elke maandag analyseert een taak de resultaten en past `strategie.json` aan.
- **Leren:** 80% van de keuzes volgt de best scorende opties, 20% probeert iets anders (`verkenning`). Gewichten veranderen maximaal 0,15 per week, zodat één toevalstreffer de strategie niet omgooit.

Bronnen: tekst Statenvertaling via scrollmapper/bible_databases (publiek domein). Lettertypes: Google Fonts (Open Font License).
