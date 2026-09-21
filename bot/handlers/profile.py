from aiogram import Router, F
from aiogram.types import Message
from database.models import User
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.setting import Setting
import os

router = Router(name="profile")


async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    r = await session.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


@router.message(F.text == "👤 Profil")
async def profile_handler(message: Message, user: User, session: AsyncSession):
    free_limit = int(await get_setting(session, "free_daily_pdf_limit", os.getenv("FREE_DAILY_PDF_LIMIT", "3")))
    prem_limit = int(await get_setting(session, "premium_daily_pdf_limit", os.getenv("PREMIUM_DAILY_PDF_LIMIT", "6")))

    user.reset_daily_limit_if_needed()
    limit = user.get_daily_limit(free_limit, prem_limit)
    plan_label = "👑 Premium" if user.is_premium_active() else "🆓 Oddiy"

    premium_info = ""
    if user.is_premium_active() and user.premium_until:
        until = user.premium_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        premium_info = f"\n⏳ Premium tugashi: {until.strftime('%d.%m.%Y %H:%M')}"

    text = (
        f"👤 <b>PROFIL</b>\n\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"👤 Ism: {user.first_name or '—'}\n"
        f"📛 Username: @{user.username or '—'}\n"
        f"📦 Tarif: {plan_label}{premium_info}\n"
        f"📄 Bugungi PDF: {user.daily_pdf_used} / {limit}\n"
        f"📅 Ro‘yxatdan o‘tgan: {user.created_at.strftime('%d.%m.%Y')}"
    )
    await message.answer(text, parse_mode="HTML")
