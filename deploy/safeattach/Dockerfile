# Imagen de detonación de SafeAttach (aislada, sin red en tiempo de ejecución).
# Renderiza/analiza el adjunto dentro del contenedor; nunca toca el host.
FROM debian:stable-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        libreoffice-core libreoffice-writer libreoffice-calc \
        poppler-utils \
    && pip3 install --no-cache-dir --break-system-packages oletools \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY detonate.py /detonate.py
ENTRYPOINT ["python3", "/detonate.py"]
