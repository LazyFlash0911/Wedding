import os

from flask import Flask, render_template

app = Flask(__name__)

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
        "image": "images/couple-1.jpg",
        "position": "center",
    },
    {
        "title": "Our favourite memories",
        "caption": "Add a candid, a favourite trip, or a special moment.",
        "image": "images/couple-2.jpg",
        "position": "center",
    },
    {
        "title": "The beginning of forever",
        "caption": "One more photo to make this invitation yours.",
        "image": "images/couple-3.jpg",
        "position": "center",
    },
]


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
    )

if __name__ == "__main__":
    app.run(debug=True)
