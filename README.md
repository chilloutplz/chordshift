# ChordShift

기타 코드 악보를 **업로드 → OCR → 보정 → 조옮김 → 결과 저장**하는 웹 앱입니다.

악보 이미지에서 코드를 인식하고, **코드줄** 단위로 위치를 맞춘 뒤 반음 조옮김한 새 악보를 생성합니다.  
메타데이터는 **PostgreSQL**, 정식 이미지는 **Cloudflare R2**에 저장하며, 브라우저는 Django 프록시(`/api/files/...`)로 이미지를 조회합니다.

---

## 주요 기능

| 단계 | 내용 |
|------|------|
| **검색** | 제목 검색, 가나다(초성) 폴더, 전체 N곡 |
| **업로드** | 이미지 업로드 시 자동 OCR (임시 저장, DB 없음) |
| **보정** | 코드줄 배치·이동, 코드 삽입/삭제, 더블클릭 이름 수정 |
| **확정** | 보정본 DB 등록 + 결과 이미지 생성 (같은 키는 덮어쓰기) |
| **조옮김** | ± 반음 (12로 정규화), 결과 생성·저장·다운로드, 로딩 표시 |
| **저장소** | Song + ScoreVariant (A코드, G코드 등) |
| **클라우드** | 원본·결과 → R2, 임시 업로드 → 로컬 `media/tmp` |

### UX 요약

- 검색 후에만「새 악보 업로드」표시
- 코드 선택 → 코드줄 클릭 삽입, **Esc** 취소
- 코드 이름 수정은 **더블클릭**
- 변형 라벨: 시작 코드 기준 (`G코드`, `A코드` …)
- 같은 곡·같은 반음 결과는 **파일·DB 덮어쓰기** (+2와 +14는 동일)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.12, Django 5, Django REST Framework |
| OCR | PaddleOCR |
| Frontend | Vue 3, Vite |
| DB | **PostgreSQL** (`psycopg`) |
| 이미지 | Pillow |
| 스토리지 | 로컬 `media/tmp` (임시) + **Cloudflare R2** (정식) |

---

## 폴더 구조

```
chordshift/
├── backend/
│   ├── config/             # settings, urls
│   ├── scores/             # API, models, OCR, render, R2 proxy
│   ├── media/tmp/          # 임시 업로드 (git 제외)
│   ├── .env                # 비밀값 (커밋 금지)
│   ├── .env.example
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   └── components/
│   └── package.json
└── README.md
```

---

## 환경 변수

`backend/.env` (`.env.example` 참고):

```env
# PostgreSQL (필수)
DB_HOST=svc.sel3.cloudtype.app
DB_PORT=30315
DB_NAME=chordshift
DB_USER=
DB_PASSWORD=

# Cloudflare R2
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=chordshift
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_REGION=auto
```

- DB 값이 없으면 서버가 기동하지 않습니다 (SQLite 없음).
- R2 키가 있으면 `ImageField` 기본 저장소가 R2입니다.
- 이미지 URL은 `/api/files/<경로>` 프록시를 사용합니다.

**`.env` 는 Git에 올리지 마세요.**

---

## 로컬 실행

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

API: `http://127.0.0.1:8000`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

앱: `http://localhost:5173`  
Vite가 `/api`, `/media`를 백엔드로 프록시합니다.

---

## 데이터 모델

```
Song (곡)
 ├─ title, chords(보정 위치), original_image
 └─ ScoreVariant[]   # song + transpose_semitones 유니크
      ├─ label (A코드 …)
      └─ image → R2 songs/variants/{song_id}_t{N}.jpg
```

- 업로드만: DB 없음, `tmp` 만
- 보정 확정 시: Song 생성 + R2 저장
- 같은 반음 재생성: **덮어쓰기**

---

## API 개요

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/songs/` | 곡 목록 |
| GET | `/api/songs/search/?q=` | 검색 |
| POST | `/api/temp/upload/` | 임시 업로드 + OCR |
| POST | `/api/songs/from-temp/` | 보정본 → Song 생성 |
| PATCH | `/api/songs/{id}/` | 코드줄 등 수정 |
| POST | `/api/songs/{id}/render_variant/` | 조옮김/보정 결과 이미지 |
| GET | `/api/files/<path>` | R2/로컬 파일 프록시 |

---

## 배포 메모 (Cloudtype 등)

1. PostgreSQL 리소스 생성 → `DB_*` 환경변수
2. R2 → `R2_*` 환경변수
3. 배포 시 `migrate` 실행
4. 프론트 빌드 산출물 또는 별도 서비스
5. 운영 시 `DEBUG=false`, `SECRET_KEY`, `ALLOWED_HOSTS` 설정 권장

---

## 라이선스

개인/팀 프로젝트용. 필요 시 라이선스를 명시하세요.
