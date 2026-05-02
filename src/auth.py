import os
import json
import logging
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

logger = logging.getLogger(__name__)

def get_google_credentials():
    """
    Obtiene las credenciales de Google a partir de la variable de entorno GOOGLE_CREDENTIALS.
    Este enfoque es stateless y es ideal para Render.
    """
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        try:
            creds_info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            logger.info("Autenticado exitosamente usando GOOGLE_CREDENTIALS desde variable de entorno.")
            return creds
        except Exception as e:
            logger.error(f"Error parseando GOOGLE_CREDENTIALS JSON: {e}")
            raise Exception(f"Error parseando GOOGLE_CREDENTIALS: {e}")

    # Fallback para desarrollo local
    service_account_file = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
    if os.path.exists(service_account_file):
        creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        logger.info(f"Autenticado usando archivo local: {service_account_file}.")
        return creds

    raise Exception("No se encontraron credenciales de Google. Configura la variable GOOGLE_CREDENTIALS.")
