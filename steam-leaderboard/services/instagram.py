import os
import logging

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, PhotoConfigureError

import config

logger = logging.getLogger("instagrapi")
logger.setLevel(logging.INFO)

SETTINGS_FILE = os.path.expanduser(
    os.environ.get("INSTAGRAM_SESSION_FILE", "~/.secrets/instagram_session.json")
)

_client = None


def _persist_settings(cl):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    cl.dump_settings(SETTINGS_FILE)
    try:
        os.chmod(SETTINGS_FILE, 0o600)
    except OSError:
        logger.warning("Konnte Dateirechte fuer %s nicht setzen", SETTINGS_FILE)


def _get_client():
    global _client
    if _client is not None:
        return _client

    _client = Client()

    if os.path.exists(SETTINGS_FILE):
        _client.load_settings(SETTINGS_FILE)
        try:
            _client.get_timeline_feed()
            logger.info("Instagram-Session wiederverwendet")
        except LoginRequired:
            logger.warning("Session abgelaufen, logge neu ein...")
            _client.login(config.INSTAGRAM_USER, config.INSTAGRAM_PASS)
            _persist_settings(_client)
    else:
        _client.login(config.INSTAGRAM_USER, config.INSTAGRAM_PASS)
        _persist_settings(_client)

    logger.info("Instagram login erfolgreich")
    return _client


def ensure_instagram_login():
    """Stellt sicher dass ein gültiger Instagram-Login besteht. Wirft Exception bei Fehler."""
    _get_client()


def upload_photo(image_path, caption):
    try:
        cl = _get_client()
        media = cl.photo_upload(image_path, caption)
        logger.info(f"Foto hochgeladen: Media ID {media.id}, Code {media.code}")
        return media
    except PhotoConfigureError as e:
        logger.error(f"Photo configure fehlgeschlagen: {e}")
    except ChallengeRequired as e:
        logger.error(f"Challenge required (Account-Verifikation noetig): {e}")
    except LoginRequired:
        logger.error("Nicht eingeloggt")
    return None


def upload_album(image_paths, caption):
    try:
        cl = _get_client()
        media = cl.album_upload(image_paths, caption)
        logger.info(f"Album hochgeladen: Media ID {media.id}, Code {media.code}")
        return media
    except PhotoConfigureError as e:
        logger.error(f"Album configure fehlgeschlagen: {e}")
    except ChallengeRequired as e:
        logger.error(f"Challenge required (Account-Verifikation noetig): {e}")
    except LoginRequired:
        logger.error("Nicht eingeloggt")
    return None


def upload_story(image_path):
    try:
        cl = _get_client()
        media = cl.photo_upload_to_story(image_path)
        logger.info(f"Story hochgeladen: Media ID {media.id}, Code {media.code}")
        return media
    except PhotoConfigureError as e:
        logger.error(f"Story configure fehlgeschlagen: {e}")
    except ChallengeRequired as e:
        logger.error(f"Challenge required (Account-Verifikation noetig): {e}")
    except LoginRequired:
        logger.error("Nicht eingeloggt")
    return None
