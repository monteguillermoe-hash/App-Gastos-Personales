#!/bin/bash
# Iniciar el bot en segundo plano
python src/bot.py &

# Iniciar el dashboard de Dash con Gunicorn
exec gunicorn src.app:server --bind 0.0.0.0:$PORT
