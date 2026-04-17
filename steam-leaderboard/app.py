import logging
import os
import threading
from flask import Flask, render_template, request, jsonify
from database.db import init_db
from services.snapshot import run_snapshot
from services import rankings
from services.instagram_jobs import run_weekly_instagram_job, run_monthly_instagram_job, run_yearly_instagram_job
from services.instagram import ensure_instagram_login

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)

with app.app_context():
    init_db()


def _days_from_period(period):
    if period == "month":
        return 30
    if period == "year":
        return 365
    if period == "ever":
        return None
    return 7


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/leaderboard")
def leaderboard():
    period = request.args.get("period", "week")
    days = _days_from_period(period)
    data = {
        "total_playtime":         rankings.get_total_playtime_ranking(days),
        "most_played_overall":    rankings.get_most_played_game_overall(days),
        "most_played_per_player": rankings.get_most_played_game_per_player(days),
        "most_games":             rankings.get_player_with_most_games(),
        "recently_played":        rankings.get_recently_played(days),
        "avg_playtime":           rankings.get_avg_playtime_per_game(days),
    }
    return render_template("leaderboard.html", data=data, period=period, days=days)


@app.route("/api/snapshot")
def api_snapshot():
    if not _check_snapshot_token():
        return jsonify({"error": "unauthorized"}), 401
    result = run_snapshot()
    return jsonify(result)


def _check_snapshot_token():
    token = request.args.get("token", "")
    expected = os.environ.get("SNAPSHOT_TOKEN", "")
    return bool(expected and token == expected)


def _start_instagram_job(job_fn, period):
    """
    Prüft Instagram-Login und startet den eigentlichen Job als Daemon-Thread.
    Gibt sofort eine HTTP-Antwort zurück, sobald der Login erfolgreich war.
    """
    if not _check_snapshot_token():
        return jsonify({"error": "unauthorized"}), 401
    try:
        ensure_instagram_login()
    except Exception as e:
        logging.error("Instagram-Login fehlgeschlagen: %s", e)
        return jsonify({"ok": False, "error": "instagram_login_failed", "detail": str(e)}), 500
    threading.Thread(
        target=job_fn,
        daemon=True,
        name=f"instagram_{period}",
    ).start()
    return jsonify({"ok": True, "status": "started", "period": period})


@app.route("/api/instagram/weekly")
def api_instagram_weekly():
    return _start_instagram_job(run_weekly_instagram_job, "weekly")


@app.route("/api/instagram/monthly")
def api_instagram_monthly():
    return _start_instagram_job(run_monthly_instagram_job, "monthly")


@app.route("/api/instagram/yearly")
def api_instagram_yearly():
    return _start_instagram_job(run_yearly_instagram_job, "yearly")


@app.route("/api/rankings")
def api_rankings():
    period = request.args.get("period", "week")
    days = _days_from_period(period)
    data = {
        "period": period,
        "days": days,
        "total_playtime":         rankings.get_total_playtime_ranking(days),
        "most_played_overall":    rankings.get_most_played_game_overall(days),
        "most_played_per_player": rankings.get_most_played_game_per_player(days),
        "most_games":             rankings.get_player_with_most_games(),
        "recently_played":        rankings.get_recently_played(days),
        "avg_playtime":           rankings.get_avg_playtime_per_game(days),
    }
    return jsonify(data)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
