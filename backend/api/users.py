from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from database.models import User
from backend.api.deps import get_db, get_current_admin
from services.payment_service import PaymentService

router = APIRouter()


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    plan: str
    premium_until: Optional[datetime]
    daily_pdf_used: int
    is_blocked: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("")
async def list_users(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    query = select(User)
    if q:
        like = f"%{q}%"
        filters = [User.username.ilike(like), User.first_name.ilike(like)]
        if q.isdigit():
            filters.append(User.telegram_id == int(q))
        query = query.where(or_(*filters))

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await session.execute(
        query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    users = result.scalars().all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [UserOut.model_validate(u) for u in users],
    }


@router.post("/{user_id}/premium")
async def grant_premium(
    user_id: int,
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.plan = "premium"
    user.premium_until = PaymentService.calculate_premium_until(days)
    return {"ok": True, "premium_until": user.premium_until}


@router.post("/{user_id}/remove-premium")
async def remove_premium(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.plan = "free"
    user.premium_until = None
    return {"ok": True}


@router.post("/{user_id}/block")
async def block_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_blocked = True
    return {"ok": True}


@router.post("/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_blocked = False
    return {"ok": True}
