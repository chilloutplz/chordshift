# ChordShift

기타 코드 악보 이미지를 업로드하고 **OCR → 코드 보정 → 조옮김 → 공유/저장**하는 웹 앱입니다.

악보 이미지를 기반으로 코드 위치를 편집하고, 원하는 Key로 변환한 결과를 생성합니다.

---

## 현재 구현 방향

ChordShift는 OCR 정확도를 100% 자동화하는 방식보다,

**OCR로 초안 생성 → 사용자가 빠르게 보정 → 결과 생성**

방식을 목표로 합니다.

---

## 주요 기능

| 기능 | 상태 |
|---|---|
| 악보 이미지 업로드 | 구현 |
| OCR 코드 추출 | 구현 |
| 코드 위치/내용 보정 | 구현 진행 |
| 조옮김 처리 | 구현 |
| 결과 악보 렌더링 | 구현 |
| 공유용 토큰 생성 | 구현 |
| 변형 악보 관리 | 구현 |

---

## 데이터 구조

```
Song
 ├── original_image
 ├── chords (JSON)
 ├── original_key
 └── ScoreVariant
       ├── corrected
       └── transposed
```

- Song은 원본 악보와 보정된 코드 데이터를 관리합니다.
- 조옮김 결과는 ScoreVariant로 관리합니다.
- 같은 곡의 같은 반음 변환 결과는 하나만 유지합니다.

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| OCR | Google Vision OCR |
| Frontend | Vue 3, Vite |
| DB | PostgreSQL |
| Image | Pillow |
| Storage | Cloudflare R2 |

---

## 프로젝트 구조

```
chordshift/
├── backend/
│   ├── config/
│   ├── scores/
│   │   ├── models.py
│   │   ├── OCR 처리
│   │   ├── 렌더링
│   │   └── API
│   └── manage.py
│
├── frontend/
│   └── src/
│
└── README.md
```

---

## Backend 모델

### Song

- 제목
- 원본 이미지
- 코드 위치 데이터
- OCR 원문
- 원곡 Key
- 공유 토큰

### ScoreVariant

- 수정본(corrected)
- 조옮김본(transposed)
- 반음 이동 값
- 결과 이미지

---

## 저장 구조

### 임시 처리

업로드 후 검증 전 데이터는 임시 영역에서 처리합니다.

### 정식 저장

확정된 악보는 PostgreSQL 메타데이터와 Cloudflare R2 이미지를 사용합니다.

---

## 실행

### Backend

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
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

Backend `.env`

```env
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=

R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=
```

---

## 향후 계획

- 모바일 UI 개선
- 코드 자동 인식 정확도 향상
- 곡 검색 및 라이브러리 기능
- 사용자 공유 기능 확장

---

개인/팀 프로젝트용
