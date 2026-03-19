FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (opcional)
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar proyecto
COPY . .

# Exponer puerto
EXPOSE 8000

# Ejecutar FastAPI en modo producción
CMD ["bash", "-c", "echo $DATABASE_URL && fastapi run --host 0.0.0.0 --port 8000"]
