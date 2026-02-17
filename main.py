
import base64
from datetime import datetime
from pathlib import Path
import os

from dotenv import load_dotenv

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import (
    create_jwt_token,
    get_current_user_context,
    get_optional_user_context,
    hash_password,
    verify_password,
)
from db import get_db, init_db
from mongo import close_mongo, init_mongo
from analysis_mongo import (
    AnalysisLog,
    AnalysisSaveRequest,
    DiaryOcrEntry,
    DrawingAnalysis,
    DrawingAnalysisSaveRequest,
)
from db_models import (
    Child,
    CommunityCategory,
    CommunityComment,
    CommunityPost,
    CommunityPostBookmark,
    CommunityPostImage,
    CommunityPostLike,
    CommunityPostTag,
    CommunityTag,
    ExpertProfile,
    Post,
    User,
)
from models import (
    ChildCreateRequest,
    CommunityCommentCreateRequest,
    CommunityPostCreateRequest,
    CommunityPostUpdateRequest,
    LoginRequest,
    PostCreateRequest,
    PostUpdateRequest,
    SignupRequest,
)


current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir / ".env")

AIMODELS_BASE_URL = os.getenv("AIMODELS_BASE_URL", "http://localhost:8080")
OCR_BASE_URL = os.getenv("OCR_BASE_URL", "http://127.0.0.1:8090")


class ChatbotRequest(BaseModel):
    question: str
    analysis_context: dict | None = None


class ChatbotResponse(BaseModel):
    question: str
    answer: str
from utils import (
    serialize_community_comment,
    serialize_community_post,
    serialize_community_posts,
    serialize_post,
    serialize_posts,
)
from s3_storage import (
    upload_profile_image_to_s3,
    upload_analysis_box_image_to_s3,
    upload_diary_ocr_image_to_s3,
)

app = FastAPI()

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Docker health check endpoint"""
    return {"status": "healthy"}


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("startup")
async def on_startup_mongo():
    await init_mongo()


@app.on_event("shutdown")
async def on_shutdown_mongo():
    await close_mongo()


@app.post("/chatbot", response_model=ChatbotResponse)
async def chatbot_proxy(payload: ChatbotRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "질문을 입력해 주세요."})

    request_body = {"question": question}
    if payload.analysis_context:
        request_body["analysis_context"] = payload.analysis_context

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AIMODELS_BASE_URL}/chatbot",
                json=request_body,
            )
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "챗봇 서버에 연결할 수 없습니다.", "error": str(exc)},
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": f"챗봇 서버 오류: {exc.response.status_code}",
                "body": exc.response.text,
            },
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "챗봇 응답이 JSON이 아닙니다.", "body": response.text},
        )

    answer = data.get("answer")
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "챗봇 응답이 올바르지 않습니다.", "body": data},
        )

    return ChatbotResponse(question=question, answer=answer)


# --- AI 분석 로그 (MongoDB) ---


@app.post("/analysis/save", status_code=status.HTTP_201_CREATED)
async def analysis_save(payload: AnalysisSaveRequest):
    """AI 그림 해석 결과 JSON을 MongoDB analysis_logs에 저장 (image_to_json, jsonToLlm, ocr 모듈 결과)."""
    log = AnalysisLog(
        user_id=payload.user_id,
        image_to_json=payload.image_to_json,
        json_to_llm_json=payload.json_to_llm_json,
        llm_result_text=payload.llm_result_text,
        ocr_json=payload.ocr_json,
    )
    await log.insert()
    return {
        "id": str(log.id),
        "user_id": log.user_id,
        "created_at": log.created_at.isoformat(),
    }


@app.get("/analysis/{user_id}")
async def get_analysis_logs(user_id: int):
    """특정 유저의 분석 기록 목록 (최신순). [레거시] analysis_logs"""
    logs = (
        await AnalysisLog.find(AnalysisLog.user_id == user_id)
        .sort([("created_at", -1)])
        .to_list()
    )
    return [
        {
            "id": str(doc.id),
            "user_id": doc.user_id,
            "created_at": doc.created_at.isoformat(),
            "image_to_json": doc.image_to_json,
            "json_to_llm_json": doc.json_to_llm_json,
            "llm_result_text": doc.llm_result_text,
            "ocr_json": doc.ocr_json,
        }
        for doc in logs
    ]


# --- 그림 분석 저장 (drawing_analyses: 요소분석 + S3 이미지 + 심리해석) ---


@app.post("/drawing-analyses", status_code=status.HTTP_201_CREATED)
async def create_drawing_analysis(payload: DrawingAnalysisSaveRequest):
    """그림 분석 1건 저장. element_analysis(image_json+features)를 MongoDB에 저장. S3 업로드는 실패해도 DB 저장 진행."""
    analyzed_urls = {}
    for key in ("tree", "house", "man", "woman"):
        b64 = payload.box_images_base64.get(key)
        if b64:
            try:
                url = await upload_analysis_box_image_to_s3(
                    b64, payload.user_id, key
                )
                if url:
                    analyzed_urls[key] = url
            except Exception:
                pass  # S3 실패해도 element_analysis는 DB에 저장
    doc = DrawingAnalysis(
        user_id=payload.user_id,
        child_info=payload.child_info,
        element_analysis=payload.element_analysis,
        analyzed_image_urls=analyzed_urls,
        psychological_interpretation=payload.psychological_interpretation,
        comparison=payload.comparison,
        recommendations=getattr(payload, "recommendations", []) or [],
        overall_psychology_result=getattr(payload, "overall_psychology_result", {}) or {},
    )
    await doc.insert()
    return {
        "id": str(doc.id),
        "user_id": doc.user_id,
        "created_at": doc.created_at.isoformat(),
    }


@app.get("/drawing-analyses")
async def list_drawing_analyses(
    user_id: int,
    context=Depends(get_current_user_context),
):
    """내 그림 분석 목록 (최신순). 인증된 유저만 본인 것 조회."""
    if context["user"].id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    docs = (
        await DrawingAnalysis.find(DrawingAnalysis.user_id == user_id)
        .sort([("created_at", -1)])
        .to_list()
    )
    return [
        {
            "id": str(d.id),
            "user_id": d.user_id,
            "child_info": d.child_info,
            "created_at": d.created_at.isoformat(),
            "element_analysis": d.element_analysis,
            "analyzed_image_urls": d.analyzed_image_urls,
            "psychological_interpretation": d.psychological_interpretation,
            "comparison": d.comparison,
            "recommendations": getattr(d, "recommendations", []) or [],
            "전체_심리_결과": getattr(d, "overall_psychology_result", {}) or {},
        }
        for d in docs
    ]


def _normalize_gender_for_score(value: str | None) -> str:
    v = (value or "").strip().lower()
    if v in {"male", "m", "남", "남아"}:
        return "남"
    if v in {"female", "f", "여", "여아"}:
        return "여"
    return ""


async def _call_aimodels_analyze_score(
    element_analysis: dict,
    child_info: dict,
) -> dict | None:
    """DB의 element_analysis로 AiModels /analyze/score 호출 → T-Score 반환."""
    results = {
        k: {"image_json": v}
        for k, v in (element_analysis or {}).items()
        if v and isinstance(v, dict) and (k in {"tree", "house", "man", "woman"})
    }
    if not results:
        return None
    try:
        age_raw = child_info.get("age") or child_info.get("나이") or "0"
        age = int(age_raw) if str(age_raw).isdigit() else 0
        age = max(7, min(13, age)) if age else 8
        gender = _normalize_gender_for_score(
            child_info.get("gender") or child_info.get("성별") or ""
        )
        if not gender:
            return None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{AIMODELS_BASE_URL}/analyze/score",
                json={"results": results, "age": age, "gender": gender},
            )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


@app.get("/drawing-analyses/{analysis_id}")
async def get_drawing_analysis(
    analysis_id: str,
    context=Depends(get_current_user_context),
):
    """그림 분석 1건 상세 조회. DB의 element_analysis로 T-Score 재계산 후 comparison에 반영."""
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(analysis_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    doc = await DrawingAnalysis.get(oid)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if doc.user_id != context["user"].id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    comparison = dict(doc.comparison or {})

    drawing_scores = await _call_aimodels_analyze_score(
        doc.element_analysis or {},
        doc.child_info or {},
    )
    if drawing_scores:
        comparison["drawing_scores"] = drawing_scores

    return {
        "id": str(doc.id),
        "user_id": doc.user_id,
        "child_info": doc.child_info,
        "created_at": doc.created_at.isoformat(),
        "element_analysis": doc.element_analysis,
        "analyzed_image_urls": doc.analyzed_image_urls,
        "psychological_interpretation": doc.psychological_interpretation,
        "comparison": comparison,
        "recommendations": getattr(doc, "recommendations", []) or [],
        "전체_심리_결과": getattr(doc, "overall_psychology_result", {}) or {},
    }


async def _call_ocr_diary_ocr(
    *,
    contents: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """OCR 서버 /diary-ocr 호출 (그림일기 OCR 파이프라인)."""
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OCR_BASE_URL}/diary-ocr",
                files={"file": (filename, contents, content_type)},
            )
        response.raise_for_status()
    except httpx.RequestError as exc:
        print(f"[diary-ocr/extract] OCR 서버 연결 실패 (URL={OCR_BASE_URL}/diary-ocr): {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "OCR 서버에 연결할 수 없습니다. OCR 서버가 실행 중인지, .env의 OCR_BASE_URL이 맞는지 확인하세요.",
                "error": str(exc),
            },
        )
    except httpx.HTTPStatusError as exc:
        print(f"[diary-ocr/extract] OCR 서버 응답 오류 status={exc.response.status_code} body={exc.response.text[:500]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "OCR 서버 오류. OCR 서버 터미널 로그를 확인하세요.",
                "status_code": exc.response.status_code,
                "body": (exc.response.text or "")[:1000],
            },
        )
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "AI Models 응답이 JSON이 아닙니다.", "body": response.text},
        )
    raw = data[0] if isinstance(data, list) and data else data
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "AI Models 응답 형식이 올바르지 않습니다.", "body": data},
        )
    return raw


@app.post("/diary-ocr/extract")
async def extract_diary_ocr_text(file: UploadFile = File(...)):
    """그림일기 이미지 → AiModels diary_ocr_pipeline → 추출 결과만 반환 (저장 없음). 텍스트 추출하기 버튼용.
    응답에 추출에 사용한 이미지를 image_data_url 로 포함해 카드 사진란에 쓸 수 있게 함."""
    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "파일을 업로드해 주세요."})
    contents = await file.read()
    content_type = file.content_type or "image/jpeg"
    extracted = await _call_ocr_diary_ocr(
        contents=contents,
        filename=file.filename,
        content_type=content_type,
    )
    if not isinstance(extracted, dict):
        extracted = {}
    out = dict(extracted)
    # AiModels가 크롭된 이미지(image_data_url)를 보냈으면 그대로 사용, 없으면 업로드 원본을 data URL로 포함
    if out.get("image_data_url"):
        pass  # 이미 있음 (크롭 이미지)
    else:
        b64 = base64.b64encode(contents).decode("utf-8")
        ct = (content_type or "image/jpeg").split(";")[0].strip() or "image/jpeg"
        out["image_data_url"] = f"data:{ct};base64,{b64}"
    return out


@app.post("/diary-ocr/extract-stream")
async def extract_diary_ocr_text_stream(file: UploadFile = File(...)):
    """그림일기 OCR 진행률 스트리밍. OCR 서버의 SSE 스트림을 그대로 전달."""
    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "파일을 업로드해 주세요."})
    contents = await file.read()
    content_type = file.content_type or "image/jpeg"

    async def stream():
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{OCR_BASE_URL}/diary-ocr-stream",
                    files={"file": (file.filename, contents, content_type)},
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                err = str(exc)
                if hasattr(exc, "response") and exc.response is not None:
                    try:
                        err = exc.response.text[:500]
                    except Exception:
                        pass
                yield f"data: {__import__('json').dumps({'error': True, 'detail': err}, ensure_ascii=False)}\n\n".encode("utf-8")

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/diary-ocr")
async def get_diary_ocr_entries(context=Depends(get_current_user_context)):
    """저장된 그림일기 OCR 목록 조회. 토큰의 로그인 사용자 기준으로만 조회."""
    user_id = context["user"].id
    entries = await DiaryOcrEntry.find(DiaryOcrEntry.user_id == user_id).sort(-DiaryOcrEntry.created_at).to_list()
    return [
        {
            "id": str(doc.id),
            "image_url": doc.image_url or "",
            "corrected_text": doc.corrected_text or "",
            "original_text": doc.original_text or "",
            "date": doc.date or "",
            "title": doc.title or "",
            "weather": doc.weather or "",
            "child_name": doc.child_name or "",
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
        }
        for doc in entries
    ]


@app.post("/diary-ocr", status_code=status.HTTP_201_CREATED)
async def save_diary_ocr_entry(
    context=Depends(get_current_user_context),
    file: UploadFile = File(...),
    date: str = Form(""),
    title: str = Form(""),
    original_text: str = Form(""),
    corrected_text: str = Form(""),
    weather: str = Form(""),
    child_id: str = Form(""),
    child_name: str = Form(""),
):
    """그림일기 저장: 크롭 이미지를 S3에 업로드 후 MongoDB에 저장."""
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "이미지 파일을 업로드해 주세요."},
        )
    user_id = context["user"].id
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "빈 파일입니다."},
        )
    content_type = file.content_type or "image/jpeg"
    image_url = await upload_diary_ocr_image_to_s3(
        contents=contents,
        user_id=user_id,
        filename=file.filename,
        content_type=content_type,
    )
    child_id_int = None
    if child_id and child_id.strip().isdigit():
        child_id_int = int(child_id.strip())
    doc = DiaryOcrEntry(
        user_id=user_id,
        image_url=image_url,
        date=(date or "").strip(),
        title=(title or "").strip(),
        original_text=(original_text or "").strip(),
        corrected_text=(corrected_text or "").strip(),
        weather=(weather or "").strip(),
        child_id=child_id_int,
        child_name=(child_name or "").strip(),
    )
    await doc.insert()
    return {
        "id": str(doc.id),
        "image_url": doc.image_url,
        "date": doc.date,
        "title": doc.title,
        "original_text": doc.original_text,
        "corrected_text": doc.corrected_text,
        "weather": doc.weather,
        "child_name": doc.child_name,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
    }


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    found = db.query(User).filter(User.email == payload.email).first()
    if found:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "회원이 있습니다!"},
        )

    hashed = hash_password(payload.password)
    user = User(
        password=hashed,
        name=payload.name,
        email=payload.email,
        profile_image_url="base",
        region=payload.region,
        agree_terms=1 if payload.agree_terms else 0,
        agree_privacy=1 if payload.agree_privacy else 0,
        agree_marketing=1 if payload.agree_marketing else 0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt_token(str(user.id))
    return {"token": token, "email": user.email}



@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "회원정보가 없습니다!"},
        )

    if not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "비밀번호를 확인하세요!"},
        )

    token = create_jwt_token(str(user.id))
    return {"token": token, "email": payload.email}


@app.post("/auth/me")
def me(context=Depends(get_current_user_context)):
    user = context["user"]
    return {
        "token": context["token"],
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_image_url": _resolve_profile_image_url(user.profile_image_url),
        # "profile_image_url": user.profile_image_url,
        "region": user.region,
        "created_at": user.created_at,
    }


# --- 아이(children) API ---


@app.get("/children")
def get_my_children(
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """내가 등록한 아이 목록"""
    children = (
        db.query(Child)
        .filter(Child.user_id == context["user"].id)
        .order_by(Child.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "age": c.age,
            "gender": c.gender,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in children
    ]


@app.post("/children", status_code=status.HTTP_201_CREATED)
def create_child(
    payload: ChildCreateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """아이 등록"""
    child = Child(
        user_id=context["user"].id,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return {
        "id": child.id,
        "name": child.name,
        "age": child.age,
        "gender": child.gender,
        "created_at": child.created_at.isoformat() if child.created_at else None,
    }


@app.put("/users/me/profile-image")
async def update_profile_image(
    image: UploadFile = File(...),
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    user = context["user"]
    image_url = await upload_profile_image_to_s3(image, user.id)
    user.profile_image_url = image_url
    db.commit()
    db.refresh(user)
    return {"profile_image_url": _resolve_profile_image_url(user.profile_image_url)}


def _resolve_profile_image_url(value: str | None) -> str | None:
    if not value or value == "base":
        return "/static/profile-default.svg"
    return value


@app.get("/post")
def get_posts(
    email: str | None = None,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    query = db.query(Post)
    if email:
        query = query.filter(Post.userid == email)
    data = query.order_by(Post.createdAt.desc()).all()
    return serialize_posts(data)


@app.get("/post/{post_id}")
def get_post(
    post_id: str,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    try:
        post_id_int = int(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 포스트가 없습니다"},
        )
    post = db.query(Post).filter(Post.id == post_id_int).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 포스트가 없습니다"},
        )
    return serialize_post(post)


@app.post("/post", status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    user = context["user"]
    now = datetime.utcnow()
    post = Post(
        text=payload.text,
        userIdx=user.id,
        name=user.name,
        userid=user.email,
        createdAt=now,
        updatedAt=now,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return serialize_post(post)


@app.put("/post/{post_id}")
def update_post(
    post_id: str,
    payload: PostUpdateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    user = context["user"]
    try:
        post_id_int = int(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}에 대한 포스트가 없습니다"},
        )
    existing = db.query(Post).filter(Post.id == post_id_int).first()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}에 대한 포스트가 없습니다"},
        )
    if existing.userIdx != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    existing.text = payload.text
    existing.updatedAt = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    return serialize_post(existing)


@app.delete("/post/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: str,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    user = context["user"]
    try:
        post_id_int = int(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}에 대한 포스트가 없습니다"},
        )
    existing = db.query(Post).filter(Post.id == post_id_int).first()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}에 대한 포스트가 없습니다"},
        )
    if existing.userIdx != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    db.delete(existing)
    db.commit()
    return None


@app.get("/community/categories")
def get_community_categories(db: Session = Depends(get_db)):
    categories = (
        db.query(CommunityCategory)
        .order_by(CommunityCategory.sort_order.asc(), CommunityCategory.id.asc())
        .all()
    )
    return [
        {
            "id": category.id,
            "slug": category.slug,
            "label": category.label,
            "sort_order": category.sort_order,
        }
        for category in categories
    ]


@app.get("/community/experts")
def get_community_experts(db: Session = Depends(get_db)):
    experts = (
        db.query(ExpertProfile, User)
        .join(User, User.id == ExpertProfile.user_id)
        .order_by(ExpertProfile.answer_count.desc())
        .all()
    )
    return [
        {
            "user_id": expert.user_id,
            "name": user.name,
            "title": expert.title,
            "answer_count": expert.answer_count,
        }
        for expert, user in experts
    ]


@app.get("/community/stats")
def get_community_stats(db: Session = Depends(get_db)):
    users_count = db.query(func.count(User.id)).scalar() or 0
    posts_count = db.query(func.count(CommunityPost.id)).scalar() or 0
    comments_count = db.query(func.count(CommunityComment.id)).scalar() or 0
    experts_count = db.query(func.count(ExpertProfile.user_id)).scalar() or 0
    return {
        "users": users_count,
        "posts": posts_count,
        "comments": comments_count,
        "experts": experts_count,
    }


@app.get("/community/posts")
def get_community_posts(
    category: str | None = None,
    search: str | None = None,
    sort: str = "latest",
    page: int = 1,
    page_size: int = 10,
    context=Depends(get_optional_user_context),
    db: Session = Depends(get_db),
):
    query = db.query(CommunityPost).join(CommunityCategory)
    if category and category != "all":
        query = query.filter(CommunityCategory.slug == category)
    if search:
        keyword = f"%{search}%"
        query = query.filter(
            (CommunityPost.title.like(keyword)) | (CommunityPost.content.like(keyword))
        )

    if sort in {"view_count", "views"}:
        query = query.order_by(
            CommunityPost.view_count.desc(),
            CommunityPost.created_at.desc(),
        )
    elif sort in {"like_count", "likes"}:
        query = query.order_by(
            CommunityPost.like_count.desc(),
            CommunityPost.created_at.desc(),
        )
    elif sort == "popular":
        query = query.order_by(
            CommunityPost.like_count.desc(),
            CommunityPost.view_count.desc(),
            CommunityPost.created_at.desc(),
        )
    else:
        query = query.order_by(CommunityPost.created_at.desc())

    total = query.with_entities(func.count(CommunityPost.id)).scalar() or 0
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    offset = (page - 1) * page_size

    posts = query.offset(offset).limit(page_size).all()
    current_user_id = context["user"].id if context.get("user") else None
    return {
        "items": serialize_community_posts(posts, current_user_id),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/community/posts/{post_id}")
def get_community_post(
    post_id: int,
    context=Depends(get_optional_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )
    post.view_count += 1
    db.commit()
    db.refresh(post)
    current_user_id = context["user"].id if context.get("user") else None
    return serialize_community_post(post, current_user_id)


@app.post("/community/posts", status_code=status.HTTP_201_CREATED)
def create_community_post(
    payload: CommunityPostCreateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    category = (
        db.query(CommunityCategory)
        .filter(CommunityCategory.slug == payload.category_slug)
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "유효하지 않은 카테고리입니다"},
        )

    now = datetime.utcnow()
    post = CommunityPost(
        user_id=context["user"].id,
        category_id=category.id,
        title=payload.title,
        content=payload.content,
        created_at=now,
        updated_at=now,
    )
    db.add(post)
    db.flush()

    for index, image_url in enumerate(payload.images or []):
        db.add(
            CommunityPostImage(
                post_id=post.id,
                image_url=image_url,
                sort_order=index,
                created_at=now,
            )
        )

    for tag_name in payload.tags or []:
        normalized = tag_name.strip().lstrip("#")
        if not normalized:
            continue
        tag = db.query(CommunityTag).filter(CommunityTag.name == normalized).first()
        if not tag:
            tag = CommunityTag(name=normalized, created_at=now)
            db.add(tag)
            db.flush()
        db.add(
            CommunityPostTag(
                post_id=post.id,
                tag_id=tag.id,
                created_at=now,
            )
        )

    db.commit()
    db.refresh(post)
    return serialize_community_post(post, context["user"].id)


@app.put("/community/posts/{post_id}")
def update_community_post(
    post_id: int,
    payload: CommunityPostUpdateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )
    if post.user_id != context["user"].id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if payload.category_slug:
        category = (
            db.query(CommunityCategory)
            .filter(CommunityCategory.slug == payload.category_slug)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "유효하지 않은 카테고리입니다"},
            )
        post.category_id = category.id

    if payload.title is not None:
        post.title = payload.title
    if payload.content is not None:
        post.content = payload.content
    post.updated_at = datetime.utcnow()

    if payload.images is not None:
        db.query(CommunityPostImage).filter(
            CommunityPostImage.post_id == post.id
        ).delete()
        for index, image_url in enumerate(payload.images):
            db.add(
                CommunityPostImage(
                    post_id=post.id,
                    image_url=image_url,
                    sort_order=index,
                    created_at=post.updated_at,
                )
            )

    if payload.tags is not None:
        db.query(CommunityPostTag).filter(
            CommunityPostTag.post_id == post.id
        ).delete()
        for tag_name in payload.tags:
            normalized = tag_name.strip().lstrip("#")
            if not normalized:
                continue
            tag = (
                db.query(CommunityTag).filter(CommunityTag.name == normalized).first()
            )
            if not tag:
                tag = CommunityTag(name=normalized, created_at=post.updated_at)
                db.add(tag)
                db.flush()
            db.add(
                CommunityPostTag(
                    post_id=post.id,
                    tag_id=tag.id,
                    created_at=post.updated_at,
                )
            )

    db.commit()
    db.refresh(post)
    return serialize_community_post(post, context["user"].id)


@app.delete("/community/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community_post(
    post_id: int,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )
    if post.user_id != context["user"].id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    db.query(CommunityPostImage).filter(
        CommunityPostImage.post_id == post.id
    ).delete()
    db.query(CommunityPostTag).filter(CommunityPostTag.post_id == post.id).delete()
    db.query(CommunityComment).filter(CommunityComment.post_id == post.id).delete()
    db.query(CommunityPostLike).filter(CommunityPostLike.post_id == post.id).delete()
    db.query(CommunityPostBookmark).filter(
        CommunityPostBookmark.post_id == post.id
    ).delete()
    db.delete(post)
    db.commit()
    return None


@app.get("/community/posts/{post_id}/comments")
def get_community_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    comments = (
        db.query(CommunityComment)
        .filter(CommunityComment.post_id == post_id)
        .order_by(CommunityComment.created_at.asc())
        .all()
    )
    return [serialize_community_comment(comment) for comment in comments]


@app.post("/community/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
def create_community_comment(
    post_id: int,
    payload: CommunityCommentCreateRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )

    if payload.parent_id:
        parent = (
            db.query(CommunityComment)
            .filter(
                CommunityComment.id == payload.parent_id,
                CommunityComment.post_id == post_id,
            )
            .first()
        )
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "유효하지 않은 부모 댓글입니다"},
            )

    now = datetime.utcnow()
    comment = CommunityComment(
        post_id=post_id,
        user_id=context["user"].id,
        parent_id=payload.parent_id,
        content=payload.content,
        created_at=now,
        updated_at=now,
    )
    db.add(comment)
    post.comment_count += 1
    db.commit()
    db.refresh(comment)
    return serialize_community_comment(comment)


@app.delete("/community/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community_comment(
    comment_id: int,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    comment = (
        db.query(CommunityComment).filter(CommunityComment.id == comment_id).first()
    )
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "댓글이 없습니다"},
        )
    if comment.user_id != context["user"].id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    post = db.query(CommunityPost).filter(CommunityPost.id == comment.post_id).first()
    db.delete(comment)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    db.commit()
    return None


@app.post("/community/posts/{post_id}/like")
def toggle_community_like(
    post_id: int,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )
    existing = (
        db.query(CommunityPostLike)
        .filter(
            CommunityPostLike.post_id == post_id,
            CommunityPostLike.user_id == context["user"].id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        if post.like_count > 0:
            post.like_count -= 1
        is_liked = False
    else:
        db.add(
            CommunityPostLike(
                post_id=post_id,
                user_id=context["user"].id,
                created_at=datetime.utcnow(),
            )
        )
        post.like_count += 1
        is_liked = True
    db.commit()
    return {"post_id": post_id, "is_liked": is_liked, "like_count": post.like_count}


@app.post("/community/posts/{post_id}/bookmark")
def toggle_community_bookmark(
    post_id: int,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"{post_id}의 게시글이 없습니다"},
        )
    existing = (
        db.query(CommunityPostBookmark)
        .filter(
            CommunityPostBookmark.post_id == post_id,
            CommunityPostBookmark.user_id == context["user"].id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        is_bookmarked = False
    else:
        db.add(
            CommunityPostBookmark(
                post_id=post_id,
                user_id=context["user"].id,
                created_at=datetime.utcnow(),
            )
        )
        is_bookmarked = True
    db.commit()
    return {"post_id": post_id, "is_bookmarked": is_bookmarked}
