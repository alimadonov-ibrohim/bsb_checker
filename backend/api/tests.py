from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import Test, User, Student
from backend.api.deps import get_db, get_current_admin

router = APIRouter()


@router.get("")
async def list_tests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    total = (await session.execute(select(func.count(Test.id)))).scalar() or 0
    result = await session.execute(
        select(Test).order_by(Test.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    tests = result.scalars().all()
    items = []
    for t in tests:
        user_r = await session.execute(select(User).where(User.id == t.user_id))
        user = user_r.scalar_one_or_none()
        stu_count = (await session.execute(
            select(func.count(Student.id)).where(Student.test_id == t.id)
        )).scalar() or 0
        items.append({
            "id": t.id,
            "subject": t.subject,
            "class_name": t.class_name,
            "test_name": t.test_name,
            "test_type": t.test_type,
            "question_count": t.question_count,
            "students": stu_count,
            "teacher": user.username or user.first_name if user else None,
            "teacher_telegram_id": user.telegram_id if user else None,
            "created_at": t.created_at.isoformat(),
        })
    return {"total": total, "page": page, "per_page": per_page, "items": items}
