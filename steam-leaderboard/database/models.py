CREATE_PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    steam_id    TEXT    NOT NULL UNIQUE,
    display_name TEXT,
    avatar_url  TEXT,
    game_count  INTEGER DEFAULT 0,
    last_updated TEXT
)
"""

CREATE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id        INTEGER NOT NULL REFERENCES players(id),
    timestamp        TEXT    NOT NULL,
    game_id          INTEGER NOT NULL,
    game_name        TEXT,
    playtime_minutes INTEGER DEFAULT 0,
    last_played      INTEGER DEFAULT 0
)
"""

CREATE_PLAYER_STATS = """
CREATE TABLE IF NOT EXISTS player_stats (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id          INTEGER NOT NULL REFERENCES players(id),
    date               TEXT    NOT NULL,
    total_hours_week   REAL    DEFAULT 0,
    total_hours_month  REAL    DEFAULT 0
)
"""

ALL_TABLES = [CREATE_PLAYERS, CREATE_SNAPSHOTS, CREATE_PLAYER_STATS]
