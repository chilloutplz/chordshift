FROM python:3.11-slim

# libGL.so.1 에러 해결 - opencv가 필요로 하는 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglx-mesa0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic은 빌드타임에 DB 없이도 돌아가야 함 -> 더미 env
ENV SECRET_KEY=dummy-build-key-for-collectstatic
ENV DB_HOST=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_NAME=dummy
ENV DB_PORT=5432
ENV DEBUG=False

# static 폴더 없으면 에러나니 생성
RUN mkdir -p /app/static /app/staticfiles
RUN python manage.py collectstatic --noinput || echo "collectstatic warning - continue"

EXPOSE 8000
# CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
