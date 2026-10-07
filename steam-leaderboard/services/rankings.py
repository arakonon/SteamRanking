from datetime import datetime, timedelta, timezone
import config
from database.db import get_connection


def _window_start(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _excl(alias=''):
    """Returns (AND-clause, params) for excluding EXCLUDED_APP_IDS from snapshots queries."""
    ids = config.EXCLUDED_APP_IDS
    if not ids:
        return '', ()
    col = f'{alias}.game_id' if alias else 'game_id'
    ph = ','.join('?' * len(ids))
    return f' AND {col} NOT IN ({ph})', tuple(ids)


def _gains_cte(since):
    """Returns (WITH-clause, params) defining `gains(player_id, game_id, game_name, minutes)`:
    Spielzeit-Zunahme pro Spieler+Spiel seit `since`.
    Baseline ist der letzte Snapshot vor dem Fenster. Gibt es keinen, zählt ein Spiel,
    das erst nach dem ersten Snapshot des Spielers aufgetaucht ist (neu gekauft/gespielt),
    ab 0 – sonst ab dem ältesten Snapshot im Fenster (neu getrackter Spieler)."""
    excl_sql, excl_p = _excl()
    sql = f"""
        WITH player_first AS (
            SELECT player_id, MIN(timestamp) AS first_ts
            FROM snapshots
            GROUP BY player_id
        ),
        game_first AS (
            SELECT player_id, game_id, MIN(timestamp) AS first_ts
            FROM snapshots
            WHERE 1=1{excl_sql}
            GROUP BY player_id, game_id
        ),
        win AS (
            SELECT player_id, game_id, MAX(game_name) AS game_name,
                   MAX(playtime_minutes) AS newest,
                   MIN(playtime_minutes) AS oldest
            FROM snapshots
            WHERE timestamp >= ?{excl_sql}
            GROUP BY player_id, game_id
        ),
        before AS (
            SELECT player_id, game_id, MAX(playtime_minutes) AS playtime_minutes
            FROM snapshots
            WHERE timestamp < ?{excl_sql}
            GROUP BY player_id, game_id
        ),
        gains AS (
            SELECT w.player_id, w.game_id, w.game_name,
                   w.newest - COALESCE(
                       b.playtime_minutes,
                       CASE WHEN gf.first_ts > pf.first_ts THEN 0 ELSE w.oldest END
                   ) AS minutes
            FROM win w
            JOIN game_first gf ON gf.player_id = w.player_id AND gf.game_id = w.game_id
            JOIN player_first pf ON pf.player_id = w.player_id
            LEFT JOIN before b ON b.player_id = w.player_id AND b.game_id = w.game_id
        )
    """
    return sql, (*excl_p, since, *excl_p, since, *excl_p)


def get_total_playtime_ranking(days):
    """Gesamte Spielzeit pro Spieler.
    days=None → kumulativ (neuester Snapshot), sonst Zunahme im Zeitfenster."""
    excl_sql, excl_p = _excl()
    if days is None:
        query = f"""
            SELECT
                p.display_name AS player,
                p.steam_id,
                p.avatar_url,
                COALESCE(SUM(latest.playtime_minutes), 0) AS total_minutes_gained
            FROM players p
            LEFT JOIN (
                SELECT player_id, game_id, MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE 1=1{excl_sql}
                GROUP BY player_id, game_id
            ) latest ON latest.player_id = p.id
            GROUP BY p.id
            ORDER BY total_minutes_gained DESC, p.display_name ASC
        """
        with get_connection() as conn:
            rows = conn.execute(query, excl_p).fetchall()
    else:
        cte, cte_p = _gains_cte(_window_start(days))
        query = cte + """
            SELECT
                p.display_name AS player,
                p.steam_id,
                p.avatar_url,
                SUM(g.minutes) AS total_minutes_gained
            FROM players p
            JOIN gains g ON g.player_id = p.id
            GROUP BY p.id
            HAVING total_minutes_gained > 0
            ORDER BY total_minutes_gained DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, cte_p).fetchall()
    return [dict(r) for r in rows]


def get_most_played_game_overall(days):
    """Das Spiel mit der meisten Spielzeit über alle Spieler.
    days=None → kumulativ, sonst Zunahme im Zeitfenster."""
    excl_sql, excl_p = _excl()
    if days is None:
        query = f"""
            SELECT
                sub.game_name,
                SUM(sub.playtime_minutes) AS total_minutes,
                COUNT(DISTINCT sub.player_id) AS player_count
            FROM (
                SELECT player_id, game_id, game_name,
                       MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE 1=1{excl_sql}
                GROUP BY player_id, game_id
            ) sub
            WHERE sub.playtime_minutes > 0
            GROUP BY sub.game_name
            ORDER BY total_minutes DESC
            LIMIT 10
        """
        with get_connection() as conn:
            rows = conn.execute(query, excl_p).fetchall()
    else:
        cte, cte_p = _gains_cte(_window_start(days))
        query = cte + """
            SELECT
                game_name,
                SUM(minutes) AS total_minutes,
                COUNT(DISTINCT player_id) AS player_count
            FROM gains
            WHERE minutes > 0
            GROUP BY game_name
            ORDER BY total_minutes DESC
            LIMIT 10
        """
        with get_connection() as conn:
            rows = conn.execute(query, cte_p).fetchall()
    return [dict(r) for r in rows]


def get_most_played_game_per_player(days):
    """Pro Spieler das Spiel mit der meisten Spielzeit.
    days=None → kumulativ (neuester Snapshot), sonst Zunahme im Zeitfenster."""
    excl_sql, excl_p = _excl()
    excl_sql_s2, _ = _excl('s2')
    if days is None:
        query = f"""
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
                WHERE 1=1{excl_sql}
                GROUP BY player_id, game_id
            ) sub ON sub.player_id = p.id
            WHERE sub.playtime_minutes > 0
              AND sub.playtime_minutes = (
                SELECT MAX(s2.playtime_minutes)
                FROM snapshots s2
                WHERE s2.player_id = p.id
                  AND s2.playtime_minutes > 0{excl_sql_s2}
            )
            ORDER BY sub.playtime_minutes DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (*excl_p, *excl_p)).fetchall()
    else:
        cte, cte_p = _gains_cte(_window_start(days))
        query = cte + """
            SELECT
                p.display_name AS player,
                p.steam_id,
                g.game_name,
                g.minutes AS minutes
            FROM players p
            JOIN gains g ON g.player_id = p.id
            WHERE g.minutes > 0
              AND g.minutes = (
                SELECT MAX(g2.minutes) FROM gains g2 WHERE g2.player_id = p.id
            )
            ORDER BY g.minutes DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, cte_p).fetchall()
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
    excl_sql, excl_p = _excl('s')
    if days is None:
        query = f"""
            SELECT DISTINCT
                p.display_name AS player,
                p.steam_id,
                s.game_name,
                s.game_id,
                MAX(s.last_played) AS last_played_ts
            FROM snapshots s
            JOIN players p ON p.id = s.player_id
            WHERE s.last_played > 0{excl_sql}
            GROUP BY s.player_id, s.game_id
            ORDER BY last_played_ts DESC
            LIMIT 100
        """
        with get_connection() as conn:
            rows = conn.execute(query, excl_p).fetchall()
    else:
        since_ts = int(
            (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
        )
        query = f"""
            SELECT DISTINCT
                p.display_name AS player,
                p.steam_id,
                s.game_name,
                s.game_id,
                MAX(s.last_played) AS last_played_ts
            FROM snapshots s
            JOIN players p ON p.id = s.player_id
            WHERE s.last_played >= ?{excl_sql}
            GROUP BY s.player_id, s.game_id
            ORDER BY last_played_ts DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, (since_ts, *excl_p)).fetchall()
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
    excl_sql, excl_p = _excl()
    if days is None:
        query = f"""
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
                WHERE 1=1{excl_sql}
                GROUP BY player_id, game_id
            ) latest ON latest.player_id = p.id
            WHERE latest.playtime_minutes > 0
            GROUP BY p.id
            ORDER BY avg_minutes_per_game DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, excl_p).fetchall()
    else:
        cte, cte_p = _gains_cte(_window_start(days))
        query = cte + """
            SELECT
                p.display_name AS player,
                p.steam_id,
                ROUND(CAST(SUM(g.minutes) AS REAL) / COUNT(*), 1) AS avg_minutes_per_game,
                COUNT(*) AS games_played
            FROM players p
            JOIN gains g ON g.player_id = p.id
            WHERE g.minutes > 0
            GROUP BY p.id
            ORDER BY avg_minutes_per_game DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query, cte_p).fetchall()
    return [dict(r) for r in rows]
