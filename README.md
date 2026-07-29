# ChordShift

기타 악보 업로드 → 모바일 최적화 이미지 저장(원본 삭제) → OCR/수동 코드 보정 → 조옮김 → 클라우드 재사용

## 폴더 구조

```
chordshift/
├── backend/                 # Django
│   ├── manage.py
│   ├── config/              # 프로젝트 설정 (구 chordshift)
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── scores/              # 앱 (모델, API, OCR/조옮김 유틸)
│   ├── media/               # 최적화된 이미지
│   ├── requirements.txt
│   └── static/
└── frontend/                # Vue 3 + Vite
    ├── src/
    │   ├── App.vue
    │   └── components/
    │       ├── UploadScore.vue
    │       └── ChordEditor.vue
    └── vite.config.js       # /api, /media → Django 프록시
```

## 스택
- Backend: Django + DRF + Pillow
- Frontend: Vue 3 + Vite
- OCR: PaddleOCR

## 실행

### Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

브라우저: http://localhost:5173

## API
- `POST /api/scores/upload/` – 이미지 업로드 (모바일 최적화, 원본 삭제)
- `POST /api/scores/{id}/transpose/` – `{ "semitones": N }`
- `PATCH /api/scores/{id}/update_chords/` – 코드 보정
- `GET /api/scores/by-token/{token}/` – 공유 토큰 재사용

## 이미지 정책
- 최대 1080×1920, JPEG quality 85
- EXIF 회전 보정
- 원본은 저장하지 않음
