FROM python:3.11-slim

# Instalar Node.js 20
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências do frontend (camada em cache)
COPY frontend/package*.json ./frontend/
RUN npm --prefix frontend ci --legacy-peer-deps

# Copiar e buildar o frontend
COPY frontend/ ./frontend/
RUN npm --prefix frontend run build

# Instalar dependências Python (camada em cache)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar código do backend
COPY backend/ ./backend/

# Copiar frontend buildado para backend/static
RUN mkdir -p backend/static && cp -r frontend/dist/. backend/static/

WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
