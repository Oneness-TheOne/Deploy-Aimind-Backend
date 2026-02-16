# 분석 API 테스트 (PowerShell)
# 사용법: .\scripts\test_analysis_api.ps1
# 서버가 먼저 떠 있어야 함 (예: uvicorn main:app --reload --port 8080)

$BaseUrl = "http://localhost:8080"   # HOST_PORT에 맞게 수정 (기본 8080 또는 9090)
$UserId = 1

Write-Host "=== 1. POST /analysis/save (저장) ===" -ForegroundColor Cyan
$body = @{
    user_id = $UserId
    image_to_json = @{ elements = @(); version = "1.0" }
    json_to_llm_json = @{ positions = @(); sizes = @() }
    llm_result_text = "테스트 해석 결과입니다."
    ocr_json = @{ text = "OCR 테스트"; confidence = 0.95 }
} | ConvertTo-Json -Depth 5

try {
    $save = Invoke-RestMethod -Uri "$BaseUrl/analysis/save" -Method Post -Body $body -ContentType "application/json; charset=utf-8"
    Write-Host ($save | ConvertTo-Json)
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 2. GET /analysis/$UserId (목록 조회) ===" -ForegroundColor Cyan
try {
    $list = Invoke-RestMethod -Uri "$BaseUrl/analysis/$UserId" -Method Get
    Write-Host ($list | ConvertTo-Json -Depth 10)
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

Write-Host "`n테스트 완료." -ForegroundColor Green
