# Wedding Invitation Website (Python + Flask)

A responsive, bilingual (English / हिंदी) wedding invitation with an envelope intro, live countdown, event timeline with calendar links, venue map, family portraits, a photo carousel, Google Drive album links, and a guest wishes wall.

## 1. Requirements
- Python 3.10 or newer
- An internet connection for Google Fonts and the embedded map (the page has fallback fonts)

## 2. Run it locally

Open a terminal in this folder and run:

### Windows
```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser. The first page load takes a few seconds while web-sized copies of the photos are generated in `static/generated/`; after that it is fast.

The envelope intro shows once per browser session. To see it again, open the page in a new private window.

## 3. Personalize it
All content lives near the top of `app.py`, with Hindi text in the matching `_hi` fields:
- `WEDDING`: names, date, ceremony time. `date_iso` drives the countdown (ISO format with the +05:30 offset).
- `VENUES`: venue names, addresses and "getting there" tips.
- `EVENTS`: each celebration, including its dress code, accent colour, and `start`/`end` times used for "Add to calendar".
- `FAMILY_GROUPS`: optional `names` shown under each portrait.
- `MEMORY_CAPTIONS`: titles and captions for the couple photos, in order.
- `PHOTO_ALBUMS`: Google Drive links. Leave `url` empty to show "Shared after the wedding".
- `STAYS` and `CONTACTS`: hotels and phone numbers for guests. Each section stays hidden until you add entries.

Text that is written directly in the page lives in `templates/index.html`; the Hindi version of each piece of text is in its `data-hi` attribute.

## 4. Photos
Put photos in `static/images/` (JPG, JPEG, PNG, GIF or WebP). Full-size phone photos are fine: the site resizes and rotates them automatically.

- **Memories carousel:** `couple-1.jpg`, `couple-2.jpg`, … (as many as you like). The first one is also used as the WhatsApp link preview image.
- **Family portraits:** use these prefixes, numbered from 1:
  `groom-parents-`, `bride-parents-`, `groom-siblings-`, `bride-siblings-`, `groom-grandparents-`, `bride-grandparents-`.
  Groups without photos are hidden.

Refresh the page after adding images.

## 5. Music
`static/music.mp3` plays when a guest opens the envelope, and can be toggled from the menu bar. Delete the file to remove the music button.

## 6. Guest wishes
Wishes are saved in `instance/wishes.db` (SQLite). To review or remove one:
```powershell
flask --app app list-wishes
flask --app app delete-wish 12
```

## 7. QR cards for the venue
Open http://127.0.0.1:5000/qr for printable QR cards linking to the invitation and each shared photo album. Set `SITE_URL` (below) before printing so the codes point at your public address.

## 8. Publish it
Deploy to any Python host and run it with a WSGI server, for example `waitress-serve --port=8000 app:app` or `gunicorn app:app`. Set these environment variables:
- `FLASK_SECRET_KEY`: a long random string.
- `SITE_URL`: your public address, such as `https://priyanka-ankoosh.in`. Used for WhatsApp previews and QR codes.

Make sure the `instance/` folder is on persistent storage, or guest wishes will be lost when the host restarts. Use HTTPS. Running `python app.py` starts Flask's debug server, which is for local use only.
