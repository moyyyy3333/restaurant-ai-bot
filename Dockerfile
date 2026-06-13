FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg yt-dlp && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data && chmod 777 /data
ENV DATABASE_URL=sqlite:///data/restaurant-bot.db

# Start both bot and server
CMD sh -c 'python bot.py & gunicorn server:app --bind 0.0.0.0:${PORT:-8080} --workers 2'
