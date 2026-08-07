FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV TMPDIR=/tmp
ENV XDG_RUNTIME_DIR=/tmp

# 조옮김 악보 렌더링용 폰트.
# 이게 없으면 scores/utils/render_sheet.py의 _get_font()가 시스템 폰트를
# 하나도 못 찾아서 PIL 기본 비트맵 폰트로 폴백되는데, 이 폰트는 크기 인자를
# 무시하므로 사용자가 코드 크기를 바꿔도 결과 이미지에 반영되지 않는다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

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

RUN chmod -R 777 /app /tmp || true

EXPOSE 8000
CMD ["sh", "-c", "python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 2 --timeout 60 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile -"]
