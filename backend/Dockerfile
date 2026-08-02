FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libglx-mesa0 \
    libgomp1 libgcc-s1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV TMPDIR=/tmp
ENV XDG_RUNTIME_DIR=/tmp
ENV PADDLEX_HOME=/tmp/.paddlex
ENV PADDLE_HOME=/tmp/.paddlex
ENV HF_HOME=/tmp/.cache/huggingface
ENV PADDLEX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install gunicorn
COPY . .

RUN mkdir -p /app/static /app/staticfiles /app/media /app/media/tmp /tmp/.paddlex /tmp/.paddle /tmp/.cache/huggingface

ENV SECRET_KEY=dummy-build-key-for-collectstatic
ENV DB_HOST=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_NAME=dummy
ENV DB_PORT=5432
ENV DEBUG=False

RUN python manage.py collectstatic --noinput || echo "collectstatic warning"

# 모델 미리 다운로드 - /tmp에 캐시
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='korean', use_textline_orientation=True)" || echo "paddle model cache failed"

RUN chmod -R 777 /app /tmp || true

EXPOSE 8000
CMD ["sh", "-c", "mkdir -p /tmp/.paddlex /tmp/.cache/huggingface && chmod -R 777 /tmp 2>/dev/null; python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 2 --timeout 180 --graceful-timeout 60 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile -"]
