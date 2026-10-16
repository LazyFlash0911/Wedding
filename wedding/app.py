import hmac
import io
import os
import secrets
from functools import lru_cache
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

PROJECT_FOLDER = Path(__file__).resolve().parent
DRIVE_TOKEN_FILE = Path(
    os.environ.get(
        "GOOGLE_DRIVE_TOKEN_FILE",
        str(PROJECT_FOLDER / "secrets" / "google-drive-token.json"),
    )
)
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_UPLOAD_PASSWORD = os.environ.get("DRIVE_UPLOAD_PASSWORD", "")
DRIVE_CATEGORIES = [
    {"id": "pre-wedding", "title": "Pre-wedding"},
    {"id": "engagement", "title": "Engagement"},
    {"id": "wedding", "title": "Wedding"},
]
DRIVE_FOLDER_ENV_VARS = {
    "pre-wedding": "GOOGLE_DRIVE_PRE_WEDDING_FOLDER_ID",
    "engagement": "GOOGLE_DRIVE_ENGAGEMENT_FOLDER_ID",
    "wedding": "GOOGLE_DRIVE_WEDDING_FOLDER_ID",
}
ALLOWED_DRIVE_IMAGES = {
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".gif": ("image/gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
    ".webp": (
        "image/webp",
        lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    ),
}
MAX_DRIVE_IMAGE_SIZE = 20 * 1024 * 1024

STATIC_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), "static", "images")
FAMILY_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

FAMILY_GROUPS = [
    {"id": "groom-parents", "title": "Groom's Parents"},
    {"id": "bride-parents", "title": "Bride's Parents"},
    {"id": "groom-siblings", "title": "Groom's Siblings"},
    {"id": "bride-siblings", "title": "Bride's Siblings"},
    {"id": "groom-grandparents", "title": "Groom's Grandparents"},
    {"id": "bride-grandparents", "title": "Bride's Grandparents"},
]

WEDDING = {
    "partner_one": "Priyanka Yadav",
    "partner_two": "Ankoosh Yadav",
    "date_text": "Wednesday, 9 December 2026",
    "date_iso": "2026-12-09T17:00:00+05:30",
    "venue": "Coco Island",
    "address": "Coco Island, Marve Village, Malad West, Malad, Mumbai, Maharashtra 400095",
    "ceremony_time": "5:00 PM onwards",
}

EVENTS = [
    {
        "id": "sangeet",
        "name": "Sangeet",
        "short_name": "Sangeet",
        "subtitle": "One evening, two hearts, endless dancing",
        "date": "Monday, 7 December 2026",
        "time": "6:00 PM",
        "venue": "Club Aquaria",
        "address": "Club Aquaria, Shanti Ashram, Devidas Cross Ln, near St.Lawrence High School, LIC Colony, Borivali West, Mumbai, Maharashtra 400103",
        "icon": "♪",
        "description": "An evening of music, dance, laughter, and celebration with both families.",
        "accent": "rose",
    },
    {
        "id": "groom-haldi",
        "name": "Ankoosh's Haldi",
        "short_name": "Groom's Haldi",
        "subtitle": "A golden beginning for the groom",
        "date": "Tuesday, 8 December 2026",
        "time": "6:00 PM",
        "venue": "Club Aquaria",
        "address": "Club Aquaria, Shanti Ashram, Devidas Cross Ln, near St.Lawrence High School, LIC Colony, Borivali West, Mumbai, Maharashtra 400103",
        "icon": "✿",
        "description": "Traditional rituals, joyful blessings, and happy moments with Ankoosh's loved ones.",
        "accent": "sage",
    },
    {
        "id": "bride-haldi",
        "name": "Priyanka's Haldi",
        "short_name": "Bride's Haldi",
        "subtitle": "A golden beginning for the bride",
        "date": "Wednesday, 9 December 2026",
        "time": "9:00 AM",
        "venue": "Hotel Sai Palace Grand",
        "address": "Hotel Sai Palace Grand, Link Rd, Malad, Evershine Nagar, Malad West, Mumbai, Maharashtra 400064",
        "icon": "✿",
        "description": "A beautiful morning of flowers, traditional rituals, and family blessings for Priyanka.",
        "accent": "gold",
    },
]

GALLERY = [
    {
        "title": "A little bit of magic",
        "caption": "Replace this card with one of your favourite couple photos.",
        "image": "images/couple-1.JPG",
        "position": "center",
    },
    {
        "title": "Our favourite memories",
        "caption": "Add a candid, a favourite trip, or a special moment.",
        "image": "images/couple-2.JPG",
        "position": "center",
    },
    {
        "title": "The beginning of forever",
        "caption": "One more photo to make this invitation yours.",
        "image": "images/couple-3.JPG",
        "position": "center",
    },
]


def drive_configuration_error():
    if not Path(DRIVE_TOKEN_FILE).is_file():
        return "Google Drive is not connected yet. The site owner must authorize their Google account."
    if not DRIVE_UPLOAD_PASSWORD:
        return "Google Drive uploads are not enabled: set DRIVE_UPLOAD_PASSWORD."
    if any(not get_drive_folder_id(category["id"]) for category in DRIVE_CATEGORIES):
        return "Google Drive uploads are not enabled: configure all three album folder IDs."
    return None


@lru_cache(maxsize=1)
def get_drive_service():
    credentials = Credentials.from_authorized_user_file(
        str(DRIVE_TOKEN_FILE), scopes=DRIVE_SCOPES
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleAuthRequest())
        Path(DRIVE_TOKEN_FILE).write_text(credentials.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def get_drive_folder_id(category):
    env_name = DRIVE_FOLDER_ENV_VARS.get(category)
    return os.environ.get(env_name, "") if env_name else ""


def is_valid_drive_image(upload):
    extension = Path(secure_filename(upload.filename or "")).suffix.lower()
    image_info = ALLOWED_DRIVE_IMAGES.get(extension)
    if image_info is None:
        return None

    upload.stream.seek(0, os.SEEK_END)
    file_size = upload.stream.tell()
    upload.stream.seek(0)
    if file_size == 0 or file_size > MAX_DRIVE_IMAGE_SIZE:
        return None

    header = upload.stream.read(12)
    upload.stream.seek(0)
    mime_type, signature_check = image_info
    return mime_type if signature_check(header) else None


def get_family_groups_with_photos():
    family_groups = []
    try:
        filenames = os.listdir(STATIC_IMAGE_FOLDER)
    except OSError:
        filenames = []

    for group in FAMILY_GROUPS:
        filename_prefix = f"{group['id']}-"
        photos = [
            {"filename": f"images/{filename}"}
            for filename in sorted(filenames, key=str.casefold)
            if filename.casefold().startswith(filename_prefix)
            and os.path.splitext(filename)[1].lower() in FAMILY_IMAGE_EXTENSIONS
            and os.path.isfile(os.path.join(STATIC_IMAGE_FOLDER, filename))
        ]
        family_groups.append({**group, "photos": photos})

    return family_groups


@app.get("/")
def index():
    return render_template(
        "index.html",
        wedding=WEDDING,
        events=EVENTS,
        gallery=GALLERY,
        family_groups=get_family_groups_with_photos(),
        drive_categories=DRIVE_CATEGORIES,
        drive_upload_enabled=drive_configuration_error() is None,
    )


@app.get("/api/drive/photos/<category>")
def list_drive_photos(category):
    folder_id = get_drive_folder_id(category)
    if not any(item["id"] == category for item in DRIVE_CATEGORIES):
        return jsonify({"error": "Unknown photo category."}), 404
    if not folder_id:
        return jsonify({"error": f"The Google Drive folder for {category} is not configured."}), 503
    if not Path(DRIVE_TOKEN_FILE).is_file():
        return jsonify({"error": "Google Drive is not configured on this server."}), 503

    try:
        service = get_drive_service()
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false and mimeType contains 'image/'",
            pageSize=100,
            orderBy="name",
            fields="files(id,name,mimeType)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
    except (GoogleAuthError, HttpError, OSError, ValueError):
        app.logger.exception("Failed to list Google Drive wedding photos")
        return jsonify({"error": "Could not load photos from Google Drive."}), 502

    photos = [
        {
            "id": photo["id"],
            "name": photo.get("name", "Wedding photo"),
            "url": url_for("drive_photo", file_id=photo["id"]),
        }
        for photo in response.get("files", [])
        if photo.get("id")
    ]
    return jsonify({"category": category, "photos": photos})


@app.get("/drive/photo/<file_id>")
def drive_photo(file_id):
    if not Path(DRIVE_TOKEN_FILE).is_file():
        return "Google Drive is not configured.", 503

    try:
        service = get_drive_service()
        metadata = service.files().get(
            fileId=file_id,
            fields="id,mimeType,parents,size",
            supportsAllDrives=True,
        ).execute()
        mime_type = metadata.get("mimeType", "")
        if mime_type not in {entry[0] for entry in ALLOWED_DRIVE_IMAGES.values()}:
            return "Not an image file.", 415
        permitted_folders = {
            folder_id
            for category in DRIVE_CATEGORIES
            if (folder_id := get_drive_folder_id(category["id"]))
        }
        if not permitted_folders.intersection(metadata.get("parents", [])):
            return "This image is outside the configured albums.", 404
        if int(metadata.get("size", 0)) > MAX_DRIVE_IMAGE_SIZE:
            return "This image is too large to display.", 413

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            buffer,
            service.files().get_media(fileId=file_id, supportsAllDrives=True),
        )
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
    except (GoogleAuthError, HttpError, OSError, ValueError):
        app.logger.exception("Failed to retrieve a Google Drive image")
        return "Could not retrieve the image.", 502

    return send_file(buffer, mimetype=mime_type, max_age=300, download_name="wedding-photo")


@app.post("/drive/upload")
def upload_drive_photos():
    category = request.form.get("category", "")
    if not any(item["id"] == category for item in DRIVE_CATEGORIES):
        flash("Choose a valid photo category.", "error")
        return redirect(url_for("index") + "#drive-gallery")

    setup_error = drive_configuration_error()
    if setup_error:
        flash(setup_error, "error")
        return redirect(url_for("index") + "#drive-gallery")

    submitted_password = request.form.get("upload_password", "")
    if not hmac.compare_digest(submitted_password, DRIVE_UPLOAD_PASSWORD):
        flash("The Google Drive upload password is incorrect.", "error")
        return redirect(url_for("index") + "#drive-gallery")

    folder_id = get_drive_folder_id(category)
    if not folder_id:
        flash(f"Set the Google Drive folder ID for {category} on the server first.", "error")
        return redirect(url_for("index") + "#drive-gallery")

    uploads = [item for item in request.files.getlist("photos") if item and item.filename]
    if not uploads:
        flash("Choose at least one photo to upload.", "error")
        return redirect(url_for("index") + "#drive-gallery")
    if len(uploads) > 10:
        flash("Upload no more than 10 photos at once.", "error")
        return redirect(url_for("index") + "#drive-gallery")

    validated_uploads = []
    for upload in uploads:
        mime_type = is_valid_drive_image(upload)
        if mime_type is None:
            flash("Use valid JPG, PNG, GIF, or WebP photos up to 20 MB each.", "error")
            return redirect(url_for("index") + "#drive-gallery")
        validated_uploads.append((upload, mime_type))

    try:
        service = get_drive_service()
        for upload, mime_type in validated_uploads:
            filename = secure_filename(upload.filename or "wedding-photo") or "wedding-photo"
            service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=MediaIoBaseUpload(upload.stream, mimetype=mime_type, resumable=True),
                fields="id",
                supportsAllDrives=True,
            ).execute()
    except (GoogleAuthError, HttpError, OSError, ValueError):
        app.logger.exception("Failed to upload wedding photos to Google Drive")
        flash("Google Drive could not save the photos. Check the folder sharing and server setup.", "error")
        return redirect(url_for("index") + "#drive-gallery")

    flash(f"Uploaded {len(validated_uploads)} photo(s) to {category} in Google Drive.", "success")
    return redirect(url_for("index") + "#drive-gallery")


@app.errorhandler(413)
def drive_upload_too_large(_error):
    flash("The upload is too large. Choose fewer or smaller photos.", "error")
    return redirect(url_for("index") + "#drive-gallery")

if __name__ == "__main__":
    app.run(debug=True)
