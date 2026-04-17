"""
Diagnose-Script für Snapshot/Ranking auf PythonAnywhere.

Beispiele:
  python3 debug_snapshot_state.py
  python3 debug_snapshot_state.py --run-snapshot
"""

import argparse
import json
from datetime import datetime, timezone

import config
from database.db import get_connection
from services.snapshot import run_snapshot
from services.steam_api import get_player_summary, get_owned_games


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _db_player_state(steam_id):
    with get_connection() as conn:
        player = conn.execute(
            "SELECT id, display_name, game_count, last_updated FROM players WHERE steam_id = ?",
            (steam_id,),
        ).fetchone()
        if not player:
            return {
                "exists": False,
                "player_id": None,
                "display_name": None,
                "game_count": 0,
                "last_updated": None,
                "snapshot_rows": 0,
                "distinct_games": 0,
                "last_snapshot": None,
                "total_minutes_latest": 0,
            }

        player_id = player["id"]
        snapshot_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM snapshots WHERE player_id = ?", (player_id,)
        ).fetchone()["c"]
        distinct_games = conn.execute(
            "SELECT COUNT(DISTINCT game_id) AS c FROM snapshots WHERE player_id = ?", (player_id,)
        ).fetchone()["c"]
        last_snapshot = conn.execute(
            "SELECT MAX(timestamp) AS ts FROM snapshots WHERE player_id = ?", (player_id,)
        ).fetchone()["ts"]
        total_minutes_latest = conn.execute(
            """
            SELECT COALESCE(SUM(playtime_minutes), 0) AS total
            FROM (
                SELECT game_id, MAX(playtime_minutes) AS playtime_minutes
                FROM snapshots
                WHERE player_id = ?
                GROUP BY game_id
            )
            """,
            (player_id,),
        ).fetchone()["total"]

        return {
            "exists": True,
            "player_id": player_id,
            "display_name": player["display_name"],
            "game_count": player["game_count"],
            "last_updated": player["last_updated"],
            "snapshot_rows": snapshot_rows,
            "distinct_games": distinct_games,
            "last_snapshot": last_snapshot,
            "total_minutes_latest": total_minutes_latest,
        }


def run_diagnose(run_snapshot_first=False):
    report = {
        "generated_at_utc": _utc_now(),
        "config": {
            "db_path": config.DB_PATH,
            "steam_ids_count": len(config.STEAM_IDS),
            "steam_api_key_set": bool(config.STEAM_API_KEY),
        },
        "snapshot_run": None,
        "players": [],
    }

    if run_snapshot_first:
        report["snapshot_run"] = run_snapshot()

    for steam_id in config.STEAM_IDS:
        summary = get_player_summary(steam_id)
        if summary is None:
            player_report = {
                "steam_id": steam_id,
                "summary_ok": False,
                "visibility": {},
                "owned_games_status": "skipped",
                "owned_games_reason": "player_summary_not_found_or_api_error",
                "owned_games_count": 0,
                "db": _db_player_state(steam_id),
            }
            report["players"].append(player_report)
            continue

        owned = get_owned_games(
            steam_id,
            communityvisibilitystate=summary.get("communityvisibilitystate", 0),
            profilestate=summary.get("profilestate", 0),
        )
        player_report = {
            "steam_id": steam_id,
            "summary_ok": True,
            "personaname": summary.get("personaname", ""),
            "visibility": {
                "communityvisibilitystate": summary.get("communityvisibilitystate", 0),
                "profilestate": summary.get("profilestate", 0),
            },
            "owned_games_status": owned.get("status", "unknown"),
            "owned_games_reason": owned.get("reason", ""),
            "owned_games_count": owned.get("game_count", 0),
            "db": _db_player_state(steam_id),
        }
        report["players"].append(player_report)

    return report


def _print_human(report):
    print("=== Snapshot Diagnose ===")
    print(f"Generated UTC: {report['generated_at_utc']}")
    print(f"DB_PATH: {report['config']['db_path']}")
    print(f"STEAM_IDS: {report['config']['steam_ids_count']}")
    print(f"STEAM_API_KEY gesetzt: {report['config']['steam_api_key_set']}")
    if report["snapshot_run"] is not None:
        print("\nSnapshot run result:")
        print(json.dumps(report["snapshot_run"], ensure_ascii=False, indent=2))

    print("\nPer-player status:")
    for p in report["players"]:
        print(
            f"- {p['steam_id']} | summary_ok={p['summary_ok']} "
            f"| status={p['owned_games_status']} | games={p['owned_games_count']}"
        )
        if p["visibility"]:
            print(f"  visibility={p['visibility']}")
        print(
            "  db: exists={exists}, snapshots={snapshots}, distinct_games={games}, total_latest={total}".format(
                exists=p["db"]["exists"],
                snapshots=p["db"]["snapshot_rows"],
                games=p["db"]["distinct_games"],
                total=p["db"]["total_minutes_latest"],
            )
        )
        print(f"  reason={p['owned_games_reason']}")

    print("\n=== JSON ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Diagnose für Steam Snapshot State")
    parser.add_argument(
        "--run-snapshot",
        action="store_true",
        help="Fuehrt vor der Diagnose run_snapshot() aus.",
    )
    args = parser.parse_args()
    report = run_diagnose(run_snapshot_first=args.run_snapshot)
    _print_human(report)


if __name__ == "__main__":
    main()
