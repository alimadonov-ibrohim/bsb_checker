from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import Payment, User
from backend.api.deps import get_db, get_current_admin

router = APIRouter()


@router.get("")
async def list_payments(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    query = select(Payment)
    if status:
        query = query.where(Payment.status == status)
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await session.execute(
        query.order_by(Payment.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    payments = result.scalars().all()
    items = []
    for p in payments:
        user_r = await session.execute(select(User).where(User.id == p.user_id))
        user = user_r.scalar_one_or_none()
        items.append({
            "id": p.id,
            "telegram_id": user.telegram_id if user else None,
            "username": user.username if user else None,
            "amount": p.amount,
            "status": p.status,
            "provider": p.provider,
            "transaction_id": p.transaction_id,
            "created_at": p.created_at.isoformat(),
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        })
    return {"total": total, "page": page, "per_page": per_page, "items": items}
