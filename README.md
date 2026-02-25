# Deploy-Aimind-Backend (아이마음 백엔드 API)

**아이마음**은 보호자·상담사가 아동의 HTP 그림과 그림일기를 업로드하면, AI가 분석·해석과 T-Score를 제공하는 **아동 심리 지원 플랫폼**입니다.  
이 저장소는 **FastAPI 백엔드 API**를 담당하며, 인증, 사용자·아동 관리, 일기·그림 분석 연동, 커뮤니티 기능을 제공합니다.

---

## 데모

- 웹 앱(이 API를 사용): [http://43.203.135.230.nip.io:3000/](http://43.203.135.230.nip.io:3000/)

---

## 아이마음 프로젝트 구성

아이마음은 4개 저장소로 구성됩니다. 이 저장소(Backend)는 API 게이트웨이·DB·S3·AiModels·OCR 연동을 담당합니다.

```
[사용자] → Frontend(3000) → Backend(8000) → Aimodels(8080) / OCR(8090)
```

| 저장소 | 역할 | 기본 포트 |
|--------|------|-----------|
| **Deploy-Aimind-Frontend** | 웹 UI (로그인, 그림 분석, 그림일기 OCR, 커뮤니티, 마이페이지) | 3000 |
| **Deploy-Aimind-Backend** (본 저장소) | REST API (인증, 사용자/아동, 분석·OCR 저장, 커뮤니티), AiModels·OCR 프록시 | 8000 |
| **Deploy-Aimind-Aimodels** | HTP 그림 분석·해석·T-Score·챗봇 (YOLO + RAG + Gemini) | 8080 |
| **Deploy-Aimind-OCR** | 그림일기 이미지 → 텍스트 추출 (VLM + Gemini) | 8090 |

**전체 서비스 실행 순서 (로컬):** 1) Backend → 2) Aimodels → 3) OCR → 4) Frontend.  
Backend `.env`에 `AIMODELS_BASE_URL=http://localhost:8080`, `OCR_BASE_URL=http://localhost:8090` 설정.  
Frontend의 `NEXT_PUBLIC_*`를 같은 주소로 맞추면 됩니다.

**누구를 위한 서비스인가요?**  
- **보호자**: 자녀의 HTP 그림·그림일기 업로드 → AI 해석·T-Score·추천 사항 확인  
- **상담사·교육기관**: 아동 심리 지원 참고 자료  
- **개발자**: 그림 분석·OCR·RAG 파이프라인 참고 및 확장

---

## 기능

- **인증**: 회원가입, 로그인, JWT 발급/검증, 카카오·구글 OAuth
- **사용자·아동**: 프로필, 프로필 이미지(S3), 자녀 정보 CRUD
- **일기·그림**: 그림 분석 결과 저장(MongoDB), OCR 결과 연동, AiModels·OCR 서비스 프록시
- **커뮤니티**: 카테고리, 전문가 목록, 게시글·댓글·좋아요·북마크·태그
- **챗봇**: AiModels `/chatbot` 프록시 (가이드/심리 분석 질문)

---

## 기술 스택

- **Python 3.11**, FastAPI, Uvicorn
- **MySQL** (SQLAlchemy): 사용자, 아동, 커뮤니티(게시글·댓글·태그 등)
- **MongoDB** (Motor, Beanie): 분석 로그(`analysis_logs`), 그림 분석 저장(`drawing_analyses`), 그림일기 OCR 저장(`diary_ocr`)
- **JWT, bcrypt**: 인증·비밀번호
- **AWS S3**: 프로필 이미지, 분석 박스 이미지, 그림일기 OCR 이미지

---

## 디렉터리 구조

| 경로 | 설명 |
|------|------|
| `main.py` | FastAPI 앱 진입점, 모든 라우트 |
| `auth.py` | JWT 생성/검증, 비밀번호 해시 |
| `config.py` | 환경 변수 로드 (JWT, DB, S3, MongoDB 등) |
| `db.py` | MySQL 연결, 세션 |
| `db_models.py` | SQLAlchemy 모델 (User, Child, Community* 등) |
| `mongo.py` | MongoDB 연결 (Beanie) |
| `analysis_mongo.py` | AnalysisLog, DrawingAnalysis, DiaryOcrEntry 등 MongoDB 모델 |
| `models.py` | Pydantic 요청/응답 모델 |
| `s3_storage.py` | S3 업로드 (프로필, 분석 박스 이미지, OCR 이미지) |
| `utils.py` | 커뮤니티 직렬화 등 유틸 |
| `sql/` | 스키마·초기 데이터 (users.sql, community.sql, AIMindSQL.sql 등) |
| `static/` | 정적 파일 (기본 프로필 이미지 등) |
| `scripts/` | API 테스트 스크립트 (test_analysis_api.sh, .ps1) |

---

## 사전 요구사항

- **Python 3.11+**
- **MySQL**, **MongoDB** (실행 중인 인스턴스 또는 접속 가능한 호스트)
- **AWS S3** 버킷 및 접근 키 (프로필·분석 이미지 업로드용)
- (선택) Docker

---

## 빌드 및 실행

### Docker

```bash
docker build -t aimind-backend .
docker run -p 8000:8000 --env-file .env aimind-backend
```

Dockerfile은 포트 **8000**으로 노출합니다.

### 로컬

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

`config.py`의 `HOST_PORT`(기본 9090)는 로컬 실행 시 포트 설정에 사용할 수 있습니다. Docker는 8000 고정입니다.

---

## 환경 변수

`.env` 파일에 다음을 설정합니다.

| 구분 | 변수 | 설명 |
|------|------|------|
| 인증 | `JWT_SECRET` | JWT 서명 시크릿 (필수) |
| | `JWT_EXPIRES_SEC` | 토큰 유효 시간(초), 예: 172800 |
| | `BCRYPT_SALT_ROUNDS` | 비밀번호 해시 라운드, 예: 10 |
| MySQL | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | DB 연결 정보 |
| | `DB_SSL_CA` | (선택) TLS CA 경로 |
| MongoDB | `MONGODB_URI`, `MONGODB_DB_NAME` | Beanie 연결 (분석·OCR 저장) |
| S3 | `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | 업로드용 |
| | `S3_PUBLIC_BASE_URL` | (선택) CDN/퍼블릭 URL |
| 외부 서비스 | `AIMODELS_BASE_URL` | AiModels API (챗봇, /analyze/score), 예: http://localhost:8080 |
| | `OCR_BASE_URL` | OCR 서비스 (그림일기), 예: http://127.0.0.1:8090 |
| OAuth | `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI` | 카카오 로그인 |
| | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | 구글 로그인 |
| 기타 | `FRONTEND_BASE_URL` | 프론트 주소 (리다이렉트 등), 예: http://localhost:3000 |
| | `HOST_PORT` | (선택) 로컬 포트, 기본 9090 |

---

## API 요약

인증이 필요한 엔드포인트는 `Authorization: Bearer <token>` 헤더를 사용합니다.

| 구분 | 메서드 | 경로 | 설명 |
|------|--------|------|------|
| 헬스 | GET | `/health` | 헬스 체크 |
| 챗봇 | POST | `/chatbot` | AiModels 챗봇 프록시 |
| 인증 | POST | `/auth/signup`, `/auth/login` | 회원가입, 로그인 |
| | GET | `/auth/kakao/login`, `/auth/kakao/callback` | 카카오 OAuth |
| | GET | `/auth/google/login`, `/auth/google/callback` | 구글 OAuth |
| | POST | `/auth/me` | 토큰 검증·현재 유저 |
| 사용자 | GET | `/children` | 자녀 목록 |
| | POST | `/children` | 자녀 등록 |
| | PUT | `/users/me/profile-image` | 프로필 이미지 업로드(S3) |
| 분석 | POST | `/analysis/save` | 분석 로그 저장(MongoDB) |
| | GET | `/analysis/{user_id}` | 유저별 분석 로그 목록 |
| 그림 분석 | POST | `/drawing-analyses` | 그림 분석 1건 저장 (S3 + MongoDB) |
| | GET | `/drawing-analyses` | 내 그림 분석 목록 |
| | GET | `/drawing-analyses/{analysis_id}` | 단건 조회 (T-Score는 AiModels 호출) |
| 그림일기 OCR | POST | `/diary-ocr/extract` | OCR 서비스 호출 후 결과 반환 (DB 미저장) |
| | POST | `/diary-ocr/extract-stream` | OCR 스트리밍 (SSE) |
| | GET | `/diary-ocr` | 저장된 OCR 목록 (user_id 쿼리) |
| | POST | `/diary-ocr` | OCR 이미지 S3 업로드 + OCR 호출 + MongoDB 저장 |
| 일기(레거시) | GET | `/post`, `/post/{post_id}` | 일기 목록/단건 |
| | POST | `/post`, PUT `/post/{post_id}`, DELETE `/post/{post_id}` | 일기 CRUD |
| 커뮤니티 | GET | `/community/categories`, `/community/experts`, `/community/stats` | 카테고리, 전문가, 통계 |
| | GET/POST | `/community/posts`, `/community/posts/{post_id}` | 게시글 목록/단건/작성/수정/삭제 |
| | GET/POST | `/community/posts/{post_id}/comments` | 댓글 목록/작성 |
| | DELETE | `/community/comments/{comment_id}` | 댓글 삭제 |
| | POST | `/community/posts/{post_id}/like`, `.../bookmark` | 좋아요, 북마크 |

---

## 참고

- CORS는 `main.py`에서 localhost/127.0.0.1 기준으로 설정되어 있습니다. 배포 시 `FRONTEND_BASE_URL` 등에 맞게 허용 오리진을 수정하세요.
- AiModels·OCR 서비스가 떠 있어야 챗봇, 그림 분석 T-Score, 그림일기 OCR 연동이 동작합니다.

---

## 라이선스 및 기여

라이선스는 본 저장소의 `LICENSE` 파일을 참고해 주세요. 버그 제보·기능 제안·Pull Request는 이 저장소의 이슈/PR로 남겨 주시면 됩니다.
