"""
Bildgenerierung für Instagram Posts und Stories.

Öffentliche API:
  render_post_images(days, period_label, theme)  → list[PIL.Image]  (1080×1080 je)
  render_story_images(days, period_label, theme) → list[PIL.Image]  (720×1280 je)
"""

import io
import logging
import os

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from services.rankings import (
    get_total_playtime_ranking,
    get_most_played_game_overall,
    get_most_played_game_per_player,
    get_avg_playtime_per_game,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
THEME_WEEKLY = {
    "bg_top": (10, 14, 24), "bg_bot": (18, 28, 42),
    "card": (22, 32, 48), "card_light": (30, 42, 60),
    "accent": (100, 200, 120), "accent_dim": (60, 130, 80),
    "white": (255, 255, 255), "text": (215, 220, 230),
    "dim": (100, 110, 130),
    "bar_start": (60, 180, 100), "bar_end": (40, 130, 75),
    "medals": [(255, 215, 0), (192, 192, 192), (205, 137, 63)],
    "divider": (35, 48, 65), "bar_highlight": (80, 200, 115, 100),
}

THEME_MONTHLY = {
    "bg_top": (28, 18, 40), "bg_bot": (42, 24, 58),
    "card": (38, 28, 55), "card_light": (50, 38, 70),
    "accent": (180, 140, 220), "accent_dim": (120, 80, 160),
    "white": (255, 255, 255), "text": (225, 215, 235),
    "dim": (120, 100, 140),
    "bar_start": (160, 120, 210), "bar_end": (120, 80, 170),
    "medals": [(255, 215, 0), (192, 192, 192), (205, 137, 63)],
    "divider": (55, 38, 75), "bar_highlight": (190, 160, 230, 100),
}

THEME_YEARLY = {
    "bg_top": (24, 18, 8), "bg_bot": (36, 28, 12),
    "card": (40, 32, 16), "card_light": (55, 44, 22),
    "accent": (255, 200, 60), "accent_dim": (180, 140, 40),
    "white": (255, 255, 255), "text": (235, 225, 200),
    "dim": (140, 120, 90),
    "bar_start": (230, 180, 50), "bar_end": (180, 140, 35),
    "medals": [(255, 215, 0), (192, 192, 192), (205, 137, 63)],
    "divider": (65, 52, 25), "bar_highlight": (255, 220, 100, 100),
}

# Backward-compat Aliase (für _fetch_avatar und add_story_text_overlay)
CARD_LIGHT = THEME_WEEKLY["card_light"]
WHITE = THEME_WEEKLY["white"]

FONT_CANDIDATES = [
    os.environ.get("IMAGE_FONT_PATH", "").strip(),
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "DejaVuSans.ttf",
]

_FONT_PATH = None


def _resolve_font_path():
    global _FONT_PATH
    if _FONT_PATH is not None:
        return _FONT_PATH

    for candidate in FONT_CANDIDATES:
        if not candidate:
            continue
        try:
            # Probe-Laden, damit wir nicht nur auf Dateiexistenz vertrauen.
            ImageFont.truetype(candidate, 24)
            _FONT_PATH = candidate
            logger.info("Nutze Schriftart: %s", candidate)
            return _FONT_PATH
        except Exception:
            continue

    logger.warning("Keine TrueType-Schrift gefunden, nutze Pillow-Default-Font")
    _FONT_PATH = ""
    return _FONT_PATH

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _font(size):
    try:
        font_path = _resolve_font_path()
        if font_path:
            return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def _minutes_to_str(minutes):
    minutes = int(minutes or 0)
    h, m = divmod(minutes, 60)
    if h >= 100:
        return f"{h}h"
    return f"{h}h {m:02d}m"


def _fetch_avatar(url, size):
    """Lädt Steam-Avatar und gibt kreisförmiges RGBA-Bild zurück."""
    try:
        if not url:
            raise ValueError("Keine URL")
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
    except Exception as e:
        logger.debug(f"Avatar-Ladefehler ({url}): {e}")
        img = Image.new("RGBA", (size, size), (*CARD_LIGHT, 255))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out


def _gradient_bg(W, H, theme):
    """Erzeugt vertikalen Farbverlauf von bg_top → bg_bot."""
    bg_top = theme["bg_top"]
    bg_bot = theme["bg_bot"]
    img = Image.new("RGB", (W, H), bg_top)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(bg_top[0] + (bg_bot[0] - bg_top[0]) * t)
        g = int(bg_top[1] + (bg_bot[1] - bg_top[1]) * t)
        b = int(bg_top[2] + (bg_bot[2] - bg_top[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _draw_glow(img, cx, cy, radius, color, alpha=30):
    """Zeichnet einen weichen Glow-Kreis (dezent)."""
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    for i in range(radius, 0, -2):
        a = int(alpha * (i / radius))
        d.ellipse([cx - i, cy - i, cx + i, cy + i],
                  fill=(*color[:3], a))
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 3))
    img.paste(Image.alpha_composite(
        img.convert("RGBA"), glow).convert("RGB"), (0, 0))


def _draw_header(img, draw, W, pad, title, subtitle, theme):
    """Zeichnet den Header mit Titel und Untertitel."""
    h_top = pad
    h_bot = pad + 130
    draw.rounded_rectangle([pad, h_top, W - pad, h_bot],
                           radius=18, fill=theme["card"])
    # Dezente Linie am oberen Rand der Karte
    draw.rounded_rectangle([pad, h_top, W - pad, h_top + 3],
                           radius=2, fill=theme["accent_dim"])
    draw.text((W // 2, h_top + 30), title,
              font=_font(44), fill=theme["white"], anchor="mt")
    draw.text((W // 2, h_top + 88), subtitle,
              font=_font(26), fill=theme["accent"], anchor="mt")
    return h_bot + 20


def _draw_section_title(draw, x, y, W, pad, text, theme):
    draw.text((x, y), text, font=_font(30), fill=theme["white"])
    y += 38
    draw.line([(pad, y), (W - pad, y)], fill=theme["divider"], width=2)
    return y + 16


def _draw_row_card(draw, x0, y0, x1, y1, rank, theme):
    """Zeichnet eine Zeilen-Karte mit optionalem Medal-Akzent."""
    draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=theme["card"])
    if 1 <= rank <= 3:
        color = theme["medals"][rank - 1]
        draw.rounded_rectangle([x0, y0, x0 + 4, y1], radius=2,
                               fill=(*color, 180))


def _draw_rank_badge(draw, x, y, w, h, rank, theme, font_size=24):
    medal = theme["medals"][rank - 1] if rank <= 3 else theme["dim"]
    draw.text((x + w // 2, y + h // 2), str(rank),
              font=_font(font_size), fill=medal, anchor="mm")


# ---------------------------------------------------------------------------
# Sektion 1: Meiste Spielzeit (zweizeilig: Name + Balken darunter)
# ---------------------------------------------------------------------------

def _build_spielzeit(W, H, rows, pad, title, subtitle, theme):
    img = _gradient_bg(W, H, theme)
    draw = ImageDraw.Draw(img)

    y = _draw_header(img, draw, W, pad, title, subtitle, theme)
    y = _draw_section_title(draw, pad, y, W, pad, "Meiste Spielzeit", theme)

    if not rows:
        draw.text((W // 2, y + 60), "Keine Daten",
                  font=_font(28), fill=theme["dim"], anchor="mt")
        return img

    n = len(rows)
    max_min = max(r["total_minutes_gained"] for r in rows) or 1

    # --- Dynamisches Layout: alle Einträge passen immer ins Bild ---
    IDEAL_ROW_H = 110
    avail = H - y - pad
    row_h = min(IDEAL_ROW_H, max(36, avail // max(n, 1)))
    scale = row_h / IDEAL_ROW_H

    av_size    = max(18, int(50 * scale))
    rank_w     = max(22, int(40 * scale))
    top_margin = max(3,  int(8  * scale))
    av_gap     = max(8,  int(14 * scale))   # Abstand Avatar → Name
    rank_gap   = max(8,  int(24 * scale))   # Abstand Rand → Avatar
    card_gap   = max(2,  int(8  * scale))   # Abstand Karte → nächste Zeile
    name_fs    = max(12, int(26 * scale))
    time_fs    = max(11, int(24 * scale))
    badge_fs   = max(11, int(24 * scale))
    show_bar   = row_h >= 52
    bar_h      = max(5,  int(22 * scale)) if show_bar else 0

    content_h = n * row_h
    y_start = y + max(0, (avail - content_h) // 2)

    for i, row in enumerate(rows):
        ry   = y_start + i * row_h
        rank = i + 1
        mins = int(row.get("total_minutes_gained") or 0)
        name = row.get("player", "?")

        _draw_row_card(draw, pad, ry, W - pad, ry + row_h - card_gap, rank, theme)
        _draw_rank_badge(draw, pad + 6, ry + top_margin, rank_w, av_size, rank, theme,
                         font_size=badge_fs)

        av_x = pad + rank_w + rank_gap
        avatar = _fetch_avatar(row.get("avatar_url", ""), av_size)
        img.paste(avatar, (av_x, ry + top_margin), avatar)
        draw = ImageDraw.Draw(img)  # Refresh nach paste

        name_x = av_x + av_size + av_gap
        # Name + Zeit auf Höhe der Avatar-Mitte (wenn kein Balken) oder obere Hälfte
        text_y = ry + top_margin + (av_size // 4 if show_bar else av_size // 2 - name_fs // 2)
        draw.text((name_x, text_y), name,
                  font=_font(name_fs), fill=theme["text"])
        draw.text((W - pad - 10, text_y), _minutes_to_str(mins),
                  font=_font(time_fs), fill=theme["accent"], anchor="rt")

        if show_bar:
            bar_y  = ry + top_margin + av_size + 4
            bar_x0 = name_x
            bar_x1 = W - pad - 10
            bar_max = bar_x1 - bar_x0
            bar_w  = int((mins / max_min) * bar_max)
            if bar_w > 4:
                draw.rounded_rectangle(
                    [bar_x0, bar_y, bar_x0 + bar_w, bar_y + bar_h],
                    radius=min(6, bar_h // 2), fill=theme["bar_start"])
                if bar_w > 20 and bar_h >= 10:
                    draw.rounded_rectangle(
                        [bar_x0 + 2, bar_y + 2, bar_x0 + bar_w - 2, bar_y + bar_h - 4],
                        radius=3, fill=theme["bar_highlight"])

    return img


# ---------------------------------------------------------------------------
# Sektion 2: Meistgespieltes Spiel
# ---------------------------------------------------------------------------

def _build_top_spiele(W, H, rows, pad, title, subtitle, theme):
    img = _gradient_bg(W, H, theme)
    draw = ImageDraw.Draw(img)

    y = _draw_header(img, draw, W, pad, title, subtitle, theme)
    y = _draw_section_title(draw, pad, y, W, pad, "Top Spiele", theme)

    if not rows:
        draw.text((W // 2, y + 60), "Keine Daten",
                  font=_font(28), fill=theme["dim"], anchor="mt")
        return img

    items = rows[:10]
    n = len(items)
    max_min = max(r["total_minutes"] for r in items) or 1

    IDEAL_ROW_H = 82
    avail = H - y - pad
    row_h = min(IDEAL_ROW_H, max(34, avail // max(n, 1)))
    scale = row_h / IDEAL_ROW_H
    rank_w    = max(22, int(40 * scale))
    name_fs   = max(12, int(24 * scale))
    sub_fs    = max(10, int(18 * scale))
    time_fs   = max(12, int(24 * scale))
    badge_fs  = max(11, int(24 * scale))
    card_gap  = max(2,  int(6  * scale))

    content_h = n * row_h
    y_start = y + max(0, (avail - content_h) // 2)

    for i, row in enumerate(items):
        ry = y_start + i * row_h
        rank = i + 1
        mins = int(row.get("total_minutes") or 0)
        name = row.get("game_name", "?")
        count = row.get("player_count", 0)

        _draw_row_card(draw, pad, ry, W - pad, ry + row_h - card_gap, rank, theme)
        _draw_rank_badge(draw, pad + 10, ry + 4, rank_w, row_h - 14, rank, theme,
                         font_size=badge_fs)

        name_x = pad + rank_w + 22
        draw.text((name_x, ry + row_h // 2 - sub_fs),
                  name, font=_font(name_fs), fill=theme["text"], anchor="lm")
        draw.text((name_x, ry + row_h // 2 + sub_fs),
                  f"{count} Spieler", font=_font(sub_fs), fill=theme["dim"], anchor="lm")

        bar_w = int((mins / max_min) * (W - 2 * pad - 6))
        if bar_w > 0:
            draw.rounded_rectangle(
                [pad + 3, ry + row_h - card_gap - 3, pad + 3 + bar_w, ry + row_h - card_gap],
                radius=2, fill=theme["accent_dim"])

        draw.text((W - pad - 14, ry + row_h // 2),
                  _minutes_to_str(mins), font=_font(time_fs), fill=theme["accent"], anchor="rm")

    return img


# ---------------------------------------------------------------------------
# Sektion 3: Lieblingsspiel pro Spieler
# ---------------------------------------------------------------------------

def _build_lieblingsspiel(W, H, rows, pad, title, subtitle, theme):
    img = _gradient_bg(W, H, theme)
    draw = ImageDraw.Draw(img)

    y = _draw_header(img, draw, W, pad, title, subtitle, theme)
    y = _draw_section_title(draw, pad, y, W, pad, "Lieblingsspiel pro Spieler", theme)

    if not rows:
        draw.text((W // 2, y + 60), "Keine Daten",
                  font=_font(28), fill=theme["dim"], anchor="mt")
        return img

    n = len(rows)
    IDEAL_ROW_H = 86
    avail = H - y - pad
    row_h = min(IDEAL_ROW_H, max(34, avail // max(n, 1)))
    scale = row_h / IDEAL_ROW_H
    rank_w   = max(22, int(40 * scale))
    name_fs  = max(12, int(26 * scale))
    sub_fs   = max(10, int(20 * scale))
    time_fs  = max(12, int(24 * scale))
    badge_fs = max(11, int(24 * scale))
    card_gap = max(2,  int(6  * scale))

    content_h = n * row_h
    y_start = y + max(0, (avail - content_h) // 2)

    for i, row in enumerate(rows):
        ry = y_start + i * row_h
        rank = i + 1
        player = row.get("player", "?")
        game = row.get("game_name", "?")
        mins = int(row.get("minutes") or 0)
        medal = theme["medals"][i] if i < 3 else theme["text"]

        _draw_row_card(draw, pad, ry, W - pad, ry + row_h - card_gap, rank, theme)
        _draw_rank_badge(draw, pad + 10, ry + 4, rank_w, row_h - 14, rank, theme,
                         font_size=badge_fs)

        name_x = pad + rank_w + 22
        draw.text((name_x, ry + row_h // 2 - sub_fs),
                  player, font=_font(name_fs), fill=medal, anchor="lm")
        draw.text((name_x, ry + row_h // 2 + sub_fs),
                  game, font=_font(sub_fs), fill=theme["dim"], anchor="lm")

        draw.text((W - pad - 14, ry + row_h // 2),
                  _minutes_to_str(mins), font=_font(time_fs), fill=theme["text"], anchor="rm")

    return img


# ---------------------------------------------------------------------------
# Sektion 4: Ø Spielzeit pro Spiel
# ---------------------------------------------------------------------------

def _build_avg_spielzeit(W, H, rows, pad, title, subtitle, theme):
    img = _gradient_bg(W, H, theme)
    draw = ImageDraw.Draw(img)

    y = _draw_header(img, draw, W, pad, title, subtitle, theme)
    y = _draw_section_title(draw, pad, y, W, pad, "Ø Spielzeit pro Spiel", theme)

    if not rows:
        draw.text((W // 2, y + 60), "Keine Daten",
                  font=_font(28), fill=theme["dim"], anchor="mt")
        return img

    n = len(rows)
    IDEAL_ROW_H = 86
    avail = H - y - pad
    row_h = min(IDEAL_ROW_H, max(34, avail // max(n, 1)))
    scale = row_h / IDEAL_ROW_H
    rank_w   = max(22, int(40 * scale))
    name_fs  = max(12, int(26 * scale))
    sub_fs   = max(10, int(18 * scale))
    time_fs  = max(12, int(24 * scale))
    badge_fs = max(11, int(24 * scale))
    card_gap = max(2,  int(6  * scale))

    content_h = n * row_h
    y_start = y + max(0, (avail - content_h) // 2)

    for i, row in enumerate(rows):
        ry = y_start + i * row_h
        rank = i + 1
        player = row.get("player", "?")
        avg_min = float(row.get("avg_minutes_per_game") or 0)
        count = row.get("games_played", 0)

        _draw_row_card(draw, pad, ry, W - pad, ry + row_h - card_gap, rank, theme)
        _draw_rank_badge(draw, pad + 10, ry + 4, rank_w, row_h - 14, rank, theme,
                         font_size=badge_fs)

        name_x = pad + rank_w + 22
        draw.text((name_x, ry + row_h // 2 - sub_fs),
                  player, font=_font(name_fs), fill=theme["text"], anchor="lm")
        draw.text((name_x, ry + row_h // 2 + sub_fs),
                  f"{count} Spiele", font=_font(sub_fs), fill=theme["dim"], anchor="lm")

        draw.text((W - pad - 14, ry + row_h // 2),
                  f"Ø {_minutes_to_str(avg_min)}", font=_font(time_fs),
                  fill=theme["accent"], anchor="rm")

    return img


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------

def _all_sections(W, H, pad, days, period_label, theme):
    title = "Steam Rangliste"

    playtime  = get_total_playtime_ranking(days)
    top_games = get_most_played_game_overall(days)
    fav_game  = get_most_played_game_per_player(days)
    avg_time  = get_avg_playtime_per_game(days)

    return [
        _build_spielzeit(W, H, playtime, pad, title, period_label, theme),
        _build_top_spiele(W, H, top_games, pad, title, period_label, theme),
        _build_lieblingsspiel(W, H, fav_game, pad, title, period_label, theme),
        _build_avg_spielzeit(W, H, avg_time, pad, title, period_label, theme),
    ]


def add_story_text_overlay(img, text, y_rel=0.78):
    """
    Zeichnet einen Instagram-ähnlichen Textsticker auf ein Story-Bild.

    img    – PIL.Image (wird in-place verändert, Kopie wird zurückgegeben)
    text   – Anzuzeigender Text
    y_rel  – Relative Y-Position des Sticker-Mittelpunkts (0–1), Standard 78 % von oben
    """
    W, H = img.size
    img = img.copy()

    pad_x, pad_y = 32, 22
    max_pill_w = W - 40  # 20px Rand links und rechts

    # Schriftgröße automatisch verkleinern, bis der Text passt
    font_size = 36
    while font_size >= 18:
        font = _font(font_size)
        tmp_draw = ImageDraw.Draw(img)
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        if tw + pad_x * 2 <= max_pill_w:
            break
        font_size -= 2

    th = bbox[3] - bbox[1]
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    cx = W // 2
    cy = int(H * y_rel)

    # Hintergrund-Pill (semi-transparent schwarz) via RGBA-Overlay
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [cx - pill_w // 2, cy - pill_h // 2,
         cx + pill_w // 2, cy + pill_h // 2],
        radius=pill_h // 2,
        fill=(0, 0, 0, 175),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # Text zentriert auf dem Pill
    draw = ImageDraw.Draw(img)
    draw.text((cx, cy), text, font=font, fill=WHITE, anchor="mm")

    return img


def render_post_images(days, period_label, theme=None):
    """Gibt 4 PIL.Image-Objekte (1080×1080) zurück."""
    theme = theme or THEME_WEEKLY
    return _all_sections(W=1080, H=1080, pad=40, days=days,
                         period_label=period_label, theme=theme)


def render_story_images(days, period_label, theme=None):
    """Gibt 4 PIL.Image-Objekte (720×1280) zurück."""
    theme = theme or THEME_WEEKLY
    return _all_sections(W=720, H=1280, pad=30, days=days,
                         period_label=period_label, theme=theme)
