# Tectonic BD Outreach Automation

Automated cold email system that reads contacts from a Google Sheet, sends personalized outreach emails via Gmail, detects bounces, and updates the sheet — all on a daily schedule via GitHub Actions. No server required.

---

## What It Does

Every day at **9:30 PM IST**, the system:

1. **Scans your Gmail** for any bounce-back notifications from previous sends and marks those rows as `BOUNCED` in the sheet
2. **Reads your contact list** from the Google Sheet starting at row 91
3. **Skips** anyone already marked `Yes` or `BOUNCED` in column H
4. **Sends a personalized email** to each fresh contact (name + company auto-filled)
5. **Marks the row** with `Yes` in column H and a timestamp in column J
6. **Stops** after 100 emails per day (configurable)

---

## Google Sheet Structure

**Sheet:** `Tectonic | Global BD Database`
**Tab:** `CTO/BD`

| Column | Letter | What goes here |
|--------|--------|----------------|
| A | Name | Contact's first name |
| B | Email | Email address |
| C | Company | Company name (optional) |
| H | Contacted | Script writes `Yes` or `BOUNCED` here |
| J | Last Contacted At | Script writes timestamp here |

> The script starts reading from **row 91**. Rows 1–90 are skipped entirely.
> Row 1 is assumed to be the header.

---

## Repo Structure

```
tectonic-bd-outreach/
├── send_outreach_emails.py        # Main script
├── requirements.txt               # Python dependencies
├── .gitignore                     # Excludes credentials/token from git
└── .github/
    └── workflows/
        └── daily_outreach.yml     # GitHub Actions schedule
```

**Files that are NOT in the repo** (kept out of git for security):
- `credentials.json` — Google OAuth client credentials
- `token.pickle` — Your authorized Google token (stored as a GitHub Secret)

---

## How It Was Set Up (From Scratch)

### Step 1 — Google Cloud Project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project called `tectonic-bd-outreach`
3. Enable these two APIs:
   - Gmail API
   - Google Sheets API
4. Go to **Auth Platform → OAuth Consent Screen**
   - App type: External
   - Add test users: `email1@emailID.com` and so on.
5. Go to **Auth Platform → Clients → Create Client**
   - Type: Desktop App
   - Download the JSON → rename it `credentials.json`

### Step 2 — Generate the Auth Token (One-Time)
Run this on your Mac inside the project folder:

```bash
cd ~/Downloads/tectonic-bd-outreach
python3 -m venv venv && source venv/bin/activate
pip install google-auth-oauthlib

cat > auth.py << 'EOF'
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.pickle", "wb") as f:
    pickle.dump(creds, f)

print("token.pickle created successfully")
EOF

python3 auth.py
```

Sign in with `[yourname]@email.xyz` when the browser opens. Wait for **"The authentication flow has completed"** before closing the tab.

### Step 3 — Create the GitHub Repo

```bash
git init
git add send_outreach_emails.py requirements.txt .gitignore .github/
git commit -m "Initial commit"
gh repo create tectonic-bd-outreach --private --source=. --push
```

### Step 4 — Add GitHub Secrets

Two secrets are required. Go to your repo → **Settings → Secrets and variables → Actions**, or use the CLI:

```bash
# Secret 1: contents of credentials.json
gh secret set GOOGLE_CREDENTIALS_JSON --body '<paste contents of credentials.json here>'

# Secret 2: base64-encoded token.pickle
base64 -i token.pickle -o /tmp/token_b64.txt
gh secret set GOOGLE_TOKEN_PICKLE_B64 < /tmp/token_b64.txt
rm /tmp/token_b64.txt
```

---

## Configuration

All settings are at the top of `send_outreach_emails.py`:

| Setting | Current Value | What It Controls |
|---------|--------------|------------------|
| `SPREADSHEET_ID` | `1BQFriAiZGJs5mI9i5P1LiQ2Rop_ozff_dfDcRpADeFA` | Which Google Sheet to use |
| `SHEET_TAB` | `CTO/BD` | Which tab inside the sheet |
| `SENDER_NAME` | `Tanay` | Name used in email sign-off |
| `DAILY_LIMIT` | `100` | Max emails per day |
| `DELAY_SECONDS` | `30` | Seconds to wait between each send |
| `DRY_RUN` | `False` | Set to `True` to test without actually sending |
| `START_ROW` | `91` | First sheet row to process (skips rows above this) |
| `COL_CONTACTED` | `7` (col H) | Where to write `Yes` / `BOUNCED` |
| `COL_LAST_CONTACTED` | `9` (col J) | Where to write the send timestamp |

To change any setting, edit the value in `send_outreach_emails.py`, commit, and push.

---

## Schedule

The workflow runs automatically via GitHub Actions.

**Cron:** `0 16 * * *` = 4:00 PM UTC = **9:30 PM IST**, every day.

Configured in `.github/workflows/daily_outreach.yml`.

---

## How to Run, Stop, and Re-Enable

### Trigger a manual run right now
```bash
gh workflow run daily_outreach.yml --repo tanaygandhi/tectonic-bd-outreach
```

### Cancel a run that's currently in progress
```bash
gh run cancel <RUN_ID> --repo tanaygandhi/tectonic-bd-outreach
```
Find the run ID at: `https://github.com/tanaygandhi/tectonic-bd-outreach/actions`

### Stop all future automatic runs (pause the system)
```bash
gh workflow disable daily_outreach.yml --repo tanaygandhi/tectonic-bd-outreach
```

### Re-enable automatic runs
```bash
gh workflow enable daily_outreach.yml --repo tanaygandhi/tectonic-bd-outreach
```

### Watch a run in real time
```bash
gh run watch --repo tanaygandhi/tectonic-bd-outreach
```

---

## How Bounce Detection Works

At the start of every run, before sending anything, the script:

1. Searches Gmail for messages matching:
   `from:mailer-daemon subject:"We'd love to audit your stack against quantum threats" newer_than:30d`
2. Parses the snippet of each bounce email to extract the failed address
   (looks for the pattern: *"wasn't delivered to EMAIL because"*)
3. Finds that email address in the Google Sheet
4. Writes `BOUNCED` to column H for that row

On all future runs, any row with `BOUNCED` in column H is permanently skipped.

---

## How Token Rotation Works

OAuth tokens expire after a while. To keep the system running without manual re-auth:

- After every run, the workflow re-encodes the (possibly refreshed) `token.pickle` and updates the `GOOGLE_TOKEN_PICKLE_B64` GitHub Secret automatically using PyNaCl encryption.
- This means the token stays fresh indefinitely without you having to touch it.

If the token ever breaks (e.g. you revoke access in your Google account), you'll need to re-run `auth.py` locally and update the secret manually — same as Step 2 above.

---

## Updating the Token Secret Manually

If you ever regenerate `token.pickle` (e.g. to add new scopes):

```bash
cd ~/Downloads/tectonic-bd-outreach
base64 -i token.pickle -o /tmp/ntb64.txt
gh secret set GOOGLE_TOKEN_PICKLE_B64 < /tmp/ntb64.txt
rm /tmp/ntb64.txt
```

---

## Checking Run Logs

**In the browser:**
`https://github.com/tanaygandhi/tectonic-bd-outreach/actions`

Click any run → click the `send-emails` job → click **"View raw logs"** (top right) for full output.

**In the terminal:**
```bash
gh run list --repo tanaygandhi/tectonic-bd-outreach
gh run view <RUN_ID> --repo tanaygandhi/tectonic-bd-outreach --log
```

---

## Dry Run (Test Without Sending)

To test the script without actually sending any emails:

1. Open `send_outreach_emails.py`
2. Change `DRY_RUN = False` to `DRY_RUN = True`
3. Commit and push
4. Trigger a manual run

The script will print what it *would* send but won't call the Gmail API or update the sheet.

Remember to set it back to `False` when done.

---

## Dependencies

Listed in `requirements.txt`:

```
gspread
google-auth
google-auth-oauthlib
google-api-python-client
```

Installed automatically by the GitHub Actions workflow on each run.
