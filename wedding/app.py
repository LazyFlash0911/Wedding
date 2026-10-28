import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import lru_cache
from html import escape as html_escape
from pathlib import Path
from urllib.parse import urlencode

import click
import qrcode
import qrcode.image.svg
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    get_flashed_messages,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, URLSafeTimedSerializer
from markupsafe import Markup
from PIL import Image, ImageOps
from werkzeug.middleware.proxy_fix import ProxyFix

PROJECT_FOLDER = Path(__file__).resolve().parent
STATIC_FOLDER = PROJECT_FOLDER / "static"
IMAGE_FOLDER = STATIC_FOLDER / "images"
GENERATED_FOLDER = STATIC_FOLDER / "generated"
# Vercel's deployment folder is read-only; only /tmp is writable (and it is temporary).
ON_VERCEL = bool(os.environ.get("VERCEL"))
INSTANCE_FOLDER = Path("/tmp/instance") if ON_VERCEL else PROJECT_FOLDER / "instance"
WISHES_DB = INSTANCE_FOLDER / "wishes.db"


def load_secret_key():
    # Production (Vercel): use the env var
    key = os.environ.get("SECRET_KEY")
    if key:
        return key

    # Local dev: persist a key in instance/
    try:
        INSTANCE_FOLDER.mkdir(exist_ok=True)
        key_file = INSTANCE_FOLDER / "secret_key"
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_hex(32)
        key_file.write_text(key)
        return key
    except OSError:
        # Read-only filesystem and no env var: fail with a clear message
        raise RuntimeError("Set the SECRET_KEY environment variable.")


# Optional: the public address of the site (e.g. https://priyanka-ankoosh.in), used for
# WhatsApp link previews and QR codes. Defaults to the address the page was opened with.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

# Optional: a password for /admin/wishes, where inappropriate wishes can be removed.
# The admin page is switched off while this is empty.
WISHES_ADMIN_PASSWORD = os.environ.get("WISHES_ADMIN_PASSWORD", "")

# Guest blessings stay hidden until the couple approve them. Each new blessing is emailed to
# NOTIFY_EMAIL (several addresses can be separated by commas) with a private approve / reject link.
# For Gmail, SMTP_PASSWORD must be an "app password" (Google Account > Security > App passwords).
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "") or SMTP_USER
# Alternative to SMTP: send the email through Resend's web API (works where Gmail's SMTP is refused).
# Without a verified domain, Resend only delivers to the address you signed up with, so use that as NOTIFY_EMAIL.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "") or "Wedding invitation <onboarding@resend.dev>"
WISH_REVIEW_MAX_AGE = 60 * 60 * 24 * 30  # review links stop working after 30 days

# Vercel's /tmp is wiped regularly, so on Vercel blessings must live in a real database.
# Add a free Postgres (e.g. Neon from the Vercel Marketplace); it sets DATABASE_URL for you.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or ""

app = Flask(__name__)
app.secret_key = load_secret_key()
app.config.update(
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SITE_URL.startswith("https://"),
)
# Hosting platforms put the app behind a proxy; this keeps https:// in generated links.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

IST = timezone(timedelta(hours=5, minutes=30))
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_SIZES = {"thumb": 600, "medium": 1100, "large": 1920}

WEDDING = {
    "partner_one": "Ankoosh Yadav",
    "partner_one_hi": "अंकुश यादव",
    "partner_two": "Priyanka Yadav",
    "partner_two_hi": "प्रियंका यादव",
    "date_text": "Wednesday, 9 December 2026",
    "date_text_hi": "बुधवार, 9 दिसंबर 2026",
    "date_iso": "2026-12-09T17:00:00+05:30",
    "venue": "coco-island",
    "ceremony_time": "5:00 PM onwards",
    "ceremony_time_hi": "शाम 5:00 बजे से",
}

VENUES = {
    "club-aquaria": {
        "name": "Club Aquaria",
        "name_hi": "क्लब एक्वेरिया",
        "address": "Club Aquaria, Shanti Ashram, Devidas Cross Ln, near St.Lawrence High School, LIC Colony, Borivali West, Mumbai, Maharashtra 400103",
        "tip": "Nearest local station: Borivali (Western line).",
        "tip_hi": "नज़दीकी लोकल स्टेशन: बोरीवली (वेस्टर्न लाइन)।",
    },
    "sai-palace": {
        "name": "Hotel Sai Palace Grand",
        "name_hi": "होटल साई पैलेस ग्रैंड",
        "address": "Hotel Sai Palace Grand, Link Rd, Malad, Evershine Nagar, Malad West, Mumbai, Maharashtra 400064",
        "tip": "Nearest local station: Malad (Western line).",
        "tip_hi": "नज़दीकी लोकल स्टेशन: मलाड (वेस्टर्न लाइन)।",
    },
    "coco-island": {
        "name": "Coco Island",
        "name_hi": "कोको आइलैंड",
        "address": "Coco Island, Marve Village, Malad West, Malad, Mumbai, Maharashtra 400095",
        "tip": "Nearest local station: Malad (Western line), then a cab or auto towards Marve.",
        "tip_hi": "नज़दीकी लोकल स्टेशन: मलाड (वेस्टर्न लाइन), वहाँ से मार्वे की ओर कैब या ऑटो लें।",
    },
}

# start/end are used for "Add to calendar". End times are estimates; adjust as needed.
EVENTS = [
    {
        "id": "sangeet",
        "name": "Sangeet",
        "name_hi": "संगीत",
        "subtitle": "One evening, two hearts, endless dancing",
        "subtitle_hi": "एक शाम, दो दिल, अनगिनत थिरकते कदम",
        "date": "Monday, 7 December 2026",
        "date_hi": "सोमवार, 7 दिसंबर 2026",
        "time": "6:00 PM",
        "time_hi": "शाम 6:00 बजे",
        "start": datetime(2026, 12, 7, 18, 0, tzinfo=IST),
        "end": datetime(2026, 12, 7, 23, 0, tzinfo=IST),
        "venue": "club-aquaria",
        "icon": "♪",
        "description": "An evening of music, dance, laughter, and celebration with both families.",
        "description_hi": "दोनों परिवारों के साथ संगीत, नृत्य, हँसी और उत्सव से भरी एक शाम।",
        "dress_code": "Festive glam: Indo-western, lehengas or sharp kurtas\nColors: Refer to the Image attached",
        "dress_code_hi": "उत्सवी अंदाज़: इंडो-वेस्टर्न, लहंगा या शानदार कुर्ता\nरंग: संलग्न छवि देखें",
        "accent": "plum",
    },
    {
        "id": "groom-haldi",
        "name": "Ankoosh's Haldi",
        "name_hi": "अंकुश की हल्दी",
        "subtitle": "A golden beginning for the groom",
        "subtitle_hi": "दूल्हे के लिए एक सुनहरी शुरुआत",
        "date": "Tuesday, 8 December 2026",
        "date_hi": "मंगलवार, 8 दिसंबर 2026",
        "time": "6:00 PM",
        "time_hi": "शाम 6:00 बजे",
        "start": datetime(2026, 12, 8, 18, 0, tzinfo=IST),
        "end": datetime(2026, 12, 8, 22, 0, tzinfo=IST),
        "venue": "club-aquaria",
        "icon": "✿",
        "description": "Traditional rituals, joyful blessings, and happy moments with Ankoosh's loved ones.",
        "description_hi": "अंकुश के अपनों के साथ पारंपरिक रस्में, आशीर्वाद और खुशियों भरे पल।",
        "dress_code": "Wear something you don't mind getting haldi on\nColors: Refer to the Image attached",
        "dress_code_hi": "पीले रंग के परिधान: ऐसे कपड़े पहनें जिन पर हल्दी लग जाए तो चिंता न हो\nरंग: संलग्न छवि देखें",
        "accent": "gold",
    },
    {
        "id": "bride-haldi",
        "name": "Priyanka's Haldi",
        "name_hi": "प्रियंका की हल्दी",
        "subtitle": "A golden beginning for the bride",
        "subtitle_hi": "दुल्हन के लिए एक सुनहरी शुरुआत",
        "date": "Wednesday, 9 December 2026",
        "date_hi": "बुधवार, 9 दिसंबर 2026",
        "time": "9:00 AM",
        "time_hi": "सुबह 9:00 बजे",
        "start": datetime(2026, 12, 9, 9, 0, tzinfo=IST),
        "end": datetime(2026, 12, 9, 12, 0, tzinfo=IST),
        "venue": "sai-palace",
        "icon": "✿",
        "description": "A beautiful morning of flowers, traditional rituals, and family blessings for Priyanka.",
        "description_hi": "प्रियंका के लिए फूलों, पारंपरिक रस्मों और परिवार के आशीर्वाद से सजी एक सुंदर सुबह।",
        "dress_code": "Wear something you don't mind getting haldi on\nColors: Refer to the Image attached",
        "dress_code_hi": "ऐसे कपड़े पहनें जिन पर हल्दी लग जाए तो चिंता न हो\nरंग: संलग्न छवि देखें",
        "accent": "marigold",
    },
    {
        "id": "wedding",
        "name": "The Wedding",
        "name_hi": "शुभ विवाह",
        "subtitle": "Two families, one forever",
        "subtitle_hi": "दो परिवार, एक नया सफ़र",
        "date": "Wednesday, 9 December 2026",
        "date_hi": "बुधवार, 9 दिसंबर 2026",
        "time": "5:00 PM onwards",
        "time_hi": "शाम 5:00 बजे से",
        "start": datetime(2026, 12, 9, 17, 0, tzinfo=IST),
        "end": datetime(2026, 12, 9, 23, 0, tzinfo=IST),
        "venue": "coco-island",
        "icon": "❦",
        "description": "Join us as we take our pheras and begin our new life together, surrounded by the people we love.",
        "description_hi": "अपनों के बीच हमारे फेरों और नए जीवन की शुरुआत के साक्षी बनें।",
        "dress_code": "Traditional Indian attire",
        "dress_code_hi": "पारंपरिक भारतीय परिधान",
        "accent": "crimson",
    },
]
EVENTS_BY_ID = {event["id"]: event for event in EVENTS}

# Optional names shown under each family portrait, e.g. "Mr. & Mrs. Yadav".
# Photos are read from static/images/<id>-1.jpg, <id>-2.jpg, ...
FAMILY_GROUPS = [
    {"id": "groom-parents", "title": "Groom's Parents", "title_hi": "दूल्हे के माता-पिता", "names": "", "names_hi": ""},
    {"id": "bride-parents", "title": "Bride's Parents", "title_hi": "दुल्हन के माता-पिता", "names": "", "names_hi": ""},
    {"id": "groom-siblings", "title": "Groom's Siblings", "title_hi": "दूल्हे के भाई-बहन", "names": "", "names_hi": ""},
    {"id": "bride-siblings", "title": "Bride's Siblings", "title_hi": "दुल्हन के भाई-बहन", "names": "", "names_hi": ""},
    {"id": "groom-grandparents", "title": "Groom's Grandparents", "title_hi": "दूल्हे के दादा-दादी", "names": "", "names_hi": ""},
    {"id": "bride-family", "title": "Bride's Family", "title_hi": "दुल्हन का परिवार", "names": "", "names_hi": ""},
    {"id": "groom-family", "title": "Groom's Family", "title_hi": "दूल्हे का परिवार", "names": "", "names_hi": ""},
]

# The two cards in "Meet the family". Each opens a pop-up with all photos of its groups, in this order.
# Photos still come from static/images/<group id>-1.jpg, <group id>-2.jpg, ... (see FAMILY_GROUPS).
FAMILY_SIDES = [
    {
        "id": "groom",
        "title": "Groom's Family",
        "title_hi": "दूल्हे का परिवार",
        "groups": ["groom-parents", "groom-siblings", "groom-grandparents", "groom-family"],
    },
    {
        "id": "bride",
        "title": "Bride's Family",
        "title_hi": "दुल्हन का परिवार",
        "groups": ["bride-parents", "bride-siblings", "bride-family"],
    },
]

# Most photos shown in each family pop-up. Extra photos are ignored, starting from the end of the list.
MAX_FAMILY_PHOTOS = 10

# Captions for static/images/couple-1.jpg, couple-2.jpg, ... in order.
MEMORY_CAPTIONS = [
    {
        "title": "A little bit of magic",
        "title_hi": "थोड़ा सा जादू",
        "caption": "Every love story is beautiful, but ours is our favourite.",
        "caption_hi": "हर प्रेम कहानी खूबसूरत होती है, पर हमारी हमें सबसे प्यारी है।",
    },
    {
        "title": "Our favourite memories",
        "title_hi": "हमारी सबसे प्यारी यादें",
        "caption": "Little moments that turned into the best chapters of our story.",
        "caption_hi": "छोटे-छोटे पल, जो हमारी कहानी के सबसे खूबसूरत अध्याय बन गए।",
    },
    {
        "title": "The beginning of forever",
        "title_hi": "हमेशा की शुरुआत",
        "caption": "Hand in hand, ready for the adventure of a lifetime.",
        "caption_hi": "हाथों में हाथ, ज़िंदगी भर के सफ़र के लिए तैयार।",
    },
]

# Google Drive album links. Leave "url" empty until an album is ready to share.
# PHOTO_ALBUMS = [
#     {
#         "id": "pre-wedding",
#         "title": "Pre-wedding",
#         "title_hi": "प्री-वेडिंग",
#         "url": "https://drive.google.com/drive/folders/1nMtn7yWR-Tb8Q5sLMuur7yge8txNjLIs?usp=drive_link",
#     },
#     {
#         "id": "engagement",
#         "title": "Engagement",
#         "title_hi": "सगाई",
#         "url": "https://drive.google.com/drive/folders/1jylBAKrPNjuR-6OotSnrbMc2mDB5xFb0?usp=drive_link",
#     },
#     {"id": "wedding", "title": "Wedding", "title_hi": "विवाह", "url": ""},
# ]

# Optional hotels for out-of-town guests. Each section is hidden while its list is empty.
# Example: {"name": "Hotel Name", "note": "5 min from Coco Island", "note_hi": "...", "url": "https://..."}
STAYS = []

# Optional contacts for guests. Example: {"name": "Rahul (Groom's brother)", "name_hi": "...", "phone": "+91 98xxxxxxxx"}
CONTACTS = []

# Messages flashed after a wish is submitted, in both languages.
FLASH_MESSAGES = {
    "wish-saved": ("Thank you! Your blessing will appear here once we have approved it.", "धन्यवाद! हमारी स्वीकृति के बाद आपका आशीर्वाद यहाँ दिखाई देगा।"),
    "wish-missing": ("Please add your name and a message.", "कृपया अपना नाम और संदेश लिखें।"),
    "wish-too-long": ("Please keep your name under 60 and your message under 500 characters.", "कृपया नाम 60 और संदेश 500 अक्षरों से कम रखें।"),
    "wish-too-soon": ("Please wait a moment before sending another blessing.", "कृपया अगला संदेश भेजने से पहले थोड़ा रुकें।"),
}
MAX_WISH_NAME = 60
MAX_WISH_MESSAGE = 500


def needs_build(target, source):
    """True if a generated image must be (re)created. On Vercel, ship pre-generated files and never rebuild."""
    if not target.is_file():
        return not ON_VERCEL
    if ON_VERCEL:
        return False
    return target.stat().st_mtime < source.stat().st_mtime


def natural_key(filename):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", filename)]


def list_images(prefix):
    try:
        filenames = os.listdir(IMAGE_FOLDER)
    except OSError:
        return []
    return sorted(
        (
            name
            for name in filenames
            if name.casefold().startswith(prefix)
            and Path(name).suffix.lower() in IMAGE_EXTENSIONS
            and (IMAGE_FOLDER / name).is_file()
        ),
        key=natural_key,
    )


def save_jpeg(image, target):
    temporary = target.with_name(f"{target.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
    image.save(temporary, "JPEG", quality=82, optimize=True, progressive=True)
    os.replace(temporary, target)


def web_image(filename, size):
    """Static path of a resized, correctly rotated copy of an image, created on first use."""
    source = IMAGE_FOLDER / filename
    target = GENERATED_FOLDER / f"{Path(filename).stem}-{size}.jpg"
    try:
        if needs_build(target, source):
            GENERATED_FOLDER.mkdir(exist_ok=True)
            max_side = IMAGE_SIZES[size]
            with Image.open(source) as image:
                image.draft("RGB", (max_side, max_side))
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((max_side, max_side))
                save_jpeg(image, target)
    except OSError:
        app.logger.exception("Could not resize %s", filename)
        return f"images/{filename}"
    if not target.is_file():  # e.g. read-only host with no pre-generated copy
        return f"images/{filename}"
    return f"generated/{target.name}"


def share_image(filename):
    """A 1200×630 crop for WhatsApp and social link previews."""
    source = IMAGE_FOLDER / filename
    target = GENERATED_FOLDER / "share-preview.jpg"
    try:
        if needs_build(target, source):
            GENERATED_FOLDER.mkdir(exist_ok=True)
            with Image.open(source) as image:
                image.draft("RGB", (2400, 2400))
                image = ImageOps.exif_transpose(image).convert("RGB")
                save_jpeg(ImageOps.fit(image, (1200, 630), centering=(0.5, 0.4)), target)
    except OSError:
        app.logger.exception("Could not create the share preview image")
        return None
    if not target.is_file():
        return f"images/{filename}"
    return f"generated/{target.name}"


def touch_icon(filename):
    """A square icon for phones' home screens and bookmarks."""
    source = IMAGE_FOLDER / filename
    target = GENERATED_FOLDER / "touch-icon.png"
    try:
        if needs_build(target, source):
            GENERATED_FOLDER.mkdir(exist_ok=True)
            with Image.open(source) as image:
                image.draft("RGB", (720, 720))
                image = ImageOps.exif_transpose(image).convert("RGB")
                ImageOps.fit(image, (180, 180), centering=(0.5, 0.3)).save(target, "PNG", optimize=True)
    except OSError:
        app.logger.exception("Could not create the touch icon")
        return None
    if not target.is_file():
        return f"images/{filename}"
    return f"generated/{target.name}"


def prepare_images():
    """Resize every photo ahead of time, so the first guest to open the link doesn't wait."""
    couple = list_images("couple-")
    for name in couple:
        web_image(name, "medium")
        web_image(name, "large")
    for group in FAMILY_GROUPS:
        for name in list_images(f"{group['id']}-"):
            web_image(name, "thumb")
            web_image(name, "large")
    if couple:
        share_image(couple[0])
        touch_icon(couple[0])


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_valid():
    return hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf", ""))


app.jinja_env.globals["csrf_token"] = csrf_token


def site_url():
    return SITE_URL or request.url_root.rstrip("/")


def absolute_static(path):
    return site_url() + url_for("static", filename=path)


def utc_stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def google_calendar_url(event):
    venue = VENUES[event["venue"]]
    return "https://calendar.google.com/calendar/render?" + urlencode(
        {
            "action": "TEMPLATE",
            "text": f"{event['name']} · Ankoosh & Priyanka",
            "dates": f"{utc_stamp(event['start'])}/{utc_stamp(event['end'])}",
            "details": event["description"],
            "location": venue["address"],
        }
    )


def get_family_groups():
    groups = []
    for group in FAMILY_GROUPS:
        photos = [
            {"thumb": web_image(name, "thumb"), "large": web_image(name, "large")}
            for name in list_images(f"{group['id']}-")
        ]
        if photos:
            groups.append({**group, "photos": photos})
    return groups


def get_family_sides():
    """One entry per card: a cover photo plus every photo (and caption) shown in its pop-up."""
    groups = {group["id"]: group for group in get_family_groups()}
    sides = []
    for side in FAMILY_SIDES:
        photos = []
        for group_id in side["groups"]:
            group = groups.get(group_id)
            if not group:
                continue
            caption = group["title"] + (f" · {group['names']}" if group["names"] else "")
            caption_hi = group["title_hi"] + (f" · {group['names_hi'] or group['names']}" if group["names"] else "")
            for photo in group["photos"]:
                photos.append(
                    {
                        "src": url_for("static", filename=photo["large"]),
                        "thumb": url_for("static", filename=photo["thumb"]),
                        "caption": caption,
                        "caption_hi": caption_hi,
                    }
                )
        if photos:
            sides.append({**side, "photos": photos, "cover": photos[0]["thumb"]})
    return sides


def get_memories():
    memories = []
    for index, name in enumerate(list_images("couple-")):
        caption = MEMORY_CAPTIONS[index] if index < len(MEMORY_CAPTIONS) else {}
        memories.append(
            {
                "file": name,
                "src": url_for("static", filename=web_image(name, "medium")),
                "large": url_for("static", filename=web_image(name, "large")),
                "title": caption.get("title", ""),
                "title_hi": caption.get("title_hi", ""),
                "caption": caption.get("caption", ""),
                "caption_hi": caption.get("caption_hi", ""),
            }
        )
    return memories


def get_event_days():
    days = []
    for event in sorted(EVENTS, key=lambda item: item["start"]):
        if not days or days[-1]["date"] != event["date"]:
            days.append({"date": event["date"], "date_hi": event["date_hi"], "events": []})
        days[-1]["events"].append({**event, "google_calendar_url": google_calendar_url(event)})
    return days


def get_venues():
    return [
        {**venue, "id": venue_id, "events": [event for event in EVENTS if event["venue"] == venue_id]}
        for venue_id, venue in VENUES.items()
    ]


def get_db():
    if "db" not in g:
        if DATABASE_URL:
            import psycopg
            from psycopg.rows import dict_row

            # prepare_threshold=None keeps this working behind a pooled (pgbouncer) connection string.
            connection = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None, connect_timeout=10)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS wishes ("
                "id SERIAL PRIMARY KEY, name TEXT NOT NULL, message TEXT NOT NULL, "
                "created_at TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)"
            )
        else:
            INSTANCE_FOLDER.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(WISHES_DB)
            connection.row_factory = sqlite3.Row
            connection.execute(
                "CREATE TABLE IF NOT EXISTS wishes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
                "message TEXT NOT NULL, created_at TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)"
            )
            columns = [row["name"] for row in connection.execute("PRAGMA table_info(wishes)")]
            if "approved" not in columns:  # database from before approvals: keep those blessings visible
                connection.execute("ALTER TABLE wishes ADD COLUMN approved INTEGER NOT NULL DEFAULT 1")
        connection.commit()
        g.db = connection
    return g.db


def db_execute(sql, params=()):
    """Run a query on either database; write queries with ? placeholders."""
    if DATABASE_URL:
        sql = sql.replace("?", "%s")
    return get_db().execute(sql, params)


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.get("/")
def index():
    memories = get_memories()
    preview = share_image(memories[0]["file"]) if memories else None
    icon = touch_icon(memories[0]["file"]) if memories else None
    flashes = [
        {"category": category, "en": FLASH_MESSAGES[key][0], "hi": FLASH_MESSAGES[key][1]}
        for category, key in get_flashed_messages(with_categories=True)
        if key in FLASH_MESSAGES
    ]
    wishes = db_execute(
        "SELECT name, message FROM wishes WHERE approved = 1 ORDER BY id DESC LIMIT 60"
    ).fetchall()
    music_file = STATIC_FOLDER / "music.mp3"
    return render_template(
        "index.html",
        wedding=WEDDING,
        wedding_venue=VENUES[WEDDING["venue"]],
        wedding_event=EVENTS_BY_ID["wedding"],
        wedding_calendar_url=google_calendar_url(EVENTS_BY_ID["wedding"]),
        event_days=get_event_days(),
        venues=get_venues(),
        family_sides=get_family_sides(),
        memories=memories,
        albums=[],  # PHOTO_ALBUMS disabled
        # albums=PHOTO_ALBUMS,
        stays=STAYS,
        contacts=CONTACTS,
        wishes=wishes,
        flashes=flashes,
        page_url=site_url() + "/",
        preview_image_url=absolute_static(preview) if preview else None,
        touch_icon_url=url_for("static", filename=icon) if icon else None,
        music_url=url_for("static", filename="music.mp3") if music_file.is_file() else None,
    )


@app.post("/wishes")
def add_wish():
    back = redirect(url_for("index") + "#wishes")
    if request.form.get("website") or not csrf_valid():  # Bots fill the hidden field; forged posts lack the token.
        return back

    name = " ".join(request.form.get("name", "").split())
    message = request.form.get("message", "").strip()
    if not name or not message:
        flash("wish-missing", "error")
        return back
    if len(name) > MAX_WISH_NAME or len(message) > MAX_WISH_MESSAGE:
        flash("wish-too-long", "error")
        return back
    if time.time() - session.get("last_wish_at", 0) < 30:
        flash("wish-too-soon", "error")
        return back

    cursor = db_execute(
        "INSERT INTO wishes (name, message, created_at, approved) VALUES (?, ?, ?, 0)"
        + (" RETURNING id" if DATABASE_URL else ""),
        (name, message, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    wish_id = cursor.fetchone()["id"] if DATABASE_URL else cursor.lastrowid
    get_db().commit()
    send_review_email(wish_id, name, message)
    session["last_wish_at"] = time.time()
    flash("wish-saved", "success")
    return back


def review_serializer():
    return URLSafeTimedSerializer(app.secret_key, salt="wish-review")


def report(text):
    """Write a line straight to the runtime logs (Vercel shows stderr), without any buffering."""
    print(text, file=sys.stderr, flush=True)


def send_review_email(wish_id, name, message):
    """Email the couple a private link to approve or reject a new blessing. Never raises."""
    link = site_url() + url_for("review_wish", token=review_serializer().dumps(wish_id))
    use_resend = bool(RESEND_API_KEY)
    settings = [("NOTIFY_EMAIL", NOTIFY_EMAIL)]
    settings += [("RESEND_API_KEY", RESEND_API_KEY)] if use_resend else [("SMTP_USER", SMTP_USER), ("SMTP_PASSWORD", SMTP_PASSWORD)]
    missing = [setting for setting, value in settings if not value]
    if missing:
        report(f"EMAIL NOT SENT for blessing {wish_id}: these settings are empty: {', '.join(missing)}. Review link: {link}")
        return False

    subject = f"New blessing from {name} - approve?"
    text_body = (
        f"{name} left a blessing on your wedding website:\n\n"
        f"\"{message}\"\n\n"
        f"Approve or reject it here:\n{link}\n\n"
        "It stays hidden on the website until you approve it."
    )
    html_body = (
        f"<p><b>{html_escape(name)}</b> left a blessing on your wedding website:</p>"
        f"<blockquote style=\"margin:12px 0;padding-left:12px;border-left:3px solid #a45f70\">"
        f"{html_escape(message).replace(chr(10), '<br>')}</blockquote>"
        f"<p><a href=\"{html_escape(link)}\" style=\"display:inline-block;padding:10px 18px;background:#a45f70;"
        f"color:#fff;text-decoration:none;border-radius:999px\">Approve or reject</a></p>"
        "<p style=\"color:#777\">It stays hidden on the website until you approve it.</p>"
    )
    stage = "connecting"
    where = "Resend" if use_resend else f"{SMTP_HOST}:{SMTP_PORT}"
    try:
        if use_resend:
            stage = "calling the Resend API"
            api_request = urllib.request.Request(
                "https://api.resend.com/emails",
                data=json.dumps({
                    "from": RESEND_FROM,
                    "to": [address.strip() for address in NOTIFY_EMAIL.split(",") if address.strip()],
                    "subject": subject,
                    "text": text_body,
                    "html": html_body,
                }).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "wedding-invitation/1.0",
                },
            )
            with urllib.request.urlopen(api_request, timeout=10) as response:
                response.read()
        else:
            mail = EmailMessage()
            mail["Subject"] = subject
            mail["From"] = MAIL_FROM
            mail["To"] = NOTIFY_EMAIL
            mail.set_content(text_body)
            mail.add_alternative(html_body, subtype="html")
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) if SMTP_PORT == 465 else smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            with server:
                if SMTP_PORT != 465:
                    stage = "starting TLS"
                    server.starttls()
                stage = "logging in"
                server.login(SMTP_USER, SMTP_PASSWORD)
                stage = "sending"
                server.send_message(mail)
        report(f"Review email sent for blessing {wish_id} to {NOTIFY_EMAIL} via {where}")
        return True
    except Exception as error:  # a failed email must never break the guest's submission
        detail = f"{type(error).__name__}: {error}"
        if isinstance(error, urllib.error.HTTPError):
            try:
                detail += " - " + error.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
        report(f"EMAIL NOT SENT for blessing {wish_id} while {stage} ({where}): {detail}. Review link: {link}")
        return False


REVIEW_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Review a blessing</title>
<style>
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 20px; background: #f6e6e8; color: #4a2c36; font: 17px/1.5 Georgia, serif; }
  main { width: min(100%, 460px); padding: 28px 24px; background: #fff; border-radius: 22px; box-shadow: 0 14px 34px rgba(110, 60, 75, .18); text-align: center; }
  blockquote { margin: 1rem 0; font-style: italic; white-space: pre-wrap; overflow-wrap: anywhere; }
  .from { color: #a45f70; }
  .buttons { display: flex; gap: 12px; justify-content: center; margin-top: 1.4rem; }
  button { padding: 12px 22px; border: 0; border-radius: 999px; font: inherit; cursor: pointer; }
  .approve { background: #a45f70; color: #fff; }
  .reject { background: #eadbde; color: #4a2c36; }
</style></head>
<body><main>
{% if result == "approved" %}
  <h1>Approved &#10084;</h1><p>This blessing is now showing on your website.</p>
{% elif result == "rejected" %}
  <h1>Removed</h1><p>This blessing has been deleted and will not appear.</p>
{% elif not wish %}
  <h1>Not found</h1><p>This blessing is no longer here. It may already have been removed.</p>
{% elif wish["approved"] %}
  <h1>Already approved</h1><blockquote>{{ wish["message"] }}</blockquote><p class="from">&mdash; {{ wish["name"] }}</p>
{% else %}
  <h1>New blessing</h1>
  <blockquote>{{ wish["message"] }}</blockquote>
  <p class="from">&mdash; {{ wish["name"] }}</p>
  <form method="post" class="buttons">
    <button class="approve" type="submit" name="action" value="approve">Approve</button>
    <button class="reject" type="submit" name="action" value="reject">Reject</button>
  </form>
{% endif %}
</main></body></html>"""


@app.route("/wishes/review/<token>", methods=["GET", "POST"])
def review_wish(token):
    """Private page opened from the email. The signed link is the password; it expires after 30 days."""
    try:
        wish_id = review_serializer().loads(token, max_age=WISH_REVIEW_MAX_AGE)
    except BadSignature:  # also covers expired links
        abort(404)
    wish = db_execute("SELECT id, name, message, approved FROM wishes WHERE id = ?", (wish_id,)).fetchone()
    result = None
    # Approving needs a button press (POST), so email scanners that just open links can't approve by accident.
    if wish and request.method == "POST":
        action = request.form.get("action")
        if action == "approve":
            db_execute("UPDATE wishes SET approved = 1 WHERE id = ?", (wish_id,))
            result = "approved"
        elif action == "reject":
            db_execute("DELETE FROM wishes WHERE id = ?", (wish_id,))
            result = "rejected"
        get_db().commit()
    page = render_template_string(REVIEW_PAGE, wish=wish, result=result)
    return page, 200, {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}


def admin_enabled():
    return bool(WISHES_ADMIN_PASSWORD)


@app.route("/admin/wishes", methods=["GET", "POST"])
def admin_wishes():
    """Phone-friendly page for the couple to remove inappropriate wishes."""
    if not admin_enabled():
        abort(404)
    error = None
    if request.method == "POST":
        if not csrf_valid():
            abort(400)
        if hmac.compare_digest(request.form.get("password", ""), WISHES_ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_wishes"))
        time.sleep(1)  # Slow down password guessing.
        error = "That password is not correct."
    wishes = []
    if session.get("admin"):
        wishes = db_execute(
            "SELECT id, name, message, created_at FROM wishes ORDER BY id DESC"
        ).fetchall()
    return render_template("admin_wishes.html", wishes=wishes, logged_in=session.get("admin", False), error=error)


@app.post("/admin/wishes/<int:wish_id>/delete")
def admin_delete_wish(wish_id):
    if not admin_enabled() or not session.get("admin"):
        abort(404)
    if not csrf_valid():
        abort(400)
    db_execute("DELETE FROM wishes WHERE id = ?", (wish_id,))
    get_db().commit()
    return redirect(url_for("admin_wishes"))


@app.post("/admin/logout")
def admin_logout():
    if csrf_valid():
        session.pop("admin", None)
    return redirect(url_for("index"))


def ics_escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    """Fold calendar lines to 75 bytes, as the iCalendar format requires."""
    parts, current = [], ""
    for character in line:
        limit = 75 if not parts else 74
        if len((current + character).encode("utf-8")) > limit:
            parts.append(current)
            current = character
        else:
            current += character
    parts.append(current)
    return "\r\n ".join(parts)


@app.get("/calendar/<event_id>.ics")
def event_calendar(event_id):
    event = EVENTS_BY_ID.get(event_id) or abort(404)
    venue = VENUES[event["venue"]]
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ankoosh & Priyanka//Wedding Invitation//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event_id}-2026@priyanka-ankoosh-wedding",
        f"DTSTAMP:{utc_stamp(datetime.now(timezone.utc))}",
        f"DTSTART:{utc_stamp(event['start'])}",
        f"DTEND:{utc_stamp(event['end'])}",
        f"SUMMARY:{ics_escape(event['name'] + ' · Ankoosh & Priyanka')}",
        f"LOCATION:{ics_escape(venue['address'])}",
        f"DESCRIPTION:{ics_escape(event['description'])}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    body = "\r\n".join(ics_fold(line) for line in lines) + "\r\n"
    return Response(
        body,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{event_id}.ics"'},
    )


def qr_svg(data):
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    return Markup(image.to_string(encoding="unicode"))


@app.get("/qr")
def qr_codes():
    """Printable QR cards for the venue: the invitation and each shared photo album."""
    invitation_url = site_url() + "/"
    codes = [
        {
            "title": "Our wedding invitation",
            "subtitle": "Scan to open the invitation",
            "url": invitation_url,
            "svg": qr_svg(invitation_url),
        }
    ]
#     codes += [
#         {
#             "title": f"{album['title']} photos",
#             "subtitle": "Scan to view the album",
#             "url": album["url"],
#             "svg": qr_svg(album["url"]),
#         }
#         for album in PHOTO_ALBUMS
#         if album["url"]
#     ]
    return render_template("qr.html", codes=codes)


@app.cli.command("list-wishes")
def list_wishes_command():
    """Show all guest wishes with their IDs and whether they are approved."""
    with app.app_context():
        for row in db_execute("SELECT id, created_at, name, message, approved FROM wishes ORDER BY id"):
            status = "approved" if row["approved"] else "PENDING"
            click.echo(f"{row['id']}\t{status}\t{row['created_at']}\t{row['name']}: {row['message']}")


@app.cli.command("approve-wish")
@click.argument("wish_id", type=int)
def approve_wish_command(wish_id):
    """Approve a guest wish by its ID (see list-wishes), e.g. if the email never arrived."""
    with app.app_context():
        updated = db_execute("UPDATE wishes SET approved = 1 WHERE id = ?", (wish_id,)).rowcount
        get_db().commit()
    click.echo(f"Approved wish {wish_id}." if updated else f"No wish with ID {wish_id}.")


@app.cli.command("delete-wish")
@click.argument("wish_id", type=int)
def delete_wish_command(wish_id):
    """Remove a guest wish by its ID (see list-wishes)."""
    with app.app_context():
        deleted = db_execute("DELETE FROM wishes WHERE id = ?", (wish_id,)).rowcount
        get_db().commit()
    click.echo(f"Deleted wish {wish_id}." if deleted else f"No wish with ID {wish_id}.")


@app.cli.command("prepare-images")
def prepare_images_command():
    """Resize every photo into static/generated/. Run on your computer after adding photos, then commit that folder."""
    if ON_VERCEL:
        click.echo("Run this on your own computer, not on Vercel.")
        return
    prepare_images()

    def megabytes(folder):
        try:
            total = sum(path.stat().st_size for path in folder.iterdir() if path.is_file())
        except OSError:
            total = 0
        return total / 1_000_000

    click.echo(f"Original photos: {megabytes(IMAGE_FOLDER):.1f} MB in {IMAGE_FOLDER}")
    click.echo(f"Web copies:      {megabytes(GENERATED_FOLDER):.1f} MB in {GENERATED_FOLDER}")
    click.echo("Now commit and push the static/generated folder so the live site can use these smaller copies.")


@lru_cache(maxsize=None)
def static_version(filename):
    """Short fingerprint of a CSS/JS file, so browsers and Vercel's CDN fetch the new copy after every change."""
    try:
        return hashlib.md5((STATIC_FOLDER / filename).read_bytes()).hexdigest()[:10]
    except OSError:
        return ""


@app.url_defaults
def add_static_version(endpoint, values):
    filename = values.get("filename", "")
    if endpoint == "static" and filename.endswith((".css", ".js")):
        version = static_version(filename)
        if version:
            values["v"] = version


@app.after_request
def cache_static_files(response):
    """Let browsers and Vercel's CDN keep photos and styles instead of asking the app for them every time."""
    if request.path.startswith("/static/") and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=86400, s-maxage=604800"
    return response


if not ON_VERCEL:
    threading.Thread(target=prepare_images, daemon=True).start()

if __name__ == "__main__":
    # Set FLASK_DEBUG=1 while editing locally for auto-reload. Never enable it on a public host .
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")