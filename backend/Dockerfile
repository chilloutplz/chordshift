FROM python:3.11-slim

# opencv 필요 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libglx-mesa0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV HOME=/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install gunicorn

COPY . .

# 중요! media 폴더 권한 문제 해결
RUN mkdir -p /app/static /app/staticfiles /app/media /app/media/tmp && chmod -R 777 /app/media /app/staticfiles

# 빌드타임용 더미 env
ENV SECRET_KEY=dummy-build-key-for-collectstatic
ENV DB_HOST=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_NAME=dummy
ENV DB_PORT=5432
ENV DEBUG=False

RUN python manage.py collectstatic --noinput || echo "collectstatic warning"

EXPOSE 8000
CMD ["sh", "-c", "python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --error-logfile -"]
