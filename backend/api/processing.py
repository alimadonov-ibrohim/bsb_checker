from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import ProcessingJob, User
from backend.api.deps import get_db, get_current_admin

router = APIRouter()


@router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    total = (await session.execute(select(func.count(ProcessingJob.id)))).scalar() or 0
    result = await session.execute(
        select(ProcessingJob)
        .order_by(ProcessingJob.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    jobs = result.scalars().all()
    items = []
    for j in jobs:
        user_r = await session.execute(select(User).where(User.id == j.user_id))
        user = user_r.scalar_one_or_none()
        items.append({
            "id": j.id,
            "user_telegram_id": user.telegram_id if user else None,
            "test_id": j.test_id,
            "file_name": j.file_name,
            "total_pages": j.total_pages,
            "processed_pages": j.processed_pages,
            "status": j.status,
            "error": j.error,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        })
    return {"total": total, "page": page, "per_page": per_page, "items": items}
