import base64
import io
import os
import re
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from PIL import Image

from config import settings

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 1024


def _build_public_url(key: str) -> str:
    if settings.s3_public_base_url:
        return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
    if settings.s3_region == "us-east-1":
        return f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


def _build_object_key(user_id: int, filename: str | None, content_type: str | None) -> str:
    ext = ""
    if content_type in ALLOWED_IMAGE_TYPES:
        ext = ALLOWED_IMAGE_TYPES[content_type]
    elif filename:
        _, guessed = os.path.splitext(filename)
        if guessed and len(guessed) <= 10:
            ext = guessed.lower()
    return f"users/{user_id}/profile/{uuid4().hex}{ext}"


def _build_analysis_image_key(user_id: int, object_type: str, content_type: str = "image/jpeg") -> str:
    ext = ALLOWED_IMAGE_TYPES.get(content_type, ".jpg")
    return f"users/{user_id}/analyses/{uuid4().hex}_{object_type}{ext}"


def _build_diary_ocr_image_key(user_id: int, content_type: str = "image/jpeg") -> str:
    ext = ALLOWED_IMAGE_TYPES.get(content_type, ".jpg")
    return f"users/{user_id}/diary-ocr/{uuid4().hex}{ext}"


def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )


def _reencode_image(contents: bytes, content_type: str) -> bytes:
    image = Image.open(io.BytesIO(contents))
    image.load()

    if content_type == "image/jpeg" and image.mode != "RGB":
        image = image.convert("RGB")

    max_dim = MAX_DIMENSION
    while True:
        resized = image.copy()
        resized.thumbnail((max_dim, max_dim))

        output = io.BytesIO()
        if content_type == "image/png":
            resized.save(output, format="PNG", optimize=True, compress_level=9)
        elif content_type == "image/webp":
            resized.save(output, format="WEBP", quality=85, method=6)
        else:
            if resized.mode != "RGB":
                resized = resized.convert("RGB")
            resized.save(output, format="JPEG", quality=85, optimize=True, progressive=True)

        data = output.getvalue()
        if len(data) <= MAX_IMAGE_BYTES or max_dim <= 320:
            return data
        max_dim = int(max_dim * 0.8)


async def upload_profile_image_to_s3(upload: UploadFile, user_id: int) -> str:
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "이미지 파일이 필요합니다"},
        )
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"message": "JPEG/PNG/WEBP 이미지만 업로드 가능합니다"},
        )

    contents = await upload.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "빈 파일입니다"},
        )
    if len(contents) > MAX_IMAGE_BYTES:
        contents = _reencode_image(contents, upload.content_type)
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"message": "이미지는 5MB 이하만 가능합니다"},
            )

    key = _build_object_key(user_id, upload.filename, upload.content_type)
    s3 = _get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=contents,
            ContentType=upload.content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "S3 업로드에 실패했습니다", "error": str(exc)},
        )

    return _build_public_url(key)


def _decode_base64_image(data_url: str) -> tuple[bytes, str]:
    """data:image/jpeg;base64,... 형태에서 (bytes, content_type) 반환."""
    m = re.match(r"data:image/(\w+);base64,(.+)", data_url or "")
    if not m:
        raise ValueError("유효한 base64 이미지 형식이 아닙니다")
    subtype = m.group(1).lower()
    content_type = f"image/{subtype}" if subtype in {"jpeg", "jpg", "png", "webp", "gif"} else "image/jpeg"
    raw = base64.b64decode(m.group(2))
    if not raw:
        raise ValueError("base64 디코드 실패")
    return raw, content_type


async def upload_analysis_box_image_to_s3(
    base64_data_url: str | None,
    user_id: int,
    object_type: str,
) -> str | None:
    """분석 박스 이미지(base64 data URL)를 S3에 업로드 후 public URL 반환. None이면 None 반환."""
    if not base64_data_url or not base64_data_url.strip():
        return None
    try:
        contents, content_type = _decode_base64_image(base64_data_url)
    except (ValueError, TypeError):
        return None
    if content_type not in ALLOWED_IMAGE_TYPES:
        content_type = "image/jpeg"
    key = _build_analysis_image_key(user_id, object_type, content_type)
    s3 = _get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=contents,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError):
        return None
    return _build_public_url(key)


async def upload_diary_ocr_image_to_s3(
    contents: bytes,
    user_id: int,
    filename: str | None = None,
    content_type: str | None = None,
) -> str:
    """
    그림일기(원본 이미지)를 S3에 업로드 후 public URL 반환.
    UploadFile을 직접 받지 않는 이유: 읽기(consume) 문제를 피하기 위해 bytes로 받습니다.
    """
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "빈 파일입니다"},
        )

    ct = content_type or "image/jpeg"
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"message": "JPEG/PNG/WEBP 이미지만 업로드 가능합니다"},
        )

    data = contents
    if len(data) > MAX_IMAGE_BYTES:
        data = _reencode_image(data, ct)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"message": "이미지는 5MB 이하만 가능합니다"},
            )

    key = _build_diary_ocr_image_key(user_id, ct)
    s3 = _get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=ct,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "S3 업로드에 실패했습니다", "error": str(exc)},
        )

    return _build_public_url(key)
