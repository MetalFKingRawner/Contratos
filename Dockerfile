# ─────────────────────────────────────────────────
# 1. Base: Python + Debian slim
FROM python:3.11-slim

# 2. Instala dependencias de sistema y LibreOffice/unoconv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-writer \
    libreoffice-java-common \
    openjdk-11-jre-headless \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-roboto \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    fontconfig \
    build-essential \
    libpq-dev && \
    fc-cache -f -v && \
    rm -rf /var/lib/apt/lists/*

# 3. Crea directorio de la app
WORKDIR /app

# 4. Copia requirements y código
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comandos para aplicar migraciones directamente
#python manage.py makemigrations && \
RUN python manage.py migrate && \
    python manage.py collectstatic --noinput
 
# 5. Variables de entorno (opcionalmente puedes moverlas a Render)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 6. Expone puerto y comando de arranque
EXPOSE 8000
CMD ["gunicorn", "inmobiliaria.wsgi:application", "--bind", "0.0.0.0:8000"]
# ─────────────────────────────────────────────────
