"""Company Info Portal (CMS) router — TSK-045 (US-GL-008)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.onboarding.models import CmsArticle

router = APIRouter(prefix="/cms/articles", tags=["cms"])


# ─── Schemas ──────────────────────────────────────────────────────


class ArticleCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    category: str = Field(..., min_length=2, max_length=30)
    content: str = Field(..., min_length=10)
    summary: str | None = None
    is_published: bool = False
    is_pinned: bool = False
    sort_order: int = 0


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    category: str | None = None
    content: str | None = None
    summary: str | None = None
    is_published: bool | None = None
    is_pinned: bool | None = None
    sort_order: int | None = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    category: str
    content: str
    summary: str | None
    is_published: bool
    is_pinned: bool
    sort_order: int
    created_by_user_id: UUID
    updated_by_user_id: UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    s = re.sub(r"\s+", "-", s.strip())
    return s[:200]


# ─── Endpoints ────────────────────────────────────────────────────


@router.get("", response_model=list[ArticleOut])
async def list_articles_endpoint(
    session: DBSession,
    _user: CurrentUser,
    category: str | None = Query(None),
    published_only: bool = Query(True),
    search: str | None = Query(None, max_length=100),
) -> list[ArticleOut]:
    """Public list — semua authenticated user dapat akses. Filter by category +
    fuzzy search title/content."""
    stmt = select(CmsArticle).where(CmsArticle.deleted_at.is_(None))
    if published_only:
        stmt = stmt.where(CmsArticle.is_published.is_(True))
    if category:
        stmt = stmt.where(CmsArticle.category == category)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                CmsArticle.title.ilike(pattern),
                CmsArticle.content.ilike(pattern),
                CmsArticle.summary.ilike(pattern),
            )
        )
    stmt = stmt.order_by(
        CmsArticle.is_pinned.desc(),
        CmsArticle.sort_order.asc(),
        CmsArticle.title.asc(),
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [ArticleOut.model_validate(a) for a in rows]


@router.get("/categories")
async def list_categories_endpoint(
    session: DBSession,
    _user: CurrentUser,
) -> dict:
    """Aggregate count per category untuk sidebar."""
    from sqlalchemy import func as _f
    stmt = (
        select(CmsArticle.category, _f.count(CmsArticle.id))
        .where(CmsArticle.deleted_at.is_(None))
        .where(CmsArticle.is_published.is_(True))
        .group_by(CmsArticle.category)
    )
    result = await session.execute(stmt)
    return {
        "categories": [
            {"category": cat, "count": int(cnt)} for cat, cnt in result.all()
        ]
    }


@router.get("/{slug_or_id}", response_model=ArticleOut)
async def get_article_endpoint(
    slug_or_id: str,
    session: DBSession,
    _user: CurrentUser,
) -> ArticleOut:
    """Get by slug or UUID."""
    try:
        uid = UUID(slug_or_id)
        a = await session.get(CmsArticle, uid)
    except (ValueError, TypeError):
        stmt = select(CmsArticle).where(CmsArticle.slug == slug_or_id)
        a = (await session.execute(stmt)).scalar_one_or_none()

    if a is None or a.deleted_at is not None:
        raise HTTPException(404, detail={"message": "Article not found"})
    return ArticleOut.model_validate(a)


@router.post("", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
async def create_article_endpoint(
    data: ArticleCreate,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("employee.edit"))],
) -> ArticleOut:
    """HR-only — create new CMS article."""
    slug = _slugify(data.title)
    # Make unique
    existing_stmt = select(CmsArticle).where(CmsArticle.slug == slug)
    i = 1
    while (await session.execute(existing_stmt)).scalar_one_or_none() is not None:
        slug = f"{_slugify(data.title)}-{i}"
        existing_stmt = select(CmsArticle).where(CmsArticle.slug == slug)
        i += 1

    a = CmsArticle(
        title=data.title,
        slug=slug,
        category=data.category,
        content=data.content,
        summary=data.summary,
        is_published=data.is_published,
        is_pinned=data.is_pinned,
        sort_order=data.sort_order,
        created_by_user_id=user.id,
        published_at=datetime.now(UTC) if data.is_published else None,
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)

    await audit_log(
        session=session, actor=user, action="CMS_ARTICLE_CREATED",
        resource_type="cms_article", resource_id=str(a.id),
        after_state={"title": a.title, "category": a.category},
    )
    return ArticleOut.model_validate(a)


@router.patch("/{article_id}", response_model=ArticleOut)
async def update_article_endpoint(
    article_id: UUID,
    data: ArticleUpdate,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("employee.edit"))],
) -> ArticleOut:
    a = await session.get(CmsArticle, article_id)
    if a is None or a.deleted_at is not None:
        raise HTTPException(404, detail={"message": "Article not found"})

    if data.title is not None:
        a.title = data.title
    if data.category is not None:
        a.category = data.category
    if data.content is not None:
        a.content = data.content
    if data.summary is not None:
        a.summary = data.summary
    if data.is_published is not None:
        was_unpublished = not a.is_published
        a.is_published = data.is_published
        if data.is_published and was_unpublished and a.published_at is None:
            a.published_at = datetime.now(UTC)
    if data.is_pinned is not None:
        a.is_pinned = data.is_pinned
    if data.sort_order is not None:
        a.sort_order = data.sort_order

    a.updated_by_user_id = user.id
    await session.commit()
    await session.refresh(a)
    return ArticleOut.model_validate(a)


@router.delete("/{article_id}")
async def delete_article_endpoint(
    article_id: UUID,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("employee.edit"))],
) -> dict:
    """Soft delete."""
    a = await session.get(CmsArticle, article_id)
    if a is None or a.deleted_at is not None:
        raise HTTPException(404, detail={"message": "Article not found"})
    a.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"deleted": True, "id": str(article_id)}
