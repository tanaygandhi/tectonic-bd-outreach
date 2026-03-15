import gspread, time, base64, pickle, os
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_NAME="Tectonic | Global BD Database"; SHEET_TAB="CTO/BD"
SENDER_NAME="Tanay"; DAILY_LIMIT=100; DELAY_SECONDS=30; DRY_RUN=False
COL_NAME=0;COL_EMAIL=1;COL_COMPANY=2;COL_CONTACTED=7;COL_LAST_CONTACTED=9
SCOPES=["https://www.googleapis.com/auth/gmail.send","https://www.googleapis.com/auth/spreadsheets"]

def get_google_credentials():
    creds=None
    if os.path.exists("token.pickle"):
        with open("token.pickle","rb") as f: creds=pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing token..."); creds.refresh(Request())
            with open("token.pickle","wb") as f: pickle.dump(creds,f)
        else: raise RuntimeError("No valid token.")
    return creds

def send_emails():
    creds=get_google_credentials()
    gmail=build("gmail","v1",credentials=creds)
    gc=gspread.authorize(creds)
    sheet=gc.open_by_key("1BQFriAiZGJs5mI9i5P1LiQ2Rop_ozff_dfDcRpADeFA").worksheet(SHEET_TAB)
    rows=sheet.get_all_values()[90:]
    IST=timezone(timedelta(hours=5,minutes=30))
    sent=0;skipped=0
    for i,row in enumerate(rows):
        if sent>=DAILY_LIMIT: print(f"Limit reached."); break
        name=row[COL_NAME].strip() if len(row)>COL_NAME else ""
        email=row[COL_EMAIL].strip() if len(row)>COL_EMAIL else ""
        company=row[COL_COMPANY].strip() if len(row)>COL_COMPANY else ""
        contacted=row[COL_CONTACTED].strip() if len(row)>COL_CONTACTED else ""
        if not email or "@" not in email: skipped+=1; continue
        if contacted.lower() in ("yes","true","1","contacted"): skipped+=1; continue
        company_line=f" at {company}" if company else ""
        subject="We'd love to audit your stack against quantum threats"
        body=f"Hey {name},\n\nA lot of teams are starting to look at post-quantum migration now, especially with groups like Coinbase and the Ethereum ecosystem forming advisory efforts around it.\n\nWe've launched Post-Quantum Readiness Audits to help teams understand where quantum risk appears in their stack and how to plan the transition. If that's something your team{company_line} is exploring, happy to share more.\n\nBest,\n{SENDER_NAME}"
        msg=MIMEText(body);msg["to"]=email;msg["subject"]=subject
        raw={"raw":base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        timestamp=datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
        if DRY_RUN: print(f"  [DRY RUN] {name} <{email}>"); sent+=1; continue
        try:
            gmail.users().messages().send(userId="me",body=raw).execute()
            sheet.update_cell(i+91,COL_CONTACTED+1,"Yes")
            sheet.update_cell(i+91,COL_LAST_CONTACTED+1,timestamp)
            print(f"  Sent -> {name} <{email}> [{timestamp}]"); sent+=1; time.sleep(DELAY_SECONDS)
        except Exception as e: print(f"  FAILED {email}: {e}")
    print(f"Done. Sent:{sent} Skipped:{skipped}")

if __name__=="__main__": send_emails()
