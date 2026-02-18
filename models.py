from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field, constr


class LoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=4)


from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    agree_terms: bool = False
    agree_privacy: bool = False
    agree_marketing: bool = False



class PostCreateRequest(BaseModel):
    text: constr(min_length=4)


class PostUpdateRequest(BaseModel):
    text: constr(min_length=4)


class CommunityPostCreateRequest(BaseModel):
    category_slug: constr(min_length=2)
    title: constr(min_length=5, max_length=200)
    content: constr(min_length=10)
    tags: List[str] = []
    images: List[str] = []


class CommunityPostUpdateRequest(BaseModel):
    category_slug: Optional[constr(min_length=2)] = None
    title: Optional[constr(min_length=5, max_length=200)] = None
    content: Optional[constr(min_length=10)] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None


class CommunityCommentCreateRequest(BaseModel):
    content: constr(min_length=1)
    parent_id: Optional[int] = None


class ChildCreateRequest(BaseModel):
    name: constr(min_length=1, max_length=100)
    age: int = Field(ge=7, le=13, description="7~13세, 그림 분석 지원 나이")
    gender: Literal["male", "female"]
