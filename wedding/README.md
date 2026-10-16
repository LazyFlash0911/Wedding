# Wedding Invitation Website (Python + Flask)

A responsive starter wedding invitation website with a countdown, venue directions, and a simple RSVP form.

## 1. Requirements
- Python 3.10 or newer
- Internet connection for Google Fonts (optional; the page has fallback fonts)

## 2. Set up

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

Open http://127.0.0.1:5000 in your browser.

## 3. Personalize it
Open `app.py` and edit the `WEDDING` dictionary:
- `partner_one` and `partner_two`
- `date_text` and `date_iso`
- `venue` and `address`
- `ceremony_time` and `contact`

Update the text and styling in `templates/index.html` and `static/style.css` as needed.

**Important:** `date_iso` should be in ISO format such as `2027-02-14T17:00:00`. Use the correct local time for your event.

## 4. Meet the family photos
The family gallery reads image files directly from `static/images/`. Add JPG, JPEG, PNG, GIF, or WebP files using these filename prefixes:
- `groom-parents-` (for example, `groom-parents-1.jpg`)
- `bride-parents-`
- `groom-siblings-`
- `bride-siblings-`
- `groom-grandparents-`
- `bride-grandparents-`

Add as many numbered photos as needed, such as `bride-siblings-1.jpg` and `bride-siblings-2.jpg`. Refresh the page after adding images; no upload form or database is used.

## 5. RSVP storage
For this starter project, RSVP entries are saved in `rsvps.json` on the server. This is suitable for a local demo, not a production system. For a public website, use a database or managed form backend, protect guest data, and add spam protection.

## 6. Publish it
To share a public link, deploy the Flask app to a Python-compatible hosting provider. Set a strong `FLASK_SECRET_KEY` environment variable, turn off debug mode, and use persistent database storage before collecting real guest RSVPs. Do not expose `rsvps.json` publicly.
