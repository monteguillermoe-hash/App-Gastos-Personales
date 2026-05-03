"""
╔══════════════════════════════════════════════════════════════════════════╗
║           DASHBOARD GASTOS PERSONALES 2026 — app.py                     ║
╠══════════════════════════════════════════════════════════════════════════╣
║  SETUP RÁPIDO (3 pasos):                                                 ║
║                                                                          ║
║  1. Instalá dependencias:                                                ║
║     pip install dash dash-bootstrap-components plotly pandas             ║
║          google-api-python-client flask                                  ║
║                                                                          ║
║  2. Asegurate de tener configurada la variable de entorno                ║
║     GOOGLE_CREDENTIALS con el JSON de tu Service Account de Google.      ║
║                                                                          ║
║  3. Ejecutá:  python app.py                                              ║
║     Abrí:     http://localhost:8080                                      ║
║                                                                          ║
║  Despliegue en Render:                                                   ║
║  La app está lista para desplegarse configurando las variables de        ║
║  entorno GOOGLE_CREDENTIALS y TELEGRAM_TOKEN en Render.                  ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os, json, traceback, io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
def parse_fecha(fecha_str):
    return datetime.strptime(fecha_str, "%d/%m/%Y")
from flask import Flask, redirect, request, send_from_directory
from dash import Dash, dcc, html, dash_table, Input, Output
import dash_bootstrap_components as dbc
from googleapiclient.discovery import build
from src.auth import get_google_credentials

# ═══════════════════════════════════════════════
#  ⚙️  CONFIGURACIÓN — LEER DESDE VARIABLES DE ENTORNO
# ═══════════════════════════════════════════════
SHEET_ID    = os.getenv("SHEET_ID", "1R6CujT2y1BY24nTQID9mieOd2Bek_NpFzDVhxC4f2T4")
SHEET_RANGE = "Gastos Personales 2026!A:Z"
SECRET_KEY  = os.getenv("SECRET_KEY", "b36ac1d3ffaf7a5ba0cabd3299e1a5cee229111701bab640f3d273e04acfd870")
PORT        = int(os.getenv("PORT", 8080))
# ═══════════════════════════════════════════════

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
COLS   = ["Fecha", "Hora", "Concepto", "Importe", "Rubro Principal", "Sub-rubro", "Medio de Pago"]

# ──────────────────────────────────────────────
# Flask + Dash
# ──────────────────────────────────────────────
server = Flask(__name__)
server.secret_key = SECRET_KEY

app = Dash(
    __name__,
    server=server,
    url_base_pathname="/dashboard/",
    # assets_folder cargará automáticamente assets/style.css
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="💰 Gastos 2026",
    meta_tags=[
        {"name": "viewport",
         "content": "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"},
        {"name": "apple-mobile-web-app-capable", "content": "yes"},
        {"name": "theme-color",                  "content": "#0d1117"},
    ],
)

# ──────────────────────────────────────────────
# PWA Routes
# ──────────────────────────────────────────────
@server.route("/manifest.json")
def serve_manifest():
    return send_from_directory("assets", "manifest.json")

@server.route("/sw.js")
def serve_sw():
    return send_from_directory("assets", "sw.js")


app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="manifest" href="/manifest.json">
        <link rel="apple-touch-icon" href="/assets/icon-192.png">
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', function () {
                    navigator.serviceWorker.register('/sw.js')
                        .then(r  => console.log('SW registrado:', r.scope))
                        .catch(e => console.log('SW error:', e));
                });
            }
        </script>
    </body>
</html>
"""


# ──────────────────────────────────────────────
# Google Sheets helpers
# ──────────────────────────────────────────────

def load_listas(creds):
    """
    Carga las categorías maestras desde la pestaña 'Listas'.
    Estructura esperada (con encabezado en fila 1):
        Col A → Rubro Principal
        Col B → Sub-rubro
        Col C → Medio de Pago
    CORRECCIÓN: se salta la fila 0 (encabezado) con values[1:]
    para evitar que los títulos de columna aparezcan como opciones.
    """
    try:
        service = build("sheets", "v4", credentials=creds)
        result  = (service.spreadsheets().values()
                          .get(spreadsheetId=SHEET_ID, range="Listas!A:Z")
                          .execute())
        values = result.get("values", [])

        if not values:
            print("⚠️  Pestaña 'Listas' vacía o sin datos.")
            return {"rubros": [], "subrubros": [], "medios": []}

        # ── FIX PRINCIPAL: saltar la fila de encabezado explícitamente ──
        data_rows = values[1:]          # values[0] = encabezados → se descarta

        rubros    = []
        subrubros = []
        medios    = []

        for row in data_rows:
            # Columna A — Rubro Principal
            val_a = row[0].strip() if len(row) > 0 and row[0].strip() else None
            if val_a:
                rubros.append(val_a)

            # Columna B — Sub-rubro
            val_b = row[1].strip() if len(row) > 1 and row[1].strip() else None
            if val_b:
                subrubros.append(val_b)

            # Columna C — Medio de Pago
            val_c = row[2].strip() if len(row) > 2 and row[2].strip() else None
            if val_c:
                medios.append(val_c)

        result_listas = {
            "rubros":    sorted(set(rubros)),
            "subrubros": sorted(set(subrubros)),
            "medios":    sorted(set(medios)),
        }
        print(f"✅ Listas cargadas → rubros:{len(result_listas['rubros'])}  "
              f"subrubros:{len(result_listas['subrubros'])}  "
              f"medios:{len(result_listas['medios'])}")
        return result_listas

    except Exception as e:
        print(f"⚠️  Error en load_listas: {e}")
        traceback.print_exc()
        return {"rubros": [], "subrubros": [], "medios": []}


def load_sheet_data():
    """Carga los datos de gastos y las listas maestras desde Google Sheets."""
    try:
        creds = get_google_credentials()
    except Exception as e:
        print(f"⚠️  No se obtuvieron credenciales: {e}")
        return None, None, "no_auth"

    try:
        service = build("sheets", "v4", credentials=creds)

        # 1. Hoja de Gastos — UNFORMATTED_VALUE: fechas como serial, números como float
        res_gastos = (service.spreadsheets().values()
                             .get(spreadsheetId=SHEET_ID,
                                  range="Gastos Personales 2026!A:Z",
                                  valueRenderOption="UNFORMATTED_VALUE",
                                  dateTimeRenderOption="SERIAL_NUMBER")
                             .execute())

        values_g = res_gastos.get("values", [])
        if not values_g:
            return pd.DataFrame(), {}, "empty"

        max_cols = max(len(r) for r in values_g)
        padded   = [r + [""] * (max_cols - len(r)) for r in values_g]
        header   = [h.strip() if h and h.strip() else f"Col_{i}"
                    for i, h in enumerate(padded[0])]
        df = pd.DataFrame(padded[1:], columns=header)

        # Mapeo dinámico de columnas (tolerante a variaciones de nombre)
        col_map = {}
        for col in df.columns:
            cl = str(col).lower().strip()
            if   cl in ("fecha", "fechas", "date", "día", "dia"):
                col_map[col] = "Fecha"
            elif cl in ("concepto", "detalle", "descripción", "descripcion", "gasto"):
                col_map[col] = "Concepto"
            elif cl in ("importe", "monto", "precio", "valor"):
                col_map[col] = "Importe"
            elif cl in ("rubro principal", "rubro", "rubros", "categoria", "categoría"):
                col_map[col] = "Rubro Principal"
            elif cl in ("sub-rubro", "subrubro", "sub rubro", "subcategoria", "subcategoría"):
                col_map[col] = "Sub-rubro"
            elif cl in ("medio de pago", "medio", "metodo de pago", "forma de pago", "pago"):
                col_map[col] = "Medio de Pago"

        df = df.rename(columns=col_map)

        use_cols    = ["Fecha", "Concepto", "Importe", "Rubro Principal", "Sub-rubro", "Medio de Pago"]
        missing     = [c for c in use_cols if c not in df.columns]
        if missing:
            msg = f"error: Faltan columnas: {', '.join(missing)}. Leídas: {list(header)}"
            return None, None, msg

        df = df[use_cols].copy()

        for col in ("Rubro Principal", "Sub-rubro", "Medio de Pago", "Concepto"):
            df[col] = df[col].astype(str).str.strip()

        # ── FECHA: UNFORMATTED_VALUE devuelve serial numérico (ej: 46054 = 01/02/2026)
        # Epoch de Google Sheets = 1899-12-30
        # 100% libre de ambigüedad de locale: 46054 siempre es 2026-02-01
        SHEETS_EPOCH = pd.Timestamp("1899-12-30")

        def serial_to_fecha(val):
            # Caso principal: número serial (UNFORMATTED_VALUE)
            if isinstance(val, (int, float)):
                n = float(val)
                if 40000 < n < 60000:
                    return SHEETS_EPOCH + pd.Timedelta(days=int(n))
                return pd.NaT
            # Fallback texto (por si alguna celda tiene fórmula que devuelve texto)
            s = str(val).strip()
            if not s or s in ("","nan","None"):
                return pd.NaT
            try:
                n = float(s)
                if 40000 < n < 60000:
                    return SHEETS_EPOCH + pd.Timedelta(days=int(n))
            except (ValueError, TypeError):
                pass
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"):
                try:
                    return pd.Timestamp(datetime.strptime(s, fmt))
                except ValueError:
                    pass
            return pd.NaT

        df["Fecha"] = df["Fecha"].apply(serial_to_fecha)

        # ── IMPORTE: UNFORMATTED_VALUE ya devuelve float directamente
        def parse_importe(val):
            if isinstance(val, (int, float)):
                return float(val)
            # Fallback texto
            s = str(val).strip().replace("$","").replace(" ","").replace("\xa0","")
            if not s or s in ("nan","None","-",""):
                return None
            dp, dc = s.rfind("."), s.rfind(",")
            if dp > 0 and dc > 0:
                s = s.replace(",","") if dp > dc else s.replace(".","").replace(",",".")
            elif dc > 0:
                s = s.replace(",",".")
            try:
                return float(s)
            except (ValueError, TypeError):
                return None

        df["Importe"] = pd.to_numeric(df["Importe"].apply(parse_importe), errors="coerce")

        antes = len(df)
        df = df.dropna(subset=["Fecha","Importe"])
        print(f"📊 Cargados: {len(df)} registros de {antes} filas")
        print(f"   Rango: {df['Fecha'].min().date()} → {df['Fecha'].max().date()}")

        if df.empty:
            return pd.DataFrame(), {}, "empty"

        df["Mes"]       = df["Fecha"].dt.to_period("M").astype(str)
        df["Fecha_str"] = df["Fecha"].dt.strftime("%d/%m/%Y")

        # 2. Listas maestras
        listas = load_listas(creds)

        return df, listas, "ok"

    except Exception as e:
        print(f"🔥 Error en load_sheet_data: {e}")
        traceback.print_exc()
        return None, None, f"error: {e}"


# ──────────────────────────────────────────────
# OAuth redirect
# ──────────────────────────────────────────────
@server.route("/")
def index():
    return redirect("/dashboard/")

# ──────────────────────────────────────────────
# Ruta de diagnóstico: /debug
# Abrí https://tu-app.onrender.com/debug
# Muestra los datos CRUDOS de Google Sheets antes de cualquier parsing
# ──────────────────────────────────────────────
@server.route("/debug")
def debug_data():
    try:
        from src.auth import get_google_credentials
        creds = get_google_credentials()
        service = build("sheets", "v4", credentials=creds)

        # 1. Pedir con FORMATTED_VALUE para ver el texto real de las celdas
        res_fmt = (service.spreadsheets().values()
                          .get(spreadsheetId=SHEET_ID,
                               range="Gastos Personales 2026!A:D",
                               valueRenderOption="FORMATTED_VALUE")
                          .execute())

        # 2. Pedir con UNFORMATTED_VALUE para ver números/seriales
        res_raw = (service.spreadsheets().values()
                          .get(spreadsheetId=SHEET_ID,
                               range="Gastos Personales 2026!A:D",
                               valueRenderOption="UNFORMATTED_VALUE",
                               dateTimeRenderOption="SERIAL_NUMBER")
                          .execute())

        fmt_rows = res_fmt.get("values", [])
        raw_rows = res_raw.get("values", [])

        EPOCH = pd.Timestamp("1899-12-30")

        rows_html = []
        header_fmt = fmt_rows[0] if fmt_rows else []
        for i, (rf, rr) in enumerate(zip(fmt_rows[1:], raw_rows[1:]), start=2):
            fecha_fmt = rf[0] if len(rf) > 0 else "?"
            fecha_raw = rr[0] if len(rr) > 0 else "?"
            importe_fmt = rf[3] if len(rf) > 3 else "?"
            importe_raw = rr[3] if len(rr) > 3 else "?"

            # Parsear fecha serial
            fecha_parsed = "?"
            try:
                n = float(str(fecha_raw))
                if 40000 < n < 60000:
                    fecha_parsed = (EPOCH + pd.Timedelta(days=int(n))).strftime("%d/%m/%Y")
                else:
                    fecha_parsed = f"serial fuera de rango: {n}"
            except:
                # Es texto, no serial
                fecha_parsed = f"TEXTO: {fecha_raw}"

            # Detectar anomalías
            anomalia = ""
            if fecha_fmt != fecha_parsed and fecha_parsed != "?":
                anomalia = f" ⚠️ DIFERENCIA: fmt={fecha_fmt} vs parsed={fecha_parsed}"

            rows_html.append(
                f"<tr style='background:{'#1a1a2e' if i%2==0 else '#16213e'}'>"
                f"<td style='padding:4px 10px;color:#aaa'>{i}</td>"
                f"<td style='padding:4px 10px;color:#0f3460'>{fecha_fmt}</td>"
                f"<td style='padding:4px 10px;color:#e94560'>{fecha_raw}</td>"
                f"<td style='padding:4px 10px;color:#00d4aa'>{fecha_parsed}</td>"
                f"<td style='padding:4px 10px;color:#ffd700'>{importe_fmt}</td>"
                f"<td style='padding:4px 10px;color:#90ee90'>{importe_raw}</td>"
                f"<td style='padding:4px 10px;color:red;font-weight:bold'>{anomalia}</td>"
                f"</tr>"
            )

        table_html = "\n".join(rows_html)

        return f"""
        <html><body style='background:#0d1117;color:#e6edf3;font-family:monospace;padding:20px'>
        <h2 style='color:#00d4aa'>🔍 Debug — Datos crudos de Google Sheets</h2>
        <p style='color:#8b949e'>
            Columna FORMATTED = lo que ves en el sheet |
            Columna RAW = serial/número sin formato |
            Columna PARSED = cómo lo interpreta el código
        </p>
        <table style='border-collapse:collapse;width:100%;font-size:13px'>
        <thead>
          <tr style='background:#21262d'>
            <th style='padding:6px 10px;color:#00d4aa'>#</th>
            <th style='padding:6px 10px;color:#58a6ff'>Fecha FORMATTED</th>
            <th style='padding:6px 10px;color:#f78166'>Fecha RAW (serial)</th>
            <th style='padding:6px 10px;color:#00d4aa'>Fecha PARSED</th>
            <th style='padding:6px 10px;color:#ffd700'>Importe FORMATTED</th>
            <th style='padding:6px 10px;color:#90ee90'>Importe RAW</th>
            <th style='padding:6px 10px;color:red'>Anomalía</th>
          </tr>
        </thead>
        <tbody>{table_html}</tbody>
        </table>
        </body></html>
        """, 200, {{"Content-Type": "text/html"}}

    except Exception as e:
        import traceback
        return f"<pre style='color:red;background:#000;padding:20px'>{traceback.format_exc()}</pre>", 500




# ──────────────────────────────────────────────
# Paletas y estilos
# ──────────────────────────────────────────────
ACCENT  = "#00d4aa"
BG_CARD = "#1a1f2e"
BG_DARK = "#0d1117"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"

PALETTE = px.colors.qualitative.Plotly
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Arial"),
    margin=dict(t=40, b=20, l=20, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT)),
)


def stat_card(title, value, icon, color=ACCENT):
    return dbc.Card(
        dbc.CardBody([
            html.Div(icon, style={"fontSize": "2rem", "marginBottom": "4px"}),
            html.P(title, style={"color": MUTED, "margin": "0", "fontSize": ".85rem"}),
            html.H4(value, style={"color": color, "margin": "0", "fontWeight": "bold"}),
        ]),
        style={
            "background": BG_CARD,
            "border": f"1px solid {color}22",
            "borderRadius": "12px",
            "textAlign": "center",
        },
    )


# ──────────────────────────────────────────────
# Layout
# ──────────────────────────────────────────────

# ── Estilos inline para que los dropdowns nunca queden tapados ──
DROPDOWN_STYLE = {
    "background": "#252d3d",
    # overflow visible es clave: sin esto el menú queda cortado por el card padre
    "overflow": "visible",
    "position": "relative",
    "zIndex": 1000,
}

FILTER_CARD_BODY_STYLE = {
    # El CardBody también debe permitir overflow visible
    "overflow": "visible",
    "position": "relative",
    "zIndex": 900,
}

app.layout = dbc.Container(
    fluid=True,
    style={"background": BG_DARK, "minHeight": "100vh", "padding": "20px"},
    children=[
        dcc.Store(id="store-data"),
        dcc.Interval(id="load-trigger", interval=500, max_intervals=1),

        # ── Header ──
        dbc.Row([
            dbc.Col([
                html.H2("💰 Gastos Personales 2026",
                        style={"color": ACCENT, "margin": "0", "fontWeight": "bold"}),
                html.P("Dashboard financiero personal · Google Sheets",
                       style={"color": MUTED, "margin": "0", "fontSize": ".9rem"}),
            ], width=9),
            dbc.Col([
                dbc.Button("🔄 Actualizar", id="btn-refresh", color="success",
                           outline=True, size="sm", className="me-2"),
            ], width=3, className="text-end d-flex align-items-center justify-content-end"),
        ], className="mb-4 align-items-center"),

        # ── Estado ──
        html.Div(id="alert-status"),

        # ── Filtros ──
        # FIX z-index: overflow visible en Card y CardBody
        dbc.Card(
            dbc.CardBody(
                dbc.Row([
                    dbc.Col([
                        html.Label("📅 Rango de fechas",
                                   style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.DatePickerRange(
                            id="filter-dates",
                            display_format="DD/MM/YYYY",
                            style={"width": "100%"},
                        ),
                    ], xs=12, md=4),

                    dbc.Col([
                        html.Label("📁 Rubro",
                                   style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(
                            id="filter-rubro",
                            multi=True,
                            placeholder="Todos",
                            style=DROPDOWN_STYLE,
                            # optionHeight para textos largos
                            optionHeight=38,
                        ),
                    ], xs=12, md=3, style={"overflow": "visible", "zIndex": 900}),

                    dbc.Col([
                        html.Label("🏷️ Sub-rubro",
                                   style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(
                            id="filter-subrubro",
                            multi=True,
                            placeholder="Todos",
                            style=DROPDOWN_STYLE,
                            optionHeight=38,
                        ),
                    ], xs=12, md=3, style={"overflow": "visible", "zIndex": 850}),

                    dbc.Col([
                        html.Label("💳 Medio de pago",
                                   style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(
                            id="filter-medio",
                            multi=True,
                            placeholder="Todos",
                            style=DROPDOWN_STYLE,
                            optionHeight=38,
                        ),
                    ], xs=12, md=2, style={"overflow": "visible", "zIndex": 800}),

                ], className="g-3"),
                style=FILTER_CARD_BODY_STYLE,
            ),
            style={
                "background": BG_CARD,
                "border": "1px solid #30363d",
                "borderRadius": "12px",
                "marginBottom": "20px",
                # FIX CLAVE: el card no debe recortar el dropdown con overflow hidden
                "overflow": "visible",
            },
        ),


        # ── KPI Cards ──
        dbc.Row(id="kpi-row", className="mb-4 g-3"),

        # ── Gráficos fila 1 ──
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📊 Gastos por Rubro",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-rubro",
                                          config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d",
                          "borderRadius": "12px"}),
            ], xs=12, lg=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🥧 Distribución por Medio de Pago",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-medio",
                                          config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d",
                          "borderRadius": "12px"}),
            ], xs=12, lg=6),
        ], className="mb-4 g-3"),

        # ── Gráficos fila 2 ──
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📈 Evolución Mensual de Gastos",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-evolucion",
                                          config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d",
                          "borderRadius": "12px"}),
            ], xs=12, lg=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🏷️ Top 8 Sub-rubros",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-subrubro",
                                          config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d",
                          "borderRadius": "12px"}),
            ], xs=12, lg=4),
        ], className="mb-4 g-3"),

        # ── Tabla ──
        dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    dbc.Col(html.Span("📋 Detalle de Gastos",
                                      style={"color": TEXT, "fontWeight": "bold"})),
                    dbc.Col(html.Span(id="table-count",
                                      style={"color": MUTED, "fontSize": ".85rem"}),
                            className="text-end"),
                ]),
                style={"background": BG_CARD, "borderBottom": "1px solid #30363d"},
            ),
            dbc.CardBody([
                dash_table.DataTable(
                    id="tabla-gastos",
                    columns=[
                        {"name": "Fecha",       "id": "Fecha_str"},
                        {"name": "Concepto",    "id": "Concepto"},
                        {"name": "Importe ($)", "id": "Importe_fmt"},
                        {"name": "Rubro",       "id": "Rubro Principal"},
                        {"name": "Sub-rubro",   "id": "Sub-rubro"},
                        {"name": "Medio",       "id": "Medio de Pago"},
                    ],
                    page_size=15,
                    sort_action="native",
                    filter_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#1f2937", "color": ACCENT,
                        "fontWeight": "bold", "border": "1px solid #30363d",
                    },
                    style_cell={
                        "backgroundColor": BG_CARD, "color": TEXT,
                        "border": "1px solid #30363d", "padding": "8px 12px",
                        "fontSize": ".88rem", "fontFamily": "Arial",
                        "maxWidth": "300px", "overflow": "hidden",
                        "textOverflow": "ellipsis",
                    },
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#161b22"},
                        {"if": {"filter_query": '{Rubro Principal} = "Ahorro/Inversiones"'},
                         "color": "#3fb950"},
                    ],
                    style_filter={
                        "backgroundColor": "#161b22", "color": TEXT,
                        "border": "1px solid #30363d",
                    },
                )
            ]),
        ], style={"background": BG_CARD, "border": "1px solid #30363d",
                  "borderRadius": "12px", "marginBottom": "20px"}),
    ],
)


# ──────────────────────────────────────────────
# Callbacks
# ──────────────────────────────────────────────

# 1. Carga inicial / Actualizar
@app.callback(
    Output("store-data",   "data"),
    Output("alert-status", "children"),
    Input("load-trigger",  "n_intervals"),
    Input("btn-refresh",   "n_clicks"),
    prevent_initial_call=False,
)
def load_data(_, __):
    df, listas, status = load_sheet_data()

    if status == "no_auth":
        return None, dbc.Alert(
            [html.Strong("⚠️ No autenticado. "),
             html.Span("Asegurate de tener configurada la variable GOOGLE_CREDENTIALS.")],
            color="warning", dismissable=False,
            style={"borderRadius": "8px", "marginBottom": "16px"},
        )
    if status == "empty":
        return None, dbc.Alert(
            "La hoja está vacía.", color="info",
            style={"borderRadius": "8px", "marginBottom": "16px"},
        )
    if status.startswith("error"):
        return None, dbc.Alert(
            f"Error al cargar datos: {status}", color="danger",
            style={"borderRadius": "8px", "marginBottom": "16px"},
        )

    store = {
        "df":     df.to_json(date_format="iso", orient="split"),
        "listas": listas,
    }
    return json.dumps(store), None


# 2. Poblar filtros
@app.callback(
    Output("filter-rubro",    "options"),
    Output("filter-subrubro", "options"),
    Output("filter-medio",    "options"),
    Output("filter-dates",    "min_date_allowed"),
    Output("filter-dates",    "max_date_allowed"),
    Output("filter-dates",    "start_date"),
    Output("filter-dates",    "end_date"),
    Input("store-data", "data"),
)
def populate_filters(data):
    try:
        if not data:
            return [], [], [], None, None, None, None

        store  = json.loads(data)
        df     = pd.read_json(io.StringIO(store["df"]), orient="split")
        listas = store.get("listas", {})

        if not df.empty:
            # Store serializa en ISO → no usar format fijo
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

        # Prioridad: Listas maestras > valores únicos del DataFrame
        rubros = listas.get("rubros") or sorted(
            df["Rubro Principal"].dropna().apply(lambda x: str(x).strip()).unique().tolist()
        )
        subrubros = listas.get("subrubros") or sorted(
            df["Sub-rubro"].dropna().apply(lambda x: str(x).strip()).unique().tolist()
        )
        medios = listas.get("medios") or sorted(
            df["Medio de Pago"].dropna().apply(lambda x: str(x).strip()).unique().tolist()
        )

        # Filtrar cadenas vacías
        rubros    = [v for v in rubros    if v and str(v).strip()]
        subrubros = [v for v in subrubros if v and str(v).strip()]
        medios    = [v for v in medios    if v and str(v).strip()]

        # Forzar inclusión de “Gasto Corriente”
        if "Gasto Corriente" not in rubros:
            rubros.append("Gasto Corriente")

        mk  = lambda lst: [{"label": v, "value": v} for v in lst]
        mn  = df["Fecha"].min().date() if not df.empty else None
        mx  = df["Fecha"].max().date() if not df.empty else None

        return mk(rubros), mk(subrubros), mk(medios), mn, mx, mn, mx

    except Exception:
        print("🔥 Error en populate_filters:")
        traceback.print_exc()
        return [], [], [], None, None, None, None

# 3. Actualizar dashboard
@app.callback(
    Output("kpi-row",         "children"),
    Output("chart-rubro",     "figure"),
    Output("chart-medio",     "figure"),
    Output("chart-evolucion", "figure"),
    Output("chart-subrubro",  "figure"),
    Output("tabla-gastos",    "data"),
    Output("table-count",     "children"),
    Input("store-data",       "data"),
    Input("filter-dates",     "start_date"),
    Input("filter-dates",     "end_date"),
    Input("filter-rubro",     "value"),
    Input("filter-subrubro",  "value"),
    Input("filter-medio",     "value"),
)
def update_dashboard(data, start_date, end_date, rubro, subrubro, medio):
    try:
        if not data:
            return [], go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], "0 registros"

        store = json.loads(data)
        df = pd.read_json(io.StringIO(store["df"]), orient="split")

        # Store serializa en ISO → sin format fijo; normalizar a medianoche
        df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.normalize()

        # ── Filtro de fechas: comparar solo la parte DATE (sin hora) ──
        if start_date and end_date:
            fi = pd.Timestamp(start_date).normalize()
            ff = pd.Timestamp(end_date).normalize()
            mask = (df["Fecha_dt"] >= fi) & (df["Fecha_dt"] <= ff)
            print(f"\n🗓  Filtro fecha: {fi.date()} → {ff.date()}")
            print(f"   Total antes del filtro: {len(df)}")
            print(f"   Registros fuera del rango:")
            fuera = df[~mask][["Fecha_dt","Importe","Concepto"]]
            for _, row in fuera.iterrows():
                print(f"     {row['Fecha_dt'].date()} | {row['Importe']} | {row['Concepto']}")
            df = df[mask]
            print(f"   Total después del filtro: {len(df)}")

        # ── Filtros categóricos (multi=True → value es lista) ──
        if rubro:
            df = df[df["Rubro Principal"].isin(rubro)]
        if subrubro:
            df = df[df["Sub-rubro"].isin(subrubro)]
        if medio:
            df = df[df["Medio de Pago"].isin(medio)]

        # Si después de filtrar no hay datos
        if df.empty:
            return [], go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], "0 registros"

        # ── Cálculos KPI ──
        total       = df["Importe"].sum()
        n_registros = len(df)
        promedio    = df["Importe"].mean()
        top_rubro   = (df.groupby("Rubro Principal")["Importe"].sum()
                         .reset_index()
                         .sort_values("Importe", ascending=False)
                         .iloc[0]["Rubro Principal"])

        # ── KPI cards ──
        kpis = dbc.Row([
            dbc.Col(stat_card("Total Gastado",  f"$ {total:,.0f}",    "💸"),          xs=6, md=3),
            dbc.Col(stat_card("Registros",      str(n_registros),      "📋", "#58a6ff"), xs=6, md=3),
            dbc.Col(stat_card("Promedio/gasto", f"$ {promedio:,.0f}", "📊", "#d2a8ff"), xs=6, md=3),
            dbc.Col(stat_card("Mayor rubro",    top_rubro,             "🏆", "#ffa657"), xs=6, md=3),
        ], className="g-3")

        # ── Gráfico Rubro ──
        rubro_df = (df.groupby("Rubro Principal")["Importe"].sum()
                      .reset_index().sort_values("Importe", ascending=True))
        fig_rubro = px.bar(
            rubro_df, x="Importe", y="Rubro Principal", orientation="h",
            color="Rubro Principal", color_discrete_sequence=PALETTE,
            text=rubro_df["Importe"].apply(lambda x: f"$ {x:,.0f}"),
        )
        fig_rubro.update_traces(textposition="outside", textfont_size=11)
        fig_rubro.update_layout(**PLOTLY_LAYOUT, showlegend=False,
                                 xaxis=dict(showgrid=True, gridcolor="#30363d"),
                                 yaxis=dict(showgrid=False))

        # ── Gráfico Medio de pago ──
        medio_df = (df.groupby("Medio de Pago")["Importe"].sum()
              .reset_index().sort_values("Importe", ascending=True))
        fig_medio = px.pie(
            medio_df, names="Medio de Pago", values="Importe",
            color="Medio de Pago", color_discrete_sequence=PALETTE,
            hole=0.4
        )
        fig_medio.update_layout(**PLOTLY_LAYOUT)

        # ── Evolución mensual ──
        df["Mes"] = df["Fecha_dt"].dt.to_period("M").dt.to_timestamp()
        evol_df  = (df.groupby(["Mes", "Rubro Principal"])["Importe"].sum()
                      .reset_index().sort_values("Mes"))
        fig_evol = px.line(
            evol_df, x="Mes", y="Importe", color="Rubro Principal",
            markers=True, color_discrete_sequence=PALETTE,
        )
        fig_evol.update_traces(line_width=2, marker_size=7)
        fig_evol.update_layout(
            **PLOTLY_LAYOUT,
            xaxis=dict(showgrid=True, gridcolor="#30363d"),
            yaxis=dict(showgrid=True, gridcolor="#30363d", tickformat="$,.0f"),
        )

        # ── Top 8 Sub-rubros ──
        sub_df  = (df.groupby("Sub-rubro")["Importe"].sum()
                     .nlargest(8).reset_index().sort_values("Importe", ascending=True))
        fig_sub = px.bar(
            sub_df, x="Importe", y="Sub-rubro", orientation="h",
            color="Sub-rubro", color_discrete_sequence=PALETTE,
            text=sub_df["Importe"].apply(lambda x: f"$ {x:,.0f}")
        )
        fig_sub.update_traces(textposition="outside", textfont_size=11)
        fig_sub.update_layout(**PLOTLY_LAYOUT, showlegend=False,
                               xaxis=dict(showgrid=True, gridcolor="#30363d",
                                          tickformat="$,.0f"),
                               yaxis=dict(showgrid=False))

        # ── Tabla ──
        df["Fecha_str"] = df["Fecha_dt"].dt.strftime("%d/%m/%Y")
        df["Importe_fmt"] = df["Importe"].apply(lambda x: f"$ {x:,.2f}")

        table_cols = ["Fecha_str", "Concepto", "Importe_fmt",
                      "Rubro Principal", "Sub-rubro", "Medio de Pago"]

        table_data = (df[table_cols + ["Fecha"]]
                        .sort_values("Fecha", ascending=False)
                        .drop(columns=["Fecha"])
                        .to_dict("records"))

        count_label = f"{n_registros} registros · Total: $ {total:,.0f}"

        return kpis, fig_rubro, fig_medio, fig_evol, fig_sub, table_data, count_label

    except Exception:
        print("🔥 Error en update_dashboard:")
        traceback.print_exc()
        return [], empty_fig, empty_fig, empty_fig, empty_fig, [], "Error en callback"


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  💰 Dashboard Gastos Personales 2026")
    print("=" * 60)
    print(f"  🌐 Abrí: http://localhost:{PORT}")
    print("=" * 60)
    app.run(debug=True, port=PORT, host="0.0.0.0")
