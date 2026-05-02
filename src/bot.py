"""
APP FINANZAS – Bot de Telegram + Google Sheets
================================================
Dependencias:  pip install -r requirements.txt
Credenciales:  coloca credentials.json (OAuth Desktop) en esta misma carpeta.
Uso:           python3.11 bot.py
"""

import os
import re
import logging
from datetime import datetime
from dotenv import load_dotenv
import shlex
import requests

# ── Google Auth / Sheets ──────────────────────────────────────────────────────
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json

# ── Telegram ──────────────────────────────────────────────────────────────────
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID", "1R6CujT2y1BY24nTQID9mieOd2Bek_NpFzDVhxC4f2T4")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")
SCOPES           = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE       = os.path.join(os.path.dirname(__file__), "token.json")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Diccionario de clasificación – construido desde el historial del Excel
#
# Formato: lista de (palabras_clave, rubro_principal, sub_rubro)
# Las reglas se evalúan en orden; gana la primera que hace match.
# Cada entrada puede tener UNA o VARIAS palabras/frases: basta que
# cualquiera de ellas aparezca (en minúsculas) en el detalle.
# ─────────────────────────────────────────────────────────────────────────────
CLASIFICACION_RUBRO: list[tuple[list[str], str, str]] = [

    # ── Ahorro / Inversiones ─────────────────────────────────────────────────
    (["zurich", "zurich interna"],               "Ahorro/Inversiones",       "Seguro de retiro"),
    (["nacion retiro", "aporte ordinario"],       "Ahorro/Inversiones",       "Seguro de retiro"),

    # ── Obra / Estructura ────────────────────────────────────────────────────
    (["corralón", "corralo", "aleman"],           "Obra/Estructura",          "Materiales"),
    (["colorshop", "pintura interior"],           "Obra/Estructura",          "Materiales"),
    (["materiales", "alemani"],                   "Obra/Estructura",          "Materiales"),
    (["cables", "tapas ciegas", "altura -"],      "Obra/Estructura",          "Materiales"),
    (["recubrir escalon", "pvc"],                 "Obra/Estructura",          "Materiales"),
    (["plomeria", "plomería"],                    "Obra/Estructura",          "Materiales"),
    (["camuzzi instalac", "instalacion medidor"], "Obra/Estructura",          "Instalaciones"),
    (["vanitory", "sanitario", "griferia",
      "griferí", "porc life", "tiza nat"],        "Obra/Estructura",          "Sanitarios/Grifería"),
    (["var acero", "terminacion cocina",
      "terminaciones cocina"],                    "Obra/Estructura",          "Terminaciones: Cocina"),
    (["panel plafon", "plafon led", "spot embutir",
      "ferrolux", "lámpara led", "lampara led",
      "lamp led", "dicro", "zocalo gu10",
      "dicroica", "macroled"],                    "Obra/Estructura",          "Mobiliario Fijo y Equipamiento"),
    (["mueble cocina"],                           "Obra/Estructura",          "Mobiliario Fijo y Equipamiento"),

    # ── Equipamiento / Mobiliario ────────────────────────────────────────────
    (["toalla", "toallon", "juego toall",
      "taper", "tabla cocina", "bazar"],          "Equipamiento/Mobiliario",  "Bazar y Blanco"),
    (["tacho de basura", "escobilla baño",
      "set tachos", "bano accesorio",
      "baño accesorio"],                          "Equipamiento/Mobiliario",  "Baño/Accesorios"),

    # ── Educación / Formación ────────────────────────────────────────────────
    (["iete", "hogar cristiano", "evangelismo",
      "evangelios sinopticos", "evangelios"],     "Educación/Formación",      "Formación espiritual"),
    (["curso de masaje", "masajes"],              "Educación/Formación",      "Oficio"),
    (["curso", "clase", "capacitacion",
      "capacitación", "formacion", "formación"],  "Educación/Formación",      "Curso"),

    # ── Gasto Corriente – Seguridad Social ──────────────────────────────────
    (["serv. u otros conceptos cps",
      "otros conceptos cps"],                     "Gasto Corriente",          "Seguridad Social / Aportes"),

    # ── Gasto Corriente – Préstamos ──────────────────────────────────────────
    (["cuota prestamo", "cuota préstamo",
      "prestamo hipotecario", "préstamo hipotecario",
      "cuota prestamos", "cuota préstamos"],      "Gasto Corriente",          "Préstamos y Financiación"),
    (["icbc"],                                    "Gasto Corriente",          "Préstamos y Financiación"),

    # ── Gasto Corriente – Impuestos / Gastos Bancarios ───────────────────────
    (["impuesto de sellos", "impuesto sellos",
      "sellos mercado pago", "sellos bna",
      "sellos mp", "sellos bcо", "sellos bco"],   "Gasto Corriente",          "Gastos Bancarios"),

    # ── Gasto Corriente – Vehículo ───────────────────────────────────────────
    (["nacion seguros", "seguro del auto",
      "pagos360", "applusiteuve",
      "cinturon", "cinturones", "manija criquet",
      "llave cruz", "bateria moura", "bateria m22"],
                                                  "Gasto Corriente",          "Vehiculo: Mantenimiento"),
    (["ypf lavalle", "combustible viaje",
      "nafta auto"],                              "Gasto Corriente",          "Vehiculo: Consumo"),
    (["ypf combustible", "combustible 6,",
      "combustible 6.", "moto combustible"],      "Gasto Corriente",          "Moto: Consumo"),
    (["seguro de la moto", "seguro moto"],        "Gasto Corriente",          "Moto: Mantenimiento"),

    # ── Gasto Corriente – Vivienda ───────────────────────────────────────────
    (["calefactor", "impuesto inmobiliario"],      "Gasto Corriente",          "Vivienda Casa de Papá"),
    (["camuzzi", "seguro de incendio",
      "pueyrredon"],                              "Gasto Corriente",          "Vivienda: Mantenimiento"),
    (["arba"],                                    "Gasto Corriente",          "Vivienda: Mantenimiento"),

    # ── Gasto Corriente – Impuestos municipales ──────────────────────────────
    (["falucho", "impuesto automotor",
      "impuesto municipal falucho"],              "Gasto Corriente",          "Aporte Familiar"),
    (["impuesto municipal", "impuesto autom"],    "Gasto Corriente",          "Aporte Familiar"),

    # ── Gasto Corriente – Telefonía ──────────────────────────────────────────
    (["celular", "claro pay", "telefonia",
      "telefonía", "factura claro"],              "Gasto Corriente",          "Telefonia movil"),

    # ── Gasto Corriente – Bienestar/Deportes ────────────────────────────────
    (["gimnasio"],                                "Gasto Corriente",          "Bienestar/Deportes"),
    (["futbol", "fútbol", "basquet", "básquet",
      "deporte"],                                 "Gasto Corriente",          "Bienestar/Deportes"),

    # ── Gasto Corriente – Transporte ────────────────────────────────────────
    (["pinchadura", "bicicleta", "cambio de camara"],
                                                  "Gasto Corriente",          "Transporte"),

    # ── Gasto Corriente – Cuidado Personal ──────────────────────────────────
    (["peluqueria", "peluquería", "simplicity",
      "dermaglos", "protector solar", "perfumeria",
      "perfumería", "desodorante", "jabón liquido",
      "jabon liquido", "recortadora de barba",
      "aguifarma", "mini perfumero", "atomizador",
      "perfumero", "coop obrera hogar recort"],   "Gasto Corriente",          "Cuidado Personal"),

    # ── Gasto Corriente – Indumentaria ──────────────────────────────────────
    (["wwwdigitalsport", "ropa de trabajo",
      "ropa deportiva", "pantalones", "pegasus",
      "macowens", "indumentaria", "amazon",
      "zapatill"],                                "Gasto Corriente",          "Indumentaria"),

    # ── Gasto Corriente – Comida ─────────────────────────────────────────────
    (["carne", "carniceria", "carnicería",
      "tomate", "zanahoria", "verdura",
      "cooperativa obrera", "bloxmax",
      "market las heras", "kiosco agua",
      "camcas", "express av vicenta",
      "carrefour agua", "los2hermanos",
      "ensalada"],                                "Gasto Corriente",          "Comida"),

    # ── Gasto Corriente – Donaciones / Regalos ──────────────────────────────
    (["ofrenda", "regalo pastor", "regalo",
      "mochila matera", "florero", "jarron",
      "papeles carta", "pendrive",
      "perro conejo", "vino bodega",
      "aceite de oliva", "llavero"],              "Gasto Corriente",          "Donacion/regalos"),

    # ── Gasto Corriente – Salidas y Viajes ──────────────────────────────────
    # (regla amplia al final para no pisar las anteriores)
    (["viaje", "pasaje", "hostel", "alojamiento",
      "excursion", "excursión", "potrerillos",
      "cacheuta", "mendoza", "andesmar", "uber",
      "linea 1", "linea 8", "linea 1.",
      "desde aeroparque", "aeroparque",
      "aeropuerto", "cabalgata", "canopy",
      "kayak", "rafting", "camino del vino",
      "alta montaña", "cañon del atuel",
      "restaurante", "heladeria", "heladería",
      "sorrentinos", "pollofrito", "sanguche",
      "empanada", "merienda", "gomitas",
      "bodega", "termas", "vea sm",
      "calentar agua", "fruta", "banana",
      "naranja", "3 arroyos taj", "pasajesplu",
      "facturas ypf", "cena", "partido basquet",
      "polideportivo", "candado", "adaptador enchufe",
      "toallon magico", "neceser", "tapones oidos",
      "botellas recargables", "atomizador viaje"],
                                                  "Gasto Corriente",          "Salidas y Viajes"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Diccionario de medios de pago – inferido desde el historial
#
# Formato: lista de (palabras_clave, medio_de_pago)
# ─────────────────────────────────────────────────────────────────────────────
CLASIFICACION_MEDIO: list[tuple[list[str], str]] = [
    # Recibo de sueldo
    (["serv. u otros conceptos", "otros conceptos cps",
      "nacion retiro", "aporte ordinario"],        "Recibo de Sueldo"),

    # Débito en cuenta
    (["icbc", "debito"],                           "Debito en cuenta"),

    # Efectivo
    (["ofrenda cdd", "ofrenda misionera",
      "futbol", "fútbol", "pinchadura"],           "Efectivo"),

    # Transferencia
    (["iete", "curso de masaje", "gimnasio",
      "peluqueria", "peluquería",
      "cuota prestamo hipotecario",
      "cuota préstamo hipotecario",
      "factura claro", "claro pay",
      "comida viaje", "combustible viaje",
      "transferencia"],                            "Transferencia"),

    # Tarjeta Débito
    (["bateria moura", "7 facturas ypf",
      "celular"],                                  "Tarjeta Débito"),
]

DEFAULT_MEDIO = "Tarjeta Crédito"


# ─────────────────────────────────────────────────────────────────────────────
# Funciones de clasificación
# ─────────────────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Minúsculas + eliminar prefijos de cuotas tipo '(Cuota N/M)'."""
    texto = texto.lower()
    texto = re.sub(r"\(cuota\s+\d+/\d+\)", "", texto)
    texto = re.sub(r"cuota\s+\d+\s+de\s+\d+", "", texto)
    return texto


def clasificar_rubro(detalle: str) -> tuple[str, str]:
    """
    Devuelve (rubro_principal, sub_rubro) basándose en el historial del Excel.
    Si no encuentra coincidencia retorna ("Otros", "General").
    """
    d = _normalizar(detalle)
    for keywords, rubro, subrubro in CLASIFICACION_RUBRO:
        if any(kw in d for kw in keywords):
            return rubro, subrubro
    return "Otros", "General"


def clasificar_medio(detalle: str) -> str:
    """
    Infiere el medio de pago más probable según el detalle.
    Por defecto devuelve 'Tarjeta Crédito'.
    """
    d = _normalizar(detalle)
    for keywords, medio in CLASIFICACION_MEDIO:
        if any(kw in d for kw in keywords):
            return medio
    return DEFAULT_MEDIO


# ─────────────────────────────────────────────────────────────────────────────
# Autenticación con Google
# ─────────────────────────────────────────────────────────────────────────────

def get_google_client() -> gspread.Client:
    creds = None
    
    # 1. Intentar usar la variable de entorno con el JSON del Service Account (ideal para Render)
    if GOOGLE_CREDENTIALS_JSON:
        try:
            creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
            creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            logger.info("Autenticado usando Service Account desde variable de entorno.")
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Error parseando GOOGLE_CREDENTIALS JSON: {e}")

    # 2. Intentar usar el archivo service_account.json si existe
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        logger.info("Autenticado usando archivo service_account.json.")
        return gspread.authorize(creds)

    # 3. Fallback al flujo de Desktop (token.json o credentials.json)
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Token renovado automáticamente.")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            # Como es para Render, run_local_server podría fallar sin interfaz gráfica, pero
            # asumimos que en Render usarás Service Account.
            creds = flow.run_local_server(port=0, open_browser=True)
            logger.info("Autorización completada. token.json guardado.")
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return gspread.authorize(creds)


def get_sheet():
    client = get_google_client()
    return client.open_by_key(SPREADSHEET_ID).worksheet("Gastos Personales 2026")


def get_medios_pago() -> list[str]:
    client = get_google_client()
    lista_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Listas")
    valores = lista_sheet.col_values(3)  # Columna C
    # El encabezado es "Tarjeta Crédito", que también es un medio válido
    return [v for v in valores if v]


# ─────────────────────────────────────────────────────────────────────────────
# Cotización dólar oficial (Bluelytics)
# ─────────────────────────────────────────────────────────────────────────────

def obtener_dolar_bna() -> float:
    try:
        resp = requests.get("https://api.bluelytics.com.ar/v2/latest", timeout=10)
        if resp.status_code == 200:
            return float(resp.json()["oficial"]["value_sell"])
        return 0.0
    except Exception as e:
        logger.error(f"Error al obtener cotización dólar: {e}")
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Handlers de Telegram
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = (
        "📋 *Comandos disponibles*\n\n"
        "*/ayuda* – Muestra esta ayuda.\n\n"
        "*/gasto* `<monto> \"<detalle>\" [\"<rubro>\"] [\"<subrubro>\"] [\"<medio>\"]`\n"
        "Registra un gasto en la planilla.\n\n"
        "_Ejemplos:_\n"
        "`/gasto 8000 \"Gimnasio\"`\n"
        "→ clasifica automáticamente rubro, sub-rubro y medio de pago.\n\n"
        "`/gasto 50000 \"Material Corralón\" \"Obra/Estructura\" \"Materiales\" \"Transferencia\"`\n"
        "→ valores manuales para todo.\n\n"
        "ℹ️ Si no especificás rubro/sub-rubro/medio, el bot los completa "
        "basándose en tu historial de gastos."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


async def cmd_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Normalizar comillas tipográficas de teclados móviles
    raw = update.message.text
    raw = raw.replace("\u201c", '"').replace("\u201d", '"') \
             .replace("\u2018", "'").replace("\u2019", "'")

    try:
        args = shlex.split(raw)[1:]  # quitar "/gasto"
    except ValueError as e:
        await update.message.reply_text(
            f"⚠️ Error al parsear el comando: {e}\n"
            "Asegurate de cerrar correctamente las comillas.",
            parse_mode="Markdown",
        )
        return

    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Faltan datos.\n"
            "Uso mínimo: `/gasto <monto> \"<detalle>\"`",
            parse_mode="Markdown",
        )
        return

    # ── Parsear monto ────────────────────────────────────────────────────────
    try:
        monto = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "⚠️ El monto debe ser numérico (ej: `1500` o `1500.50`).",
            parse_mode="Markdown",
        )
        return

    detalle      = args[1]
    categoria    = args[2] if len(args) > 2 else ""
    subcategoria = args[3] if len(args) > 3 else ""
    medio        = args[4] if len(args) > 4 else ""

    # ── Auto-clasificar lo que falte ─────────────────────────────────────────
    auto_rubro, auto_subrubro = clasificar_rubro(detalle)

    if not categoria:
        categoria = auto_rubro
    if not subcategoria:
        subcategoria = auto_subrubro
    if not medio:
        medio = clasificar_medio(detalle)

    # ── Validar medio de pago ────────────────────────────────────────────────
    medios_validos = get_medios_pago()
    if medio not in medios_validos:
        logger.warning(f"Medio '{medio}' no encontrado en Listas; usando default.")
        medio = DEFAULT_MEDIO

    # ── Fecha / hora / dólar ─────────────────────────────────────────────────
    ahora     = datetime.now()
    fecha     = ahora.strftime("%d/%m/%Y")
    hora      = ahora.strftime("%H:%M:%S")
    dolar_bna = obtener_dolar_bna()
    monto_usd = round(monto / dolar_bna, 4) if dolar_bna else ""

    # ── Escribir en Sheets ───────────────────────────────────────────────────
    try:
        sheet    = get_sheet()
        next_row = len(sheet.col_values(1)) + 1
        sheet.update(
            f"A{next_row}:I{next_row}",
            [[fecha, hora, detalle, monto, categoria, subcategoria, medio, dolar_bna, monto_usd]],
        )
    except Exception as e:
        logger.error(f"Error al escribir en Sheets: {e}")
        await update.message.reply_text(
            f"❌ Error al guardar en Google Sheets:\n`{e}`",
            parse_mode="Markdown",
        )
        return

    # ── Respuesta ────────────────────────────────────────────────────────────
    usd_str = f"{monto_usd:.4f}" if monto_usd else "N/A"
    dolar_str = f"{dolar_bna:,.2f}" if dolar_bna else "N/A"

    await update.message.reply_text(
        f"✅ *Gasto registrado* (fila {next_row})\n\n"
        f"📅 {fecha}  {hora}\n"
        f"📝 {detalle}\n"
        f"💰 ${monto:,.2f} ARS\n"
        f"🗂 {categoria}\n"
        f"📌 {subcategoria}\n"
        f"💳 {medio}\n"
        f"💵 Dólar Oficial: ${dolar_str}\n"
        f"🌎 Importe USD: {usd_str}",
        parse_mode="Markdown",
    )
    logger.info(f"Gasto guardado — fila {next_row} | {detalle} | {monto} | {categoria} / {subcategoria} | {medio}")


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN no está definido en el archivo .env")

    logger.info("Iniciando autenticación con Google…")
    get_google_client()
    logger.info("Autenticación exitosa. Iniciando bot de Telegram…")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("start", cmd_ayuda))
    app.add_handler(CommandHandler("gasto", cmd_gasto))

    logger.info("Bot corriendo. Esperando mensajes…")
    app.run_polling()


if __name__ == "__main__":
    main()
