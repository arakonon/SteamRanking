import logging
from datetime import datetime, timezone
import config
from database.db import get_connection
from services.steam_api import get_player_summary, get_owned_games

logger = logging.getLogger(__name__)


def run_snapshot():
    """Holt für jeden Spieler in config.STEAM_IDS Profil + Spieleliste und
    schreibt einen Snapshot in die Datenbank.
    Gibt dict mit Zählern + pro-Steam-ID-Debugdetails zurück."""
    processed = 0
    errors = 0
    private_accounts = 0
    empty_libraries = 0
    api_failures = 0
    details = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for steam_id in config.STEAM_IDS:
        detail = {
            "steam_id": steam_id,
            "summary_ok": False,
            "visibility": {},
            "owned_games_status": "unknown",
            "games_count": 0,
            "player_upserted": False,
            "snapshots_inserted": 0,
            "reason": "",
        }
        try:
            summary = get_player_summary(steam_id)
            if summary is None:
                logger.error("Kein Summary für steam_id=%s – überspringe.", steam_id)
                detail["reason"] = "player_summary_not_found_or_api_error"
                errors += 1
                details.append(detail)
                continue
            detail["summary_ok"] = True
            detail["player_name"] = summary.get("personaname", "")
            detail["visibility"] = {
                "communityvisibilitystate": summary.get("communityvisibilitystate", 0),
                "profilestate": summary.get("profilestate", 0),
            }

            owned = get_owned_games(
                steam_id,
                communityvisibilitystate=summary.get("communityvisibilitystate", 0),
                profilestate=summary.get("profilestate", 0),
            )
            detail["owned_games_status"] = owned.get("status", "unknown")
            detail["games_count"] = int(owned.get("game_count", 0) or 0)
            detail["reason"] = owned.get("reason", "")

            games = owned.get("games", [])
            if detail["owned_games_status"] == "private_or_hidden":
                private_accounts += 1
            elif detail["owned_games_status"] == "public_no_games":
                empty_libraries += 1
            elif detail["owned_games_status"] == "api_error":
                api_failures += 1
                errors += 1

            with get_connection() as conn:
                # Upsert Spieler
                conn.execute(
                    """
                    INSERT INTO players (steam_id, display_name, avatar_url, game_count, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(steam_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        avatar_url   = excluded.avatar_url,
                        game_count   = excluded.game_count,
                        last_updated = excluded.last_updated
                    """,
                    (
                        steam_id,
                        summary["personaname"],
                        summary["avatarfull"],
                        detail["games_count"],
                        timestamp,
                    ),
                )
                detail["player_upserted"] = True

                row = conn.execute(
                    "SELECT id FROM players WHERE steam_id = ?", (steam_id,)
                ).fetchone()
                player_id = row["id"]

                # Snapshots einfügen
                conn.executemany(
                    """
                    INSERT INTO snapshots (player_id, timestamp, game_id, game_name,
                                          playtime_minutes, last_played)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            player_id,
                            timestamp,
                            g["appid"],
                            g["name"],
                            g["playtime_forever"],
                            g["rtime_last_played"],
                        )
                        for g in games
                    ],
                )
                detail["snapshots_inserted"] = len(games)
                conn.commit()

            processed += 1
            details.append(detail)
            logger.info("Snapshot für %s (%s) gespeichert.", summary["personaname"], steam_id)

        except Exception as e:
            logger.error("Fehler bei steam_id=%s: %s", steam_id, e)
            detail["reason"] = f"snapshot_exception:{type(e).__name__}"
            errors += 1
            details.append(detail)

    return {
        "processed": processed,
        "errors": errors,
        "private_accounts": private_accounts,
        "empty_libraries": empty_libraries,
        "api_failures": api_failures,
        "details": details,
    }
