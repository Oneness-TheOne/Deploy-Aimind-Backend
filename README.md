# AiMind Backend (Docker)

AiMind 서비스의 **FastAPI 백엔드 API**입니다. 인증, 사용자/아동 관리, 일기·그림 분석 연동, 커뮤니티 기능을 제공합니다.

## 기능

- **인증**: 회원가입, 로그인, JWT 발급/검증
- **사용자·아동**: 프로필, 자녀 정보 CRUD
- **일기·그림**: 일기 작성, 그림 업로드, OCR/AI 분석 결과 연동 (외부 서비스 호출)
- **커뮤니티**: 게시글, 댓글, 좋아요, 북마크, 태그
- **전문가**: 전문가 프로필 등

## 기술 스택

- **Python 3.11**, FastAPI, Uvicorn
- **MySQL** (SQLAlchemy): 사용자, 아동, 커뮤니티 등
- **MongoDB** (Motor, Beanie): 분석 로그, 그림 분석 결과, OCR 결과 등
- **JWT, bcrypt**: 인증·비밀번호

## 디렉터리 구조

- `main.py` — FastAPI 앱 진입점, 라우트
- `auth.py` — JWT 생성/검증, 비밀번호 해시
- `db.py` — MySQL 연결, 세션
- `db_models.py` — SQLAlchemy 모델
- `mongo.py` — MongoDB 연결
- `analysis_mongo.py` — 분석·OCR 관련 MongoDB 모델
- `models.py` — Pydantic 요청/응답 모델
- `static/` — 정적 파일 (필요 시)

## 빌드 및 실행

```bash
docker build -t aimind-backend .
docker run -p 8000:8000 --env-file .env aimind-backend
```

## 환경 변수

- MySQL: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` 등
- MongoDB: `MONGO_URI` 등
- JWT: `JWT_SECRET`, `JWT_ALGORITHM` 등
- 외부 서비스 URL: OCR, AI 모델 API 주소 (필요 시)

## API 포트

기본 **8000** (Uvicorn). `GET /health` 등 헬스 체크 엔드포인트 제공.
