# Imagen con la aplicación (la librería) y su suite de pruebas.
#
# El código se copia dentro de la imagen y nunca se monta desde el host: un
# volumen enlazado sobre el directorio de trabajo taparía el código recién
# compilado y el contenedor podría ejecutar código obsoleto.
#
# El único estado persistente es la caché de paquetes, que vive en el volumen
# de datos `/data` declarado en `docker-compose.yml`.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CACHE_DIR=/data/pip-cache

WORKDIR /app

# Metadatos del proyecto y código de la aplicación: se hornean en la imagen.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY tests/ ./tests/

RUN mkdir -p "$PIP_CACHE_DIR"

# Las dependencias de desarrollo se resuelven al arrancar, con la caché
# persistida en el volumen de datos.
CMD ["sh", "-c", "pip install -e '.[dev]' && python -m pytest"]
