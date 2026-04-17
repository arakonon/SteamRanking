"""
Caption-Generierung für Instagram Posts und Stories.

SPLASH_TEXTS: Hier neue Texte hinzufügen.
Platzhalter {player} wird durch den Erstplatzierten ersetzt.
"""
import random
from datetime import datetime

from services.rankings import get_total_playtime_ranking

# ---------------------------------------------------------------------------
# Splash-Texte – einfach ergänzen
# ---------------------------------------------------------------------------
SPLASH_TEXTS = [
    "{player} priorisiert das Wichtige im Leben",
    "{player} weiß wie man Freizeit verbringt",
    "{player} hat kein Leben",
    "{player} hat die Kontrolle verloren",
    "{player} kennt keine Natur",
    "{player} ist der Gamemaster",
    "{player} hat wieder zugeschlagen",
    "{player}, geht es dir Gut",
    "{player}, Eat-Spiel-Sleep Repeat",
    "{player}, hat die Work-Gaming-Balance",
    "{player} needs to toch grass",
    "{player} lässt alle hinter sich?",
    "{player} hat keine Freunde",
    "{player} ist verantwortlicher für 9/11",
    "{player} hat schon Heroin genommen",
    "{player} muss koks ziehen",
    "Merz leck eier",
    "{player} leck eier",
    "{player} du fette sau",
]


def _first_place_player(days):
    rows = get_total_playtime_ranking(days)
    if rows:
        return rows[0].get("player", "Unbekannt")
    return "Unbekannt"


def build_caption(days, period="weekly"):
    """
    Gibt die Post-Caption zurück.
    Format: KW XX\n<Splash-Text> (weekly/monthly)
            Jahresrückblick YYYY\n<Splash-Text> (yearly)
    """
    player = _first_place_player(days)
    splash = random.choice(SPLASH_TEXTS).format(player=player)
    if period == "yearly":
        year = datetime.now().year
        return f"Jahresrückblick {year}\n{splash}"
    kw = datetime.now().isocalendar()[1]
    return f"KW {kw:02d}\n{splash}"


def build_story_text(days):
    """
    Gibt kompakten Overlay-Text für den Story-Sticker zurück.
    Format: <Splash-Text>
    """
    player = _first_place_player(days)
    return random.choice(SPLASH_TEXTS).format(player=player)
