import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SHEET_ID = "1R6CujT2y1BY24nTQID9mieOd2Bek_NpFzDVhxC4f2T4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def test_sheet():
    creds = None
    if os.path.exists("token.pickle"):
        import pickle
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        import pickle
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)

    service = build("sheets", "v4", credentials=creds)
    
    # Leer headers de Gastos Personales 2026
    res = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Gastos Personales 2026!A1:Z1"
    ).execute()
    
    values = res.get("values", [])
    print("Headers en Gastos Personales 2026:", values)
    
    # Leer headers de Listas
    res2 = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Listas!A1:Z1"
    ).execute()
    
    values2 = res2.get("values", [])
    print("Headers en Listas:", values2)

if __name__ == "__main__":
    try:
        test_sheet()
    except Exception as e:
        print("Error:", e)
