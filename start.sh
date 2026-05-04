#!/bin/bash
# Iniciar el bot solo si existe
if [ -f "src/bot.py" ]; then
    python src/bot.py &
elif [ -f "bot.py" ]; then
    python bot.py &
fi

# Iniciar el dashboard de Dash con Gunicorn
# app.py está en la raíz, por lo que usamos 'app:server'
exec gunicorn app:server --bind 0.0.0.0:$PORT
