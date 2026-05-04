import os
import json
from google.oauth2 import service_account

def get_google_credentials():
    """
    Obtiene las credenciales de Google Service Account desde una variable de entorno.
    La variable GOOGLE_CREDENTIALS debe contener el JSON completo del Service Account.
    """
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    
    if not creds_json:
        # Si no hay variable de entorno, intentar cargar desde un archivo local (solo para desarrollo)
        if os.path.exists("credentials.json"):
            return service_account.Credentials.from_service_account_file(
                "credentials.json",
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
        raise ValueError("La variable de entorno GOOGLE_CREDENTIALS no está configurada.")

    try:
        # Intentar parsear como JSON
        info = json.loads(creds_json)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
    except Exception as e:
        # Si no es JSON, podría ser una ruta a un archivo
        if os.path.exists(creds_json):
            return service_account.Credentials.from_service_account_file(
                creds_json,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
        raise e
