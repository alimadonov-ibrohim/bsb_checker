"""
Bot admin panel (Telegram ichida).
Ruxsat faqat ADMIN_TELEGRAM_IDS ro'yxatidagi telegram_id lar uchun.
"""
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Test, ProcessingJob, Payment
from database.models.setting import Setting
from bot.keyboards.admin_kb import admin_menu_kb
from bot.services.admin_access import is_bot_admin

router = Router(name="admin")


async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    r = await session.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


async def _deny(message: Message) -> None:
    await message.answer("⛔ Bu buyruq faqat admin uchun.")


def _format_user(u: User) -> str:
    name = u.first_name or u.username or "—"
    plan = "👑" if u.is_premium_active() else "🆓"
    until = (
        f" | ⏳ {u.premium_until.strftime('%d.%m.%Y')}"
        if u.is_premium_active() and u.premium_until
        else ""
    )
    block = "⛔" if u.is_blocked else ""
    return f"• <code>{u.telegram_id}</code> {name} {plan}{until} {block}"


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_bot_admin(message.from_user.id):
        await _deny(message)
        return
    await message.answer(
        "🛡 <b>Bot admin paneli</b>\n\n"
        "Buyruqlar:\n"
        "<code>/stats</code> — statistika\n"
        "<code>/users</code> — foydalanuvchilar\n"
        "<code>/premium &lt;telegram_id&gt; [kun]</code> — Premium berish (kun=0 bo'lsa bekor qiladi)\n"
        "<code>/ban &lt;telegram_id&gt;</code> — bloklash\n"
        "<code>/unban &lt;telegram_id&gt;</code> — blokdan ochish",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery):
    if not is_bot_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer()
    await callback.answer()


async def _stats_text(session: AsyncSession) -> str:
    total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    premium_users = (
        await session.execute(
            select(func.count()).select_from(User).where(User.plan == "premium")
        )
    ).scalar() or 0
    tests = (await session.execute(select(func.count()).select_from(Test))).scalar() or 0
    jobs = (
        await session.execute(select(func.count()).select_from(ProcessingJob))
    ).scalar() or 0
    paid = (
        await session.execute(
            select(func.count()).select_from(Payment).where(Payment.status == "paid")
        )
    ).scalar() or 0
    today = datetime.now(timezone.utc).date()
    new_today = (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(func.date(User.created_at) == today)
        )
    ).scalar() or 0
    return (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{new_today}</b>\n"
        f"👑 Premium: <b>{premium_users}</b>\n"
        f"🧾 To'lovlar (paid): <b>{paid}</b>\n"
        f"📝 Testlar: <b>{tests}</b>\n"
        f"⚙️ Qayta ishlashlar: <b>{jobs}</b>"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    if not is_bot_admin(message.from_user.id):
        await _deny(message)
        return
    await message.answer(await _stats_text(session), parse_mode="HTML")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_bot_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return
    await callback.message.answer(await _stats_text(session), parse_mode="HTML")
    await callback.answer()


@router.message(Command("users"))
async def cmd_users(message: Message, session: AsyncSession):
    if not is_bot_admin(message.from_user.id):
        await _deny(message)
        return
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(10)
    )
    users = result.scalars().all()
    total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    lines = [f"👥 <b>Oxirgi 10 foydalanuvchi</b> (jami {total}):\n"]
    lines += [_format_user(u) for u in users]
    if not users:
        lines.append("Hali foydalanuvchilar yo'q.")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, session: AsyncSession):
    if not is_bot_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(10)
    )
    users = result.scalars().all()
    total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    lines = [f"👥 <b>Oxirgi 10 foydalanuvchi</b> (jami {total}):\n"]
    lines += [_format_user(u) for u in users]
    if not users:
        lines.append("Hali foydalanuvchilar yo'q.")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.message(Command("premium"))
async def cmd_premium(message: Message, command: CommandObject, session: AsyncSession):
    if not is_bot_admin(message.from_user.id):
        await _deny(message)
        return
    parts = (command.args or "").strip().split()
    if not parts:
        await message.answer(
            "🎁 <b>Premium berish:</b>\n"
            "<code>/premium &lt;telegram_id&gt; [kun]</code>\n"
            "Masalan:\n"
            "<code>/premium 123456789 30</code>\n"
            "<code>/premium 123456789 0</code> — bekor qilish",
            parse_mode="HTML",
        )
        return

    try:
        telegram_id = int(parts[0])
    except ValueError:
        await message.answer("⚠️ Telegram ID raqam bo'lishi kerak.")
        return

    days_str = parts[1] if len(parts) > 1 else "0"
    try:
        days = int(days_str)
    except ValueError:
        await message.answer("⚠️ Kunlar soni raqam bo'lishi kerak.")
        return

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer(f"⚠️ <code>{telegram_id}</code> topilmadi. Botda ishlatilmagan foydalanuvchi.", parse_mode="HTML")
        return

    label = _format_user(user)
    if days <= 0:
        user.plan = "free"
        user.premium_until = None
        await session.flush()
        await message.answer(
            f"✅ Premium bekor qilindi.\n{label}", parse_mode="HTML"
        )
        return

    default_days = int(
        await get_setting(session, "premium_duration_days", "30")
    )
    if len(parts) == 1:
        days = default_days

    now = datetime.now(timezone.utc)
    base = user.premium_until if user.is_premium_active() else now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    user.plan = "premium"
    user.premium_until = max(base, now) + timedelta(days=days)
    await session.flush()

    await message.answer(
        f"✅ <b>Premium berildi!</b> {days} kun\n"
        f"Yangilangan muddat: {user.premium_until.strftime('%d.%m.%Y')}\n"
        f"{label}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:premium")
async def admin_premium_help(callback: CallbackQuery):
    if not is_bot_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return
    await callback.message.answer(
        "🎁 <b>Premium berish:</b>\n"
        "<code>/premium &lt;telegram_id&gt; [kun]</code>\n\n"
        "Masalan:\n"
        "<code>/premium 123456789 30</code>\n"
        "<code>/premium 123456789 0</code> — bekor qilish",
        parse_mode="HTML",
    )
    await callback.answer()


async def _set_block(message: Message, command: CommandObject, session: AsyncSession, blocked: bool):
    if not is_bot_admin(message.from_user.id):
        await _deny(message)
        return
    parts = (command.args or "").strip().split()
    if not parts:
        verb = "unban" if blocked is False else "ban"
        await message.answer(
            f"⚠️ Foydalanish: <code>/{verb} &lt;telegram_id&gt;</code>",
            parse_mode="HTML",
        )
        return
    try:
        telegram_id = int(parts[0])
    except ValueError:
        await message.answer("⚠️ Telegram ID raqam bo'lishi kerak.")
        return

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer(f"⚠️ <code>{telegram_id}</code> topilmadi.", parse_mode="HTML")
        return

    user.is_blocked = bool(blocked)
    await session.flush()
    verb = "bloklandi" if blocked else "blokdan ochildi"
    await message.answer(
        f"{'⛔' if blocked else '✅'} Foydalanuvchi {verb}\n{_format_user(user)}",
        parse_mode="HTML",
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session: AsyncSession):
    await _set_block(message, command, session, True)


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session: AsyncSession):
    await _set_block(message, command, session, False)


@router.callback_query(F.data == "admin:ban")
async def admin_ban_help(callback: CallbackQuery):
    if not is_bot_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return
    await callback.message.answer(
        "🚫 <b>Bloklash:</b>\n"
        "<code>/ban &lt;telegram_id&gt;</code>\n"
        "<code>/unban &lt;telegram_id&gt;</code> — blokdan ochish",
        parse_mode="HTML",
    )
    await callback.answer()