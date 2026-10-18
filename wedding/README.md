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

Open http://127.0.0.1:5000 in your browser. When the app starts it makes web-sized copies of the photos in `static/generated/` (a few seconds). While editing, run with `$env:FLASK_DEBUG = "1"` (Windows) or `FLASK_DEBUG=1` (macOS/Linux) so changes reload automatically.

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
`static/music.mp3` plays when a guest opens the envelope, and can be toggled from the menu bar. Delete the file to remove the music button. Keep it small for guests on mobile data: a 96 kbps MP3 is about 3 MB for a 4-minute song.

## 6. Built for phones
Most guests will open the link from WhatsApp on a phone, so the page includes:
- A bottom bar (Events, Venue, Photos, Wishes, Share) on phone-sized screens.
- **Share:** opens the phone's share sheet, or WhatsApp directly, with a ready-written message in the guest's language.
- **Add to calendar:** opens Apple Calendar on iPhones and Google Calendar everywhere else.
- **On event days:** a banner at the top shows what is happening today, with a link to it; event cards show "Today", "Happening now" or "Completed".
- Hindi is chosen automatically for phones set to Hindi; guests can switch at any time.
- Works on older phones (iOS 12+, older Android). If the page's script ever fails to load, guests see the full invitation without the envelope animation instead of a stuck screen.
- The phone's Back button closes a full-screen photo instead of leaving the site, and music pauses when the guest switches apps.
- The page asks search engines not to index it, so family photos and addresses stay out of Google; WhatsApp previews are unaffected.

## 7. Guest wishes
Wishes are saved in `instance/wishes.db` (SQLite) and appear on the invitation straight away.

To remove an inappropriate wish from your phone, set `WISHES_ADMIN_PASSWORD` and open `/admin/wishes` (for example https://your-site/admin/wishes). The page is switched off while the password is not set.

From a terminal on the server you can also run:
```powershell
flask --app app list-wishes
flask --app app delete-wish 12
```

## 8. QR cards for the venue
Open http://127.0.0.1:5000/qr for printable QR cards linking to the invitation and each shared photo album. Set `SITE_URL` (below) before printing so the codes point at your public address.

## 9. Publish it
Deploy to any Python host and run it with a WSGI server, for example `waitress-serve --port=8000 app:app` or `gunicorn app:app`. Set these environment variables:
- `FLASK_SECRET_KEY`: a long random string.
- `SITE_URL`: your public address, such as `https://priyanka-ankoosh.in`. Used for WhatsApp previews and QR codes. When it starts with `https://`, the session cookie is HTTPS-only, so don't set it while testing on `http://127.0.0.1`.
- `WISHES_ADMIN_PASSWORD`: a long password for `/admin/wishes`.

Make sure the `instance/` folder is on persistent storage, or guest wishes will be lost when the host restarts. Use HTTPS. Never set `FLASK_DEBUG=1` on a public host.
