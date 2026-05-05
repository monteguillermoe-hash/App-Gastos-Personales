# Dashboard de Gastos y Bot de Telegram (PWA)

Este proyecto unifica un bot de Telegram y un dashboard interactivo en Dash (Flask) para gestionar gastos personales en Google Sheets. Está estructurado para ser desplegado como un único servicio web en Render y es instalable en celulares como PWA.

## 🚀 Estructura del Proyecto

```
APP/
├── src/
│   ├── app.py          # Dashboard web en Dash (Flask)
│   └── bot.py          # Bot de Telegram (python-telegram-bot)
├── assets/
│   ├── style.css       # Estilos del dashboard
│   ├── manifest.json   # Configuración PWA
│   ├── sw.js           # Service Worker PWA
│   ├── icon-192.png    # Icono PWA
│   └── icon-512.png    # Icono PWA
├── start.sh            # Script para iniciar bot y dashboard simultáneamente
├── Procfile            # Comando de inicio para Render
└── requirements.txt    # Dependencias de Python
```

## 🛠️ Requisitos Previos

1. **Telegram Token**: Créalo con [@BotFather](https://t.me/botfather).
2. **Google Service Account**:
   - Ve a [Google Cloud Console](https://console.cloud.google.com).
   - Crea una credencial de cuenta de servicio (Service Account).
   - Descarga la clave JSON.
   - **IMPORTANTE**: Asegúrate de compartir tu Google Sheet (`Gastos Personales 2026`) dándole permisos de Editor al email del Service Account (ej: `tu-bot@tu-proyecto.iam.gserviceaccount.com`).
3. **ID del Sheet**: Cópialo de la URL de tu Google Sheet.

## 💻 Desarrollo Local

1. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Crear archivo `.env` en la raíz con tus variables:
   ```env
   TELEGRAM_TOKEN=tu_token
   SPREADSHEET_ID=tu_sheet_id
   GOOGLE_CREDENTIALS={"type": "service_account", "project_id": "..."}
   ```
   *(Nota: Puedes pegar todo el JSON de Google Credentials en una sola línea en tu archivo `.env`, o crear un archivo `service_account.json` temporal).*
3. Ejecutar la aplicación:
   ```bash
   bash start.sh
   ```
   El dashboard estará en `http://localhost:8080/dashboard/`.

## ☁️ Despliegue en Render

1. Sube tu código a un repositorio en **GitHub**.
2. En Render, crea un nuevo **Web Service** conectado a tu repo.
3. Configuración de Render:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `bash start.sh` (o déjalo en blanco si Render detecta el `Procfile`).
4. Configurar **Variables de Entorno (Environment Variables)** en Render:
   - `TELEGRAM_TOKEN`: (El token de tu bot).
   - `SPREADSHEET_ID`: (El ID de tu Google Sheet).
   - `GOOGLE_CREDENTIALS`: (Copia y pega TODO el contenido del archivo JSON de tu Service Account aquí).

¡Listo! Al desplegar, Render correrá `start.sh` e iniciará tanto tu Bot como tu Dashboard.

## 📱 Instalar como App en el Celular (PWA)

1. Abre la URL pública de Render desde el navegador Safari (iOS) o Chrome (Android) en tu celular.
2. En Safari: Toca el botón "Compartir" y selecciona **"Agregar a inicio"**.
3. En Chrome: Debería salirte un banner inferior, o ve a los 3 puntos y toca **"Agregar a la pantalla de inicio"**.
