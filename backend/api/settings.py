from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Setting
from backend.api.deps import get_db, get_current_admin

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str


@router.get("")
async def list_settings(
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(Setting).order_by(Setting.key))
    settings = result.scalars().all()
    return [
        {"key": s.key, "value": s.value, "description": s.description}
        for s in settings
    ]


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    session: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await session.execute(select(Setting).where(Setting.key == key))
    s = result.scalar_one_or_none()
    if not s:
        s = Setting(key=key, value=body.value)
        session.add(s)
    else:
        s.value = body.value
    return {"ok": True, "key": key, "value": body.value}
