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
from flask import Flask, redirect, request, send_from_directory
from dash import Dash, dcc, html, dash_table, Input, Output
import dash_bootstrap_components as dbc
from googleapiclient.discovery import build
from src.auth import get_google_credentials

# ═══════════════════════════════════════════════
#  ⚙️  CONFIGURACIÓN — LEER DESDE VARIABLES DE ENTORNO
# ═══════════════════════════════════════════════
SHEET_ID         = os.getenv("SHEET_ID", "1R6CujT2y1BY24nTQID9mieOd2Bek_NpFzDVhxC4f2T4")
SHEET_RANGE      = "Gastos Personales 2026!A:Z"
SECRET_KEY       = os.getenv("SECRET_KEY", "b36ac1d3ffaf7a5ba0cabd3299e1a5cee229111701bab640f3d273e04acfd870")
PORT             = int(os.getenv("PORT", 8080))
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
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="💰 Gastos 2026",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"},
        {"name": "apple-mobile-web-app-capable", "content": "yes"},
        {"name": "theme-color", "content": "#0d1117"}
    ]
)

# ──────────────────────────────────────────────
# PWA Routes and Configuration
# ──────────────────────────────────────────────
@server.route('/manifest.json')
def serve_manifest():
    return send_from_directory('assets', 'manifest.json')

@server.route('/sw.js')
def serve_sw():
    return send_from_directory('assets', 'sw.js')

app.index_string = '''
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
                window.addEventListener('load', function() {
                    navigator.serviceWorker.register('/sw.js').then(function(registration) {
                        console.log('ServiceWorker registration successful with scope: ', registration.scope);
                    }, function(err) {
                        console.log('ServiceWorker registration failed: ', err);
                    });
                });
            }
        </script>
    </body>
</html>
'''


# ──────────────────────────────────────────────
# Google Sheets helpers
# ──────────────────────────────────────────────



def load_listas(creds):
    """Carga las categorías maestras desde la pestaña Listas"""
    try:
        service = build("sheets", "v4", credentials=creds)
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range="Listas!A:Z"
        ).execute()
        values = result.get("values", [])
        if not values:
            return {"rubros": [], "subrubros": [], "medios": []}

        # Asumimos estructura fija basada en bot.py:
        # Columna A (0): Rubros
        # Columna B (1): Sub-rubros
        # Columna C (2): Medios de Pago
        
        rubros = []
        subrubros = []
        medios = []
        
        for row in values:
            if len(row) > 0 and row[0].strip() and row[0].strip().lower() not in ["rubro", "rubros", "rubro principal"]:
                rubros.append(row[0].strip())
            if len(row) > 1 and row[1].strip() and row[1].strip().lower() not in ["sub-rubro", "subrubro", "subrubros"]:
                subrubros.append(row[1].strip())
            if len(row) > 2 and row[2].strip() and row[2].strip().lower() not in ["medio de pago", "medios de pago", "medio"]:
                medios.append(row[2].strip())
                
        return {
            "rubros": sorted(list(set(rubros))),
            "subrubros": sorted(list(set(subrubros))),
            "medios": sorted(list(set(medios))),
        }
    except Exception as e:
        print(f"⚠️ Error en load_listas: {e}")
        return {"rubros": [], "subrubros": [], "medios": []}


def load_sheet_data():
    """Carga los datos de gastos y las listas maestras"""
    try:
        creds = get_google_credentials()
    except Exception as e:
        return None, None, "no_auth"
        
    try:
        service  = build("sheets", "v4", credentials=creds)
        
        # 1. Leer Gastos (Hoja: Gastos Personales 2026)
        RANGE_GASTOS = "Gastos Personales 2026!A:Z"
        res_gastos = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=RANGE_GASTOS
        ).execute()
        
        values_g = res_gastos.get("values", [])
        if not values_g:
            return pd.DataFrame(), {}, "empty"
            
        max_cols_g = max(len(row) for row in values_g)
        padded_g   = [row + [""] * (max_cols_g - len(row)) for row in values_g]
        header_g   = [h.strip() if h and h.strip() else f"Col_{i}" for i, h in enumerate(padded_g[0])]
        df = pd.DataFrame(padded_g[1:], columns=header_g)
        
        # Mapeo dinámico de columnas
        col_map = {}
        for col in df.columns:
            cl = str(col).lower().strip()
            if cl in ["fecha", "fechas", "date", "día", "dia"]: 
                col_map[col] = "Fecha"
            elif cl in ["concepto", "detalle", "descripción", "descripcion", "gasto"]: 
                col_map[col] = "Concepto"
            elif cl in ["importe", "monto", "precio", "valor"]: 
                col_map[col] = "Importe"
            elif cl in ["rubro principal", "rubro", "rubros", "categoria", "categoría"]: 
                col_map[col] = "Rubro Principal"
            elif cl in ["sub-rubro", "subrubro", "sub rubro", "subcategoria", "subcategoría"]: 
                col_map[col] = "Sub-rubro"
            elif cl in ["medio de pago", "medio", "metodo de pago", "forma de pago", "pago"]: 
                col_map[col] = "Medio de Pago"

        df = df.rename(columns=col_map)
        
        use_cols = ["Fecha", "Concepto", "Importe", "Rubro Principal", "Sub-rubro", "Medio de Pago"]
        missing_cols = [c for c in use_cols if c not in df.columns]
        
        if missing_cols:
            return None, None, f"error: Faltan columnas clave en la hoja. Esperaba: {', '.join(missing_cols)}. Leídas: {list(header_g)}"
            
        df = df[use_cols]
        
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
        df["Importe"] = pd.to_numeric(
            df["Importe"].astype(str).str.replace(",", ".").str.replace(" ", "").str.replace("$", ""),
            errors="coerce"
        )
        
        df = df.dropna(subset=["Fecha", "Importe"])
        
        if df.empty:
            return pd.DataFrame(), {}, "empty"
            
        df["Mes"] = df["Fecha"].dt.to_period("M").astype(str)
        df["Fecha_str"] = df["Fecha"].dt.strftime("%d/%m/%Y")

        # 2. Cargar Listas Maestras
        listas = load_listas(creds)

        return df, listas, "ok"
        
    except Exception as e:
        print(f"🔥 Error en load_sheet_data: {e}")
        return None, None, f"error: {e}"


# ──────────────────────────────────────────────
# OAuth routes
# ──────────────────────────────────────────────
@server.route("/")
def index():
    return redirect("/dashboard/")


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
        style={"background": BG_CARD, "border": f"1px solid {color}22",
               "borderRadius": "12px", "textAlign": "center"},
    )


# ──────────────────────────────────────────────
# Layout del dashboard
# ──────────────────────────────────────────────
app.layout = dbc.Container(
    fluid=True,
    style={"background": BG_DARK, "minHeight": "100vh", "padding": "20px"},
    children=[
        dcc.Store(id="store-data"),
        dcc.Interval(id="load-trigger", interval=500, max_intervals=1),

        # Header
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

        # Alerta de estado
        html.Div(id="alert-status"),

        # ── Filtros ────────────────────────────────────────────
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("📅 Rango de fechas", style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.DatePickerRange(
                            id="filter-dates",
                            display_format="DD/MM/YYYY",
                            style={"width": "100%"},
                        ),
                    ], xs=12, md=4),
                    dbc.Col([
                        html.Label("📁 Rubro", style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(id="filter-rubro", multi=True, placeholder="Todos",
                                     style={"background": "#252d3d"}),
                    ], xs=12, md=3),
                    dbc.Col([
                        html.Label("🏷️ Sub-rubro", style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(id="filter-subrubro", multi=True, placeholder="Todos",
                                     style={"background": "#252d3d"}),
                    ], xs=12, md=3),
                    dbc.Col([
                        html.Label("💳 Medio de pago", style={"color": MUTED, "fontSize": ".85rem"}),
                        dcc.Dropdown(id="filter-medio", multi=True, placeholder="Todos",
                                     style={"background": "#252d3d"}),
                    ], xs=12, md=2),
                ], className="g-3"),
            ])
        ], style={"background": BG_CARD, "border": "1px solid #30363d",
                  "borderRadius": "12px", "marginBottom": "20px"}),

        # ── KPI Cards ──────────────────────────────────────────
        dbc.Row(id="kpi-row", className="mb-4 g-3"),

        # ── Gráficos fila 1 ────────────────────────────────────
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📊 Gastos por Rubro",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-rubro", config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d", "borderRadius": "12px"}),
            ], xs=12, lg=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🥧 Distribución por Medio de Pago",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-medio", config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d", "borderRadius": "12px"}),
            ], xs=12, lg=6),
        ], className="mb-4 g-3"),

        # ── Gráficos fila 2 ────────────────────────────────────
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📈 Evolución Mensual de Gastos",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-evolucion", config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d", "borderRadius": "12px"}),
            ], xs=12, lg=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🏷️ Top 8 Sub-rubros",
                                   style={"background": BG_CARD, "color": TEXT,
                                          "borderBottom": "1px solid #30363d"}),
                    dbc.CardBody(dcc.Graph(id="chart-subrubro", config={"displayModeBar": False})),
                ], style={"background": BG_CARD, "border": "1px solid #30363d", "borderRadius": "12px"}),
            ], xs=12, lg=4),
        ], className="mb-4 g-3"),

        # ── Tabla ──────────────────────────────────────────────
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
                        {"name": "Fecha",          "id": "Fecha_str"},
                        {"name": "Concepto",        "id": "Concepto"},
                        {"name": "Importe ($)",     "id": "Importe_fmt"},
                        {"name": "Rubro",           "id": "Rubro Principal"},
                        {"name": "Sub-rubro",       "id": "Sub-rubro"},
                        {"name": "Medio",           "id": "Medio de Pago"},
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

# 1. Carga inicial y actualización
@app.callback(
    Output("store-data",  "data"),
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
        return None, dbc.Alert("La hoja está vacía.", color="info",
                                style={"borderRadius": "8px", "marginBottom": "16px"})
    if status.startswith("error"):
        return None, dbc.Alert(f"Error al cargar datos: {status}",
                                color="danger", style={"borderRadius": "8px", "marginBottom": "16px"})

    store = {
        "df": df.to_json(date_format="iso", orient="split"),
        "listas": listas
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
        
        store = json.loads(data)
        df = pd.read_json(io.StringIO(store["df"]), orient="split")
        if not df.empty:
            df["Fecha"] = pd.to_datetime(df["Fecha"])
        
        listas = store.get("listas", {})
        
        if df.empty and not listas.get("rubros"):
            return [], [], [], None, None, None, None
            
        # 1. Rubros (Listas > Datos)
        rubros = listas.get("rubros") or sorted(df["Rubro Principal"].dropna().unique())
        
        # 2. Sub-rubros (Listas > Datos)
        subrubros = listas.get("subrubros") or sorted(df["Sub-rubro"].dropna().unique())
        
        # 3. Medios de pago (Listas > Datos)
        medios = listas.get("medios") or sorted(df["Medio de Pago"].dropna().unique())

        mk = lambda lst: [{"label": v, "value": v} for v in lst]
        mn = df["Fecha"].min().date() if not df.empty else None
        mx = df["Fecha"].max().date() if not df.empty else None
        return mk(rubros), mk(subrubros), mk(medios), mn, mx, mn, mx
    except Exception:
        print("🔥 Error en populate_filters:")
        traceback.print_exc()
        return [], [], [], None, None, None, None


# 3. Actualizar todo el dashboard con los filtros
@app.callback(
    Output("kpi-row",        "children"),
    Output("chart-rubro",    "figure"),
    Output("chart-medio",    "figure"),
    Output("chart-evolucion","figure"),
    Output("chart-subrubro", "figure"),
    Output("tabla-gastos",   "data"),
    Output("table-count",    "children"),
    Input("store-data",       "data"),
    Input("filter-dates",     "start_date"),
    Input("filter-dates",     "end_date"),
    Input("filter-rubro",     "value"),
    Input("filter-subrubro",  "value"),
    Input("filter-medio",     "value"),
)
def update_dashboard(data, start_date, end_date, rubros, subrubros, medios):
    try:
        empty_fig = go.Figure(layout={**PLOTLY_LAYOUT,
                                       "annotations": [{"text": "Sin datos", "showarrow": False,
                                                         "font": {"color": MUTED, "size": 16}}]})
        empty = [[], [], empty_fig, empty_fig, empty_fig, empty_fig, "0 registros"]

        if not data:
            return (
                [],
                empty_fig, empty_fig, empty_fig, empty_fig,
                [], "Sin datos"
            )

        store = json.loads(data)
        df = pd.read_json(io.StringIO(store["df"]), orient="split")
        if df.empty:
             return ([], empty_fig, empty_fig, empty_fig, empty_fig, [], "0 registros")
             
        df["Fecha"] = pd.to_datetime(df["Fecha"])

        # Aplicar filtros
        if start_date:
            df = df[df["Fecha"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["Fecha"] <= pd.to_datetime(end_date)]
        if rubros:
            df = df[df["Rubro Principal"].isin(rubros)]
        if subrubros:
            df = df[df["Sub-rubro"].isin(subrubros)]
        if medios:
            df = df[df["Medio de Pago"].isin(medios)]

        if df.empty:
            return ([], empty_fig, empty_fig, empty_fig, empty_fig, [], "0 registros")

        total       = df["Importe"].sum()
        promedio    = df["Importe"].mean()
        n_registros = len(df)
        top_rubro   = df.groupby("Rubro Principal")["Importe"].sum().idxmax()

        # KPI cards
        kpis = dbc.Row([
            dbc.Col(stat_card("Total Gastado",  f"$ {total:,.0f}",      "💸"),  xs=6, md=3),
            dbc.Col(stat_card("Registros",      str(n_registros),        "📋", "#58a6ff"), xs=6, md=3),
            dbc.Col(stat_card("Promedio/gasto", f"$ {promedio:,.0f}",   "📊", "#d2a8ff"), xs=6, md=3),
            dbc.Col(stat_card("Mayor rubro",    top_rubro,               "🏆", "#ffa657"), xs=6, md=3),
        ], className="g-3")

        # ── Gráfico Rubro (barras horizontales)
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

        # ── Gráfico Medio de pago (torta)
        medio_df = df.groupby("Medio de Pago")["Importe"].sum().reset_index()
        fig_medio = px.pie(
            medio_df, values="Importe", names="Medio de Pago",
            color_discrete_sequence=PALETTE, hole=0.45,
        )
        fig_medio.update_traces(textposition="inside", textinfo="percent+label",
                                 textfont_size=12)
        fig_medio.update_layout(**PLOTLY_LAYOUT)

        # ── Evolución mensual (líneas por rubro)
        evol_df = (df.groupby(["Mes", "Rubro Principal"])["Importe"].sum()
                     .reset_index().sort_values("Mes"))
        fig_evol = px.line(
            evol_df, x="Mes", y="Importe", color="Rubro Principal",
            markers=True, color_discrete_sequence=PALETTE,
        )
        fig_evol.update_traces(line_width=2, marker_size=7)
        fig_evol.update_layout(
            **PLOTLY_LAYOUT,
            xaxis=dict(showgrid=True, gridcolor="#30363d"),
            yaxis=dict(showgrid=True, gridcolor="#30363d",
                       tickformat="$,.0f"),
        )

        # ── Top 8 Sub-rubros (barras verticales)
        sub_df = (df.groupby("Sub-rubro")["Importe"].sum()
                    .nlargest(8).reset_index().sort_values("Importe", ascending=True))
        fig_sub = px.bar(
            sub_df, x="Importe", y="Sub-rubro", orientation="h",
            color="Sub-rubro", color_discrete_sequence=PALETTE,
        )
        fig_sub.update_layout(**PLOTLY_LAYOUT, showlegend=False,
                               xaxis=dict(showgrid=True, gridcolor="#30363d",
                                          tickformat="$,.0f"),
                               yaxis=dict(showgrid=False))

        # ── Tabla
        df["Importe_fmt"] = df["Importe"].apply(lambda x: f"$ {x:,.2f}")
        if "Fecha_str" not in df.columns:
            df["Fecha_str"] = df["Fecha"].dt.strftime("%d/%m/%Y")
        table_cols = ["Fecha_str", "Concepto", "Importe_fmt",
                      "Rubro Principal", "Sub-rubro", "Medio de Pago"]
        table_data = df[table_cols].sort_values("Fecha_str", ascending=False).to_dict("records")
        count_label = f"{n_registros} registros · Total: $ {total:,.0f}"

        return kpis, fig_rubro, fig_medio, fig_evol, fig_sub, table_data, count_label

    except Exception:
        print("🔥 Error en update_dashboard:")
        traceback.print_exc()
        return ([], empty_fig, empty_fig, empty_fig, empty_fig, [], "Error en callback")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  💰 Dashboard Gastos Personales 2026")
    print("=" * 60)
    if SHEET_ID == "TU_SHEET_ID_AQUI":
        print("\n  ⚠️  ACORDATE de editar SHEET_ID en app.py")
        print("  El ID está en la URL de tu Google Sheet:")
        print("  https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit\n")
    print(f"  🌐 Abrí: http://localhost:{PORT}")
    print("=" * 60)

    app.run(debug=True, port=PORT, host="0.0.0.0")
y_fig, empty_fig, empty_fig, [], "Error en callback")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  💰 Dashboard Gastos Personales 2026")
    print("=" * 60)
    if SHEET_ID == "TU_SHEET_ID_AQUI":
        print("\n  ⚠️  ACORDATE de editar SHEET_ID en app.py")
        print("  El ID está en la URL de tu Google Sheet:")
        print("  https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit\n")
    print(f"  🌐 Abrí: http://localhost:{PORT}")
    print("=" * 60)

    app.run(debug=True, port=PORT, host="0.0.0.0")
