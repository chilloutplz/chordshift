# ChordShift

기타 코드 악보를 **업로드 → OCR → 보정 → 조옮김 → 결과 저장**하는 웹 앱입니다.

악보 이미지에서 코드를 인식하고, **코드줄** 단위로 위치를 맞춘 뒤 반음 조옮김한 새 악보를 생성합니다.  
정식 이미지는 **Cloudflare R2**에 저장하고, 브라우저는 Django 프록시(`/api/files/...`)로 조회합니다.

---

## 주요 기능

| 단계 | 내용 |
|------|------|
| **검색** | 곡 제목 검색, 가나다(초성) 폴더, 전체 N곡 표시 |
| **업로드** | 이미지 업로드 시 자동 OCR (임시 저장, DB 없음) |
| **보정** | 코드줄 배치·이동, 코드 삽입/삭제, 더블클릭 이름 수정 |
| **확정** | 보정본 DB 등록 + 수정본 이미지 생성 |
| **조옮김** | ± 반음 조옮김 후 결과 악보 생성·저장·다운로드 |
| **저장소** | 곡(Song) 단위 + 코드 변형(A코드, G코드 등 Variant) |
| **클라우드** | 원본·결과 이미지 → Cloudflare R2 |

### UX 요약

- 검색 후에만「새 악보 업로드」표시 (결과 없음 / 원하는 곡 없을 때)
- 코드 선택 후 코드줄 클릭으로 삽입, **Esc**로 선택 취소
- 코드 이름 수정은 **더블클릭**
- 변형 라벨은 시작 코드 기준 (`G코드`, `A코드` …)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.12, Django 5, Django REST Framework |
| OCR | PaddleOCR |
| Frontend | Vue 3, Vite |
| DB | SQLite (개발) |
| 이미지 | Pillow (리사이즈·결과 렌더) |
| 스토리지 | 로컬 `media/tmp` (임시) + **Cloudflare R2** (정식) |

---

## 폴더 구조

```
chordshift/
├── backend/
│   ├── config/           # Django settings, urls
│   ├── scores/           # API, models, OCR, render, R2 proxy
│   ├── media/tmp/        # 임시 업로드 (로컬, git 제외)
│   ├── .env              # 비밀키 (커밋 금지)
│   ├── .env.example
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   └── components/   # Home, Upload, ChordEditor, Transpose …
│   └── package.json
└── README.md
```

---

## 로컬 실행

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

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

## 환경 변수 (Cloudflare R2)

`backend/.env` 예시 (`.env.example` 참고):

```env
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=chordshift
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_REGION=auto
```

- R2 키가 있으면 `ImageField` 기본 저장소가 R2로 동작합니다.
- **임시 업로드**는 계속 로컬 `media/tmp` 를 사용합니다.
- 브라우저 이미지 URL은 `/api/files/<경로>` 프록시를 사용합니다 (비공개 버킷 대응).

`.env` 는 **Git에 올리지 마세요.**

---

## API 개요

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/songs/` | 곡 목록 |
| GET | `/api/songs/search/?q=` | 제목·토큰 검색 |
| POST | `/api/temp/upload/` | 임시 업로드 + OCR |
| POST | `/api/songs/from-temp/` | 보정본 저장 → Song 생성 |
| PATCH | `/api/songs/{id}/` | 코드줄 등 수정 |
| POST | `/api/songs/{id}/render_variant/` | 조옮김 결과 이미지 생성 |
| GET | `/api/files/<path>` | R2/로컬 파일 프록시 |

(구 `ScoreSheet` `/api/scores/` 엔드포인트도 일부 남아 있을 수 있습니다.)

---

## 데이터 모델 (개념)

```
Song (곡)
 ├─ title, chords(보정 위치), original_image
 └─ ScoreVariant[]  (A코드, G코드 … 결과 이미지)
```

- 업로드만 한 상태: DB 없음, `tmp` 만 존재  
- 보정본 저장/확정 시점: Song 생성 및 R2 저장  

---

## 개발 메모

- OCR 코드줄 위치는 인식 박스 기준 약간의 오프셋을 적용합니다.
- 결과 렌더는 코드줄 단위 흰 띠 + 코드 텍스트를 Pillow로 그립니다.
- 삭제 UI는 다인 사용을 고려해 프론트에서 제거된 상태입니다.
- Python 3.12 + PaddleOCR 버전은 `requirements.txt` 기준으로 맞추세요.

---

## 라이선스

개인/팀 프로젝트용. 필요 시 라이선스를 명시하세요.
