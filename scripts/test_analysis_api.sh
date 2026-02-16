#!/usr/bin/env bash
# 분석 API 테스트 (Bash / Git Bash)
# 사용법: bash scripts/test_analysis_api.sh
# 서버가 먼저 떠 있어야 함 (예: uvicorn main:app --reload --port 8080)

BASE_URL="${BASE_URL:-http://localhost:8080}"
USER_ID="${USER_ID:-1}"

echo "=== 1. POST /analysis/save (저장) ==="
curl -s -X POST "$BASE_URL/analysis/save" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": $USER_ID,
    \"image_to_json\": {\"elements\": [], \"version\": \"1.0\"},
    \"json_to_llm_json\": {\"positions\": [], \"sizes\": []},
    \"llm_result_text\": \"테스트 해석 결과입니다.\",
    \"ocr_json\": {\"text\": \"OCR 테스트\", \"confidence\": 0.95}
  }" | python -m json.tool

echo ""
echo "=== 2. GET /analysis/$USER_ID (목록 조회) ==="
curl -s "$BASE_URL/analysis/$USER_ID" | python -m json.tool

echo ""
echo "테스트 완료."
