# SteamFriendRanking

Flask/SQLite-Webapp, die Spielzeiten einer festen Steam-Freundesgruppe per Steam Web API snapshotted und als Wochen-/Monats-/Jahresleaderboard darstellt. Optional: automatisch generierte Instagram-Posts/-Stories mit Bildern und Captions.

## Features

- Periodische Snapshots der Spielzeiten via Steam Web API
- Leaderboards fuer Woche, Monat, Jahr und "ever"
- JSON-API fuer Rankings
- Optionaler Instagram-Autopost (Bild + Caption + Story) via `instagrapi`

## Setup

1. **Repository klonen**

   ```bash
   git clone https://github.com/<your-user>/SteamFriendRanking.git
   cd SteamFriendRanking
   ```

2. **Secrets anlegen** — `.steamsecrets.example` nach `~/.steamsecrets` kopieren und ausfuellen:

   ```bash
   cp .steamsecrets.example ~/.steamsecrets
   # anschliessend in einem Editor oeffnen
   ```

   - `STEAM_API_KEY` bekommst du unter https://steamcommunity.com/dev/apikey
   - `SNAPSHOT_TOKEN` ist ein beliebiger Random-String zum Absichern der API-Routen, z. B.:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(24))"
     ```
   - `INSTAGRAM_USER`/`INSTAGRAM_PASS` nur noetig, wenn du den Autopost benutzen willst.

3. **Spieler definieren** — `players.example.json` nach `players.json` kopieren und die gewuenschten SteamID64 eintragen:

   ```bash
   cp steam-leaderboard/players.example.json steam-leaderboard/players.json
   ```

   Eigene oder fremde SteamID64 findest du ueber https://steamid.io/ oder https://steamdb.info/calculator/.

4. **Dependencies installieren**

   ```bash
   pip install -r steam-leaderboard/requirements.txt
   ```

5. **Starten**

   ```bash
   cd steam-leaderboard
   python app.py
   ```

   Dev-Server laeuft unter http://127.0.0.1:5000.

## Routes

| Route | Zweck |
|-------|-------|
| `GET /` | Startseite |
| `GET /leaderboard?period=week\|month\|year\|ever` | Leaderboard anzeigen |
| `GET /api/rankings?period=...` | Rankings als JSON |
| `GET /api/snapshot?token=...` | Snapshot aller Spieler ausloesen (Token-Auth) |
| `GET /api/instagram/weekly?token=...` | Wochenpost ausloesen |
| `GET /api/instagram/monthly?token=...` | Monatspost ausloesen |
| `GET /api/instagram/yearly?token=...` | Jahrespost ausloesen |

Alle `token`-Parameter muessen mit `SNAPSHOT_TOKEN` uebereinstimmen.

## Deployment

Laeuft z. B. auf PythonAnywhere. Wichtige Env-Variablen (entweder in `~/.steamsecrets` oder in der WSGI-Config):

- `DB_PATH` — absoluter Pfad zur SQLite-Datei (Default: `steam-leaderboard/database/steam_leaderboard.db`)
- `PROJECT_DIR` — absoluter Projektpfad, falls `run_snapshot.py` aus einem Cronjob laeuft und das Skript nicht im Projektverzeichnis liegt

Die DB wird beim ersten Start automatisch angelegt (siehe `database/db.py` / `init_db`).

## Architektur

```
steam-leaderboard/
├── app.py            # Flask-App, alle HTTP-Routes
├── config.py         # Secrets + Steam-IDs + DB-Pfad laden
├── players.json      # (lokal, gitignored) eigene Steam-IDs
├── requirements.txt
├── database/
│   ├── db.py         # SQLite-Verbindung & Schema-Init
│   └── models.py
└── services/
    ├── steam_api.py      # Steam Web API Wrapper
    ├── snapshot.py       # Daten-Snapshot
    ├── rankings.py       # SQL-Queries fuer Rankings
    ├── instagram.py      # instagrapi-Client
    ├── instagram_jobs.py # Orchestrierung der IG-Posts
    ├── image_gen.py      # PIL-Bildgenerierung
    └── captions.py       # Caption-Texte
```

