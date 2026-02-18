from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from db import Base


class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)  # 'male' | 'female'
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="children")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    profile_image_url = Column(String(1000), nullable=False, default="base")
    agree_terms = Column(Integer, nullable=False, default=0)
    agree_privacy = Column(Integer, nullable=False, default=0)
    agree_marketing = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    posts = relationship("Post", back_populates="user")
    community_posts = relationship("CommunityPost", back_populates="user")
    community_comments = relationship("CommunityComment", back_populates="user")
    community_likes = relationship("CommunityPostLike", back_populates="user")
    community_bookmarks = relationship("CommunityPostBookmark", back_populates="user")
    expert_profile = relationship(
        "ExpertProfile", back_populates="user", uselist=False
    )
    children = relationship("Child", back_populates="user", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    text = Column(Text, nullable=False)
    userIdx = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    userid = Column(String(50), nullable=False)
    createdAt = Column(DateTime, nullable=False)
    updatedAt = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="posts")


class CommunityCategory(Base):
    __tablename__ = "community_categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    slug = Column(String(50), nullable=False, unique=True, index=True)
    label = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    posts = relationship("CommunityPost", back_populates="category")


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(
        Integer, ForeignKey("community_categories.id"), nullable=False, index=True
    )
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    view_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="community_posts")
    category = relationship("CommunityCategory", back_populates="posts")
    images = relationship(
        "CommunityPostImage", back_populates="post", cascade="all, delete-orphan"
    )
    comments = relationship(
        "CommunityComment", back_populates="post", cascade="all, delete-orphan"
    )
    likes = relationship(
        "CommunityPostLike", back_populates="post", cascade="all, delete-orphan"
    )
    bookmarks = relationship(
        "CommunityPostBookmark", back_populates="post", cascade="all, delete-orphan"
    )
    tags = relationship(
        "CommunityTag",
        secondary="community_post_tags",
        back_populates="posts",
    )


class CommunityPostImage(Base):
    __tablename__ = "community_post_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False, index=True)
    image_url = Column(String(1000), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)

    post = relationship("CommunityPost", back_populates="images")


class CommunityTag(Base):
    __tablename__ = "community_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False)

    posts = relationship(
        "CommunityPost",
        secondary="community_post_tags",
        back_populates="tags",
    )


class CommunityPostTag(Base):
    __tablename__ = "community_post_tags"

    post_id = Column(
        Integer, ForeignKey("community_posts.id"), primary_key=True, nullable=False
    )
    tag_id = Column(
        Integer, ForeignKey("community_tags.id"), primary_key=True, nullable=False
    )
    created_at = Column(DateTime, nullable=False)


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("community_comments.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    post = relationship("CommunityPost", back_populates="comments")
    user = relationship("User", back_populates="community_comments")
    parent = relationship("CommunityComment", remote_side=[id])


class CommunityPostLike(Base):
    __tablename__ = "community_post_likes"

    post_id = Column(
        Integer, ForeignKey("community_posts.id"), primary_key=True, nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, nullable=False)
    created_at = Column(DateTime, nullable=False)

    post = relationship("CommunityPost", back_populates="likes")
    user = relationship("User", back_populates="community_likes")


class CommunityPostBookmark(Base):
    __tablename__ = "community_post_bookmarks"

    post_id = Column(
        Integer, ForeignKey("community_posts.id"), primary_key=True, nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, nullable=False)
    created_at = Column(DateTime, nullable=False)

    post = relationship("CommunityPost", back_populates="bookmarks")
    user = relationship("User", back_populates="community_bookmarks")


class ExpertProfile(Base):
    __tablename__ = "expert_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    title = Column(String(100), nullable=False)
    answer_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="expert_profile")
