"""Authorize this project to access the owner's Google Drive account once."""

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_FOLDER = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = Path(
    os.environ.get(
        "GOOGLE_OAUTH_CLIENT_FILE",
        str(PROJECT_FOLDER / "secrets" / "google-oauth-client.json"),
    )
)
TOKEN_FILE = Path(
    os.environ.get(
        "GOOGLE_DRIVE_TOKEN_FILE",
        str(PROJECT_FOLDER / "secrets" / "google-drive-token.json"),
    )
)
SCOPES = ["https://www.googleapis.com/auth/drive"]


def main():
    if not CLIENT_SECRETS_FILE.is_file():
        raise SystemExit(
            "OAuth client file not found. Download a Google OAuth Desktop app JSON "
            "to secrets/google-oauth-client.json or set GOOGLE_OAUTH_CLIENT_FILE."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE), SCOPES
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        access_type="offline",
        prompt="consent",
    )
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Google Drive authorization saved to {TOKEN_FILE}")
    print("Keep this token private and do not commit it to Git.")


if __name__ == "__main__":
    main()
