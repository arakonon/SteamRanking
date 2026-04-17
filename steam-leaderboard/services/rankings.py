from datetime import datetime, timedelta, timezone
from database.db import get_connection


def _window_start(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def get_total_playtime_ranking(days):
    """Gesamte Spielzeit pro Spieler.
    days=None → kumulativ (neuester Snapshot), sonst Zunahme im Zeitfenster."""
    if days is None:
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                p.avatar_url,
                COALESCE(SUM(latest.playtime_minutes), 0) AS total_minutes_gained
            FROM players p
            LEFT JOIN (
                SELECT player_id, game_id, MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                GROUP BY player_id, game_id
            ) latest ON latest.player_id = p.id
            GROUP BY p.id
            ORDER BY total_minutes_gained DESC, p.display_name ASC
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
    else:
        since = _window_start(days)
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                p.avatar_url,
                SUM(newest.playtime_minutes - oldest.playtime_minutes) AS total_minutes_gained
            FROM players p
            JOIN (
                SELECT player_id, game_id,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) newest ON newest.player_id = p.id
            JOIN (
                SELECT player_id, game_id,
                       MIN(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) oldest ON oldest.player_id = newest.player_id
                     AND oldest.game_id  = newest.game_id
            GROUP BY p.id
            HAVING total_minutes_gained > 0
            ORDER BY total_minutes_gained DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since, since)).fetchall()
    return [dict(r) for r in rows]


def get_most_played_game_overall(days):
    """Das Spiel mit der meisten Spielzeit über alle Spieler.
    days=None → kumulativ, sonst Zunahme im Zeitfenster."""
    if days is None:
        query = """
            SELECT
                sub.game_name,
                SUM(sub.playtime_minutes) AS total_minutes,
                COUNT(DISTINCT sub.player_id) AS player_count
            FROM (
                SELECT player_id, game_id, game_name,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                GROUP BY player_id, game_id
            ) sub
            WHERE sub.playtime_minutes > 0
            GROUP BY sub.game_name
            ORDER BY total_minutes DESC
            LIMIT 10
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
    else:
        since = _window_start(days)
        query = """
            SELECT
                newest.game_name,
                SUM(newest.playtime_minutes - oldest.playtime_minutes) AS total_minutes,
                COUNT(DISTINCT newest.player_id) AS player_count
            FROM (
                SELECT player_id, game_id, game_name,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) newest
            JOIN (
                SELECT player_id, game_id,
                       MIN(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) oldest ON oldest.player_id = newest.player_id
                     AND oldest.game_id  = newest.game_id
            WHERE newest.playtime_minutes - oldest.playtime_minutes > 0
            GROUP BY newest.game_name
            ORDER BY total_minutes DESC
            LIMIT 10
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since, since)).fetchall()
    return [dict(r) for r in rows]


def get_most_played_game_per_player(days):
    """Pro Spieler das Spiel mit der meisten Spielzeit.
    days=None → kumulativ (neuester Snapshot), sonst Zunahme im Zeitfenster."""
    if days is None:
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                sub.game_name,
                sub.playtime_minutes AS minutes
            FROM players p
            JOIN (
                SELECT player_id, game_id, game_name,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                GROUP BY player_id, game_id
            ) sub ON sub.player_id = p.id
            WHERE sub.playtime_minutes > 0
              AND sub.playtime_minutes = (
                SELECT MAX(s2.playtime_minutes)
                FROM snapshots s2
                WHERE s2.player_id = p.id
                  AND s2.playtime_minutes > 0
            )
            ORDER BY sub.playtime_minutes DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
    else:
        since = _window_start(days)
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                sub.game_name,
                sub.minutes AS minutes
            FROM players p
            JOIN (
                SELECT
                    newest.player_id,
                    newest.game_name,
                    (newest.playtime_minutes - oldest.playtime_minutes) AS minutes
                FROM (
                    SELECT player_id, game_id, game_name,
                           MAX(playtime_minutes) AS playtime_minutes
                    FROM snapshots
                    WHERE timestamp >= ?
                    GROUP BY player_id, game_id
                ) newest
                JOIN (
                    SELECT player_id, game_id,
                           MIN(playtime_minutes) AS playtime_minutes
                    FROM snapshots
                    WHERE timestamp >= ?
                    GROUP BY player_id, game_id
                ) oldest ON oldest.player_id = newest.player_id
                         AND oldest.game_id  = newest.game_id
                WHERE newest.playtime_minutes - oldest.playtime_minutes > 0
            ) sub ON sub.player_id = p.id
            WHERE sub.minutes = (
                SELECT MAX(inner_sub.minutes)
                FROM (
                    SELECT
                        newest2.player_id,
                        (newest2.playtime_minutes - oldest2.playtime_minutes) AS minutes
                    FROM (
                        SELECT player_id, game_id,
                               MAX(playtime_minutes) AS playtime_minutes
                        FROM snapshots
                        WHERE timestamp >= ?
                        GROUP BY player_id, game_id
                    ) newest2
                    JOIN (
                        SELECT player_id, game_id,
                               MIN(playtime_minutes) AS playtime_minutes
                        FROM snapshots
                        WHERE timestamp >= ?
                        GROUP BY player_id, game_id
                    ) oldest2 ON oldest2.player_id = newest2.player_id
                              AND oldest2.game_id  = newest2.game_id
                ) inner_sub
                WHERE inner_sub.player_id = p.id
            )
            ORDER BY sub.minutes DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since, since, since, since)).fetchall()
    return [dict(r) for r in rows]


def get_player_with_most_games():
    """Spieler-Rangliste nach Gesamtanzahl Spiele in der Bibliothek (game_count)."""
    query = """
        SELECT display_name AS player, steam_id, avatar_url, game_count
        FROM players
        ORDER BY game_count DESC
    """
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


def get_recently_played(days):
    """Spiele, die im Zeitfenster gespielt wurden (last_played-Timestamp >= Fensterstart),
    dedupliziert pro Spieler + Spiel.
    days=None → alle je gespielten Spiele (last_played > 0), neueste zuerst."""
    if days is None:
        query = """
            SELECT DISTINCT
                p.display_name AS player,
                p.steam_id,
                s.game_name,
                s.game_id,
                MAX(s.last_played) AS last_played_ts
            FROM snapshots s
            JOIN players p ON p.id = s.player_id
            WHERE s.last_played > 0
            GROUP BY s.player_id, s.game_id
            ORDER BY last_played_ts DESC
            LIMIT 100
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
    else:
        since_ts = int(
            (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
        )
        query = """
            SELECT DISTINCT
                p.display_name AS player,
                p.steam_id,
                s.game_name,
                s.game_id,
                MAX(s.last_played) AS last_played_ts
            FROM snapshots s
            JOIN players p ON p.id = s.player_id
            WHERE s.last_played >= ?
            GROUP BY s.player_id, s.game_id
            ORDER BY last_played_ts DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since_ts,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d["last_played_ts"]:
            d["last_played_str"] = datetime.fromtimestamp(
                d["last_played_ts"], tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M")
        else:
            d["last_played_str"] = "—"
        result.append(d)
    return result


def get_avg_playtime_per_game(days):
    """Durchschnittliche Spielzeit pro gespieltem Spiel je Spieler.
    days=None → kumulativ (neuester Snapshot), sonst Zunahme im Zeitfenster."""
    if days is None:
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                ROUND(
                    CAST(SUM(latest.playtime_minutes) AS REAL) / COUNT(*),
                    1
                ) AS avg_minutes_per_game,
                COUNT(*) AS games_played
            FROM players p
            JOIN (
                SELECT player_id, game_id, MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                GROUP BY player_id, game_id
            ) latest ON latest.player_id = p.id
            WHERE latest.playtime_minutes > 0
            GROUP BY p.id
            ORDER BY avg_minutes_per_game DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
    else:
        since = _window_start(days)
        query = """
            SELECT
                p.display_name AS player,
                p.steam_id,
                ROUND(
                    CAST(SUM(newest.playtime_minutes - oldest.playtime_minutes) AS REAL)
                    / COUNT(*),
                    1
                ) AS avg_minutes_per_game,
                COUNT(*) AS games_played
            FROM players p
            JOIN (
                SELECT player_id, game_id,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) newest ON newest.player_id = p.id
            JOIN (
                SELECT player_id, game_id,
                       MIN(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE timestamp >= ?
                GROUP BY player_id, game_id
            ) oldest ON oldest.player_id = newest.player_id
                     AND oldest.game_id  = newest.game_id
            WHERE newest.playtime_minutes - oldest.playtime_minutes > 0
            GROUP BY p.id
            ORDER BY avg_minutes_per_game DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since, since)).fetchall()
    return [dict(r) for r in rows]
