# Servicio de Chat Maquita
FROM python:3.13-slim

WORKDIR /srv/chat

# Dependencias del sistema (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8790

# eventlet para Socket.IO en tiempo real
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:8790", "app_chat:application"]
