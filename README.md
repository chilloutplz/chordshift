# ChordShift

기타 코드 악보 이미지를 업로드하고 **OCR → 코드 보정 → 조옮김 → 공유/저장**하는 웹 앱입니다.

모바일에서도 악보 위 코드 위치를 빠르게 고치고, 원하는 Key로 변환한 결과를 만들 수 있습니다.

---

## 설계 방향

OCR 정확도를 100% 자동화하기보다,

**OCR로 초안 생성 → 사용자가 빠르게 보정 → 조옮김·결과 생성**

흐름을 목표로 합니다.

- 코드 **가로 좌표(`t`)** 는 OCR/사용자가 둔 값을 그대로 표시·저장합니다. (임의 재배치 없음)
- 편집 UI는 **모바일 터치**를 우선합니다. (단일 선택 기본 + `Mul.` 로 다중)

---

## 사용 흐름

1. **업로드** — 악보 이미지 선택
2. **OCR** — Google Vision으로 코드 초안 추출
3. **보정 (ChordEditor)** — 줄·코드 위치/이름 수정 후 저장
4. **조옮김 (Transpose)** — 반음 이동 후 결과 이미지 생성
5. **공유/보관** — 공유 토큰, 변형 악보 관리

---

## 주요 기능

| 기능 | 상태 |
|---|---|
| 악보 이미지 업로드 | 구현 |
| OCR 코드 추출 (대기열·상태 표시) | 구현 |
| 코드 위치/이름 보정 (ChordEditor) | 구현 |
| 줄(Line) / 코드(Chord) 탭 편집 | 구현 |
| 단일·다중 선택 (`Mul.`) | 구현 |
| 줄 박스 Top/Bottom/Left/Right 조절 | 구현 |
| 모바일 글자 크기 비례 축소 | 구현 |
| 가로 보기(landscape) 모드 | 구현 |
| 조옮김 처리 | 구현 |
| 결과 악보 렌더링 | 구현 |
| 공유용 토큰 | 구현 |
| 변형 악보(ScoreVariant) 관리 | 구현 |
| PWA (아이콘·스플래시) | 구현 |

### ChordEditor 요약

| 탭 | 역할 |
|---|---|
| **Line** | 줄 추가·선택, 세로 이동, Top/Bottom/Left/Right 가장자리 조절 |
| **Chord** | 코드 선택·이름 변경·삭제·좌우 미세 이동, 글자 크기(A−/A+) |

- 줄·코드 모두 **기본 단일 선택**, `Mul.` 켠 뒤에만 다중
- 저장 시 빈 코드만 제거하고, **x/y/`t` 좌표는 유지**

---

## 데이터 구조

```
Song
 ├── original / optimized image
 ├── chords (JSON: lines → items)
 ├── original_key
 ├── chord_font_size
 └── ScoreVariant
       ├── corrected
       └── transposed (semitone shift)
```

- **Song**: 원본 악보 + 보정된 코드 데이터
- **ScoreVariant**: 수정본·조옮김본. 같은 곡·같은 반음 결과는 하나만 유지
- 업로드 직후·확정 전은 **임시(temp)** 영역에서 처리

코드 JSON(대략):

```json
[
  {
    "id": "L0",
    "y": 0.12,
    "height": 0.032,
    "xStart": 0.05,
    "xEnd": 0.95,
    "items": [{ "id": "i0", "chord": "G", "t": 0.42 }]
  }
]
```

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Backend | Python 3.12, Django 5, DRF |
| OCR | Google Vision |
| Frontend | Vue 3, Vite 8, PWA |
| DB | PostgreSQL |
| Image | Pillow |
| Storage | Cloudflare R2 (S3 호환) |

---

## 프로젝트 구조

```
chordshift/
├── backend/
│   ├── config/              # Django settings, urls
│   ├── scores/
│   │   ├── models.py        # Song, ScoreVariant, OcrUsage
│   │   ├── song_views.py    # API
│   │   └── utils/
│   │         ocr.py
│   │         chord_transpose.py
│   │         render_sheet.py
│   │         temp_store.py
│   │         image_process.py
│   ├── requirements.txt
│   └── env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │     ChordEditor.vue
│   │   │     TransposePage.vue
│   │   │     HomePage.vue
│   │   │     UploadScore.vue
│   │   │     HelpPage.vue
│   │   ├── composables/chord-editor/
│   │   │     useStageZoom.js
│   │   │     useOcr.js
│   │   │     useLinesData.js
│   │   │     useStageInteractions.js
│   │   ├── constants/chords.js
│   │   ├── api/api.js
│   │   └── assets/chord-editor.css
│   └── package.json
│
└── README.md
```

ChordEditor는 큰 SFC를 composable로 나눈 상태입니다.

| Composable | 역할 |
|---|---|
| `useStageZoom` | 줌·팬 |
| `useOcr` | OCR 요청·큐 상태 |
| `useLinesData` | `toLines` / `compactLinesForSave` |
| `useStageInteractions` | 탭·드래그·배치 |

---

## 실행

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env   # 값 채우기
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 환경 변수

`backend/.env` (참고: `backend/env.example`)

```env
# PostgreSQL
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=

# Cloudflare R2
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=chordshift
R2_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_REGION=auto
# R2_CUSTOM_DOMAIN=https://pub-xxxx.r2.dev
```

Google Vision 등 OCR 관련 키는 배포 환경에 맞게 별도 설정합니다.

---

## 향후 계획

- 모바일 보정 UX 다듬기
- OCR 인식 품질 개선
- 곡 검색·라이브러리
- 공유 기능 확장

---

개인/팀 프로젝트용 · v1.0 계열
