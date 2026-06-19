FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json ./
RUN npm install --omit=dev

RUN playwright install --with-deps chromium

COPY dashboard/package.json dashboard/
RUN cd dashboard && npm install --omit=dev

COPY . .
RUN cd dashboard && npm run build

RUN mkdir -p screenshots

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
