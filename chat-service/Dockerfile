# Servicio de Chat Maquita
FROM python:3.13-slim

WORKDIR /srv/chat

# Base oficial con etiqueta actual y paquetes del sistema al día en cada build (Snyk 07/09/2026).
# No se migra a Alpine ni a versiones «rc» (D-9). Dependencias del sistema (psycopg2, etc.).
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        gcc libpq-dev curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# pip no hace falta en tiempo de ejecución: se retira tras instalar. Trivy/Snyk señalaban en
# la imagen las copias VENDORIZADAS dentro de pip (msgpack 1.1.2, setuptools 70.3.0), que no
# se pueden actualizar por separado; sin pip en la imagen no están y la superficie es menor.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip /root/.cache

COPY . .

EXPOSE 8790

# eventlet para Socket.IO en tiempo real
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:8790", "app_chat:application"]
