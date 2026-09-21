import os
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Payment
from database.models.setting import Setting
from bot.keyboards.main_kb import main_menu_kb, premium_kb
from services.payment_service import PaymentService

router = Router(name="premium")


async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    r = await session.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


@router.message(F.text == "👑 Premium")
async def premium_info(message: Message, session: AsyncSession, user: User):
    price = await get_setting(session, "premium_price_uzs", os.getenv("PREMIUM_PRICE_UZS", "35000"))
    duration = await get_setting(session, "premium_duration_days", os.getenv("PREMIUM_DURATION_DAYS", "30"))
    free_limit = await get_setting(session, "free_daily_pdf_limit", os.getenv("FREE_DAILY_PDF_LIMIT", "3"))
    prem_limit = await get_setting(session, "premium_daily_pdf_limit", os.getenv("PREMIUM_DAILY_PDF_LIMIT", "6"))

    status = "👑 Premium faol" if user.is_premium_active() else "🆓 Oddiy tarif"
    until = ""
    if user.is_premium_active() and user.premium_until:
        until = f"\n⏳ Tugash: {user.premium_until.strftime('%d.%m.%Y')}"

    text = (
        f"👑 <b>PREMIUM</b>\n\n"
        f"Holat: {status}{until}\n\n"
        f"💰 Narxi: {price} so‘m\n"
        f"⏳ Muddat: {duration} kun\n"
        f"📄 Kunlik limit: {prem_limit} ta PDF\n"
        f"🆓 Oddiy tarif: {free_limit} ta PDF/kun"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=premium_kb())


@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery, session: AsyncSession, user: User):
    if user.is_premium_active():
        await callback.answer("Sizda allaqachon Premium bor!", show_alert=True)
        return

    price = float(await get_setting(session, "premium_price_uzs", os.getenv("PREMIUM_PRICE_UZS", "35000")))
    duration = int(await get_setting(session, "premium_duration_days", os.getenv("PREMIUM_DURATION_DAYS", "30")))

    payment_svc = PaymentService()
    result = await payment_svc.initiate_premium_payment(
        user_id=user.id,
        amount=price,
        duration_days=duration,
    )

    payment = Payment(
        user_id=user.id,
        amount=price,
        status=result.get("status", "pending"),
        provider=os.getenv("PAYMENT_PROVIDER") or "manual",
        transaction_id=result.get("transaction_id"),
        meta_json=str(result.get("raw", {})),
    )
    session.add(payment)
    await session.flush()

    if result.get("payment_url"):
        text = (
            f"💳 To‘lov uchun havola:\n{result['payment_url']}\n\n"
            f"To‘lov muvaffaqiyatli bo‘lgach Premium avtomatik faollashadi."
        )
    else:
        text = (
            f"💳 To‘lov so‘rovi yaratildi.\n"
            f"🆔 Transaction: <code>{result.get('transaction_id')}</code>\n"
            f"💰 Summa: {price} so‘m\n\n"
            f"⚠️ Hozircha to‘lov tizimi to‘liq ulanmagan.\n"
            f"Admin panel orqali Premium qo‘lda faollashtirilishi mumkin.\n"
            f"Yoki to‘lov providerini .env da sozlang."
        )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
