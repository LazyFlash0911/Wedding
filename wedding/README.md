# Wedding Invitation Website (Python + Flask)

A responsive wedding invitation website with a countdown, venue directions, family photos, and Google Drive albums.

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

Add as many numbered photos as needed, such as `bride-siblings-1.jpg` and `bride-siblings-2.jpg`. Refresh the page after adding images.

## 5. Google Drive pre-wedding, engagement, and wedding albums
The photo album at the top of the page reads and displays images from three Google Drive folders. The upload form sends selected photos directly to the matching folder.

### One-time Google setup
1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project and enable the **Google Drive API**.
2. Configure the OAuth consent screen and add your Google account as a test user if the app is in Testing mode.
3. Create an OAuth client with application type **Desktop app**. Download its JSON file to `secrets/google-oauth-client.json` beside `app.py` (or set `GOOGLE_OAUTH_CLIENT_FILE`). Keep this private; `secrets/` is git-ignored.
4. Create three folders in the Google Drive account you want to use: Pre-wedding, Engagement, and Wedding. Copy each folder ID from its Drive URL: `https://drive.google.com/drive/folders/FOLDER_ID`.
5. Run the authorization helper below. It opens Google sign-in in your browser and saves a private refresh token to `secrets/google-drive-token.json`. Authorize with the Google account whose Drive will store the photos. Google will ask to grant Drive access so the app can list and upload files in the configured folders.

### Configure and run (Windows PowerShell)
Set these environment variables, authorize your Google account once, then start Flask (replace the example values):
```powershell
$env:GOOGLE_DRIVE_PRE_WEDDING_FOLDER_ID = "your-pre-wedding-folder-id"
$env:GOOGLE_DRIVE_ENGAGEMENT_FOLDER_ID = "your-engagement-folder-id"
$env:GOOGLE_DRIVE_WEDDING_FOLDER_ID = "your-wedding-folder-id"
$env:DRIVE_UPLOAD_PASSWORD = "choose-a-long-private-upload-password"
$env:FLASK_SECRET_KEY = "use-a-long-random-secret"
pip install -r requirements.txt
python authorize_google_drive.py
python app.py
```

JPG, JPEG, PNG, GIF, and WebP images up to 20 MB each are accepted; upload up to 10 photos per submission. The upload password is checked server-side. The Drive OAuth token grants the app access to the authorized account, so protect it like a password. Album photos are served by the website and are visible to its visitors. Never commit the OAuth client JSON, token file, or passwords. Deploy only over HTTPS and configure the token as a private secret file on your host. Google OAuth consent-screen Testing mode may expire refresh tokens after seven days; follow Google's publishing and verification requirements for longer-lived public use.

## 6. Publish it
Deploy the Flask app to a Python-compatible hosting provider. Configure the Drive settings above as private environment variables, provide the OAuth token file using your host's secret-file mechanism, use HTTPS, and turn off debug mode in production.
