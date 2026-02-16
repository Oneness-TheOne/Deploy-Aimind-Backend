import os
from dotenv import load_dotenv

load_dotenv()


def required(key: str, default_value=None):
    value = os.getenv(key, default_value)
    if value is None or value == "":
        raise ValueError(f"키 {key}는 undefined!!")
    return value


class Settings:
    jwt_secret = required("JWT_SECRET")
    jwt_expires_sec = int(required("JWT_EXPIRES_SEC"))
    bcrypt_salt_rounds = int(required("BCRYPT_SALT_ROUNDS", 12))
    host_port = int(required("HOST_PORT", 9090))
    db_host = required("DB_HOST")
    db_port = int(required("DB_PORT", 3306))
    db_name = required("DB_NAME", "AiMind")
    db_user = required("DB_USER")
    db_password = required("DB_PASSWORD")
    # Optional: path to CA bundle for TLS connections
    db_ssl_ca = os.getenv("DB_SSL_CA")
    s3_bucket = required("S3_BUCKET")
    s3_region = required("S3_REGION")
    s3_access_key_id = required("S3_ACCESS_KEY_ID")
    s3_secret_access_key = required("S3_SECRET_ACCESS_KEY")
    # Optional: CDN or custom public base URL for objects
    s3_public_base_url = os.getenv("S3_PUBLIC_BASE_URL")

    # MongoDB (AI 분석 로그 등)
    mongodb_uri = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://wob0217_db_user:D2THWGAN9HXh9vL7@aimind.ixkqnnp.mongodb.net/?appName=AiMind",
    )
    mongodb_db_name = os.getenv("MONGODB_DB_NAME", "aimind")


settings = Settings()
