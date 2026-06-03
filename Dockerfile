FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:///data/restaurant-bot.db

# Run both bot and demo server
CMD ["sh", "-c", "python bot.py & gunicorn server:app --bind 0.0.0.0:${PORT:-8080} --workers 2"]
