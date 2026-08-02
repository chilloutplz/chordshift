FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV TMPDIR=/tmp
ENV XDG_RUNTIME_DIR=/tmp

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install gunicorn
COPY . .

RUN mkdir -p /app/static /app/staticfiles /app/media /app/media/tmp /tmp/.cache

ENV SECRET_KEY=dummy-build-key-for-collectstatic
ENV DB_HOST=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_NAME=dummy
ENV DB_PORT=5432
ENV DEBUG=False

RUN python manage.py collectstatic --noinput || echo "collectstatic warning"

# RapidOCR 모델 미리 캐시 - 이거 없으면 배포 후 첫 요청 60초 걸림
RUN python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR(lang='korean_english')" || echo "rapidocr cache failed"

RUN chmod -R 777 /app /tmp || true

EXPOSE 8000
CMD ["sh", "-c", "python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile -"]