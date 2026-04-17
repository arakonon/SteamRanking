"""Wöchentlicher Instagram-Upload (Post-Carousel + Stories)."""

import json
import logging

from services.instagram_jobs import run_weekly_instagram_job

logging.basicConfig(level=logging.WARNING)
logging.getLogger("instagrapi").setLevel(logging.INFO)


def run():
    result = run_weekly_instagram_job()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
