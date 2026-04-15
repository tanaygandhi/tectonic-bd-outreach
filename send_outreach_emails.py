import gspread, time, base64, pickle, os, re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID     = "1BQFriAiZGJs5mI9i5P1LiQ2Rop_ozff_dfDcRpADeFA"
SHEET_TAB          = "CTO/BD"
LOG_TAB            = "Log"
SENDER_NAME        = "Tanay"
DAILY_LIMIT        = 300
DELAY_SECONDS      = 12
DRY_RUN            = False
START_ROW          = 91

COL_NAME=0; COL_EMAIL=1; COL_COMPANY=2; COL_CONTACTED=7; COL_LAST_CONTACTED=9

SCOPES=["https://www.googleapis.com/auth/gmail.send","https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/spreadsheets"]
EMAIL_SUBJECT = "We'd love to audit your stack against quantum threats"

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

def mark_bounces(gmail, sheet):
    print("Checking for bounces...")
    bounced=set()
    for q in [f'subject:"{EMAIL_SUBJECT}" from:mailer-daemon newer_than:30d',
              f'"wasn\'t delivered" "{EMAIL_SUBJECT}" newer_than:30d']:
        res=gmail.users().messages().list(userId="me",q=q,maxResults=200).execute()
        for ref in res.get("messages",[]):
            msg=gmail.users().messages().get(userId="me",id=ref["id"],format="metadata").execute()
            m=re.search(r"wasn't delivered to\s+(\S+@\S+?)\s+because",msg.get("snippet",""))
            if m: bounced.add(m.group(1).strip(".,<>").lower())
    if not bounced: print("  No bounces found."); return 0
    print(f"  Found {len(bounced)} bounce(s)")
    rows=sheet.get_all_values(); count=0
    for i,row in enumerate(rows[1:],start=2):
        email=row[COL_EMAIL].strip().lower() if len(row)>COL_EMAIL else ""
        if email in bounced:
            cur=row[COL_CONTACTED].strip() if len(row)>COL_CONTACTED else ""
            if cur.upper()!="BOUNCED":
                sheet.update_cell(i,COL_CONTACTED+1,"BOUNCED"); count+=1
    print(f"  Marked {count} row(s)."); return count

def get_or_create_log(spreadsheet):
    try:
        log = spreadsheet.worksheet(LOG_TAB)
    except gspread.exceptions.WorksheetNotFound:
        log = spreadsheet.add_worksheet(title=LOG_TAB, rows=5000, cols=6)
        log.append_row(["Timestamp", "Name", "Email", "Company", "Status", "Run Date"])
        print("  Created Log tab.")
    return log

def send_emails():
    print("Authenticating...")
    creds=get_google_credentials()
    gmail=build("gmail","v1",credentials=creds)
    gc=gspread.authorize(creds)
    spreadsheet=gc.open_by_key(SPREADSHEET_ID)
    sheet=spreadsheet.worksheet(SHEET_TAB)
    log=get_or_create_log(spreadsheet)
    mark_bounces(gmail,sheet)
    rows=sheet.get_all_values()
    data_rows=rows[START_ROW-1:]
    IST=timezone(timedelta(hours=5,minutes=30))
    run_date=datetime.now(IST).strftime("%Y-%m-%d")
    sent=0;skipped=0
    for i,row in enumerate(data_rows):
        if sent>=DAILY_LIMIT: print(f"Daily limit reached."); break
        name=row[COL_NAME].strip() if len(row)>COL_NAME else ""
        email=row[COL_EMAIL].strip() if len(row)>COL_EMAIL else ""
        company=row[COL_COMPANY].strip() if len(row)>COL_COMPANY else ""
        contacted=row[COL_CONTACTED].strip() if len(row)>COL_CONTACTED else ""
        if not email or "@" not in email: skipped+=1; continue
        if contacted.lower() in ("yes","true","1","contacted","bounced"): skipped+=1; continue
        company_line=f" at {company}" if company else ""
        body=f"""Hey {name or 'there'},

Hope you're doing well. I'm reaching out because quantum computing is moving faster than most people expect — and the teams that start preparing now will have a significant edge.

At Tectonic, we help security and engineering leaders run a Post-Quantum Readiness Audit: a structured review of your current encryption stack, identifying what's vulnerable to quantum attacks and mapping out a migration path before NIST deadlines hit.

It's not a huge lift — most audits wrap up in 2–3 weeks — but the insight is genuinely valuable given where things are heading.

Would it make sense to find 20 minutes to walk through what this looks like for {company or 'your team'}?

Best,
{SENDER_NAME}
Tectonic"""
        msg=MIMEText(body);msg["to"]=email;msg["subject"]=EMAIL_SUBJECT
        raw={"raw":base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        timestamp=datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
        sheet_row=i+START_ROW
        if DRY_RUN: print(f"  [DRY RUN] {name} <{email}>"); sent+=1; continue
        try:
            gmail.users().messages().send(userId="me",body=raw).execute()
            sheet.update_cell(sheet_row,COL_CONTACTED+1,"Yes")
            sheet.update_cell(sheet_row,COL_LAST_CONTACTED+1,timestamp)
            log.append_row([timestamp,name,email,company,"Sent",run_date])
            print(f"  Sent -> {name} <{email}> [{timestamp}]"); sent+=1; time.sleep(DELAY_SECONDS)
        except Exception as e:
            log.append_row([timestamp,name,email,company,f"Failed: {e}",run_date])
            print(f"  FAILED {email}: {e}")
    print(f"\nDone. Sent:{sent} Skipped:{skipped}")

if __name__=="__main__": send_emails()
