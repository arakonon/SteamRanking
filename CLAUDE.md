# SteamFriendRanking

Flask/SQLite-Webapp das Spielzeiten einer konfigurierbaren Steam-Freundesgruppe trackt und als Leaderboard darstellt. Zusätzlich werden automatisch Instagram-Posts mit generierten Bildern und Captions erstellt.

## Architektur

```
steam-leaderboard/
├── app.py            # Flask-App, alle HTTP-Routes
├── config.py         # Secrets laden (.steamsecrets), Steam-IDs, DB-Pfad
├── players.json      # (gitignored) Liste der zu trackenden SteamID64
├── players.example.json # Vorlage im Repo
├── requirements.txt  # Flask, requests, Pillow, instagrapi
├── database/
│   ├── db.py         # SQLite-Verbindung & Schema-Init
│   └── models.py     # CREATE TABLE Statements
└── services/
    ├── steam_api.py      # Steam Web API Wrapper
    ├── snapshot.py       # Daten-Snapshot (Spielzeiten abrufen & speichern)
    ├── rankings.py       # SQL-Queries für Wochen-/Monats-Rankings
    ├── instagram.py      # instagrapi-Client (Login, Session-Cache)
    ├── instagram_jobs.py # Orchestrierung: wöchentlicher/monatlicher Post
    ├── image_gen.py      # PIL-Bildgenerierung für Instagram
    └── captions.py       # Deutschen Caption-Text generieren
```

## Datenbank (SQLite)

3 Tabellen: `players`, `snapshots`, `player_stats`  
Pfad: `steam-leaderboard/database/steam_leaderboard.db` (in `.gitignore`)

## Routes

| Route | Zweck |
|-------|-------|
| `GET /` | Startseite |
| `GET /leaderboard?period=week\|month` | Leaderboard anzeigen |
| `GET /api/snapshot?token=...` | Snapshot auslösen (Token-Auth) |
| `GET /api/instagram/weekly?token=...` | Wöchentlichen Instagram-Post auslösen |
| `GET /api/instagram/monthly?token=...` | Monatlichen Instagram-Post auslösen |
| `GET /api/rankings?period=...` | Rankings als JSON |

## Konfiguration

Secrets werden aus `~/.steamsecrets` geladen (key=value Format). Vorlage: `.steamsecrets.example` im Repo-Root.
- `STEAM_API_KEY`
- `INSTAGRAM_USER` / `INSTAGRAM_PASS`
- `SNAPSHOT_TOKEN` (API-Auth)
- `DB_PATH` (optional, absoluter Pfad)
- `PROJECT_DIR` (optional, fuer `run_snapshot.py` aus Cronjobs)

Steam-IDs werden aus `steam-leaderboard/players.json` geladen (gitignored). Vorlage: `players.example.json`.

## Deployment

Ziel: PythonAnywhere. DB-Pfad wird ueber die Env-Var `DB_PATH` gesetzt (Fallback: lokaler Pfad in `steam-leaderboard/database/`).
