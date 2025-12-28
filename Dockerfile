# Usar imagen base de Python Alpine (muy ligera)
FROM python:3.11-alpine

# Metadata
LABEL maintainer="Fran"
LABEL description="Indexerr - API compatible con Jackett para indexers de torrents"

# Instalar dependencias del sistema necesarias para lxml
RUN apk add --no-cache \
    libxml2-dev \
    libxslt-dev \
    gcc \
    musl-dev \
    && rm -rf /var/cache/apk/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Crear usuario no-root para seguridad
RUN addgroup -g 1000 indexerr && \
    adduser -D -u 1000 -G indexerr indexerr && \
    chown -R indexerr:indexerr /app

# Cambiar a usuario no-root
USER indexerr

# Exponer puerto
EXPOSE 15505

# Variables de entorno
ENV PYTHONUNBUFFERED=1

# Comando de inicio
CMD ["python3", "app.py"]
