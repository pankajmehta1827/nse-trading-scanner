# NSE Swing Scanner: builds the React page, then serves it with the FastAPI backend.
#   docker build -t nse-scanner .
#   docker run -p 8000:8000 -e NSE_SCANNER_PASSWORD=choose-one nse-scanner

FROM node:20-slim AS page
WORKDIR /app/scanner/frontend
COPY scanner/frontend/package.json scanner/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund && test -x node_modules/.bin/vite   # npm can crash yet exit 0
COPY scanner/frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY scanner/backend/requirements.txt scanner/backend/requirements.txt
RUN pip install --no-cache-dir -r scanner/backend/requirements.txt
COPY .claude/skills/nse-swing/ .claude/skills/nse-swing/
COPY scanner/backend/ scanner/backend/
COPY --from=page /app/scanner/frontend/dist scanner/frontend/dist
RUN useradd --create-home scanner
USER scanner
WORKDIR /app/scanner/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
