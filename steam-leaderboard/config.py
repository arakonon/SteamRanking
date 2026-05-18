import json
import logging
import os


def _load_secrets(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass


_load_secrets(os.path.expanduser("~/.steamsecrets"))


def _load_steam_ids():
    path = os.path.join(os.path.dirname(__file__), "players.json")
    try:
        with open(path) as f:
            data = json.load(f)
        return list(data.get("steam_ids", []))
    except FileNotFoundError:
        logging.warning(
            "players.json nicht gefunden (%s). Lege eine Datei nach dem Vorbild "
            "von players.example.json an. STEAM_IDS ist vorerst leer.",
            path,
        )
        return []


STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")
STEAM_IDS = _load_steam_ids()

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "database", "steam_leaderboard.db"),
)
BASE_URL = "https://api.steampowered.com"

INSTAGRAM_USER = os.environ.get("INSTAGRAM_USER", "")
INSTAGRAM_PASS = os.environ.get("INSTAGRAM_PASS", "")

# Steam App-IDs, die komplett ignoriert werden (kein Tracking, kein Ranking)
EXCLUDED_APP_IDS = (3419430, 431960)  # Bongo Cat, WallpaperEngine
