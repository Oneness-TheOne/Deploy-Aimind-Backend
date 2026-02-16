"""
AI 그림 해석 프로세스 결과 저장용 MongoDB 스키마 및 API 요청/응답 모델.

컬렉션:
- analysis_logs: 레거시 (호환 유지)
- drawing_analyses: 그림 분석 1건 전체 (요소분석, S3 이미지 URL, 심리해석)
"""
from datetime import datetime, timezone
from typing import Any

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class DrawingAnalysis(Document):
    """
    그림 분석 1건. 요소분석 결과, S3 분석이미지 URL, 심리해석 JSON 저장.
    """
    user_id: Indexed(int) = Field(..., description="MySQL User ID")
    child_info: dict[str, Any] = Field(
        default_factory=dict,
        description="아이 정보 { name, age, gender }",
    )
    element_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="요소 분석 결과 { tree, house, man, woman } → image_json",
    )
    analyzed_image_urls: dict[str, str] = Field(
        default_factory=dict,
        description="분석 이미지 S3 URL { tree, house, man, woman }",
    )
    psychological_interpretation: dict[str, Any] = Field(
        default_factory=dict,
        description="심리해석 JSON { tree, house, man, woman } → { interpretation, analysis }",
    )
    comparison: dict[str, Any] = Field(default_factory=dict, description="또래 비교 등")
    recommendations: list[Any] = Field(
        default_factory=list,
        description="추천 사항 [{ category, items }] (result 페이지와 동일)",
    )
    overall_psychology_result: dict[str, Any] = Field(
        default_factory=dict,
        description="전체 심리 결과 { 종합_요약, 인상적_분석, 구조적_분석_요약, 표상적_분석_종합 }",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시각",
    )

    class Settings:
        name = "drawing_analyses"


class DrawingAnalysisSaveRequest(BaseModel):
    """POST /drawing-analyses 저장 요청."""
    user_id: int = Field(..., description="MySQL User ID")
    child_info: dict[str, Any] = Field(default_factory=dict)
    element_analysis: dict[str, Any] = Field(default_factory=dict)
    box_images_base64: dict[str, str | None] = Field(
        default_factory=dict,
        description="분석 박스 이미지 base64 { tree, house, man, woman }",
    )
    psychological_interpretation: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[Any] = Field(default_factory=list)
    overall_psychology_result: dict[str, Any] = Field(default_factory=dict)


class AnalysisLog(Document):
    """
    그림 해석 프로세스에서 발생하는 AI 분석 결과 문서.
    MySQL user_id를 기준으로 조회 (외래키처럼 사용).
    """
    user_id: Indexed(int) = Field(..., description="MySQL User ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시각",
    )
    # image_to_json (객체탐지 → 그림 요소 분석) 결과
    image_to_json: dict[str, Any] = Field(default_factory=dict)
    # jsonToLlm (요소 위치/크기 분석) 결과
    json_to_llm_json: dict[str, Any] = Field(default_factory=dict)
    # jsonToLlm 등 그림 해석 LLM 결과 (객체, 선택)
    llm_result_text: dict[str, Any] | None = None
    # ocr 모듈 결과 (선택)
    ocr_json: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "analysis_logs"


class DiaryOcrEntry(Document):
    """
    그림일기 OCR 결과 1건.
    - 이미지: S3 URL로 저장 (크롭 이미지)
    - 텍스트: 날짜/제목/내용 + 원본 텍스트 저장
    """
    user_id: Indexed(int) = Field(..., description="MySQL User ID")
    region: str = Field(default="", description="지역(사용자 선택)")
    image_url: str = Field(default="", description="그림일기 이미지 S3 URL (크롭)")
    date: str = Field(default="", description="추출된 날짜(YYYY-MM-DD)")
    title: str = Field(default="", description="추출된 제목")
    original_text: str = Field(default="", description="OCR 후처리 원본 텍스트")
    corrected_text: str = Field(default="", description="교정된 내용")
    weather: str = Field(default="", description="날씨 (맑음/흐림/비/눈/바람)")
    child_id: int | None = Field(default=None, description="등록 아이 ID (선택 시)")
    child_name: str = Field(default="", description="아이 이름 (표시용)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시각",
    )

    class Settings:
        # 사용자가 말한 'diary-ocr 폴더'를 컬렉션으로 해석
        name = "diary_ocr"


# --- API 요청/응답 스키마 ---


class AnalysisSaveRequest(BaseModel):
    """POST /analysis/save 요청 바디."""
    user_id: int = Field(..., description="MySQL User ID")
    image_to_json: dict[str, Any] = Field(default_factory=dict)
    json_to_llm_json: dict[str, Any] = Field(default_factory=dict)
    llm_result_text: dict[str, Any] | None = None
    ocr_json: dict[str, Any] = Field(default_factory=dict)


class AnalysisLogResponse(BaseModel):
    """분석 로그 한 건 응답 (JSON 리스트 항목)."""
    id: str
    user_id: int
    created_at: datetime
    image_to_json: dict[str, Any]
    json_to_llm_json: dict[str, Any]
    llm_result_text: dict[str, Any] | None
    ocr_json: dict[str, Any]

    class Config:
        from_attributes = True
