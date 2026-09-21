from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User, Test, Payment, ProcessingJob, Result
from backend.api.deps import get_db, get_current_admin

router = APIRouter()


@router.get("/stats")
async def stats(
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    new_today = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar() or 0
    premium_users = (await session.execute(
        select(func.count(User.id)).where(User.plan == "premium")
    )).scalar() or 0
    pdfs_today = (await session.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.created_at >= today_start)
    )).scalar() or 0
    checks_today = (await session.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.created_at >= today_start,
            ProcessingJob.status == "completed",
        )
    )).scalar() or 0
    total_payments = (await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid")
    )).scalar() or 0
    total_tests = (await session.execute(select(func.count(Test.id)))).scalar() or 0
    failed_jobs = (await session.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status == "failed")
    )).scalar() or 0

    return {
        "total_users": total_users,
        "new_today": new_today,
        "premium_users": premium_users,
        "pdfs_today": pdfs_today,
        "checks_today": checks_today,
        "total_payments": float(total_payments),
        "total_tests": total_tests,
        "failed_jobs": failed_jobs,
    }
