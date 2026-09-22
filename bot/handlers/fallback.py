"""
Catch-all handler for unsent file/photo messages.
Runs only when no other handler matched (e.g., user sent image outside the flow).
"""
from aiogram import Router, F
from aiogram.types import Message, ContentType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Test, AnswerKey

router = Router(name="fallback")


@router.message(
    F.content_type.in_({ContentType.DOCUMENT, ContentType.PHOTO})
)
async def unexpected_file(message: Message, session: AsyncSession, user: User):
    result = await session.execute(
        select(Test)
        .where(Test.user_id == user.id)
        .order_by(Test.created_at.desc())
        .limit(5)
    )
    tests = result.scalars().all()

    tests_with_key = []
    for t in tests:
        ak = await session.execute(select(AnswerKey).where(AnswerKey.test_id == t.id))
        if ak.scalar_one_or_none():
            tests_with_key.append(t)

    if not tests_with_key:
        await message.answer(
            "🖼 Rasm tirik qabul qilindi, lekin hozircha tekshira olmayman.\n"
            "Buning uchun avval:\n"
            "1) ➕ <b>Yangi test</b> yarating\n"
            "2) 📋 <b>Javoblar kaliti</b> ni yuklang\n"
            "3) Keyin 📄 <b>O'quvchilar javoblari</b> orqali rasmni yana yuboring.\n\n"
            "Odatda meni «📄 O'quvchilar javoblari» bo'limidan foydalanish kerak.",
            parse_mode="HTML",
        )
        return

    lines = [
        "🖼 Rasm tirik qabul qilindi, lekin uni tekshirish uchun qaysi test ekanligini bilishim kerak.\n",
        "Quyidagicha davom eting:\n"
        "1) 📄 <b>O'quvchilar javoblari</b> tugmasini bosing\n"
        "2) Testni tanlang (yoki ID raqamini yozing)\n"
        "3) <b>Rasmni qaytadan yuboring</b>\n",
        "Tayyor testlar (kalit bilan):",
    ]
    for t in tests_with_key[:5]:
        lines.append(f"• ID <code>{t.id}</code> — {t.subject} | {t.test_name}")
    await message.answer("\n".join(lines), parse_mode="HTML")