from datetime import datetime


def serialize_post(post):
    if post is None:
        return None
    return {
        "id": post.id,
        "text": post.text,
        "userIdx": post.userIdx,
        "name": post.name,
        "userid": post.userid,
        "email": post.userid,
        "createdAt": _format_dt(post.createdAt),
        "updatedAt": _format_dt(post.updatedAt),
    }


def serialize_posts(posts):
    return [serialize_post(post) for post in posts]


def _format_dt(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _resolve_profile_image_url(value):
    if not value or value == "base":
        return "/static/profile-default.svg"
    return value


def serialize_community_post(post, current_user_id=None):
    if post is None:
        return None
    is_liked = False
    is_bookmarked = False
    if current_user_id:
        is_liked = any(like.user_id == current_user_id for like in post.likes)
        is_bookmarked = any(
            bookmark.user_id == current_user_id for bookmark in post.bookmarks
        )
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "category": post.category.slug if post.category else None,
        "created_at": _format_dt(post.created_at),
        "updated_at": _format_dt(post.updated_at),
        "view_count": post.view_count,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "is_liked": is_liked,
        "is_bookmarked": is_bookmarked,
        "tags": [tag.name for tag in post.tags],
        "images": [
            {"id": image.id, "url": image.image_url, "sort_order": image.sort_order}
            for image in sorted(post.images, key=lambda item: item.sort_order)
        ],
        "author": {
            "id": post.user.id if post.user else None,
            "name": post.user.name if post.user else None,
            "badge": "전문가" if post.user and post.user.expert_profile else None,
            "profile_image_url": _resolve_profile_image_url(
                post.user.profile_image_url if post.user else None
            ),
        },
    }


def serialize_community_posts(posts, current_user_id=None):
    return [serialize_community_post(post, current_user_id) for post in posts]


def serialize_community_comment(comment):
    if comment is None:
        return None
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "created_at": _format_dt(comment.created_at),
        "updated_at": _format_dt(comment.updated_at),
        "author": {
            "id": comment.user.id if comment.user else None,
            "name": comment.user.name if comment.user else None,
            "badge": "전문가" if comment.user and comment.user.expert_profile else None,
            "profile_image_url": _resolve_profile_image_url(
                comment.user.profile_image_url if comment.user else None
            ),
        },
    }
