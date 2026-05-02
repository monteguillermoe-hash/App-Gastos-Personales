import os
import subprocess
import sys

# Evitar que el bot se ejecute varias veces si hay múltiples workers de Gunicorn
if not os.environ.get("BOT_STARTED"):
    os.environ["BOT_STARTED"] = "1"
    print("Iniciando el bot de Telegram en segundo plano...")
    subprocess.Popen([sys.executable, "-m", "src.bot"])

# Importar el servidor Flask subyacente de Dash como 'app' para que Gunicorn lo encuentre
from src.app import server as app
