import logging
import time
import requests
import config

logger = logging.getLogger(__name__)


def get_player_summary(steam_id):
    """Gibt Profilinfos zurück, inkl. Sichtbarkeitsfeldern, oder None bei Fehler."""
    url = f"{config.BASE_URL}/ISteamUser/GetPlayerSummaries/v2/"
    params = {
        "key": config.STEAM_API_KEY,
        "steamids": steam_id,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        players = response.json().get("response", {}).get("players", [])
        if not players:
            logger.error("get_player_summary: keine Daten für steam_id=%s", steam_id)
            return None
        p = players[0]
        return {
            "personaname": p.get("personaname", ""),
            "avatarfull": p.get("avatarfull", ""),
            "communityvisibilitystate": p.get("communityvisibilitystate", 0),
            "profilestate": p.get("profilestate", 0),
        }
    except Exception as e:
        logger.error("get_player_summary fehlgeschlagen für steam_id=%s: %s", steam_id, e)
        return None


def _get_recently_played(steam_id):
    """Holt kürzlich gespielte Spiele über GetRecentlyPlayedGames.
    Dieser Endpoint liefert Spiele, die GetOwnedGames manchmal nicht enthält
    (z.B. Family Sharing, bestimmte Free-to-Play Titel)."""
    url = f"{config.BASE_URL}/IPlayerService/GetRecentlyPlayedGames/v1/"
    params = {
        "key": config.STEAM_API_KEY,
        "steamid": steam_id,
        "count": 100,
        "format": "json",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json().get("response", {}) or {}
        return payload.get("games") or []
    except Exception as e:
        logger.warning("GetRecentlyPlayedGames fehlgeschlagen für steam_id=%s: %s", steam_id, e)
        return []


def get_owned_games(steam_id, communityvisibilitystate=None, profilestate=None):
    """
    Gibt strukturierte Owned-Games-Infos zurück.
    Merged GetOwnedGames mit GetRecentlyPlayedGames, da letzterer
    manchmal Spiele enthält die in GetOwnedGames fehlen.

    status:
      - public_with_games
      - public_no_games
      - private_or_hidden
      - api_error
    """
    url = f"{config.BASE_URL}/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": config.STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_played_free_games": 1,
        "format": "json",
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json().get("response", {}) or {}
        raw_games = payload.get("games") or []
        games_by_appid = {}
        for g in raw_games:
            appid = g.get("appid")
            games_by_appid[appid] = {
                "appid": appid,
                "name": g.get("name", ""),
                "playtime_forever": g.get("playtime_forever", 0),
                "rtime_last_played": g.get("rtime_last_played", 0),
            }

        # Merge mit GetRecentlyPlayedGames
        now_ts = int(time.time())
        for rg in _get_recently_played(steam_id):
            appid = rg.get("appid")
            if appid in games_by_appid:
                existing = games_by_appid[appid]
                if rg.get("playtime_forever", 0) > existing["playtime_forever"]:
                    existing["playtime_forever"] = rg["playtime_forever"]
                if existing["rtime_last_played"] == 0:
                    existing["rtime_last_played"] = now_ts
            else:
                games_by_appid[appid] = {
                    "appid": appid,
                    "name": rg.get("name", ""),
                    "playtime_forever": rg.get("playtime_forever", 0),
                    "rtime_last_played": now_ts,
                }

        games = list(games_by_appid.values())
        game_count = payload.get("game_count")
        if game_count is None:
            game_count = len(games)
        else:
            game_count = max(int(game_count), len(games))

        is_hidden = False
        try:
            if int(communityvisibilitystate or 0) < 3 or int(profilestate or 0) == 0:
                is_hidden = True
        except Exception:
            is_hidden = False

        if games:
            return {
                "status": "public_with_games",
                "reason": "games_returned",
                "games": games,
                "game_count": int(game_count),
            }
        if is_hidden:
            return {
                "status": "private_or_hidden",
                "reason": "profile_not_public_or_hidden_games",
                "games": [],
                "game_count": int(game_count),
            }
        return {
            "status": "public_no_games",
            "reason": "public_profile_with_empty_library_or_hidden_free_games",
            "games": [],
            "game_count": int(game_count),
        }
    except Exception as e:
        logger.error("get_owned_games fehlgeschlagen für steam_id=%s: %s", steam_id, e)
        return {
            "status": "api_error",
            "reason": f"owned_games_request_failed:{type(e).__name__}",
            "games": [],
            "game_count": 0,
        }
