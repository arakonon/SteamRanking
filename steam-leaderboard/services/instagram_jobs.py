import logging
import os
import tempfile

from services import instagram
from services.captions import build_caption, build_story_text
from services.image_gen import (
    render_post_images, render_story_images, add_story_text_overlay,
    THEME_WEEKLY, THEME_MONTHLY, THEME_YEARLY,
)

logger = logging.getLogger(__name__)

WEEKLY_DAYS = 7
WEEKLY_LABEL = "Wöchentliches Ranking  |  letzte 7 Tage"
MONTHLY_DAYS = 30
MONTHLY_LABEL = "Monatliches Ranking  |  letzte 30 Tage"
YEARLY_DAYS = 365
YEARLY_LABEL = "Jahresrückblick  |  letzte 365 Tage"

SUFFIXES = [
    "meiste_spielzeit",
    "top_spiele",
    "lieblingsspiel",
    "avg_spielzeit",
]


def _save_tmp(img, prefix):
    """Speichert ein PIL-Image als temporäre JPEG-Datei und gibt den Pfad zurück."""
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix=prefix + "_")
    os.close(fd)
    img.save(path, "JPEG", quality=88)
    return path


def run_instagram_batch(days, label, period, theme=None):
    """
    Fuehrt einen kompletten Instagram-Batch aus (Post-Carousel + Stories).
    Gibt ein strukturiertes Ergebnis fuer CLI oder API zurueck.
    """
    result = {
        "ok": True,
        "period": period,
        "days": days,
        "post_uploaded": False,
        "stories_uploaded": 0,
        "errors": [],
    }

    try:
        caption = build_caption(days, period=period)
        story_text = build_story_text(days)

        # --- Posts: alle Bilder als ein Carousel ---
        post_imgs = render_post_images(days, label, theme=theme)
        post_paths = []
        for img, suffix in zip(post_imgs, SUFFIXES):
            post_paths.append(_save_tmp(img, f"post_{period}_{suffix}"))

        try:
            media = instagram.upload_album(post_paths, caption)
            if media is None:
                result["errors"].append("post_upload_failed")
            else:
                result["post_uploaded"] = True
        finally:
            for path in post_paths:
                if os.path.exists(path):
                    os.remove(path)

        # --- Stories ---
        story_imgs = render_story_images(days, label, theme=theme)
        story_imgs[0] = add_story_text_overlay(story_imgs[0], story_text)
        for img, suffix in zip(story_imgs, SUFFIXES):
            path = _save_tmp(img, f"story_{period}_{suffix}")
            try:
                media = instagram.upload_story(path)
                if media is None:
                    result["errors"].append(f"story_upload_failed:{suffix}")
                else:
                    result["stories_uploaded"] += 1
            finally:
                if os.path.exists(path):
                    os.remove(path)

        if result["errors"]:
            result["ok"] = False

    except Exception as e:
        logger.exception("Instagram-Batch fehlgeschlagen fuer period=%s", period)
        result["ok"] = False
        result["errors"].append(f"internal_error:{type(e).__name__}")

    return result


def run_weekly_instagram_job():
    return run_instagram_batch(WEEKLY_DAYS, WEEKLY_LABEL, "weekly", theme=THEME_WEEKLY)


def run_monthly_instagram_job():
    return run_instagram_batch(MONTHLY_DAYS, MONTHLY_LABEL, "monthly", theme=THEME_MONTHLY)


def run_yearly_instagram_job():
    return run_instagram_batch(YEARLY_DAYS, YEARLY_LABEL, "yearly", theme=THEME_YEARLY)
