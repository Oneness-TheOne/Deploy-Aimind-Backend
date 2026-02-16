"""
MongoDB 비동기 연결 및 Beanie ODM 초기화.
AI 분석 로그(analysis_logs) 등 복잡한 JSON 저장용.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from config import settings

# 앱 lifespan에서 설정됨
mongo_client: AsyncIOMotorClient | None = None


async def init_mongo():
    """FastAPI startup에서 호출. MongoDB 연결 후 Beanie 문서 모델 초기화."""
    global mongo_client
    from analysis_mongo import AnalysisLog, DrawingAnalysis, DiaryOcrEntry

    mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    database = mongo_client[settings.mongodb_db_name]
    await init_beanie(database=database, document_models=[AnalysisLog, DrawingAnalysis, DiaryOcrEntry])


async def close_mongo():
    """FastAPI shutdown에서 호출."""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        mongo_client = None
